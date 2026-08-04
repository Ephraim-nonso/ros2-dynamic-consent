"""Shared ROS 2 Jazzy / Gazebo Harmonic demonstration launch."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from .demo_launch import generate_demo_nodes


def generate_gazebo_demo_launch_description(
        condition_file: str) -> LaunchDescription:
    """Launch one consent condition in the common offline Gazebo world."""
    share = get_package_share_directory('dynamic_consent_hri')
    ros_gz_share = get_package_share_directory('ros_gz_sim')
    world = os.path.join(share, 'worlds', 'dynamic_consent_building.sdf')
    gazebo_launch = os.path.join(ros_gz_share, 'launch', 'gz_sim.launch.py')
    motion_config = os.path.join(share, 'config', 'gazebo_demo.yaml')

    headless = LaunchConfiguration('headless')
    render_engine = LaunchConfiguration('render_engine')
    common_gz_arguments = {
        'on_exit_shutdown': 'true',
    }

    gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gazebo_launch),
        launch_arguments={
            **common_gz_arguments,
            'gz_args': [
                '-r -v 3 --render-engine ', render_engine, ' ', world],
        }.items(),
        condition=UnlessCondition(headless),
    )
    server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gazebo_launch),
        launch_arguments={
            **common_gz_arguments,
            'gz_args': ['-r -s -v 3 ', world],
        }.items(),
        condition=IfCondition(headless),
    )

    nodes = generate_demo_nodes(
        condition_file, {'stage_delay_seconds': 1.8})
    nodes.extend([
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='gazebo_velocity_bridge',
            arguments=[
                '/model/consent_robot/cmd_vel'
                '@geometry_msgs/msg/Twist@gz.msgs.Twist',
                '/world/dynamic_consent_world/control'
                '@ros_gz_interfaces/srv/ControlWorld',
            ],
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='gazebo_motion_adapter',
            name='gazebo_motion_adapter',
            parameters=[motion_config],
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='study_dashboard',
            name='study_dashboard',
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='experiment_controller',
            name='experiment_controller',
            output='screen',
        ),
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'headless', default_value='false',
            description='Run the Gazebo server without its graphical client.'),
        DeclareLaunchArgument(
            'render_engine', default_value='ogre',
            description='Gazebo GUI render engine; Ogre 1 suits the UTM VM.'),
        gui,
        server,
        *nodes,
    ])
