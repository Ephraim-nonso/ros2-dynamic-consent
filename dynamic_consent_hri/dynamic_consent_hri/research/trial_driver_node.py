"""Automated, no-participant driver for reproducible Gazebo study trials.

The driver answers consent prompts with an explicit synthetic strategy and
records only closed, non-content telemetry. It is intended for protocol,
failure-mode, and threat-model analysis; its decisions are not participant
responses.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import rclpy
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import ConsentDecision, ConsentEvent, ConsentPrompt

from .decision_policies import synthetic_decision, validate_strategy
from ..common.ros_qos import PROMPT_QOS, SESSION_QOS, STATUS_QOS
from ..simulation.scenario_logic import SCENARIO_STAGES


class ResearchDriverNode(Node):
    """Answer prompts and save one privacy-safe JSON trial summary."""

    def __init__(self) -> None:
        super().__init__('research_driver')
        self.declare_parameter('consent_mode', 'dynamic')
        self.declare_parameter('decision_strategy', 'grant_all')
        self.declare_parameter('decision_delay_seconds', 0.05)
        self.declare_parameter(
            'output_directory', '~/.ros/dynamic_consent/research')
        self.declare_parameter('trial_label', 'synthetic')

        self._condition = str(self.get_parameter('consent_mode').value)
        self._strategy = validate_strategy(
            str(self.get_parameter('decision_strategy').value))
        self._decision_delay = self._positive_or_zero(
            'decision_delay_seconds')
        self._output_directory = Path(
            str(self.get_parameter('output_directory').value)).expanduser()
        self._trial_label = self._safe_label(
            str(self.get_parameter('trial_label').value))

        self._session_id = ''
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._finalized = False
        self._scenario_completed_at: float | None = None
        self._pending_decision: tuple[float, ConsentDecision] | None = None
        self._answered_request_ids: set[str] = set()
        self._prompts: list[dict[str, object]] = []
        self._events: dict[str, int] = {}
        self._stage_results: dict[int, dict[str, object]] = {}
        self._status_count = 0
        self._scenario_complete = False
        self._study_complete = False
        self._initial_x: float | None = None
        self._final_x: float | None = None

        self._decision_pub = self.create_publisher(
            ConsentDecision, '/consent/decision', 10)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_subscription(
            ConsentPrompt, '/consent/prompt', self._on_prompt, PROMPT_QOS)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_event, 10)
        self.create_subscription(
            String, '/scenario/status', self._on_scenario_status, 10)
        self.create_subscription(
            String, '/study/status', self._on_study_status, STATUS_QOS)
        self.create_subscription(
            Odometry, '/model/consent_robot/odometry', self._on_odometry, 10)
        self.create_timer(0.02, self._tick)
        self.get_logger().info(
            f'research driver ready: {self._condition}/{self._strategy}')

    def _positive_or_zero(self, name: str) -> float:
        value = self.get_parameter(name).value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{name} must be a non-negative number')
        if value < 0:
            raise ValueError(f'{name} must be a non-negative number')
        return float(value)

    @staticmethod
    def _safe_label(value: str) -> str:
        normalized = ''.join(
            character if character.isalnum() or character in '-_' else '_'
            for character in value.strip())
        return normalized[:64] or 'synthetic'

    def _on_session(self, msg: String) -> None:
        session_id = msg.data.strip()
        if not session_id or session_id == self._session_id:
            return
        if self._session_id and not self._finalized:
            self.get_logger().warning('session changed before trial completed')
        self._session_id = session_id
        self._started_at = time.time()
        self._finished_at = None
        self._finalized = False
        self._scenario_completed_at = None
        self._pending_decision = None
        self._answered_request_ids.clear()
        self._prompts.clear()
        self._events.clear()
        self._stage_results.clear()
        self._status_count = 0
        self._scenario_complete = False
        self._study_complete = False
        self._initial_x = None
        self._final_x = None
        self.get_logger().info(f'research trial started for {session_id}')

    def _on_prompt(self, msg: ConsentPrompt) -> None:
        if not self._session_id or msg.session_id != self._session_id:
            return
        if msg.request_id in self._answered_request_ids:
            return

        stage_number = self._stage_for_capability(msg.capability_id)
        if msg.capability_id == 'all_capabilities':
            stage_number = 1
        if stage_number is None:
            self.get_logger().error(
                f'cannot synthesize a decision for {msg.capability_id!r}')
            return

        granted = synthetic_decision(
            self._strategy, msg.capability_id, stage_number)
        decision = ConsentDecision()
        decision.request_id = msg.request_id
        decision.session_id = msg.session_id
        decision.capability_id = msg.capability_id
        decision.decision = (
            ConsentDecision.GRANTED if granted
            else ConsentDecision.REFUSED)
        decision.decided_at = Time()
        due_at = time.monotonic() + self._decision_delay
        self._pending_decision = (due_at, decision)
        self._answered_request_ids.add(msg.request_id)
        self._prompts.append({
            'capability': msg.capability_id,
            'decision': 'granted' if granted else 'refused',
            'stage': stage_number,
        })

    def _tick(self) -> None:
        if self._pending_decision is not None:
            due_at, decision = self._pending_decision
            if time.monotonic() >= due_at:
                decision.decided_at = self.get_clock().now().to_msg()
                self._decision_pub.publish(decision)
                self._pending_decision = None

        if (self._scenario_complete and not self._finalized
                and self._scenario_completed_at is not None
                and time.monotonic() >= self._scenario_completed_at):
            self._write_summary()

    def _on_event(self, msg: ConsentEvent) -> None:
        if msg.session_id != self._session_id:
            return
        self._events[msg.event_type] = self._events.get(msg.event_type, 0) + 1

    def _on_scenario_status(self, msg: String) -> None:
        self._status_count += 1
        if msg.data == 'scenario_complete':
            self._scenario_complete = True
            # Allow the dashboard and the final odometry sample to arrive
            # before the summary is frozen.
            self._scenario_completed_at = time.monotonic() + 0.5
            return
        parts = msg.data.split(':', maxsplit=3)
        if len(parts) != 4 or not parts[0].startswith('stage_'):
            return
        try:
            stage_number = int(parts[0].removeprefix('stage_'))
        except ValueError:
            return
        if parts[2] not in {'capability_executed', 'fallback_executed'}:
            return
        stage = next(
            (item for item in SCENARIO_STAGES if item.number == stage_number),
            None,
        )
        if stage is None or parts[1] != stage.name:
            return
        self._stage_results[stage_number] = {
            'stage': stage_number,
            'capability': stage.capability_id,
            'outcome': 'success'
            if parts[2] == 'capability_executed' else 'fallback',
            'action': parts[3],
        }

    def _on_study_status(self, msg: String) -> None:
        if 'SESSION | COMPLETE' in msg.data:
            self._study_complete = True

    def _on_odometry(self, msg: Odometry) -> None:
        x = float(msg.pose.pose.position.x)
        if self._initial_x is None:
            self._initial_x = x
        self._final_x = x

    def _stage_for_capability(self, capability_id: str) -> int | None:
        for stage in SCENARIO_STAGES:
            if stage.capability_id == capability_id:
                return stage.number
        return None

    def _write_summary(self) -> None:
        self._finalized = True
        self._finished_at = time.time()
        stages = [self._stage_results[number]
                  for number in sorted(self._stage_results)]
        granted = sum(item['outcome'] == 'success' for item in stages)
        fallback = sum(item['outcome'] == 'fallback' for item in stages)
        summary = {
            'schema_version': 1,
            'synthetic_trial': True,
            'trial_label': self._trial_label,
            'condition': self._condition,
            'decision_strategy': self._strategy,
            'session_id': self._session_id,
            'started_at': self._started_at,
            'finished_at': self._finished_at,
            'duration_seconds': (
                self._finished_at - self._started_at
                if self._started_at is not None else None),
            'prompt_decisions': self._prompts,
            'stage_results': stages,
            'metrics': {
                'stage_count': len(stages),
                'granted_stage_count': granted,
                'fallback_stage_count': fallback,
                'completion_rate': 1.0 if self._scenario_complete else 0.0,
                'odometry_delta_x': (
                    self._final_x - self._initial_x
                    if self._initial_x is not None and self._final_x is not None
                    else None),
                'scenario_status_count': self._status_count,
                'study_dashboard_complete': self._study_complete,
            },
            'event_counts': dict(sorted(self._events.items())),
        }
        self._output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._output_directory / (
            f'{self._trial_label}_{self._condition}_{self._strategy}_'
            f'{self._session_id}.json')
        path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        self.get_logger().info(f'research trial summary written to {path}')


def main(args=None):
    rclpy.init(args=args)
    node = ResearchDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
