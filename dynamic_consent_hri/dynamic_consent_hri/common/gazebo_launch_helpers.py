"""Shared ROS 2 Jazzy / Gazebo Harmonic demonstration launch."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from .launch_helpers import generate_demo_nodes


def generate_gazebo_demo_launch_description(
        condition_file: str, *, sensor_demo_default: str = 'false',
        microphone_default: str = 'false',
        stage_delay_seconds: float = 1.8) -> LaunchDescription:
    """Launch one consent condition in the common offline Gazebo world."""
    share = get_package_share_directory('dynamic_consent_hri')
    ros_gz_share = get_package_share_directory('ros_gz_sim')
    world = os.path.join(share, 'worlds', 'dynamic_consent_building.sdf')
    gazebo_launch = os.path.join(ros_gz_share, 'launch', 'gz_sim.launch.py')
    motion_config = os.path.join(share, 'config', 'gazebo_demo.yaml')
    sensor_config = os.path.join(share, 'config', 'sensor_demo.yaml')

    headless = LaunchConfiguration('headless')
    render_engine = LaunchConfiguration('render_engine')
    sensor_demo = LaunchConfiguration('sensor_demo')
    enable_microphone = LaunchConfiguration('enable_microphone')
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
        condition_file, {
            'stage_delay_seconds': stage_delay_seconds,
            'sensor_demo': sensor_demo,
        })
    nodes.extend([
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='gazebo_velocity_bridge',
            arguments=[
                '/model/consent_robot/cmd_vel'
                '@geometry_msgs/msg/Twist@gz.msgs.Twist',
                '/model/consent_robot/odometry'
                '@nav_msgs/msg/Odometry@gz.msgs.Odometry',
                '/sensors/logical_camera/raw'
                '@ros_gz_interfaces/msg/LogicalCameraImage'
                '@gz.msgs.LogicalCameraImage',
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
            executable='logical_camera_guard',
            name='logical_camera_guard',
            parameters=[sensor_config],
            condition=IfCondition(sensor_demo),
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='microphone_guard',
            name='microphone_guard',
            parameters=[sensor_config],
            condition=IfCondition(enable_microphone),
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='offline_speech_recognizer',
            name='offline_speech_recognizer',
            condition=IfCondition(enable_microphone),
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='speech_feedback',
            name='speech_feedback',
            parameters=[sensor_config],
            condition=IfCondition(enable_microphone),
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
        DeclareLaunchArgument(
            'sensor_demo', default_value=sensor_demo_default,
            description='Start consent-enforced simulated sensor nodes.'),
        DeclareLaunchArgument(
            'enable_microphone', default_value=microphone_default,
            description='Open the real microphone only after authorization.'),
        gui,
        server,
        *nodes,
    ])
