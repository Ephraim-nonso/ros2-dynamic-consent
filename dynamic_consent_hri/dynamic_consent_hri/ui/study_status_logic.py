"""Privacy-safe participant-facing status text for the embodied study."""

from __future__ import annotations

from dataclasses import dataclass

from ..simulation.gazebo_motion_logic import ScenarioSignal, ScenarioSignalKind


@dataclass(frozen=True)
class StudyDisplay:
    state: str
    stage_number: int
    title: str
    detail: str
    colour: str

    def as_message(self) -> str:
        stage = (
            f'STAGE {self.stage_number}'
            if self.stage_number else 'SESSION')
        return (f'{stage} | {self.state.upper()} | {self.title} | '
                f'{self.detail} | indicator={self.colour}')


_STAGE_TITLES = {
    1: 'Returning-user recognition',
    2: 'Spoken destination',
    3: 'Interaction memory',
    4: 'Body-pose assistance',
    5: 'Route guidance',
    6: 'Private-space boundary',
    7: 'Remote staff assistance',
}

_ALLOWED_DETAILS = {
    1: 'Recognition was permitted; the robot scans and approaches.',
    2: 'Speech input was permitted; the robot listens and continues.',
    3: 'Memory was permitted; the robot confirms and continues.',
    4: 'Pose processing was permitted; the robot orients and continues.',
    5: 'Route guidance was permitted; the robot leads toward the destination.',
    6: 'Private-space access was permitted; the robot crosses the red line.',
    7: 'The named staff stream was permitted; the robot signals connection.',
}

_FALLBACK_DETAILS = {
    1: 'Using an anonymous temporary session.',
    2: 'Showing the destination menu instead of listening.',
    3: 'Using session-only memory without saving a profile.',
    4: 'Using on-screen direction and assistance controls.',
    5: 'Showing written directions instead of tracking the route.',
    6: 'Waiting outside and showing instructions.',
    7: 'Offering local help or an in-person staff request.',
}


def display_for_signal(signal: ScenarioSignal) -> StudyDisplay:
    """Create fixed display copy without participant-entered content."""
    if signal.kind is ScenarioSignalKind.READY:
        return StudyDisplay(
            'ready', 0, 'Building assistance task',
            'The robot is at reception and the study is ready.', 'blue')
    if signal.kind is ScenarioSignalKind.COMPLETE:
        return StudyDisplay(
            'complete', 0, 'Assistance task complete',
            'The robot has completed all seven privacy stages.', 'purple')
    if signal.stage is None:
        raise ValueError('stage status requires a scenario stage')

    number = signal.stage.number
    title = _STAGE_TITLES[number]
    if signal.kind is ScenarioSignalKind.REQUESTED:
        return StudyDisplay(
            'waiting_for_consent', number, title,
            'The robot is stopped until an explicit choice is made.', 'yellow')
    if signal.kind is ScenarioSignalKind.CAPABILITY_EXECUTED:
        return StudyDisplay(
            'permission_granted', number, title,
            _ALLOWED_DETAILS[number], 'green')
    if signal.kind is ScenarioSignalKind.FALLBACK_EXECUTED:
        return StudyDisplay(
            'fallback_active', number, title,
            _FALLBACK_DETAILS[number], 'orange')
    raise ValueError(f'unhandled scenario signal: {signal.kind!r}')
