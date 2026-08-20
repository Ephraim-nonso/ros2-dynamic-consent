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
    privacy_dimensions: tuple[str, ...]
    data_inputs: tuple[str, ...]
    purpose: str
    processing: str
    processing_location: str
    recipients: tuple[str, ...]
    prompt_text: str
    retention: str
    retention_seconds: int
    expiry_seconds: int


_RETENTION_LABELS = {
    'not_stored': 'The data will not be stored.',
    'interaction_only': 'The data is retained only for this interaction.',
    'session_only': 'The data is retained only until this session ends.',
    'mixed': (
        'Retention differs by capability; review the combined privacy notice.'
    ),
}


def _duration_description(seconds: int) -> str:
    if seconds > 0 and seconds % 86400 == 0:
        days = seconds // 86400
        return f'{days} day' + ('' if days == 1 else 's')
    if seconds > 0 and seconds % 3600 == 0:
        hours = seconds // 3600
        return f'{hours} hour' + ('' if hours == 1 else 's')
    return f'{seconds} seconds'


def retention_description(retention: str,
                          retention_seconds: int = 0) -> str:
    if retention == 'declared_period':
        if retention_seconds <= 0:
            return 'The retention rule could not be verified.'
        return (
            'The data will be retained for '
            f'{_duration_description(retention_seconds)}.'
        )
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
    dimensions = ', '.join(_display_label(item)
                           for item in prompt.privacy_dimensions)
    recipients = ', '.join(_display_label(item)
                           for item in prompt.recipients)
    return (
        '\n' + '=' * 50 + '\n'
        f'The robot would like to use: {sensor}\n\n'
        f'Purpose:\n{prompt.purpose}\n\n'
        f'Privacy dimensions:\n{dimensions}\n\n'
        f'Privacy notice:\n{prompt.prompt_text}\n\n'
        f'Recipients:\n{recipients}\n\n'
        f'Retention:\n{retention_description(prompt.retention, prompt.retention_seconds)}\n\n'
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
        f'Data inputs: {_display_values(prompt.data_inputs)}\n'
        f'Processing: {prompt.processing}\n'
        f'Processing location: {_display_label(prompt.processing_location)}\n'
        f'Recipients: {_display_values(prompt.recipients)}\n'
        f'Consent validity: {expiry}\n'
        f'{retention_description(prompt.retention, prompt.retention_seconds)}\n'
        'You may refuse now or revoke a grant later.\n'
    )


def _display_label(value: str) -> str:
    return value.replace('_', ' ')


def _display_values(values: tuple[str, ...]) -> str:
    return ', '.join(_display_label(value) for value in values)
