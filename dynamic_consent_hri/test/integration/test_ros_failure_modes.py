# flake8: noqa: E402
"""Live-node tests for fail-closed ROS integration failures."""

from __future__ import annotations

import pytest

launch_pytest = pytest.importorskip('launch_pytest')
pytest.importorskip('rclpy')

from launch import LaunchDescription
from launch_ros.actions import Node
from std_msgs.msg import String

from .integration_helpers import running_probe


@launch_pytest.fixture
def gate_without_manager():
    return LaunchDescription([
        Node(
            package='dynamic_consent_hri',
            executable='privacy_gate',
            parameters=[{
                'consent_mode': 'dynamic',
                'session_id': 'session_deadbeef',
            }],
            output='screen',
        ),
        launch_pytest.actions.ReadyToTest(),
    ])


@launch_pytest.fixture
def gate_with_missing_policy():
    return LaunchDescription([
        Node(
            package='dynamic_consent_hri',
            executable='privacy_gate',
            parameters=[{
                'consent_mode': 'dynamic',
                'session_id': 'session_deadbeef',
                'policy_file': 'file_that_does_not_exist.yaml',
            }],
            output='screen',
        ),
        launch_pytest.actions.ReadyToTest(),
    ])


def _subscriptions():
    return [
        ('/capability/authorized', String, 10),
        ('/capability/blocked', String, 10),
    ]


def _request():
    message = String()
    message.data = 'route_guidance'
    return message


@pytest.mark.ros_integration
@pytest.mark.launch(fixture=gate_without_manager)
def test_unavailable_consent_service_never_authorizes():
    with running_probe(_subscriptions()) as probe:
        probe.publish('/capability/requested', _request())
        probe.assert_no_message(
            '/capability/authorized',
            lambda msg: msg.data == 'route_guidance',
            duration=1.0)


@pytest.mark.ros_integration
@pytest.mark.launch(fixture=gate_with_missing_policy)
def test_missing_policy_is_explicitly_blocked():
    with running_probe(_subscriptions()) as probe:
        probe.publish('/capability/requested', _request())
        probe.wait_for_message(
            '/capability/blocked',
            lambda msg: msg.data == 'route_guidance')
        probe.assert_no_message(
            '/capability/authorized',
            lambda msg: msg.data == 'route_guidance',
            duration=0.5)
