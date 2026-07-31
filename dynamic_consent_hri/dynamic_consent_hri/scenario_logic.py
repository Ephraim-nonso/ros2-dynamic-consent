"""Privacy-dimension task stages shared by both conditions."""

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
        name='returning_user',
        capability_id='person_recognition',
        capability_action='recognise_simulated_returning_user',
        fallback_action='start_anonymous_temporary_session',
    ),
    ScenarioStage(
        number=2,
        name='destination',
        capability_id='speech_input',
        capability_action='accept_simulated_speech_destination',
        fallback_action='show_destination_menu',
    ),
    ScenarioStage(
        number=3,
        name='personalisation',
        capability_id='interaction_memory',
        capability_action='remember_simulated_user_preferences',
        fallback_action='use_session_only_memory',
    ),
    ScenarioStage(
        number=4,
        name='direction',
        capability_id='body_pose_tracking',
        capability_action='accept_simulated_body_pose',
        fallback_action='show_direction_and_assistance_controls',
    ),
    ScenarioStage(
        number=5,
        name='guidance',
        capability_id='route_guidance',
        capability_action='provide_simulated_route_guidance',
        fallback_action='show_written_route',
    ),
    ScenarioStage(
        number=6,
        name='private_space_boundary',
        capability_id='proximity_or_private_space_access',
        capability_action='follow_user_across_simulated_boundary',
        fallback_action='wait_at_boundary_and_show_instructions',
    ),
    ScenarioStage(
        number=7,
        name='remote_assistance',
        capability_id='remote_assistance_stream',
        capability_action='connect_simulated_authorised_staff_member',
        fallback_action='show_local_help_or_request_in_person_staff',
    ),
)
