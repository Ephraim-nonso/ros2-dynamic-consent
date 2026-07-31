import pytest

from dynamic_consent_hri.ui_logic import (
    PromptView,
    UiChoice,
    format_more_information,
    format_prompt,
    parse_choice,
    retention_description,
)


@pytest.fixture
def prompt():
    return PromptView(
        request_id='request_1',
        session_id='session_12345678',
        capability_id='speech_input',
        sensor='microphone',
        privacy_dimensions=('informational',),
        data_inputs=('live_audio', 'spoken_destination'),
        purpose='Understand the requested destination',
        processing='Transcribe the destination from live audio',
        processing_location='on_robot',
        recipients=('robot_assistance_system',),
        prompt_text='May I use the microphone?',
        retention='not_stored',
        retention_seconds=0,
        expiry_seconds=300,
    )


@pytest.mark.parametrize(('value', 'expected'), [
    ('1', UiChoice.ALLOW),
    ('yes', UiChoice.ALLOW),
    ('2', UiChoice.REFUSE),
    ('N', UiChoice.REFUSE),
    ('3', UiChoice.MORE_INFORMATION),
    ('info', UiChoice.MORE_INFORMATION),
    ('', None),
    ('unexpected', None),
])
def test_parse_choice(value, expected):
    assert parse_choice(value) is expected


def test_prompt_contains_required_notice(prompt):
    text = format_prompt(prompt)
    assert 'MICROPHONE' in text
    assert prompt.purpose in text
    assert prompt.prompt_text in text
    assert 'informational' in text
    assert 'robot assistance system' in text
    assert 'will not be stored' in text
    assert '[1] Allow' in text
    assert '[2] Refuse' in text


def test_more_information_contains_expiry_and_revocation(prompt):
    text = format_more_information(prompt)
    assert '300 seconds' in text
    assert 'live audio' in text
    assert 'on robot' in text
    assert 'revoke' in text


def test_unknown_retention_fails_closed_in_wording():
    assert 'could not be verified' in retention_description('forever')


def test_declared_retention_period_is_human_readable():
    assert retention_description('declared_period', 2592000) == (
        'The data will be retained for 30 days.')


def test_mixed_static_retention_requires_review_of_notice():
    assert 'differs by capability' in retention_description('mixed')


def test_closed_or_empty_input_has_no_default_decision():
    assert parse_choice('') is None
