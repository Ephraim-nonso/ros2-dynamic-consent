"""Headless-friendly static-consent trial with synthetic decisions."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('dynamic_consent_hri')
    base = os.path.join(share, 'launch', 'gazebo_static_demo.launch.py')
    headless = LaunchConfiguration('headless')
    strategy = LaunchConfiguration('decision_strategy')
    delay = LaunchConfiguration('decision_delay_seconds')
    output = LaunchConfiguration('output_directory')
    label = LaunchConfiguration('trial_label')

    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='true'),
        DeclareLaunchArgument('decision_strategy', default_value='grant_all'),
        DeclareLaunchArgument('decision_delay_seconds', default_value='0.05'),
        DeclareLaunchArgument(
            'output_directory',
            default_value='~/.ros/dynamic_consent/research'),
        DeclareLaunchArgument('trial_label', default_value='synthetic'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(base),
            launch_arguments={
                'headless': headless,
                'sensor_demo': 'false',
                'enable_microphone': 'false',
            }.items(),
        ),
        Node(
            package='dynamic_consent_hri',
            executable='research_driver',
            name='research_driver',
            parameters=[{
                'consent_mode': 'static',
                'decision_strategy': strategy,
                'decision_delay_seconds': delay,
                'output_directory': output,
                'trial_label': label,
            }],
            output='screen',
        ),
    ])
