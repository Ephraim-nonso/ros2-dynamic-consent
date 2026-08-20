"""Strict anonymous event validation and durable per-session CSV logging.

This module deliberately has no ROS dependency. It accepts only the frozen
research schema and rejects any value that could introduce identifiers,
free-text payloads, CSV injection, or ambiguous event semantics.
"""

from __future__ import annotations

import csv
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


CSV_FIELDS = (
    'session_id',
    'condition',
    'event_type',
    'capability',
    'decision',
    'timestamp',
    'response_ms',
    'task_outcome',
)

VALID_CONDITIONS = frozenset({'static', 'dynamic'})
VALID_EVENT_TYPES = frozenset({
    'session_started',
    'consent_requested',
    'consent_decided',
    'consent_revoked',
    'consent_expired',
    'capability_authorized',
    'capability_blocked',
    'capability_executed',
    'fallback_executed',
    'session_reset',
})

_SESSION_PATTERN = re.compile(r'^session_[0-9a-f]{8}$')
_CAPABILITY_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
_MAX_UINT32 = (1 << 32) - 1


class EventValidationError(ValueError):
    """Raised when an event does not match the anonymous research schema."""


class EventLogError(RuntimeError):
    """Raised when a session log cannot be created or safely appended."""


@dataclass(frozen=True)
class AnonymousEvent:
    session_id: str
    condition: str
    event_type: str
    capability_id: str
    decision: str
    timestamp: str
    response_ms: int
    task_outcome: str

    def to_row(self) -> dict[str, str | int]:
        return {
            'session_id': self.session_id,
            'condition': self.condition,
            'event_type': self.event_type,
            'capability': self.capability_id,
            'decision': self.decision,
            'timestamp': self.timestamp,
            'response_ms': self.response_ms,
            'task_outcome': self.task_outcome,
        }


def validate_session_id(session_id: object) -> str:
    if not isinstance(session_id, str) or not _SESSION_PATTERN.fullmatch(
            session_id):
        raise EventValidationError('invalid anonymous session id')
    return session_id


def create_anonymous_event(
        *, session_id: object, condition: object, event_type: object,
        capability_id: object = '', decision: object = '',
        timestamp_seconds: object, response_ms: object = 0,
        task_outcome: object = '') -> AnonymousEvent:
    """Validate primitive event fields and return a CSV-ready record."""
    session_id = validate_session_id(session_id)
    condition = _allowed_string(condition, VALID_CONDITIONS, 'condition')
    event_type = _allowed_string(
        event_type, VALID_EVENT_TYPES, 'event type')
    capability_id = _capability_id(capability_id)
    decision = _allowed_string(
        decision, frozenset({'', 'granted', 'refused', 'revoked'}),
        'decision')
    task_outcome = _allowed_string(
        task_outcome, frozenset({'', 'success', 'fallback', 'abandoned'}),
        'task outcome')
    response_ms = _response_ms(response_ms)
    timestamp = _timestamp(timestamp_seconds)

    _validate_event_semantics(
        event_type, capability_id, decision, response_ms, task_outcome)
    return AnonymousEvent(
        session_id=session_id,
        condition=condition,
        event_type=event_type,
        capability_id=capability_id,
        decision=decision,
        timestamp=timestamp,
        response_ms=response_ms,
        task_outcome=task_outcome,
    )


def _allowed_string(value: object, allowed: frozenset[str],
                    label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise EventValidationError(f'invalid {label}')
    return value


def _capability_id(value: object) -> str:
    if not isinstance(value, str):
        raise EventValidationError('invalid capability id')
    if value and not _CAPABILITY_PATTERN.fullmatch(value):
        raise EventValidationError('invalid capability id')
    return value


def _response_ms(value: object) -> int:
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < 0 or value > _MAX_UINT32):
        raise EventValidationError('invalid response time')
    return value


