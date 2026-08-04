"""Launch the static-consent study condition in Gazebo."""

from dynamic_consent_hri.gazebo_demo_launch import (
    generate_gazebo_demo_launch_description,
)


def generate_launch_description():
    return generate_gazebo_demo_launch_description('static_condition.yaml')
