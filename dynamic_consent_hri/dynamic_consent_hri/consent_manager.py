"""Consent manager node: owns consent state for the active session.

Loads and validates the privacy policy, creates consent requests, stores
decisions, expires and revokes permissions, and publishes anonymous consent
events. If the policy fails to load, the node stays up but denies everything
(fail closed).
"""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import (ConsentDecision, ConsentEvent,
                                            ConsentPrompt)
from dynamic_consent_interfaces.srv import (CheckConsent, ResetSession,
                                            RevokeConsent)

from .consent_state import (ConsentRecord, ConsentStateError, ConsentStore,
                            UnknownCapabilityError)
from .package_paths import resolve_policy_path
from .policy_loader import PolicyError, load_policy
from .ros_qos import SESSION_QOS
from .ros_time import to_time_msg
from .session import generate_session_id


class ConsentManagerNode(Node):

    def __init__(self) -> None:
        super().__init__('consent_manager')

        self.declare_parameter('policy_file', 'privacy_policy.yaml')
        self.declare_parameter('session_id', '')
        self.declare_parameter('consent_mode', 'dynamic')

        self._condition = self.get_parameter('consent_mode').value
        self._session_id = (self.get_parameter('session_id').value
                            or generate_session_id())
        self.get_logger().info(
            f'session {self._session_id}, condition {self._condition}')

        self._event_pub = self.create_publisher(
            ConsentEvent, '/consent/event', 10)
        self._prompt_pub = self.create_publisher(
            ConsentPrompt, '/consent/prompt', 10)
        self._session_pub = self.create_publisher(
            String, '/consent/session', SESSION_QOS)

        self._policy = None
        self._store: ConsentStore | None = None
        policy_file = self.get_parameter('policy_file').value
        try:
            self._policy = load_policy(resolve_policy_path(policy_file))
            self._store = ConsentStore(self._policy,
                                       on_expire=self._on_expire)
            self.get_logger().info(
                f'policy {self._policy.version} loaded: '
                f'{sorted(self._policy.capabilities)}')
        except PolicyError as exc:
            # Fail closed: node runs, but every check is denied.
            self.get_logger().error(
                f'policy invalid, denying all capabilities: {exc}')

        self.create_subscription(
            String, '/consent/request', self._on_consent_request, 10)
        self.create_subscription(
            ConsentDecision, '/consent/decision', self._on_decision, 10)
        self.create_service(
            CheckConsent, '/consent/check', self._on_check)
        self.create_service(
            RevokeConsent, '/consent/revoke', self._on_revoke)
        self.create_service(
            ResetSession, '/consent/reset_session', self._on_reset)

        session_msg = String()
        session_msg.data = self._session_id
        self._session_pub.publish(session_msg)
        self._publish_event('session_started')

    # -- topic callbacks --------------------------------------------------

    def _on_consent_request(self, msg: String) -> None:
        """A gate (or the scenario) asks for consent to be obtained."""
        if self._store is None:
            self.get_logger().warning(
                f'request for {msg.data!r} ignored: policy invalid')
            return
        try:
            record = self._store.create_request(self._session_id, msg.data)
        except UnknownCapabilityError as exc:
            self.get_logger().warning(str(exc))
            return
        except ConsentStateError as exc:
            self.get_logger().warning(str(exc))
            return
        if record.decided_at is None and record.status.name == 'PENDING':
            self._publish_prompt(record)
            self._publish_event('consent_requested',
                                capability_id=record.capability_id)

    def _on_decision(self, msg: ConsentDecision) -> None:
        if self._store is None:
            return
        if msg.session_id != self._session_id:
            self.get_logger().warning(
                f'decision for wrong session {msg.session_id!r} ignored')
            return
        valid_decisions = (ConsentDecision.GRANTED, ConsentDecision.REFUSED,
                           ConsentDecision.REVOKED)
        if msg.decision not in valid_decisions:
            self.get_logger().warning(
                f'invalid decision value {msg.decision} ignored')
            return
        try:
            if msg.decision == ConsentDecision.REVOKED:
                record = self._store.revoke(msg.session_id, msg.capability_id)
                self._publish_event('consent_revoked',
                                    capability_id=record.capability_id,
                                    decision='revoked')
                return
            granted = msg.decision == ConsentDecision.GRANTED
            record = self._store.record_decision(
                msg.request_id, msg.session_id, msg.capability_id, granted)
        except ConsentStateError as exc:
            self.get_logger().warning(f'decision rejected: {exc}')
            return
        response_ms = int((record.decided_at - record.requested_at) * 1000)
        self._publish_event('consent_decided',
                            capability_id=record.capability_id,
                            decision=record.status.name.lower(),
                            response_ms=response_ms)

    # -- service callbacks ------------------------------------------------

    def _on_check(self, request, response):
        if self._store is None:
            response.allowed = False
            response.status = (
                CheckConsent.Response.STATUS_INVALID_CAPABILITY)
            response.reason = 'policy invalid; failing closed'
            return response
        result = self._store.check(request.session_id, request.capability_id)
        response.allowed = result.allowed
        response.status = result.status.value
        response.reason = result.reason
        response.expires_at = to_time_msg(result.expires_at)
        return response

    def _on_revoke(self, request, response):
        if self._store is None:
            response.success = False
            response.message = 'policy invalid; nothing to revoke'
            return response
        try:
            record = self._store.revoke(request.session_id,
                                        request.capability_id)
        except ConsentStateError as exc:
            response.success = False
            response.message = str(exc)
            return response
        response.success = True
        response.message = f'consent for {record.capability_id} revoked'
        self._publish_event('consent_revoked',
                            capability_id=record.capability_id,
                            decision='revoked')
        return response

    def _on_reset(self, request, response):
        if self._store is None:
            response.success = False
            response.cleared_count = 0
            response.message = 'policy invalid; nothing to reset'
            return response
        cleared = self._store.reset_session(request.session_id)
        response.success = True
        response.cleared_count = cleared
        response.message = f'cleared {cleared} consent records'
        self._publish_event('session_reset')
        return response

    # -- helpers ----------------------------------------------------------

    def _on_expire(self, record: ConsentRecord) -> None:
        self._publish_event('consent_expired',
                            capability_id=record.capability_id)

    def _publish_prompt(self, record: ConsentRecord) -> None:
        capability = self._policy.get(record.capability_id)
        msg = ConsentPrompt()
        msg.request_id = record.request_id
        msg.session_id = record.session_id
        msg.capability_id = record.capability_id
        msg.sensor = capability.sensor
        msg.purpose = capability.purpose
        msg.prompt_text = capability.prompt
        msg.retention = capability.retention
        msg.expiry_seconds = capability.expiry_seconds
        msg.requested_at = to_time_msg(record.requested_at)
        self._prompt_pub.publish(msg)

    def _publish_event(self, event_type: str, capability_id: str = '',
                       decision: str = '', response_ms: int = 0,
                       task_outcome: str = '') -> None:
        msg = ConsentEvent()
        msg.session_id = self._session_id
        msg.condition = self._condition
        msg.event_type = event_type
        msg.capability_id = capability_id
        msg.decision = decision
        msg.response_ms = response_ms
        msg.task_outcome = task_outcome
        msg.stamp = to_time_msg(time.time())
        self._event_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ConsentManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
