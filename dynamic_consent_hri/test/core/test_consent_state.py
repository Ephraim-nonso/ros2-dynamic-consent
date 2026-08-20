"""Unit tests for the consent state machine.

The essential security tests:
    No consent          -> DENY
    Granted consent     -> ALLOW
    Refused consent     -> DENY
    Revoked consent     -> DENY
    Expired consent     -> DENY
    Unknown capability  -> DENY
    Wrong session ID    -> DENY
"""

import pytest

from dynamic_consent_hri.core.consent_state import (
    ConsentStateError,
    ConsentStatus,
    ConsentStore,
    UnknownCapabilityError,
)
from dynamic_consent_hri.core.policy_loader import parse_policy

POLICY = parse_policy("""
policy_version: "2.0"
capabilities:
  speech_input:
    sensor: microphone
    privacy_dimensions: [informational]
    data_inputs: [live_audio]
    purpose: "Understand the destination"
    processing: "Transcribe live audio"
    processing_location: on_robot
    recipients: [robot_assistance_system]
    prompt: "May I use the microphone?"
    retention: "not_stored"
    retention_seconds: 0
    expiry_seconds: 300
    refusal_fallback: "show_destination_menu"
  route_guidance:
    sensor: location
    privacy_dimensions: [informational, physical]
    data_inputs: [current_indoor_location]
    purpose: "Provide navigation"
    processing: "Calculate a local route"
    processing_location: on_robot
    recipients: [robot_navigation_system]
    prompt: "May I use your location?"
    retention: "interaction_only"
    retention_seconds: 0
    expiry_seconds: 0
    refusal_fallback: "show_written_route"
""")

SESSION = "session_04f82c7a"
CAP = "speech_input"


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(clock):
    return ConsentStore(POLICY, clock=clock)


def grant(store, session=SESSION, capability=CAP):
    record = store.create_request(session, capability)
    return store.record_decision(record.request_id, session, capability,
                                 granted=True)


class TestDenyByDefault:
    def test_no_consent_denies(self, store):
        result = store.check(SESSION, CAP)
        assert not result.allowed
        assert result.status is ConsentStatus.UNKNOWN

    def test_unknown_capability_denies(self, store):
        result = store.check(SESSION, "face_recognition")
        assert not result.allowed
        assert result.status is ConsentStatus.INVALID_CAPABILITY

    def test_unknown_capability_cannot_be_requested(self, store):
        with pytest.raises(UnknownCapabilityError):
            store.create_request(SESSION, "face_recognition")

    def test_pending_denies(self, store):
        store.create_request(SESSION, CAP)
        result = store.check(SESSION, CAP)
        assert not result.allowed
        assert result.status is ConsentStatus.PENDING

    def test_wrong_session_denies(self, store):
        grant(store)
        assert not store.check("session_other", CAP).allowed


class TestGrantRefuse:
    def test_granted_allows(self, store, clock):
        record = grant(store)
        result = store.check(SESSION, CAP)
        assert result.allowed
        assert result.status is ConsentStatus.GRANTED
        assert result.expires_at == clock.now + 300
        assert record.decided_at == clock.now

    def test_refused_denies(self, store):
        record = store.create_request(SESSION, CAP)
        store.record_decision(record.request_id, SESSION, CAP, granted=False)
        result = store.check(SESSION, CAP)
        assert not result.allowed
        assert result.status is ConsentStatus.REFUSED

    def test_refusal_allows_reprompt(self, store):
        record = store.create_request(SESSION, CAP)
        store.record_decision(record.request_id, SESSION, CAP, granted=False)
        new_record = store.create_request(SESSION, CAP)
        assert new_record.status is ConsentStatus.PENDING
        assert new_record.request_id != record.request_id

    def test_decision_without_request_rejected(self, store):
        with pytest.raises(ConsentStateError):
            store.record_decision("bogus", SESSION, CAP, granted=True)
        assert not store.check(SESSION, CAP).allowed

    def test_stale_request_id_rejected(self, store):
        old = store.create_request(SESSION, CAP)
        store.record_decision(old.request_id, SESSION, CAP, granted=False)
        store.create_request(SESSION, CAP)
        with pytest.raises(ConsentStateError):
            store.record_decision(old.request_id, SESSION, CAP, granted=True)
        assert not store.check(SESSION, CAP).allowed

    def test_double_decision_rejected(self, store):
        record = store.create_request(SESSION, CAP)
        store.record_decision(record.request_id, SESSION, CAP, granted=False)
        with pytest.raises(ConsentStateError):
            store.record_decision(record.request_id, SESSION, CAP,
                                  granted=True)

    def test_request_while_granted_returns_existing(self, store):
        record = grant(store)
        again = store.create_request(SESSION, CAP)
        assert again is record
        assert again.status is ConsentStatus.GRANTED

    def test_request_while_pending_is_idempotent(self, store):
        first = store.create_request(SESSION, CAP)
        second = store.create_request(SESSION, CAP)
        assert second.request_id == first.request_id

    def test_group_grant_can_last_for_whole_session(self, store, clock):
        speech = store.create_request(SESSION, CAP)
        route = store.create_request(SESSION, 'route_guidance')
        records = store.record_group_decision(
            SESSION,
            {CAP: speech.request_id,
             'route_guidance': route.request_id},
            granted=True,
            apply_expiry=False,
        )
        assert {record.status for record in records} == {
            ConsentStatus.GRANTED}
        clock.advance(100000)
        assert store.check(SESSION, CAP).allowed

    def test_group_decision_validation_is_atomic(self, store):
        speech = store.create_request(SESSION, CAP)
        store.create_request(SESSION, 'route_guidance')
        with pytest.raises(ConsentStateError):
            store.record_group_decision(
                SESSION,
                {CAP: speech.request_id,
                 'route_guidance': 'stale-request'},
                granted=True,
            )
        assert store.check(SESSION, CAP).status is ConsentStatus.PENDING
        assert (store.check(SESSION, 'route_guidance').status
                is ConsentStatus.PENDING)


