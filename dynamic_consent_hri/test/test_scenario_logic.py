from pathlib import Path

from dynamic_consent_hri.policy_loader import load_policy
from dynamic_consent_hri.scenario_logic import SCENARIO_STAGES


def test_scenario_has_frozen_three_stage_order():
    assert [stage.capability_id for stage in SCENARIO_STAGES] == [
        'speech_input',
        'gesture_recognition',
        'route_guidance',
    ]
    assert [stage.number for stage in SCENARIO_STAGES] == [1, 2, 3]


def test_scenario_fallbacks_match_policy():
    policy_path = (
        Path(__file__).resolve().parents[1]
        / 'config' / 'privacy_policy.yaml'
    )
    policy = load_policy(policy_path)
    for stage in SCENARIO_STAGES:
        assert (policy.get(stage.capability_id).refusal_fallback
                == stage.fallback_action)