def _timestamp(value: object) -> str:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise EventValidationError('invalid timestamp')
    try:
        instant = datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise EventValidationError('invalid timestamp') from exc
    return instant.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _validate_event_semantics(event_type: str, capability_id: str,
                              decision: str, response_ms: int,
                              task_outcome: str) -> None:
    session_events = {'session_started', 'session_reset'}
    if event_type in session_events:
        if capability_id or decision or response_ms or task_outcome:
            raise EventValidationError('invalid fields for session event')
        return

    if not capability_id:
        raise EventValidationError('capability event requires capability id')

    if event_type == 'consent_decided':
        if decision not in {'granted', 'refused'} or task_outcome:
            raise EventValidationError('invalid consent decision event')
        return

    if response_ms:
        raise EventValidationError(
            'response time is allowed only for consent decisions')

    if event_type == 'consent_revoked':
        if decision != 'revoked' or task_outcome:
            raise EventValidationError('invalid consent revocation event')
        return

    if decision:
        raise EventValidationError('decision is not valid for this event')

    expected_outcomes = {
        'capability_authorized': {'success'},
        'capability_blocked': {'fallback', 'abandoned'},
        'capability_executed': {'success'},
        'fallback_executed': {'fallback'},
    }
    expected = expected_outcomes.get(event_type)
    if expected is None:
        if task_outcome:
            raise EventValidationError('task outcome is not valid here')
    elif task_outcome not in expected:
        raise EventValidationError('invalid task outcome for event')


class CsvSessionLog:
    """Append validated events to one permission-restricted session file."""

    def __init__(self, directory: str | Path, session_id: str) -> None:
        self.session_id = validate_session_id(session_id)
        requested_directory = Path(directory).expanduser()
        if requested_directory.is_symlink():
            raise EventLogError(
                'refusing to use a symbolic-link log directory')
        self.directory = requested_directory.resolve()
        self.path = self.directory / f'{self.session_id}.csv'
        self._stream: TextIO | None = None
        self._writer: csv.DictWriter | None = None
        self._open()

    def _open(self) -> None:
        try:
            directory_existed = self.directory.exists()
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory_existed:
                if self.directory.stat().st_mode & 0o077:
                    raise EventLogError(
                        'existing log directory is accessible by other users')
            else:
                os.chmod(self.directory, 0o700)
            if self.path.is_symlink():
                raise EventLogError('refusing to follow a session-log symlink')
            new_file = not self.path.exists() or self.path.stat().st_size == 0
            if not new_file:
                self._validate_existing_header()

            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            if hasattr(os, 'O_NOFOLLOW'):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags, 0o600)
            os.chmod(self.path, 0o600)
            self._stream = os.fdopen(
                descriptor, 'a', encoding='utf-8', newline='')
            self._writer = csv.DictWriter(
                self._stream, fieldnames=CSV_FIELDS, extrasaction='raise')
            if new_file:
                self._writer.writeheader()
                self._sync()
        except EventLogError:
            self.close()
            raise
        except OSError as exc:
            self.close()
            raise EventLogError(
                f'cannot open anonymous session log: {exc}') from exc

    def _validate_existing_header(self) -> None:
        try:
            with self.path.open('r', encoding='utf-8', newline='') as stream:
                header = next(csv.reader(stream), None)
        except OSError as exc:
            raise EventLogError(
                f'cannot inspect existing session log: {exc}') from exc
        if header != list(CSV_FIELDS):
            raise EventLogError('existing session log has an invalid schema')

    def append(self, event: AnonymousEvent) -> None:
        if event.session_id != self.session_id:
            raise EventLogError('event does not belong to this session log')
        if self._writer is None or self._stream is None:
            raise EventLogError('session log is closed')
        try:
            self._writer.writerow(event.to_row())
            self._sync()
        except (OSError, csv.Error, ValueError) as exc:
            raise EventLogError(
                f'cannot append anonymous event: {exc}') from exc

    def _sync(self) -> None:
        if self._stream is None:
            return
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
        self._stream = None
        self._writer = None

    def __enter__(self) -> 'CsvSessionLog':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
