"""Pure decision policies used by the no-participant research driver."""

from __future__ import annotations


DECISION_STRATEGIES = frozenset({
    'grant_all',
    'refuse_all',
    'alternate',
    'risk_weighted',
})

# Deliberately explicit so a synthetic trial is auditable and reproducible.
_HIGH_PRIVACY_CAPABILITIES = frozenset({
    'person_recognition',
    'body_pose_tracking',
    'proximity_or_private_space_access',
    'remote_assistance_stream',
})


def validate_strategy(value: object) -> str:
    if not isinstance(value, str) or value not in DECISION_STRATEGIES:
        raise ValueError(
            f"decision strategy must be one of {sorted(DECISION_STRATEGIES)}")
    return value


def synthetic_decision(strategy: str, capability_id: str,
                       stage_number: int) -> bool:
    """Return the deterministic synthetic decision for one capability.

    This is intentionally not presented as a model of participant behaviour.
    It is a test input that exercises the static/dynamic consent paths.
    """
    strategy = validate_strategy(strategy)
    if not capability_id or stage_number <= 0:
        raise ValueError('capability_id and stage_number must be valid')
    if strategy == 'grant_all':
        return True
    if strategy == 'refuse_all':
        return False
    if capability_id == 'all_capabilities':
        # Static consent is one atomic choice; mixed strategies therefore use
        # refusal rather than pretending that the seven stages can diverge.
        return False
    if strategy == 'alternate':
        return stage_number % 2 == 1
    return capability_id not in _HIGH_PRIVACY_CAPABILITIES
