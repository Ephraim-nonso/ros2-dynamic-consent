from pathlib import Path

from dynamic_consent_hri.core.policy_loader import load_policy
from dynamic_consent_hri.simulation.scenario_logic import SCENARIO_STAGES


def test_scenario_covers_each_privacy_dimension_capability_in_order():
    assert [stage.capability_id for stage in SCENARIO_STAGES] == [
        'person_recognition',
        'speech_input',
        'interaction_memory',
        'body_pose_tracking',
        'route_guidance',
        'proximity_or_private_space_access',
        'remote_assistance_stream',
    ]
    assert [stage.number for stage in SCENARIO_STAGES] == list(range(1, 8))


def test_scenario_fallbacks_match_policy():
    policy_path = (
        Path(__file__).resolve().parents[2]
        / 'config' / 'privacy_policy.yaml'
    )
    policy = load_policy(policy_path)
    for stage in SCENARIO_STAGES:
        assert (policy.get(stage.capability_id).refusal_fallback
                == stage.fallback_action)
