# flake8: noqa: E402
"""Live-node integration tests for both study consent conditions."""

from __future__ import annotations

import os

import pytest

launch_pytest = pytest.importorskip('launch_pytest')
pytest.importorskip('rclpy')
pytest.importorskip('dynamic_consent_interfaces.msg')

from ament_index_python.packages import get_package_share_directory
from builtin_interfaces.msg import Time
from launch import LaunchDescription
from launch_ros.actions import Node
from std_msgs.msg import String

from dynamic_consent_interfaces.msg import ConsentDecision, ConsentPrompt
from dynamic_consent_interfaces.srv import ResetSession, RevokeConsent
from dynamic_consent_hri.simulation.scenario_logic import SCENARIO_STAGES

from .integration_helpers import TRANSIENT_QOS, running_probe


def _condition_nodes(filename):
    config = os.path.join(
        get_package_share_directory('dynamic_consent_hri'),
        'config', filename)
    common = {'package': 'dynamic_consent_hri', 'output': 'screen'}
    return [
        Node(executable='consent_manager', name='consent_manager',
             parameters=[config], **common),
        Node(executable='privacy_gate', name='privacy_gate',
             parameters=[config], **common),
    ]


@launch_pytest.fixture
def dynamic_nodes():
    return LaunchDescription([
        *_condition_nodes('dynamic_condition.yaml'),
        launch_pytest.actions.ReadyToTest(),
    ])


@launch_pytest.fixture
def static_nodes():
    return LaunchDescription([
        *_condition_nodes('static_condition.yaml'),
        launch_pytest.actions.ReadyToTest(),
    ])


def _subscriptions():
    return [
        ('/consent/session', String, TRANSIENT_QOS),
        ('/consent/prompt', ConsentPrompt, TRANSIENT_QOS),
        ('/capability/authorized', String, 10),
        ('/capability/blocked', String, 10),
    ]


def _request(capability_id):
    message = String()
    message.data = capability_id
    return message


def _decision(prompt, granted):
    message = ConsentDecision()
    message.request_id = prompt.request_id
    message.session_id = prompt.session_id
    message.capability_id = prompt.capability_id
    message.decision = (
        ConsentDecision.GRANTED if granted else ConsentDecision.REFUSED)
    message.decided_at = Time()
    return message


@pytest.mark.ros_integration
@pytest.mark.launch(fixture=dynamic_nodes)
def test_dynamic_flow_blocks_until_granted_and_honours_revocation():
    with running_probe(_subscriptions()) as probe:
        session = probe.wait_for_message('/consent/session', timeout=15.0)
        assert session.data.startswith('session_')

        probe.publish(
            '/capability/requested', _request('unknown_capability'))
        probe.wait_for_message(
            '/capability/blocked',
            lambda msg: msg.data == 'unknown_capability')

        capability = 'person_recognition'
        probe.discard('/capability/authorized')
        probe.publish('/capability/requested', _request(capability))
        prompt = probe.wait_for_message(
            '/consent/prompt',
            lambda msg: msg.capability_id == capability)
        probe.assert_no_message(
            '/capability/authorized',
            lambda msg: msg.data == capability,
            duration=0.5)

        probe.publish('/consent/decision', _decision(prompt, True))
        probe.wait_for_message(
            '/capability/authorized',
            lambda msg: msg.data == capability)

        revoke = RevokeConsent.Request()
        revoke.session_id = session.data
        revoke.capability_id = capability
        result = probe.call('/consent/revoke', RevokeConsent, revoke)
        assert result.success

        probe.publish('/capability/requested', _request(capability))
        probe.wait_for_message(
            '/capability/blocked',
            lambda msg: msg.data == capability)


@pytest.mark.ros_integration
@pytest.mark.launch(fixture=static_nodes)
def test_static_flow_applies_one_choice_and_reset_requires_a_new_choice():
    with running_probe(_subscriptions()) as probe:
        first_session = probe.wait_for_message(
            '/consent/session', timeout=15.0)
        first_prompt = probe.wait_for_message(
            '/consent/prompt',
            lambda msg: msg.capability_id == 'all_capabilities')
        probe.publish('/consent/decision', _decision(first_prompt, True))

        for stage in SCENARIO_STAGES:
            probe.publish(
                '/capability/requested', _request(stage.capability_id))
            probe.wait_for_message(
                '/capability/authorized',
                lambda msg, cap=stage.capability_id: msg.data == cap)

        reset = ResetSession.Request()
        reset.session_id = first_session.data
        result = probe.call(
            '/consent/reset_session', ResetSession, reset)
        assert result.success

        next_session = probe.wait_for_message(
            '/consent/session',
            lambda msg: msg.data != first_session.data)
        assert next_session.data.startswith('session_')
        stale_reset = ResetSession.Request()
        stale_reset.session_id = first_session.data
        stale_result = probe.call(
            '/consent/reset_session', ResetSession, stale_reset)
        assert not stale_result.success

        next_prompt = probe.wait_for_message(
            '/consent/prompt',
            lambda msg: msg.request_id != first_prompt.request_id)
        probe.publish('/consent/decision', _decision(next_prompt, False))

        capability = SCENARIO_STAGES[0].capability_id
        probe.publish('/capability/requested', _request(capability))
        probe.wait_for_message(
            '/capability/blocked',
            lambda msg: msg.data == capability)
