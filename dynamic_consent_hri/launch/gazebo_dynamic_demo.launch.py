"""Launch the dynamic-consent study condition in Gazebo."""

from dynamic_consent_hri.common.gazebo_launch_helpers import (
    generate_gazebo_demo_launch_description,
)


def generate_launch_description():
    return generate_gazebo_demo_launch_description('dynamic_condition.yaml')
