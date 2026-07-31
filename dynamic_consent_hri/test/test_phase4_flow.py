from dynamic_consent_hri.consent_state import ConsentStatus, ConsentStore
from dynamic_consent_hri.gate_logic import GateAction, decide
from dynamic_consent_hri.policy_loader import parse_policy


POLICY = parse_policy("""
policy_version: "1.0"
capabilities:
  speech_input:
    sensor: microphone
    purpose: "Understand a destination"
    prompt: "May I use the microphone?"
    retention: "not_stored"
    expiry_seconds: 10
    refusal_fallback: "show_destination_menu"
  gesture_recognition:
    sensor: camera
    purpose: "Recognise a gesture"
    prompt: "May I use the camera?"
    retention: "not_stored"
    expiry_seconds: 10
    refusal_fallback: "show_direction_buttons"
""")

SESSION = 'session_12345678'


def test_dynamic_decision_applies_only_to_requested_capability():
    store = ConsentStore(POLICY)
    assert decide(store.check(SESSION, 'speech_input').status) is (
        GateAction.REQUEST_CONSENT)
    request = store.create_request(SESSION, 'speech_input')
    store.record_decision(
        request.request_id, SESSION, 'speech_input', granted=True)
    assert decide(store.check(SESSION, 'speech_input').status) is (
        GateAction.ALLOW)
    assert (store.check(SESSION, 'gesture_recognition').status
            is ConsentStatus.UNKNOWN)


def test_static_group_grant_authorizes_every_capability_for_session():
    store = ConsentStore(POLICY)
    requests = {
        capability_id: store.create_request(SESSION, capability_id).request_id
        for capability_id in POLICY.capabilities
    }
    store.record_group_decision(
        SESSION, requests, granted=True, apply_expiry=False)
    for capability_id in POLICY.capabilities:
        assert decide(
            store.check(SESSION, capability_id).status,
            reprompt_expired=False,
        ) is GateAction.ALLOW


def test_static_group_refusal_routes_every_capability_to_fallback():
    store = ConsentStore(POLICY)
    requests = {
        capability_id: store.create_request(SESSION, capability_id).request_id
        for capability_id in POLICY.capabilities
    }
    store.record_group_decision(SESSION, requests, granted=False)
    for capability_id in POLICY.capabilities:
        assert decide(
            store.check(SESSION, capability_id).status,
            reprompt_expired=False,
        ) is GateAction.FALLBACK
