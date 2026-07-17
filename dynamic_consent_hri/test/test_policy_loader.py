"""Unit tests for policy_loader. Every invalid policy must raise PolicyError
so the system fails closed."""

from pathlib import Path

import pytest

from dynamic_consent_hri.policy_loader import (
    ALLOWED_RETENTION,
    PolicyError,
    load_policy,
    parse_policy,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

VALID_POLICY = """
policy_version: "1.0"
capabilities:
  speech_input:
    sensor: microphone
    purpose: "Understand the destination"
    prompt: "May I use the microphone?"
    retention: "not_stored"
    expiry_seconds: 300
    required: false
    refusal_fallback: "show_destination_menu"
"""


def make_policy(**overrides) -> str:
    """Build a single-capability policy with selected fields replaced."""
    fields = {
        "sensor": "microphone",
        "purpose": '"Understand the destination"',
        "prompt": '"May I use the microphone?"',
        "retention": '"not_stored"',
        "expiry_seconds": "300",
        "refusal_fallback": '"show_destination_menu"',
    }
    fields.update(overrides)
    lines = "\n".join(f"    {k}: {v}" for k, v in fields.items() if v is not None)
    return f'policy_version: "1.0"\ncapabilities:\n  speech_input:\n{lines}\n'


class TestValidPolicy:
    def test_parses_valid_policy(self):
        policy = parse_policy(VALID_POLICY)
        assert policy.version == "1.0"
        cap = policy.get("speech_input")
        assert cap.sensor == "microphone"
        assert cap.expiry_seconds == 300
        assert cap.refusal_fallback == "show_destination_menu"
        assert not cap.required

    def test_contains(self):
        policy = parse_policy(VALID_POLICY)
        assert "speech_input" in policy
        assert "face_recognition" not in policy

    def test_unknown_capability_returns_none(self):
        assert parse_policy(VALID_POLICY).get("face_recognition") is None

    def test_shipped_config_is_valid(self):
        policy = load_policy(CONFIG_DIR / "privacy_policy.yaml")
        assert set(policy.capabilities) == {
            "speech_input", "gesture_recognition", "route_guidance"}
        for cap in policy.capabilities.values():
            assert cap.retention in ALLOWED_RETENTION
            assert cap.expiry_seconds > 0
            assert cap.refusal_fallback

    def test_capabilities_mapping_is_read_only(self):
        policy = parse_policy(VALID_POLICY)
        with pytest.raises(TypeError):
            policy.capabilities["injected"] = None


class TestInvalidPolicy:
    @pytest.mark.parametrize("field", [
        "sensor", "purpose", "prompt", "retention",
        "expiry_seconds", "refusal_fallback",
    ])
    def test_missing_field_rejected(self, field):
        with pytest.raises(PolicyError):
            parse_policy(make_policy(**{field: None}))

    @pytest.mark.parametrize("field", ["sensor", "purpose", "prompt",
                                       "refusal_fallback"])
    def test_empty_string_field_rejected(self, field):
        with pytest.raises(PolicyError):
            parse_policy(make_policy(**{field: '"  "'}))

    @pytest.mark.parametrize("expiry", ["-1", "-300", '"300"', "3.5", "true"])
    def test_bad_expiry_rejected(self, expiry):
        with pytest.raises(PolicyError):
            parse_policy(make_policy(expiry_seconds=expiry))

    def test_unknown_retention_rejected(self):
        with pytest.raises(PolicyError, match="retention"):
            parse_policy(make_policy(retention='"keep_forever"'))

    def test_duplicate_capability_ids_rejected(self):
        text = VALID_POLICY + """
  speech_input:
    sensor: microphone
    purpose: "Second definition"
    prompt: "May I?"
    retention: "not_stored"
    expiry_seconds: 60
    refusal_fallback: "menu"
"""
        with pytest.raises(PolicyError, match="duplicate"):
            parse_policy(text)

    def test_missing_version_rejected(self):
        with pytest.raises(PolicyError, match="policy_version"):
            parse_policy("capabilities: {a: {}}")

    def test_empty_capabilities_rejected(self):
        with pytest.raises(PolicyError, match="capabilities"):
            parse_policy('policy_version: "1.0"\ncapabilities: {}')

    def test_non_mapping_capability_rejected(self):
        with pytest.raises(PolicyError, match="mapping"):
            parse_policy('policy_version: "1.0"\ncapabilities:\n  a: "text"')

    def test_empty_capability_id_rejected(self):
        with pytest.raises(PolicyError, match="identifier"):
            parse_policy('policy_version: "1.0"\ncapabilities:\n  "": {}')

    @pytest.mark.parametrize("text", ["", "just a string", "- a\n- b"])
    def test_non_mapping_root_rejected(self, text):
        with pytest.raises(PolicyError):
            parse_policy(text)

    def test_invalid_yaml_rejected(self):
        with pytest.raises(PolicyError, match="YAML"):
            parse_policy("policy_version: [unclosed")

    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(PolicyError, match="cannot read"):
            load_policy(tmp_path / "does_not_exist.yaml")

    def test_non_bool_required_rejected(self):
        with pytest.raises(PolicyError, match="required"):
            parse_policy(make_policy(required='"yes"'))
