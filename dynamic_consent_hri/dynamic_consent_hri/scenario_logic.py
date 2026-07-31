"""Frozen task stages shared by both experimental conditions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioStage:
    number: int
    name: str
    capability_id: str
    capability_action: str
    fallback_action: str


SCENARIO_STAGES = (
    ScenarioStage(
        number=1,
        name='destination',
        capability_id='speech_input',
        capability_action='accept_simulated_speech_destination',
        fallback_action='show_destination_menu',
    ),
    ScenarioStage(
        number=2,
        name='direction',
        capability_id='gesture_recognition',
        capability_action='accept_simulated_pointing_direction',
        fallback_action='show_direction_buttons',
    ),
    ScenarioStage(
        number=3,
        name='guidance',
        capability_id='route_guidance',
        capability_action='provide_simulated_route_guidance',
        fallback_action='show_written_route',
    ),
)
