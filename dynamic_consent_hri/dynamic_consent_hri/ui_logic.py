"""Pure formatting and choice parsing for consent interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class UiChoice(Enum):
    ALLOW = auto()
    REFUSE = auto()
    MORE_INFORMATION = auto()


@dataclass(frozen=True)
class PromptView:
    request_id: str
    session_id: str
    capability_id: str
    sensor: str
    purpose: str
    prompt_text: str
    retention: str
    expiry_seconds: int


_RETENTION_LABELS = {
    'not_stored': 'The data will not be stored.',
    'interaction_only': 'The data is retained only for this interaction.',
    'session_only': 'The data is retained only until this session ends.',
}


def retention_description(retention: str) -> str:
    return _RETENTION_LABELS.get(
        retention, 'The retention rule could not be verified.')


def parse_choice(value: str) -> UiChoice | None:
    normalized = value.strip().lower()
    if normalized in {'1', 'allow', 'a', 'yes', 'y'}:
        return UiChoice.ALLOW
    if normalized in {'2', 'refuse', 'r', 'no', 'n'}:
        return UiChoice.REFUSE
    if normalized in {'3', 'more', 'm', 'info', 'information'}:
        return UiChoice.MORE_INFORMATION
    return None


def format_prompt(prompt: PromptView) -> str:
    sensor = prompt.sensor.upper()
    return (
        '\n' + '=' * 50 + '\n'
        f'The robot would like to use: {sensor}\n\n'
        f'Purpose:\n{prompt.purpose}\n\n'
        f'Privacy notice:\n{prompt.prompt_text}\n\n'
        f'Retention:\n{retention_description(prompt.retention)}\n\n'
        '[1] Allow\n'
        '[2] Refuse\n'
        '[3] View more information\n'
        + '=' * 50
    )


def format_more_information(prompt: PromptView) -> str:
    expiry = (f'{prompt.expiry_seconds} seconds'
              if prompt.expiry_seconds > 0 else 'the current session')
    return (
        '\nAdditional information\n'
        '----------------------\n'
        f'Capability: {prompt.capability_id}\n'
        f'Sensor or data: {prompt.sensor}\n'
        f'Consent validity: {expiry}\n'
        f'{retention_description(prompt.retention)}\n'
        'You may refuse now or revoke a grant later.\n'
    )
