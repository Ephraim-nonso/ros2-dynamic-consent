"""Consent-enforced, memory-only ALSA microphone capture."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from dynamic_consent_interfaces.msg import ConsentEvent

from ..common.ros_qos import SESSION_QOS
from ..sensors.sensor_guard_logic import AuthorizationWindow


class MicrophoneGuardNode(Node):
    """Open ``arecord`` only during an authorized speech-input window."""

    def __init__(self) -> None:
        super().__init__('microphone_guard')
        self.declare_parameter('device', 'default')
        self.declare_parameter('sample_rate', 16000)
        self.declare_parameter('channels', 1)
        self.declare_parameter('capture_seconds', 8.0)
        self.declare_parameter('chunk_bytes', 3200)
        self.declare_parameter('arecord_executable', 'arecord')

        duration = float(self.get_parameter('capture_seconds').value)
        self._window = AuthorizationWindow('speech_input', duration)
        self._chunk_bytes = int(self.get_parameter('chunk_bytes').value)
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._chunks: queue.Queue[bytes] = queue.Queue(maxsize=20)
        self._ending_reason: str | None = None

        self._audio_pub = self.create_publisher(
            UInt8MultiArray, '/privacy/speech_input/audio', 10)
        self._status_pub = self.create_publisher(
            String, '/sensors/microphone/status', 10)
        self.create_subscription(
            String, '/capability/authorized', self._on_authorized, 10)
        self.create_subscription(
            String, '/capability/blocked', self._on_blocked, 10)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_consent_event, 10)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_timer(0.05, self._tick)
        self._publish_status('inactive')

    def _on_authorized(self, msg: String) -> None:
        if msg.data != self._window.capability_id:
            return
        if self._process is not None:
            self.get_logger().warning('microphone capture is already active')
            return
        executable = str(
            self.get_parameter('arecord_executable').value).strip()
        resolved = shutil.which(executable)
        if resolved is None:
            self.get_logger().error('arecord is unavailable; failing closed')
            self._publish_status('unavailable:arecord_not_found')
            return

        rate = int(self.get_parameter('sample_rate').value)
        channels = int(self.get_parameter('channels').value)
        device = str(self.get_parameter('device').value)
        command = [
            resolved, '-q', '-D', device, '-t', 'raw', '-f', 'S16_LE',
            '-r', str(rate), '-c', str(channels), '-',
        ]
        try:
            self._discard_chunks()
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            self.get_logger().error(
                f'microphone could not be opened; failing closed: {exc}')
            self._process = None
            self._publish_status('unavailable:device_open_failed')
            return

        self._window.authorize(time.monotonic())
        self._ending_reason = None
        self._reader = threading.Thread(
            target=self._read_audio, name='microphone-reader', daemon=True)
        self._reader.start()
        self._publish_status('capture_started')
        self.get_logger().info(
            f'authorized microphone opened for at most '
            f'{self._window.duration_seconds:.1f} seconds')

    def _read_audio(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        while process.poll() is None:
            chunk = process.stdout.read(self._chunk_bytes)
            if not chunk:
                break
            try:
                self._chunks.put(chunk, timeout=0.1)
            except queue.Full:
                # Bounded memory is preferable to retaining sensitive audio.
                pass

    def _tick(self) -> None:
        if self._process is not None and not self._window.is_active(
                time.monotonic()):
            self._stop_capture('capture_complete')

        for _ in range(5):
            try:
                chunk = self._chunks.get_nowait()
            except queue.Empty:
                break
            if self._process is None or not self._window.is_active(
                    time.monotonic()):
                continue
            msg = UInt8MultiArray()
            msg.data = list(chunk)
            self._audio_pub.publish(msg)

        if (self._process is not None and self._process.poll() is not None
                and self._ending_reason is None):
            self._stop_capture('capture_failed')

    def _on_consent_event(self, msg: ConsentEvent) -> None:
        if self._window.handle_event(msg.event_type, msg.capability_id):
            self._stop_capture('capture_stopped_by_consent')

    def _on_blocked(self, msg: String) -> None:
        if msg.data == self._window.capability_id:
            self._window.close()
            self._stop_capture('blocked')

    def _on_session(self, _msg: String) -> None:
        if self._process is not None:
            self._window.close()
            self._stop_capture('capture_stopped_by_session_change')

    def _stop_capture(self, reason: str) -> None:
        process = self._process
        self._process = None
        self._ending_reason = reason
        self._window.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        reader = self._reader
        self._reader = None
        if (reader is not None and reader is not threading.current_thread()
                and reader.is_alive()):
            reader.join(timeout=1.0)
        self._discard_chunks()

        self._publish_status(reason)
        if process is not None:
            self.get_logger().info(
                f'microphone closed without storing audio ({reason})')

    def _discard_chunks(self) -> None:
        while True:
            try:
                self._chunks.get_nowait()
            except queue.Empty:
                break

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_pub.publish(msg)

    def destroy_node(self):
        self._stop_capture('shutdown')
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MicrophoneGuardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
