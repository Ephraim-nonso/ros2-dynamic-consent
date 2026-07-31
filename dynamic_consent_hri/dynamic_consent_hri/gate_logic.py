"""Privacy gate decision logic. Pure Python, no rclpy dependency.

Maps a ConsentStatus to the action the gate must take. GRANTED is the only
status that allows a capability; every other status denies, either by
requesting consent, waiting for a decision already in flight, or running the
fallback for a terminal refusal or revocation.
"""

from __future__ import annotations

from enum import Enum, auto

from .consent_state import ConsentStatus


class GateAction(Enum):
    ALLOW = auto()
    REQUEST_CONSENT = auto()
    WAIT = auto()
    FALLBACK = auto()
    DENY_UNKNOWN_CAPABILITY = auto()


_FALLBACK_STATUSES = frozenset({
    ConsentStatus.REFUSED, ConsentStatus.REVOKED,
})


def decide(status: ConsentStatus, *,
           reprompt_expired: bool = True) -> GateAction:
    if status is ConsentStatus.GRANTED:
        return GateAction.ALLOW
    if status is ConsentStatus.UNKNOWN:
        return GateAction.REQUEST_CONSENT
    if status is ConsentStatus.EXPIRED:
        return (GateAction.REQUEST_CONSENT if reprompt_expired
                else GateAction.FALLBACK)
    if status is ConsentStatus.PENDING:
        return GateAction.WAIT
    if status is ConsentStatus.INVALID_CAPABILITY:
        return GateAction.DENY_UNKNOWN_CAPABILITY
    if status in _FALLBACK_STATUSES:
        return GateAction.FALLBACK
    raise ValueError(f"unhandled consent status: {status}")
