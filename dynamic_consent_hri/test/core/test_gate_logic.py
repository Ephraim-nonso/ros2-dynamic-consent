import pytest

from dynamic_consent_hri.core.consent_state import ConsentStatus
from dynamic_consent_hri.core.gate_logic import GateAction, decide


@pytest.mark.parametrize(('status', 'expected'), [
    (ConsentStatus.UNKNOWN, GateAction.REQUEST_CONSENT),
    (ConsentStatus.PENDING, GateAction.WAIT),
    (ConsentStatus.GRANTED, GateAction.ALLOW),
    (ConsentStatus.REFUSED, GateAction.FALLBACK),
    (ConsentStatus.REVOKED, GateAction.FALLBACK),
    (ConsentStatus.EXPIRED, GateAction.REQUEST_CONSENT),
    (ConsentStatus.INVALID_CAPABILITY,
     GateAction.DENY_UNKNOWN_CAPABILITY),
])
def test_gate_action_is_fail_closed(status, expected):
    assert decide(status) is expected


def test_unhandled_status_is_rejected():
    with pytest.raises(ValueError, match='unhandled'):
        decide(object())


def test_static_condition_does_not_reprompt_expired_consent():
    assert decide(
        ConsentStatus.EXPIRED,
        reprompt_expired=False,
    ) is GateAction.FALLBACK
