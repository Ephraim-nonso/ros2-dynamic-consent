"""Consent condition definitions shared by ROS nodes and tests."""

VALID_CONSENT_MODES = frozenset({'static', 'dynamic'})


def validate_consent_mode(value: object) -> str:
    if not isinstance(value, str) or value not in VALID_CONSENT_MODES:
        raise ValueError(
            f'consent_mode must be one of {sorted(VALID_CONSENT_MODES)}, '
            f'got {value!r}')
    return value
