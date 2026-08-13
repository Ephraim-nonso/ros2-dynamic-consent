"""Translate authorized scenario outcomes into Gazebo velocity commands."""

from __future__ import annotations

import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from .gazebo_motion_logic import (MotionPlan, MotionSegment,
                                  motion_plan_for_signal,
                                  parse_scenario_status)


class GazeboMotionAdapterNode(Node):

    def __init__(self) -> None:
        super().__init__('gazebo_motion_adapter')
        self.declare_parameter(
            'cmd_vel_topic', '/model/consent_robot/cmd_vel')
        self.declare_parameter('forward_speed', 0.5)
        self.declare_parameter('forward_duration_seconds', 0.8)
        self.declare_parameter('turn_speed', 0.8)
        self.declare_parameter('turn_duration_seconds', 0.3)

        self._enabled = True
        self._forward_speed = self._positive_parameter('forward_speed')
        self._forward_duration = self._positive_parameter(
            'forward_duration_seconds')
        self._turn_speed = self._positive_parameter('turn_speed')
        self._turn_duration = self._positive_parameter(
            'turn_duration_seconds')

        topic = self.get_parameter('cmd_vel_topic').value
        if not isinstance(topic, str) or not topic.strip():
            self._enabled = False
            topic = '/model/consent_robot/cmd_vel'
            self.get_logger().error(
                'cmd_vel_topic must be a non-empty string; motion disabled')

        self._publisher = self.create_publisher(Twist, topic.strip(), 10)
        self._status_publisher = self.create_publisher(
            String, '/gazebo_demo/status', 10)
        self.create_subscription(
            String, '/scenario/status', self._on_scenario_status, 10)
        self.create_timer(0.05, self._tick)

        self._segments: list[MotionSegment] = []
        self._segment_deadline: float | None = None
        self._publish_stop()
        self.get_logger().info(
            f'Gazebo motion adapter ready on {topic}')

    def _positive_parameter(self, name: str) -> float:
        value = self.get_parameter(name).value
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or value <= 0):
            self._enabled = False
            self.get_logger().error(
                f'{name} must be a positive number; motion disabled')
            return 1.0
        return float(value)

    def _on_scenario_status(self, msg: String) -> None:
        if not self._enabled:
            self._publish_stop()
            return
        signal = parse_scenario_status(msg.data)
        if signal is None:
            self._segments.clear()
            self._segment_deadline = None
            self._publish_stop()
            self.get_logger().warning(
                f'ignored malformed scenario status {msg.data!r}')
            return
        try:
            plan = motion_plan_for_signal(
                signal,
                forward_speed=self._forward_speed,
                forward_duration=self._forward_duration,
                turn_speed=self._turn_speed,
                turn_duration=self._turn_duration,
            )
        except ValueError as exc:
            self._enabled = False
            self._publish_stop()
            self.get_logger().error(f'motion disabled: {exc}')
            return
        self._start_plan(plan, signal.stage.number if signal.stage else 0)

    def _start_plan(self, plan: MotionPlan, stage_number: int) -> None:
        self._segments = list(plan.segments)
        self._segment_deadline = None
        self._publish_adapter_status(stage_number, plan.label)
        self._start_next_segment()

    def _start_next_segment(self) -> None:
        if not self._segments:
            self._segment_deadline = None
            self._publish_stop()
            return
        segment = self._segments.pop(0)
        self._publish_velocity(segment.linear_x, segment.angular_z)
        if segment.duration_seconds <= 0:
            self._segments.clear()
            self._segment_deadline = None
            return
        self._segment_deadline = (
            time.monotonic() + segment.duration_seconds)

    def _tick(self) -> None:
        if (self._segment_deadline is not None
                and time.monotonic() >= self._segment_deadline):
            self._start_next_segment()

    def _publish_velocity(self, linear_x: float, angular_z: float) -> None:
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self._publisher.publish(msg)

    def _publish_stop(self) -> None:
        self._publish_velocity(0.0, 0.0)

    def _publish_adapter_status(self, stage_number: int, label: str) -> None:
        msg = String()
        msg.data = f'stage_{stage_number}:{label}' if stage_number else label
        self._status_publisher.publish(msg)

    def destroy_node(self):
        self._segments.clear()
        self._segment_deadline = None
        if rclpy.ok(context=self.context):
            try:
                self._publish_stop()
            except Exception:  # rclpy exception type varies by ROS release
                # A signal can invalidate the context between the readiness
                # check and publish. Destruction must still complete cleanly.
                pass
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GazeboMotionAdapterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
