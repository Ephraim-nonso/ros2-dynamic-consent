import pytest

from dynamic_consent_hri.sensor_guard_logic import AuthorizationWindow


def test_authorization_window_is_fail_closed_and_bounded():
    window = AuthorizationWindow('speech_input', 5.0)
    assert not window.is_active(10.0)

    window.authorize(10.0)
    assert window.is_active(14.999)
    assert not window.is_active(15.0)
    assert not window.is_active(16.0)


@pytest.mark.parametrize('event_type', [
    'consent_revoked',
    'consent_expired',
    'capability_blocked',
])
def test_matching_capability_event_closes_window(event_type):
    window = AuthorizationWindow('speech_input', 5.0)
    window.authorize(10.0)

    assert window.handle_event(event_type, 'speech_input')
    assert not window.is_active(11.0)


def test_unrelated_capability_does_not_close_window():
    window = AuthorizationWindow('speech_input', 5.0)
    window.authorize(10.0)

    assert not window.handle_event('consent_revoked', 'route_guidance')
    assert window.is_active(11.0)


@pytest.mark.parametrize('event_type', ['session_started', 'session_reset'])
def test_session_change_closes_window(event_type):
    window = AuthorizationWindow('speech_input', 5.0)
    window.authorize(10.0)

    assert window.handle_event(event_type, '')
    assert not window.is_active(11.0)


def test_invalid_window_configuration_is_rejected():
    with pytest.raises(ValueError):
        AuthorizationWindow('', 5.0)
    with pytest.raises(ValueError):
        AuthorizationWindow('speech_input', 0.0)
