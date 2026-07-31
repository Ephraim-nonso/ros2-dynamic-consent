from dynamic_consent_hri.consent_state import ConsentStatus, ConsentStore
from dynamic_consent_hri.gate_logic import GateAction, decide
from dynamic_consent_hri.policy_loader import parse_policy


POLICY = parse_policy("""
policy_version: "2.0"
capabilities:
  speech_input:
    sensor: microphone
    privacy_dimensions: [informational]
    data_inputs: [live_audio]
    purpose: "Understand a destination"
    processing: "Transcribe live audio"
    processing_location: on_robot
    recipients: [robot_assistance_system]
    prompt: "May I use the microphone?"
    retention: "not_stored"
    retention_seconds: 0
    expiry_seconds: 10
    refusal_fallback: "show_destination_menu"
  body_pose_tracking:
    sensor: depth_camera
    privacy_dimensions: [informational, physical]
    data_inputs: [skeletal_landmarks]
    purpose: "Recognise body pose"
    processing: "Derive temporary skeletal landmarks"
    processing_location: on_robot
    recipients: [robot_assistance_system]
    prompt: "May I analyse body pose?"
    retention: "not_stored"
    retention_seconds: 0
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
    assert (store.check(SESSION, 'body_pose_tracking').status
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
