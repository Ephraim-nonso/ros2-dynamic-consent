"""Run the isolated Mac-camera consent and Gazebo avatar demonstration."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory('dynamic_consent_hri')
    ros_gz_share = get_package_share_directory('ros_gz_sim')
    world = os.path.join(share, 'worlds', 'camera_consent_avatar.sdf')
    gazebo_launch = os.path.join(ros_gz_share, 'launch', 'gz_sim.launch.py')

    relay_url = LaunchConfiguration('relay_url')
    relay_token = LaunchConfiguration('relay_token')
    access_seconds = LaunchConfiguration('access_seconds')
    show_camera = LaunchConfiguration('show_camera')

    return LaunchDescription([
        DeclareLaunchArgument(
            'relay_url', default_value='http://10.0.2.2:8765',
            description='Mac camera relay base URL visible from Ubuntu.'),
        DeclareLaunchArgument(
            'relay_token', default_value='',
            description='Bearer token printed by mac_camera_relay.py.'),
        DeclareLaunchArgument(
            'access_seconds', default_value='60.0',
            description='Maximum duration of one approved camera window.'),
        DeclareLaunchArgument(
            'show_camera', default_value='true',
            description='Open rqt_image_view for camera/consent feedback.'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={
                'gz_args': ['-r -v 3 --render-engine ogre ', world],
                'on_exit_shutdown': 'true',
            }.items(),
        ),
        Node(
            package='dynamic_consent_hri',
            executable='consent_manager',
            name='camera_consent_manager',
            parameters=[{
                'policy_file': 'camera_avatar_policy.yaml',
                'consent_mode': 'dynamic',
            }],
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='privacy_gate',
            name='camera_privacy_gate',
            parameters=[{
                'policy_file': 'camera_avatar_policy.yaml',
                'consent_mode': 'dynamic',
            }],
            output='screen',
        ),
        Node(
            package='dynamic_consent_hri',
            executable='consent_ui',
            name='camera_consent_ui',
            output='screen',
            emulate_tty=True,
        ),
        Node(
            package='dynamic_consent_hri',
            executable='camera_avatar_gateway',
            name='camera_avatar_gateway',
            parameters=[{
                'relay_url': relay_url,
                'relay_token': relay_token,
                'access_seconds': ParameterValue(
                    access_seconds, value_type=float),
            }],
            output='screen',
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='camera_avatar_joint_bridge',
            arguments=[
                '/avatar/head_yaw@std_msgs/msg/Float64@gz.msgs.Double',
                '/avatar/head_roll@std_msgs/msg/Float64@gz.msgs.Double',
                '/avatar/eyelid@std_msgs/msg/Float64@gz.msgs.Double',
                '/avatar/jaw@std_msgs/msg/Float64@gz.msgs.Double',
            ],
            output='screen',
        ),
        Node(
            package='rqt_image_view',
            executable='rqt_image_view',
            name='consent_camera_view',
            arguments=['/camera_consent/annotated_image'],
            condition=IfCondition(show_camera),
            output='screen',
        ),
    ])
