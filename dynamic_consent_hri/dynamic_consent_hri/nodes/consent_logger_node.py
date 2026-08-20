"""ROS node that records validated anonymous consent events as CSV."""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import ConsentEvent

from ..core.conditions import validate_consent_mode
from ..core.event_log import (CsvSessionLog, EventLogError, EventValidationError,
                        create_anonymous_event, validate_session_id)
from ..common.ros_qos import SESSION_QOS


class ConsentLoggerNode(Node):

    def __init__(self) -> None:
        super().__init__('consent_logger')
        self.declare_parameter(
            'log_directory', '~/.ros/dynamic_consent/logs')
        self.declare_parameter('session_timeout_seconds', 900.0)
        self.declare_parameter('enable_raw_sensor_storage', False)
        self.declare_parameter('consent_mode', 'dynamic')

        self._enabled = True
        self._active_session = ''
        self._session_started_at: float | None = None
        self._session_log: CsvSessionLog | None = None
        self._session_failed = False

        self._condition = self._load_condition()
        self._log_directory = self._load_log_directory()
        self._session_timeout = self._load_timeout()
        self._validate_raw_storage_setting()

        self.create_subscription(
            String, '/consent/session', self._on_session, SESSION_QOS)
        self.create_subscription(
            ConsentEvent, '/consent/event', self._on_event, 10)
        self.create_timer(1.0, self._expire_timed_out_session)

        if self._enabled:
            self.get_logger().info(
                'anonymous consent logger ready; waiting for active session')
        else:
            self.get_logger().error(
                'anonymous consent logger disabled by invalid configuration')

    def _load_condition(self) -> str:
        value = self.get_parameter('consent_mode').value
        try:
            return validate_consent_mode(value)
        except ValueError as exc:
            self._enabled = False
            self.get_logger().error(str(exc))
            return 'invalid'

    def _load_log_directory(self) -> str:
        value = self.get_parameter('log_directory').value
        if not isinstance(value, str) or not value.strip():
            self._enabled = False
            self.get_logger().error(
                'log_directory must be a non-empty path string')
            return ''
        return value.strip()

    def _load_timeout(self) -> float:
        value = self.get_parameter('session_timeout_seconds').value
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or value <= 0):
            self._enabled = False
            self.get_logger().error(
                'session_timeout_seconds must be a positive number')
            return 0.0
        return float(value)

    def _validate_raw_storage_setting(self) -> None:
        value = self.get_parameter('enable_raw_sensor_storage').value
        if not isinstance(value, bool) or value:
            self._enabled = False
            self.get_logger().error(
                'raw sensor storage is prohibited by the study protocol')

    def _on_session(self, msg: String) -> None:
        if not self._enabled:
            return
        try:
            session_id = validate_session_id(msg.data)
        except EventValidationError as exc:
            self.get_logger().error(
                f'ignoring invalid active session: {exc}')
            return
        if session_id == self._active_session:
            return

        self._close_session()
        try:
            self._session_log = CsvSessionLog(
                self._log_directory, session_id)
            started = create_anonymous_event(
                session_id=session_id,
                condition=self._condition,
                event_type='session_started',
                timestamp_seconds=time.time(),
            )
            self._session_log.append(started)
        except (EventLogError, EventValidationError) as exc:
            self._session_failed = True
            self.get_logger().error(
                f'cannot start anonymous log for {session_id}: {exc}')
            return

        self._active_session = session_id
        self._session_started_at = time.monotonic()
        self._session_failed = False
        self.get_logger().info(
            f'logging anonymous events for {session_id} to '
            f'{self._session_log.path}')

    def _on_event(self, msg: ConsentEvent) -> None:
        if (not self._enabled or self._session_failed
                or self._session_log is None):
            return
        if msg.session_id != self._active_session:
            self.get_logger().warning(
                'event for non-active session rejected')
            return
        if msg.condition != self._condition:
            self.get_logger().warning('event condition mismatch rejected')
            return
        if self._session_has_timed_out():
            self._expire_timed_out_session()
            return
        # The logger owns this row so it is present even when the manager's
        # volatile publication happens before this node starts.
        if msg.event_type == 'session_started':
            return
        if msg.stamp.nanosec >= 1_000_000_000:
            self.get_logger().warning('event timestamp rejected')
            return

        timestamp = msg.stamp.sec + msg.stamp.nanosec / 1_000_000_000
        try:
            event = create_anonymous_event(
                session_id=msg.session_id,
                condition=msg.condition,
                event_type=msg.event_type,
                capability_id=msg.capability_id,
                decision=msg.decision,
                timestamp_seconds=timestamp,
                response_ms=msg.response_ms,
                task_outcome=msg.task_outcome,
            )
            self._session_log.append(event)
        except EventValidationError as exc:
            self.get_logger().warning(f'anonymous event rejected: {exc}')
        except EventLogError as exc:
            self._session_failed = True
            self.get_logger().error(
                f'anonymous event logging failed closed: {exc}')
            self._close_session(clear_identity=False)

    def _session_has_timed_out(self) -> bool:
        return (self._session_started_at is None
                or time.monotonic() - self._session_started_at
                > self._session_timeout)

    def _expire_timed_out_session(self) -> None:
        if (self._session_log is None or self._session_failed
                or not self._session_has_timed_out()):
            return
        self.get_logger().error(
            'session timeout reached; no further events will be logged')
        self._session_failed = True
        self._close_session(clear_identity=False)

    def _close_session(self, *, clear_identity: bool = True) -> None:
        if self._session_log is not None:
            self._session_log.close()
        self._session_log = None
        self._session_started_at = None
        if clear_identity:
            self._active_session = ''
            self._session_failed = False

    def destroy_node(self):
        self._close_session()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ConsentLoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
