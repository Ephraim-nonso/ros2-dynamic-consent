"""Coordinate an atomic-looking reset across Gazebo and consent sessions."""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger

from dynamic_consent_interfaces.srv import ResetSession
from ros_gz_interfaces.srv import ControlWorld

from ..common.ros_qos import SESSION_QOS, STATUS_QOS


class ExperimentControllerNode(Node):

    def __init__(self) -> None:
        super().__init__('experiment_controller')
        self._session_id = ''
        self._reset_in_progress = False
        self._status_publisher = self.create_publisher(
            String, '/study/control_status', STATUS_QOS)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self._world_client = self.create_client(
            ControlWorld, '/world/dynamic_consent_world/control')
        self._consent_client = self.create_client(
            ResetSession, '/consent/reset_session')
        self.create_service(Trigger, '/study/reset', self._on_reset)
        self.get_logger().info(
            'experiment reset controller ready on /study/reset')

    def _on_session(self, msg: String) -> None:
        if msg.data.strip():
            self._session_id = msg.data.strip()

    def _on_reset(self, _request, response):
        if self._reset_in_progress:
            response.success = False
            response.message = 'a study reset is already in progress'
            return response
        if not self._session_id:
            response.success = False
            response.message = 'no active anonymous session'
            return response
        if not self._world_client.service_is_ready():
            response.success = False
            response.message = 'Gazebo world-control service is unavailable'
            return response
        if not self._consent_client.service_is_ready():
            response.success = False
            response.message = 'consent reset service is unavailable'
            return response

        self._reset_in_progress = True
        self._publish_status('reset_requested')
        request = ControlWorld.Request()
        request.world_control.pause = False
        request.world_control.reset.all = True
        future = self._world_client.call_async(request)
        future.add_done_callback(self._on_world_reset)
        response.success = True
        response.message = (
            'reset accepted; monitor /study/control_status for completion')
        return response

    def _on_world_reset(self, future) -> None:
        try:
            result = future.result()
        except Exception:  # rclpy service exceptions vary by middleware
            self._fail_reset('world_service_error')
            return
        if result is None or not result.success:
            self._fail_reset('world_reset_rejected')
            return

        self._publish_status('gazebo_reset_complete')
        request = ResetSession.Request()
        request.session_id = self._session_id
        reset_future = self._consent_client.call_async(request)
        reset_future.add_done_callback(self._on_consent_reset)

    def _on_consent_reset(self, future) -> None:
        try:
            result = future.result()
        except Exception:  # rclpy service exceptions vary by middleware
            self._fail_reset('consent_service_error')
            return
        if result is None or not result.success:
            self._fail_reset('consent_reset_rejected')
            return
        self._reset_in_progress = False
        self._publish_status('reset_complete')

    def _fail_reset(self, reason: str) -> None:
        self._reset_in_progress = False
        self._publish_status(f'reset_failed:{reason}')
        self.get_logger().error(f'study reset failed: {reason}')

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ExperimentControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
