"""Deterministic privacy-dimension simulator for both conditions."""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import ConsentEvent

from .conditions import validate_consent_mode
from .ros_qos import SESSION_QOS
from .ros_time import to_time_msg
from .scenario_logic import SCENARIO_STAGES, ScenarioStage


SENSOR_ACTIONS = {
    'person_recognition': 'observe_simulated_person_presence',
    'speech_input': 'capture_and_transcribe_live_speech',
}


class ScenarioSimulatorNode(Node):

    def __init__(self) -> None:
        super().__init__('scenario_simulator')
        self.declare_parameter('consent_mode', 'dynamic')
        self.declare_parameter('startup_delay_seconds', 2.0)
        self.declare_parameter('stage_delay_seconds', 1.0)
        self.declare_parameter('sensor_demo', False)

        raw_condition = self.get_parameter('consent_mode').value
        try:
            self._condition = validate_consent_mode(raw_condition)
        except ValueError as exc:
            self._condition = 'invalid'
            self.get_logger().error(f'{exc}; scenario will not start')
        self._startup_delay = self._nonnegative_parameter(
            'startup_delay_seconds')
        self._stage_delay = self._nonnegative_parameter(
            'stage_delay_seconds')
        self._sensor_demo = bool(self.get_parameter('sensor_demo').value)

        self._session_id = ''
        self._next_stage_index = 0
        self._current_stage: ScenarioStage | None = None
        self._next_action_at: float | None = None
        self._complete = False
        self._waiting_for_execution = False

        self._request_pub = self.create_publisher(
            String, '/capability/requested', 10)
        self._status_pub = self.create_publisher(
            String, '/scenario/status', 10)
        self._event_pub = self.create_publisher(
            ConsentEvent, '/consent/event', 10)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_subscription(
            String, '/capability/authorized', self._on_authorized, 10)
        self.create_subscription(
            String, '/capability/blocked', self._on_blocked, 10)
        self.create_subscription(
            String,
            '/capability/execution_completed',
            self._on_execution_completed,
            10,
        )
        self.create_timer(0.1, self._tick)
        self.get_logger().info(
            f'scenario simulator ready for {self._condition} condition')

    def _nonnegative_parameter(self, name: str) -> float:
        value = self.get_parameter(name).value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.get_logger().error(
                f'{name} must be a non-negative number; using 0')
            return 0.0
        if value < 0:
            self.get_logger().error(
                f'{name} must be non-negative; using 0')
            return 0.0
        return float(value)

    def _on_session(self, msg: String) -> None:
        session_id = msg.data.strip()
        if not session_id:
            return
        if self._session_id == session_id:
            return
        if self._session_id:
            self.get_logger().warning(
                'active session changed; restarting the scenario')
        self._session_id = session_id
        self._next_stage_index = 0
        self._current_stage = None
        self._complete = False
        self._waiting_for_execution = False
        self._next_action_at = time.monotonic() + self._startup_delay
        self._publish_status('scenario_ready')

    def _tick(self) -> None:
        if (self._condition == 'invalid' or not self._session_id
                or self._complete or self._current_stage is not None
                or self._next_action_at is None
                or time.monotonic() < self._next_action_at):
            return
        if self._next_stage_index >= len(SCENARIO_STAGES):
            self._complete = True
            self._next_action_at = None
            self._publish_status('scenario_complete')
            self.get_logger().info(
                f'{len(SCENARIO_STAGES)}-stage scenario complete')
            return

        stage = SCENARIO_STAGES[self._next_stage_index]
        self._current_stage = stage
        self._next_action_at = None
        request = String()
        request.data = stage.capability_id
        self._request_pub.publish(request)
        self._publish_status(
            f'stage_{stage.number}:{stage.name}:requested:'
            f'{stage.capability_id}')
        self.get_logger().info(
            f'stage {stage.number} requests {stage.capability_id}')

    def _on_authorized(self, msg: String) -> None:
        stage = self._matching_stage(msg.data)
        if stage is None:
            return
        if self._sensor_demo and stage.capability_id in SENSOR_ACTIONS:
            self._waiting_for_execution = True
            action = SENSOR_ACTIONS[stage.capability_id]
            self._publish_status(
                f'stage_{stage.number}:{stage.name}:capability_started:'
                f'{action}')
            self.get_logger().info(
                f'stage {stage.number} starts {action}; waiting for sensor')
            return
        self._complete_authorized_stage(stage)

    def _complete_authorized_stage(self, stage: ScenarioStage) -> None:
        action = SENSOR_ACTIONS.get(
            stage.capability_id, stage.capability_action
        ) if self._sensor_demo else stage.capability_action
        self._publish_status(
            f'stage_{stage.number}:{stage.name}:capability_executed:'
            f'{action}')
        self._publish_event(
            'capability_executed', stage.capability_id, 'success')
        self.get_logger().info(
            f'stage {stage.number} executes {action}')
        self._advance()

    def _on_execution_completed(self, msg: String) -> None:
        if not self._sensor_demo or not self._waiting_for_execution:
            return
        parts = msg.data.split(':', maxsplit=1)
        if len(parts) != 2:
            return
        capability_id, result = parts
        stage = self._matching_stage(capability_id)
        if stage is None:
            return
        self._waiting_for_execution = False
        if result == 'success':
            self._complete_authorized_stage(stage)
            return
        self._publish_status(
            f'stage_{stage.number}:{stage.name}:fallback_executed:'
            f'{stage.fallback_action}')
        self._publish_event(
            'fallback_executed', stage.capability_id, 'fallback')
        self.get_logger().warning(
            f'stage {stage.number} sensor execution failed; executes '
            f'{stage.fallback_action}')
        self._advance()

    def _on_blocked(self, msg: String) -> None:
        stage = self._matching_stage(msg.data)
        if stage is None:
            return
        self._publish_status(
            f'stage_{stage.number}:{stage.name}:fallback_executed:'
            f'{stage.fallback_action}')
        self._publish_event(
            'fallback_executed', stage.capability_id, 'fallback')
        self.get_logger().info(
            f'stage {stage.number} executes {stage.fallback_action}')
        self._advance()

    def _matching_stage(self, capability_id: str) -> ScenarioStage | None:
        if (self._current_stage is None
                or capability_id != self._current_stage.capability_id):
            return None
        return self._current_stage

    def _advance(self) -> None:
        self._next_stage_index += 1
        self._current_stage = None
        self._waiting_for_execution = False
        self._next_action_at = time.monotonic() + self._stage_delay

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_pub.publish(msg)

    def _publish_event(self, event_type: str, capability_id: str,
                       task_outcome: str) -> None:
        msg = ConsentEvent()
        msg.session_id = self._session_id
        msg.condition = self._condition
        msg.event_type = event_type
        msg.capability_id = capability_id
        msg.task_outcome = task_outcome
        msg.stamp = to_time_msg(time.time())
        self._event_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ScenarioSimulatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
