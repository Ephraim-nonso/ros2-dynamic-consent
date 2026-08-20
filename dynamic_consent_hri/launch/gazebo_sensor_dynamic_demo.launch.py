"""Launch real microphone plus Gazebo logical-camera dynamic consent demo."""

from dynamic_consent_hri.common.gazebo_launch_helpers import (
    generate_gazebo_demo_launch_description,
)


def generate_launch_description():
    return generate_gazebo_demo_launch_description(
        'dynamic_condition.yaml',
        sensor_demo_default='true',
        microphone_default='true',
        stage_delay_seconds=1.8,
    )
