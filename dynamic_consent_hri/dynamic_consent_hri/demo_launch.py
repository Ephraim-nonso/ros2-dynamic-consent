"""Shared launch construction for static and dynamic conditions."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_demo_launch_description(condition_file: str) -> LaunchDescription:
    share = get_package_share_directory('dynamic_consent_hri')
    parameters = [os.path.join(share, 'config', condition_file)]
    common = {
        'package': 'dynamic_consent_hri',
        'output': 'screen',
        'emulate_tty': True,
    }
    return LaunchDescription([
        Node(executable='consent_manager', name='consent_manager',
             parameters=parameters, **common),
        Node(executable='privacy_gate', name='privacy_gate',
             parameters=parameters, **common),
        Node(executable='consent_ui', name='consent_ui', **common),
        Node(executable='consent_logger', name='consent_logger',
             parameters=parameters, **common),
        Node(executable='scenario_simulator', name='scenario_simulator',
             parameters=parameters, **common),
    ])
