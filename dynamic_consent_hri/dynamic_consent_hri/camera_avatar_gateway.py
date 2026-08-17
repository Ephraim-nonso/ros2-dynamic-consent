"""Consent-gated Mac camera input and Gazebo expression mirroring."""

from __future__ import annotations

import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Float64, String

from dynamic_consent_interfaces.msg import ConsentEvent

from .camera_avatar_logic import (AvatarCommand, FaceObservation,
                                  NEUTRAL_COMMAND,
                                  command_for_observation)
from .opencv_assets import resolve_haar_cascade_directory
from .ros_qos import SESSION_QOS


CAPABILITY_ID = 'camera_expression_mirroring'
MAX_POLICY_WINDOW_SECONDS = 60.0


class CameraAvatarGatewayNode(Node):
    """Open the host camera only inside a bounded authorization window."""

    def __init__(self) -> None:
        super().__init__('camera_avatar_gateway')
        self.declare_parameter('relay_url', 'http://10.0.2.2:8765')
        self.declare_parameter('relay_token', '')
        self.declare_parameter('access_seconds', 60.0)
        self.declare_parameter('frame_rate', 10.0)

        self._relay_url = str(self.get_parameter('relay_url').value).rstrip('/')
        self._relay_token = str(self.get_parameter('relay_token').value)
        self._access_seconds = float(
            self.get_parameter('access_seconds').value)
        self._frame_rate = float(self.get_parameter('frame_rate').value)
        self._configuration_valid = self._validate_configuration()

        self._session_id = ''
        self._request_pending = False
        self._decision_received = False
        self._authorized = False
        self._deadline = 0.0
        self._worker: threading.Thread | None = None
        self._worker_stop = threading.Event()
        self._state_lock = threading.Lock()
        self._previous_lower_face: np.ndarray | None = None
        self._eyes_missing_frames = 0

        try:
            cascade_path = resolve_haar_cascade_directory(cv2)
        except FileNotFoundError as exc:
            self._configuration_valid = False
            self.get_logger().error(f'{exc}; failing closed')
            cascade_path = None
        self._face_detector = self._load_cascade(
            cascade_path, 'haarcascade_frontalface_default.xml')
        self._eye_detector = self._load_cascade(
            cascade_path, 'haarcascade_eye_tree_eyeglasses.xml')
        self._smile_detector = self._load_cascade(
            cascade_path, 'haarcascade_smile.xml')
        if any(detector.empty() for detector in (
                self._face_detector, self._eye_detector,
                self._smile_detector)):
            self._configuration_valid = False
            self.get_logger().error(
                'OpenCV face cascades are unavailable; failing closed')

        self._request_pub = self.create_publisher(
            String, '/capability/requested', 10)
        self._raw_pub = self.create_publisher(
            Image, '/camera_consent/live_image', qos_profile_sensor_data)
        self._annotated_pub = self.create_publisher(
            Image, '/camera_consent/annotated_image', 10)
        self._status_pub = self.create_publisher(
            String, '/camera_consent/status', 10)
        self._expression_pub = self.create_publisher(
            String, '/camera_consent/expression', 10)
        self._yaw_pub = self.create_publisher(
            Float64, '/avatar/head_yaw', 10)
        self._roll_pub = self.create_publisher(
            Float64, '/avatar/head_roll', 10)
        self._eyelid_pub = self.create_publisher(
            Float64, '/avatar/eyelid', 10)
        self._jaw_pub = self.create_publisher(
            Float64, '/avatar/jaw', 10)

        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_subscription(
            String, '/capability/authorized', self._on_authorized, 10)
        self.create_subscription(
            String, '/capability/blocked', self._on_blocked, 10)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_consent_event, 10)
        self.create_timer(1.0, self._tick)
        self._publish_neutral()
        self._publish_privacy_frame('CAMERA OFF - WAITING FOR CONSENT')
        self._publish_status('camera_closed:waiting_for_consent')

    @staticmethod
    def _load_cascade(directory, filename: str):
        if directory is None:
            return cv2.CascadeClassifier()
        return cv2.CascadeClassifier(str(directory / filename))

    def _validate_configuration(self) -> bool:
        parsed = urlparse(self._relay_url)
        valid_url = parsed.scheme == 'http' and bool(parsed.hostname)
        valid = (
            valid_url
            and bool(self._relay_token)
            and 0 < self._access_seconds <= MAX_POLICY_WINDOW_SECONDS
            and 0 < self._frame_rate <= 30
        )
        if not valid:
            self.get_logger().error(
                'relay_url, relay_token, access_seconds, or frame_rate is '
                'invalid; camera access will fail closed')
        return valid

    def _on_session(self, msg: String) -> None:
        if not msg.data.strip():
            return
        if self._session_id and self._session_id != msg.data:
            self._stop_camera('session_changed')
        self._session_id = msg.data
        self._request_pending = True
        self._decision_received = False

    def _tick(self) -> None:
        if self._authorized and time.monotonic() >= self._deadline:
            self._stop_camera('authorization_window_expired')
            return
        if (self._session_id and self._request_pending
                and not self._decision_received):
            request = String()
            request.data = CAPABILITY_ID
            self._request_pub.publish(request)
            self._publish_status('consent_requested:camera_remains_closed')
        if not self._authorized:
            self._publish_privacy_frame('CAMERA OFF - CONSENT REQUIRED')

    def _on_authorized(self, msg: String) -> None:
        if msg.data != CAPABILITY_ID:
            return
        self._decision_received = True
        self._request_pending = False
        if not self._configuration_valid:
            self._publish_status('failed_closed:invalid_camera_configuration')
            return
        with self._state_lock:
            if self._authorized:
                return
            self._authorized = True
            self._deadline = time.monotonic() + self._access_seconds
            self._previous_lower_face = None
            self._eyes_missing_frames = 0
        self._worker_stop.clear()
        self._worker = threading.Thread(
            target=self._camera_loop,
            name='consent-camera-worker',
            daemon=True,
        )
        self._worker.start()
        self._publish_status('authorized:requesting_mac_camera_open')

    def _on_blocked(self, msg: String) -> None:
        if msg.data != CAPABILITY_ID:
            return
        self._decision_received = True
        self._request_pending = False
        self._stop_camera('refused')

    def _on_consent_event(self, msg: ConsentEvent) -> None:
        relevant = (
            msg.event_type in {'session_reset', 'session_started'}
            or (msg.capability_id == CAPABILITY_ID
                and msg.event_type in {
                    'consent_revoked', 'consent_expired',
                    'capability_blocked',
                })
        )
        if relevant and self._authorized:
            self._stop_camera(msg.event_type)

    def _camera_loop(self) -> None:
        try:
            self._relay_json('/start', method='POST', timeout=8.0)
            self._publish_status('camera_open:live_frames_authorized')
            delay = 1.0 / self._frame_rate
            while not self._worker_stop.is_set():
                with self._state_lock:
                    authorized = self._authorized
                    deadline = self._deadline
                if not authorized or time.monotonic() >= deadline:
                    break
                started = time.monotonic()
                jpeg = self._relay_bytes('/frame.jpg', timeout=1.0)
                encoded = np.frombuffer(jpeg, dtype=np.uint8)
                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError('relay returned an invalid JPEG')
                self._process_authorized_frame(frame)
                self._worker_stop.wait(
                    max(0.0, delay - (time.monotonic() - started)))
        except (HTTPError, URLError, TimeoutError, OSError,
                ValueError, json.JSONDecodeError) as exc:
            self.get_logger().error(
                f'camera relay failed closed: {type(exc).__name__}')
            self._publish_status('failed_closed:camera_relay_unavailable')
        finally:
            self._stop_camera_from_worker()

    def _process_authorized_frame(self, frame: np.ndarray) -> None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self._face_detector.detectMultiScale(
            gray, scaleFactor=1.12, minNeighbors=5, minSize=(80, 80))
        annotated = frame.copy()
        command = NEUTRAL_COMMAND
        label = 'face_not_detected'
        if len(faces):
            x, y, width, height = max(faces, key=lambda item: item[2] * item[3])
            observation = self._observe_face(
                gray, int(x), int(y), int(width), int(height))
            command = command_for_observation(observation)
            label = self._expression_label(observation)
            cv2.rectangle(
                annotated, (x, y), (x + width, y + height), (0, 255, 0), 2)
            cv2.putText(
                annotated, label.replace('_', ' '), (x, max(25, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            self._previous_lower_face = None
            self._eyes_missing_frames = 0
            cv2.putText(
                annotated, 'Face not detected - avatar neutral', (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 180, 255), 2)
        cv2.putText(
            annotated, 'AUTHORIZED - NOT RECORDED',
            (20, annotated.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (0, 255, 0), 2)
        self._publish_image(frame, self._raw_pub)
        self._publish_image(annotated, self._annotated_pub)
        self._publish_command(command)
        message = String()
        message.data = label
        self._expression_pub.publish(message)

    def _observe_face(self, gray, x, y, width, height) -> FaceObservation:
        region = gray[y:y + height, x:x + width]
        upper = region[:max(1, int(height * 0.60)), :]
        eyes = self._eye_detector.detectMultiScale(
            upper, scaleFactor=1.10, minNeighbors=5,
            minSize=(max(12, width // 10), max(10, height // 12)))
        smiles = self._smile_detector.detectMultiScale(
            region[int(height * 0.45):, :], scaleFactor=1.7,
            minNeighbors=20, minSize=(max(25, width // 4), 12))
        if len(eyes) >= 2:
            self._eyes_missing_frames = 0
        else:
            self._eyes_missing_frames += 1
        eye_line = 0.0
        if len(eyes) >= 2:
            selected = sorted(eyes, key=lambda item: item[2] * item[3],
                              reverse=True)[:2]
            centers = sorted(
                ((ex + ew / 2.0, ey + eh / 2.0)
                 for ex, ey, ew, eh in selected),
                key=lambda point: point[0],
            )
            dx = max(1.0, centers[1][0] - centers[0][0])
            eye_line = float(np.arctan2(
                centers[1][1] - centers[0][1], dx))
        lower = cv2.resize(
            region[int(height * 0.55):, :], (96, 44),
            interpolation=cv2.INTER_AREA)
        activity = 0.0
        if self._previous_lower_face is not None:
            difference = cv2.absdiff(lower, self._previous_lower_face)
            activity = min(1.0, float(np.mean(difference)) / 22.0)
        self._previous_lower_face = lower
        face_center = x + width / 2.0
        offset = (face_center - gray.shape[1] / 2.0) / (
            gray.shape[1] / 2.0)
        return FaceObservation(
            horizontal_offset=float(offset),
            eye_line_angle=eye_line,
            eyes_visible=(
                0 if self._eyes_missing_frames >= 2 else 2),
            smile_detected=len(smiles) > 0,
            mouth_activity=activity,
        )

    @staticmethod
    def _expression_label(observation: FaceObservation) -> str:
        labels = []
        if observation.eyes_visible < 2:
            labels.append('blink')
        if observation.smile_detected:
            labels.append('smile')
        if observation.mouth_activity > 0.20:
            labels.append('talking')
        if abs(observation.eye_line_angle) > 0.10:
            labels.append('head_tilt')
        return '_and_'.join(labels) if labels else 'neutral_face'

    def _publish_image(self, frame: np.ndarray, publisher) -> None:
        message = Image()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'mac_builtin_camera_authorized'
        message.height, message.width = frame.shape[:2]
        message.encoding = 'bgr8'
        message.is_bigendian = False
        message.step = int(frame.strides[0])
        message.data = frame.tobytes()
        publisher.publish(message)

    def _publish_privacy_frame(self, text: str) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, text, (55, 235), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 200, 255), 2)
        cv2.putText(frame, 'No camera frames are being processed.',
                    (90, 280), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (180, 180, 180), 2)
        self._publish_image(frame, self._annotated_pub)

    def _publish_command(self, command: AvatarCommand) -> None:
        for publisher, value in (
            (self._yaw_pub, command.head_yaw),
            (self._roll_pub, command.head_roll),
            (self._eyelid_pub, command.eyelid_position),
            (self._jaw_pub, command.jaw_angle),
        ):
            message = Float64()
            message.data = value
            publisher.publish(message)

    def _publish_neutral(self) -> None:
        self._publish_command(NEUTRAL_COMMAND)

    def _stop_camera(self, reason: str) -> None:
        with self._state_lock:
            was_authorized = self._authorized
            self._authorized = False
            self._deadline = 0.0
            self._previous_lower_face = None
            self._eyes_missing_frames = 0
        self._worker_stop.set()
        if was_authorized:
            threading.Thread(
                target=self._close_relay,
                name='consent-camera-close',
                daemon=True,
            ).start()
        self._publish_neutral()
        self._publish_privacy_frame('CAMERA OFF - ACCESS ENDED')
        self._publish_status(f'camera_closed:{reason}')

    def _stop_camera_from_worker(self) -> None:
        with self._state_lock:
            self._authorized = False
            self._deadline = 0.0
            self._previous_lower_face = None
            self._eyes_missing_frames = 0
        self._worker_stop.set()
        self._close_relay()
        self._publish_neutral()
        self._publish_privacy_frame('CAMERA OFF - ACCESS ENDED')

    def _close_relay(self) -> None:
        try:
            self._relay_json('/stop', method='POST', timeout=1.0)
        except (HTTPError, URLError, TimeoutError, OSError,
                json.JSONDecodeError):
            self.get_logger().warning('unable to confirm relay camera close')

    def _relay_request(self, path: str, method: str, timeout: float):
        request = Request(
            self._relay_url + path,
            method=method,
            headers={
                'Authorization': f'Bearer {self._relay_token}',
                'Cache-Control': 'no-store',
            },
        )
        return urlopen(request, timeout=timeout)

    def _relay_json(self, path: str, method: str, timeout: float) -> dict:
        with self._relay_request(path, method, timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    def _relay_bytes(self, path: str, timeout: float) -> bytes:
        with self._relay_request(path, 'GET', timeout) as response:
            return response.read()

    def _publish_status(self, value: str) -> None:
        message = String()
        message.data = value
        self._status_pub.publish(message)
        self.get_logger().info(value)

    def destroy_node(self):
        self._stop_camera('node_shutdown')
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraAvatarGatewayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
