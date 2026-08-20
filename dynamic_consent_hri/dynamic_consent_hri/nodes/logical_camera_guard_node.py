"""Consent enforcement for the Gazebo logical camera stream."""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from dynamic_consent_interfaces.msg import ConsentEvent
from ros_gz_interfaces.msg import LogicalCameraImage

from ..common.ros_qos import SESSION_QOS
from ..sensors.sensor_guard_logic import AuthorizationWindow


VISION_CAPABILITIES = frozenset({'person_recognition'})


class LogicalCameraGuardNode(Node):
    """Expose derived presence only in bounded authorized windows.

    The raw Gazebo logical-camera topic stays in the sensor namespace. This
    node deliberately publishes only a boolean derived result and metadata
    status; it never forwards model names or poses to the rest of the graph.
    """

    def __init__(self) -> None:
        super().__init__('logical_camera_guard')
        self.declare_parameter('observation_seconds', 4.0)
        self.declare_parameter(
            'target_model', 'visitor_requesting_assistance')
        duration = float(self.get_parameter('observation_seconds').value)
        self._windows = {
            capability: AuthorizationWindow(capability, duration)
            for capability in VISION_CAPABILITIES
        }
        self._active_capability: str | None = None
        self._observation_received = False
        self._target = str(self.get_parameter('target_model').value)

        self._presence_pub = self.create_publisher(
            Bool, '/perception/person_present', 10)
        self._status_pub = self.create_publisher(
            String, '/sensors/logical_camera/status', 10)
        self._completion_pub = self.create_publisher(
            String, '/capability/execution_completed', 10)
        self.create_subscription(
            LogicalCameraImage,
            '/sensors/logical_camera/raw',
            self._on_sensor_message,
            10,
        )
        self.create_subscription(
            String, '/capability/authorized', self._on_authorized, 10)
        self.create_subscription(
            String, '/capability/blocked', self._on_blocked, 10)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_consent_event, 10)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_timer(0.1, self._tick)
        self._publish_status('inactive')

    def _on_authorized(self, msg: String) -> None:
        window = self._windows.get(msg.data)
        if window is None:
            return
        self._close_all()
        window.authorize(time.monotonic())
        self._active_capability = msg.data
        self._observation_received = False
        self._publish_status(f'observation_started:{msg.data}')
        self.get_logger().info(
            f'logical camera processing authorized for {msg.data}')

    def _on_sensor_message(self, msg: LogicalCameraImage) -> None:
        window = self._active_window()
        if window is None:
            return
        present = Bool()
        present.data = any(model.name == self._target for model in msg.model)
        self._presence_pub.publish(present)
        self._observation_received = True
        outcome = 'target_present' if present.data else 'target_not_present'
        self._publish_status(
            f'observation:{window.capability_id}:{outcome}')
        self._publish_completion(
            window.capability_id, 'success' if present.data else 'failed')
        window.close()
        self._active_capability = None

    def _tick(self) -> None:
        if self._active_capability is None:
            return
        window = self._windows[self._active_capability]
        if not window.is_active(time.monotonic()):
            capability = self._active_capability
            self._active_capability = None
            self._publish_status(f'observation_complete:{capability}')
            if not self._observation_received:
                self._publish_completion(capability, 'failed')

    def _on_consent_event(self, msg: ConsentEvent) -> None:
        changed = False
        for window in self._windows.values():
            changed = window.handle_event(
                msg.event_type, msg.capability_id) or changed
        if changed:
            capability = self._active_capability
            self._active_capability = None
            self._publish_status('observation_stopped_by_consent')
            if capability is not None:
                self._publish_completion(capability, 'failed')

    def _on_blocked(self, msg: String) -> None:
        window = self._windows.get(msg.data)
        if window is None:
            return
        window.close()
        if self._active_capability == msg.data:
            self._active_capability = None
        self._publish_status(f'blocked:{msg.data}')

    def _on_session(self, _msg: String) -> None:
        if self._active_capability is not None:
            self._close_all()
            self._publish_status('observation_stopped_by_session_change')

    def _active_window(self) -> AuthorizationWindow | None:
        if self._active_capability is None:
            return None
        window = self._windows[self._active_capability]
        if not window.is_active(time.monotonic()):
            capability = self._active_capability
            self._active_capability = None
            self._publish_status(f'observation_complete:{capability}')
            self._publish_completion(capability, 'failed')
            return None
        return window

    def _close_all(self) -> None:
        for window in self._windows.values():
            window.close()
        self._active_capability = None

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_pub.publish(msg)

    def _publish_completion(self, capability: str, result: str) -> None:
        msg = String()
        msg.data = f'{capability}:{result}'
        self._completion_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = LogicalCameraGuardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
