"""ROS-independent authorization windows for privacy-sensitive sensors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthorizationWindow:
    """A bounded grant which is closed by expiry, revocation, or reset."""

    capability_id: str
    duration_seconds: float
    _active_until: float | None = None

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError('capability_id must not be empty')
        if self.duration_seconds <= 0:
            raise ValueError('duration_seconds must be positive')

    def authorize(self, now: float) -> None:
        self._active_until = now + self.duration_seconds

    def close(self) -> None:
        self._active_until = None

    def is_active(self, now: float) -> bool:
        if self._active_until is None:
            return False
        if now >= self._active_until:
            self.close()
            return False
        return True

    def handle_event(self, event_type: str, capability_id: str) -> bool:
        """Close on a relevant consent event; return whether state changed."""
        closes_session = event_type in {'session_reset', 'session_started'}
        closes_capability = (
            capability_id == self.capability_id
            and event_type in {'consent_revoked', 'consent_expired'}
        )
        if (closes_session or closes_capability
                or event_type == 'capability_blocked'
                and capability_id == self.capability_id):
            was_active = self._active_until is not None
            self.close()
            return was_active
        return False
