# flake8: noqa: E402
"""Headless end-to-end smoke test for the embodied Gazebo study."""

from __future__ import annotations

import os

import pytest

launch_pytest = pytest.importorskip('launch_pytest')
pytest.importorskip('rclpy')
pytest.importorskip('dynamic_consent_interfaces.msg')
pytest.importorskip('nav_msgs.msg')

from ament_index_python.packages import get_package_share_directory
from builtin_interfaces.msg import Time
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from std_srvs.srv import Trigger

from dynamic_consent_interfaces.msg import ConsentDecision, ConsentPrompt
from dynamic_consent_hri.scenario_logic import SCENARIO_STAGES

from .integration_helpers import TRANSIENT_QOS, running_probe


@launch_pytest.fixture
def headless_gazebo_study():
    share = get_package_share_directory('dynamic_consent_hri')
    launch_file = os.path.join(
        share, 'launch', 'gazebo_dynamic_demo.launch.py')
    study = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file),
        launch_arguments={
            'headless': 'true',
            'render_engine': 'ogre',
        }.items(),
    )
    return LaunchDescription([
        study,
        launch_pytest.actions.ReadyToTest(),
    ])


def _subscriptions():
    return [
        ('/consent/session', String, TRANSIENT_QOS),
        ('/consent/prompt', ConsentPrompt, TRANSIENT_QOS),
        ('/scenario/status', String, 10),
        ('/gazebo_demo/status', String, 10),
        ('/study/status', String, TRANSIENT_QOS),
        ('/study/control_status', String, TRANSIENT_QOS),
        ('/model/consent_robot/odometry', Odometry, 10),
    ]


def _grant(prompt):
    decision = ConsentDecision()
    decision.request_id = prompt.request_id
    decision.session_id = prompt.session_id
    decision.capability_id = prompt.capability_id
    decision.decision = ConsentDecision.GRANTED
    decision.decided_at = Time()
    return decision


@pytest.mark.gazebo
@pytest.mark.ros_integration
@pytest.mark.launch(fixture=headless_gazebo_study)
def test_headless_study_moves_completes_and_resets():
    with running_probe(_subscriptions()) as probe:
        probe.wait_for_publishers(
            ['/scenario/status', '/gazebo_demo/status'], timeout=30.0)
        first_session = probe.wait_for_message(
            '/consent/session', timeout=45.0)
        initial_odom = probe.wait_for_message(
            '/model/consent_robot/odometry', timeout=30.0)
        initial_x = initial_odom.pose.pose.position.x
        action_labels = set()

        for stage in SCENARIO_STAGES:
            prompt = probe.wait_for_message(
                '/consent/prompt',
                lambda msg, cap=stage.capability_id:
                msg.capability_id == cap,
                timeout=20.0,
            )
            probe.publish('/consent/decision', _grant(prompt))
            probe.wait_for_message(
                '/scenario/status',
                lambda msg, number=stage.number:
                msg.data.startswith(
                    f'stage_{number}:')
                and ':capability_executed:' in msg.data,
                timeout=15.0,
            )
            adapter_status = probe.wait_for_message(
                '/gazebo_demo/status',
                lambda msg, number=stage.number:
                msg.data.startswith(f'stage_{number}:')
                and not msg.data.endswith(':stop'),
                timeout=10.0,
            )
            action_labels.add(adapter_status.data.split(':', maxsplit=1)[1])

        probe.wait_for_message(
            '/scenario/status',
            lambda msg: msg.data == 'scenario_complete',
            timeout=15.0,
        )
        probe.wait_for_message(
            '/study/status',
            lambda msg: 'SESSION | COMPLETE' in msg.data,
            timeout=10.0,
        )
        final_odom = probe.wait_for_message(
            '/model/consent_robot/odometry',
            lambda msg: msg.pose.pose.position.x > initial_x + 2.0,
            timeout=15.0,
        )
        assert final_odom.pose.pose.position.x > initial_x + 2.0
        assert len(action_labels) == len(SCENARIO_STAGES)

        reset = probe.call(
            '/study/reset', Trigger, Trigger.Request(), timeout=15.0)
        assert reset.success
        probe.wait_for_message(
            '/study/control_status',
            lambda msg: msg.data == 'reset_complete',
            timeout=20.0,
        )
        next_session = probe.wait_for_message(
            '/consent/session',
            lambda msg: msg.data != first_session.data,
            timeout=10.0,
        )
        assert next_session.data.startswith('session_')
