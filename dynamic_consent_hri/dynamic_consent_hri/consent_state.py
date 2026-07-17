"""Consent state machine. Pure Python, no rclpy dependency.

State model:

    UNKNOWN -> PENDING -> GRANTED
                       └> REFUSED
    GRANTED -> REVOKED
    GRANTED -> EXPIRED

GRANTED is the only state that allows a capability; every other state, every
unknown capability and every unknown session denies (fail closed). REFUSED,
REVOKED and EXPIRED may transition back to PENDING via a new request
(re-prompting, dynamic mode only).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .policy_loader import Policy


class ConsentStatus(Enum):
    UNKNOWN = 0
    PENDING = 1
    GRANTED = 2
    REFUSED = 3
    REVOKED = 4
    EXPIRED = 5


# States from which a new consent request may be created.
_PROMPTABLE = {ConsentStatus.UNKNOWN, ConsentStatus.REFUSED,
               ConsentStatus.REVOKED, ConsentStatus.EXPIRED}


class ConsentStateError(Exception):
    """Raised on an operation that has no valid state transition."""


class UnknownCapabilityError(ConsentStateError):
    """Raised when a capability is not defined in the loaded policy."""


@dataclass
class ConsentRecord:
    request_id: str
    session_id: str
    capability_id: str
    status: ConsentStatus
    requested_at: float
    decided_at: float | None = None
    expires_at: float | None = None


@dataclass(frozen=True)
class ConsentCheck:
    """Result of a consent check. allowed is true only for valid GRANTED."""
    allowed: bool
    status: ConsentStatus
    reason: str
    expires_at: float | None = None


class ConsentStore:
    """Owns all consent state for active sessions.

    The clock is injectable so expiry behaviour is testable; it must return
    seconds since the epoch.
    """

    def __init__(self, policy: Policy,
                 clock: Callable[[], float] = time.time,
                 on_expire: Callable[[ConsentRecord], None] | None = None
                 ) -> None:
        self._policy = policy
        self._clock = clock
        self._on_expire = on_expire
        self._records: dict[tuple[str, str], ConsentRecord] = {}

    # -- queries ----------------------------------------------------------

    def check(self, session_id: str, capability_id: str) -> ConsentCheck:
        """Fail-closed consent check for (session, capability)."""
        if capability_id not in self._policy:
            return ConsentCheck(False, ConsentStatus.UNKNOWN,
                                f"capability '{capability_id}' is not in the policy")

        record = self._records.get((session_id, capability_id))
        if record is None:
            return ConsentCheck(False, ConsentStatus.UNKNOWN,
                                "consent has not been requested")

        self._expire_if_lapsed(record)

        if record.status is ConsentStatus.GRANTED:
            return ConsentCheck(True, record.status, "consent granted",
                                record.expires_at)
        return ConsentCheck(False, record.status,
                            f"consent is {record.status.name.lower()}",
                            record.expires_at)

    def get_record(self, session_id: str,
                   capability_id: str) -> ConsentRecord | None:
        record = self._records.get((session_id, capability_id))
        if record is not None:
            self._expire_if_lapsed(record)
        return record

    # -- transitions ------------------------------------------------------

    def create_request(self, session_id: str,
                       capability_id: str) -> ConsentRecord:
        """Create a PENDING request, or return the existing record when one
        is already PENDING or validly GRANTED (no downgrade)."""
        capability = self._policy.get(capability_id)
        if capability is None:
            raise UnknownCapabilityError(
                f"capability '{capability_id}' is not in the policy")

        record = self._records.get((session_id, capability_id))
        if record is not None:
            self._expire_if_lapsed(record)
            if record.status in (ConsentStatus.PENDING, ConsentStatus.GRANTED):
                return record
            if record.status not in _PROMPTABLE:
                raise ConsentStateError(
                    f"cannot re-request consent from {record.status.name}")

        record = ConsentRecord(
            request_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            capability_id=capability_id,
            status=ConsentStatus.PENDING,
            requested_at=self._clock(),
        )
        self._records[(session_id, capability_id)] = record
        return record

    def record_decision(self, request_id: str, session_id: str,
                        capability_id: str, granted: bool) -> ConsentRecord:
        """Apply a participant decision to a PENDING request.

        The request_id must match the current pending request so a stale or
        replayed decision cannot grant consent.
        """
        record = self._records.get((session_id, capability_id))
        if record is None or record.request_id != request_id:
            raise ConsentStateError(
                f"no pending request '{request_id}' for "
                f"('{session_id}', '{capability_id}')")
        if record.status is not ConsentStatus.PENDING:
            raise ConsentStateError(
                f"decision received but request is {record.status.name}, "
                "not PENDING")

        now = self._clock()
        record.decided_at = now
        if granted:
            record.status = ConsentStatus.GRANTED
            capability = self._policy.get(capability_id)
            # expiry_seconds == 0 means consent lasts for the whole session
            if capability.expiry_seconds > 0:
                record.expires_at = now + capability.expiry_seconds
        else:
            record.status = ConsentStatus.REFUSED
        return record

    def revoke(self, session_id: str, capability_id: str) -> ConsentRecord:
        """Withdraw a granted permission; only GRANTED can be revoked."""
        record = self._records.get((session_id, capability_id))
        if record is None:
            raise ConsentStateError(
                f"nothing to revoke for ('{session_id}', '{capability_id}')")
        self._expire_if_lapsed(record)
        if record.status is not ConsentStatus.GRANTED:
            raise ConsentStateError(
                f"cannot revoke consent that is {record.status.name}")
        record.status = ConsentStatus.REVOKED
        record.decided_at = self._clock()
        return record

    def reset_session(self, session_id: str) -> int:
        """Remove all consent state for a session; returns records cleared."""
        keys = [key for key in self._records if key[0] == session_id]
        for key in keys:
            del self._records[key]
        return len(keys)

    # -- internal ---------------------------------------------------------

    def _expire_if_lapsed(self, record: ConsentRecord) -> None:
        if (record.status is ConsentStatus.GRANTED
                and record.expires_at is not None
                and self._clock() >= record.expires_at):
            record.status = ConsentStatus.EXPIRED
            if self._on_expire is not None:
                self._on_expire(record)
