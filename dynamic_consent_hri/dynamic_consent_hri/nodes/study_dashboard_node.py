"""Terminal dashboard for the Phase 7 embodied assistance study."""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from ..simulation.gazebo_motion_logic import parse_scenario_status
from ..common.ros_qos import STATUS_QOS
from ..ui.study_status_logic import display_for_signal

_CONTROL_COPY = {
    'reset_requested': 'RESET | Resetting Gazebo and consent state...',
    'gazebo_reset_complete': 'RESET | Gazebo returned to its initial state.',
    'reset_complete': 'RESET | A fresh anonymous study session has started.',
    'reset_failed': 'RESET | Reset failed; the current session remains safe.',
}


class StudyDashboardNode(Node):

    def __init__(self) -> None:
        super().__init__('study_dashboard')
        self._publisher = self.create_publisher(
            String, '/study/status', STATUS_QOS)
        self.create_subscription(
            String, '/scenario/status', self._on_scenario_status, 10)
        self.create_subscription(
            String, '/study/control_status', self._on_control_status,
            STATUS_QOS)
        self.get_logger().info(
            'study dashboard ready; fixed status text contains no raw data')

    def _on_scenario_status(self, msg: String) -> None:
        signal = parse_scenario_status(msg.data)
        if signal is None:
            self.get_logger().warning('invalid scenario status ignored')
            return
        self._publish(display_for_signal(signal).as_message())

    def _on_control_status(self, msg: String) -> None:
        key = msg.data.split(':', maxsplit=1)[0]
        text = _CONTROL_COPY.get(key)
        if text is not None:
            self._publish(text)

    def _publish(self, value: str) -> None:
        output = String()
        output.data = value
        self._publisher.publish(output)
        self.get_logger().info(f'\n=== {value} ===')


def main(args=None):
    rclpy.init(args=args)
    node = StudyDashboardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
