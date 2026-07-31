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
        purpose='Understand the requested destination',
        prompt_text='May I use the microphone?',
        retention='not_stored',
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
    assert 'will not be stored' in text
    assert '[1] Allow' in text
    assert '[2] Refuse' in text


def test_more_information_contains_expiry_and_revocation(prompt):
    text = format_more_information(prompt)
    assert '300 seconds' in text
    assert 'revoke' in text


def test_unknown_retention_fails_closed_in_wording():
    assert 'could not be verified' in retention_description('forever')


def test_closed_or_empty_input_has_no_default_decision():
    assert parse_choice('') is None
