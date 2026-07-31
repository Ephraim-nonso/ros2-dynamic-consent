"""Fail-closed enforcement node for simulated capability requests."""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import ConsentEvent
from dynamic_consent_interfaces.srv import CheckConsent

from .consent_state import ConsentStatus
from .gate_logic import GateAction, decide
from .package_paths import resolve_policy_path
from .policy_loader import Policy, PolicyError, load_policy
from .ros_qos import SESSION_QOS
from .ros_time import to_time_msg


class PrivacyGateNode(Node):

    def __init__(self) -> None:
        super().__init__('privacy_gate')
        self.declare_parameter('policy_file', 'privacy_policy.yaml')
        self.declare_parameter('session_id', '')
        self.declare_parameter('consent_mode', 'dynamic')

        self._session_id = str(self.get_parameter('session_id').value)
        self._condition = str(self.get_parameter('consent_mode').value)
        self._policy = self._load_policy()
        self._pending: set[str] = set()
        self._queued: set[str] = set()
        self._checks_in_flight: dict[str, str] = {}

        self._authorized_pub = self.create_publisher(
            String, '/capability/authorized', 10)
        self._blocked_pub = self.create_publisher(
            String, '/capability/blocked', 10)
        self._consent_request_pub = self.create_publisher(
            String, '/consent/request', 10)
        self._event_pub = self.create_publisher(
            ConsentEvent, '/consent/event', 10)

        self.create_subscription(
            String, '/capability/requested', self._on_capability_request, 10)
        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_consent_event, 10)
        self._check_client = self.create_client(
            CheckConsent, '/consent/check')
        self.create_timer(0.25, self._retry_queued_checks)

        if self._session_id:
            self.get_logger().info(
                f'privacy gate ready for session {self._session_id}')
        else:
            self.get_logger().info(
                'privacy gate ready; waiting for the active session')

    def _load_policy(self) -> Policy | None:
        policy_file = str(self.get_parameter('policy_file').value)
        try:
            return load_policy(resolve_policy_path(policy_file))
        except PolicyError as exc:
            self.get_logger().error(
                f'policy invalid; all capabilities will be blocked: {exc}')
            return None

    def _on_session(self, msg: String) -> None:
        session_id = msg.data.strip()
        if not session_id:
            return
        if self._session_id and self._session_id != session_id:
            self.get_logger().error(
                f'active session changed from {self._session_id} to '
                f'{session_id}; queued requests discarded')
            self._pending.clear()
            self._queued.clear()
            self._checks_in_flight.clear()
        self._session_id = session_id
        self.get_logger().info(f'using active session {session_id}')
        self._retry_queued_checks()

    def _on_capability_request(self, msg: String) -> None:
        capability_id = msg.data.strip()
        if not capability_id:
            self._block('', 'empty capability identifier', abandoned=True)
            return
        if self._policy is None:
            self._block(capability_id, 'privacy policy unavailable')
            return
        if capability_id not in self._policy:
            self._block(capability_id, 'capability is not defined in policy',
                        abandoned=True)
            return
        if capability_id in self._pending:
            self.get_logger().info(
                f'{capability_id} is already waiting for a decision')
            return
        self._check(capability_id)

    def _check(self, capability_id: str) -> None:
        if not self._session_id or not self._check_client.service_is_ready():
            self._queued.add(capability_id)
            return
        if capability_id in self._checks_in_flight:
            return

        self._queued.discard(capability_id)
        checked_session = self._session_id
        self._checks_in_flight[capability_id] = checked_session
        request = CheckConsent.Request()
        request.session_id = checked_session
        request.capability_id = capability_id
        future = self._check_client.call_async(request)
        future.add_done_callback(
            lambda completed, cap=capability_id, session=checked_session:
            self._on_check_complete(cap, session, completed))

    def _on_check_complete(self, capability_id, checked_session,
                           future) -> None:
        if self._checks_in_flight.get(capability_id) != checked_session:
            return
        del self._checks_in_flight[capability_id]
        if checked_session != self._session_id:
            return
        try:
            result = future.result()
        except Exception as exc:  # rclpy client exceptions vary by middleware
            self._block(capability_id, f'consent check failed: {exc}')
            return
        if result is None:
            self._block(capability_id, 'consent check returned no response')
            return

        try:
            status = ConsentStatus(result.status)
            action = decide(status)
        except (ValueError, TypeError) as exc:
            self._block(capability_id,
                        f'unrecognized consent status: {exc}')
            return

        if action is GateAction.ALLOW:
            self._authorize(capability_id)
        elif action is GateAction.REQUEST_CONSENT:
            self._pending.add(capability_id)
            request = String()
            request.data = capability_id
            self._consent_request_pub.publish(request)
            self.get_logger().info(
                f'consent requested for {capability_id}')
        elif action is GateAction.WAIT:
            self._pending.add(capability_id)
            self.get_logger().info(
                f'waiting for pending consent for {capability_id}')
        elif action is GateAction.FALLBACK:
            self._block(capability_id, result.reason)
        else:
            self._block(capability_id, result.reason, abandoned=True)

    def _on_consent_event(self, msg: ConsentEvent) -> None:
        if msg.session_id != self._session_id:
            return
        if (msg.event_type == 'consent_decided'
                and msg.capability_id in self._pending):
            self._check(msg.capability_id)

    def _retry_queued_checks(self) -> None:
        if not self._session_id or not self._check_client.service_is_ready():
            return
        for capability_id in tuple(self._queued):
            self._check(capability_id)

    def _authorize(self, capability_id: str) -> None:
        self._pending.discard(capability_id)
        output = String()
        output.data = capability_id
        self._authorized_pub.publish(output)
        self._publish_event('capability_authorized', capability_id,
                            task_outcome='success')
        self.get_logger().info(f'authorized {capability_id}')

    def _block(self, capability_id: str, reason: str,
               abandoned: bool = False) -> None:
        self._pending.discard(capability_id)
        self._queued.discard(capability_id)
        output = String()
        output.data = capability_id
        self._blocked_pub.publish(output)
        outcome = 'abandoned' if abandoned else 'fallback'
        self._publish_event('capability_blocked', capability_id,
                            task_outcome=outcome)

        fallback = None
        if self._policy is not None:
            capability = self._policy.get(capability_id)
            if capability is not None:
                fallback = capability.refusal_fallback
        detail = f'; selected fallback {fallback}' if fallback else ''
        self.get_logger().warning(
            f'blocked {capability_id or "<empty>"}: {reason}{detail}')

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
    node = PrivacyGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