class TestRevocation:
    def test_revoked_denies(self, store):
        grant(store)
        store.revoke(SESSION, CAP)
        result = store.check(SESSION, CAP)
        assert not result.allowed
        assert result.status is ConsentStatus.REVOKED

    def test_revoke_without_grant_rejected(self, store):
        with pytest.raises(ConsentStateError):
            store.revoke(SESSION, CAP)

    def test_revoke_refused_rejected(self, store):
        record = store.create_request(SESSION, CAP)
        store.record_decision(record.request_id, SESSION, CAP, granted=False)
        with pytest.raises(ConsentStateError):
            store.revoke(SESSION, CAP)

    def test_revocation_allows_reprompt(self, store):
        grant(store)
        store.revoke(SESSION, CAP)
        record = store.create_request(SESSION, CAP)
        assert record.status is ConsentStatus.PENDING


class TestExpiry:
    def test_granted_expires_after_timeout(self, store, clock):
        grant(store)
        clock.advance(300)
        result = store.check(SESSION, CAP)
        assert not result.allowed
        assert result.status is ConsentStatus.EXPIRED

    def test_granted_valid_just_before_timeout(self, store, clock):
        grant(store)
        clock.advance(299)
        assert store.check(SESSION, CAP).allowed

    def test_expired_allows_reprompt(self, store, clock):
        grant(store)
        clock.advance(301)
        record = store.create_request(SESSION, CAP)
        assert record.status is ConsentStatus.PENDING

    def test_expired_cannot_be_revoked(self, store, clock):
        grant(store)
        clock.advance(301)
        with pytest.raises(ConsentStateError):
            store.revoke(SESSION, CAP)

    def test_on_expire_callback_fires_once(self, clock):
        expired = []
        store = ConsentStore(POLICY, clock=clock, on_expire=expired.append)
        record = store.create_request(SESSION, CAP)
        store.record_decision(record.request_id, SESSION, CAP, granted=True)
        clock.advance(301)
        store.check(SESSION, CAP)
        store.check(SESSION, CAP)
        assert len(expired) == 1
        assert expired[0].capability_id == CAP

    def test_zero_expiry_lasts_whole_session(self, store, clock):
        grant(store, capability="route_guidance")
        clock.advance(100000)
        assert store.check(SESSION, "route_guidance").allowed


class TestSessionReset:
    def test_reset_clears_session(self, store):
        grant(store)
        grant(store, capability="route_guidance")
        cleared = store.reset_session(SESSION)
        assert cleared == 2
        assert store.check(SESSION, CAP).status is ConsentStatus.UNKNOWN

    def test_reset_leaves_other_sessions(self, store):
        grant(store)
        grant(store, session="session_other")
        store.reset_session(SESSION)
        assert store.check("session_other", CAP).allowed

    def test_reset_unknown_session_clears_nothing(self, store):
        assert store.reset_session("session_ghost") == 0
