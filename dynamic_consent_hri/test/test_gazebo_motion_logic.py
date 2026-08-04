import pytest

from dynamic_consent_hri.gazebo_motion_logic import (
    ScenarioSignal,
    ScenarioSignalKind,
    motion_plan_for_signal,
    parse_scenario_status,
)
from dynamic_consent_hri.scenario_logic import SCENARIO_STAGES


def _status(stage, event_type, detail):
    return f'stage_{stage.number}:{stage.name}:{event_type}:{detail}'


def test_ready_and_complete_are_parsed_without_a_stage():
    assert parse_scenario_status('scenario_ready') == ScenarioSignal(
        ScenarioSignalKind.READY)
    assert parse_scenario_status('scenario_complete') == ScenarioSignal(
        ScenarioSignalKind.COMPLETE)


@pytest.mark.parametrize('stage', SCENARIO_STAGES)
def test_every_frozen_stage_status_is_accepted(stage):
    requested = parse_scenario_status(
        _status(stage, 'requested', stage.capability_id))
    allowed = parse_scenario_status(
        _status(stage, 'capability_executed', stage.capability_action))
    fallback = parse_scenario_status(
        _status(stage, 'fallback_executed', stage.fallback_action))

    assert requested == ScenarioSignal(ScenarioSignalKind.REQUESTED, stage)
    assert allowed == ScenarioSignal(
        ScenarioSignalKind.CAPABILITY_EXECUTED, stage)
    assert fallback == ScenarioSignal(
        ScenarioSignalKind.FALLBACK_EXECUTED, stage)


@pytest.mark.parametrize('value', [
    None,
    1,
    '',
    'stage_01:returning_user:requested:person_recognition',
    'stage_1:wrong_name:requested:person_recognition',
    'stage_1:returning_user:requested:wrong_capability',
    ('stage_1:returning_user:capability_executed:'
     'start_anonymous_temporary_session'),
    'stage_8:unknown:requested:unknown',
    'stage_1:returning_user:unknown:person_recognition',
])
def test_malformed_or_noncanonical_status_is_rejected(value):
    assert parse_scenario_status(value) is None


def test_allowed_outcome_moves_forward_for_a_bounded_duration():
    plan = motion_plan_for_signal(ScenarioSignal(
        ScenarioSignalKind.CAPABILITY_EXECUTED, SCENARIO_STAGES[0]))
    assert plan.label == 'allowed_forward'
    assert len(plan.segments) == 1
    assert plan.segments[0].linear_x > 0
    assert plan.segments[0].angular_z == 0
    assert plan.segments[0].duration_seconds > 0


def test_fallback_acknowledges_without_crossing_the_boundary():
    plan = motion_plan_for_signal(ScenarioSignal(
        ScenarioSignalKind.FALLBACK_EXECUTED, SCENARIO_STAGES[5]))
    assert plan.label == 'fallback_acknowledgement'
    assert [segment.linear_x for segment in plan.segments] == [0.0, 0.0]
    assert plan.segments[0].angular_z == -plan.segments[1].angular_z
    assert (plan.segments[0].duration_seconds
            == plan.segments[1].duration_seconds)


@pytest.mark.parametrize('kind', [
    ScenarioSignalKind.READY,
    ScenarioSignalKind.REQUESTED,
    ScenarioSignalKind.COMPLETE,
])
def test_non_outcome_signal_commands_a_stop(kind):
    plan = motion_plan_for_signal(ScenarioSignal(kind))
    assert plan.label == 'stop'
    assert plan.segments[0].linear_x == 0
    assert plan.segments[0].angular_z == 0


@pytest.mark.parametrize('argument,value', [
    ('forward_speed', 0),
    ('forward_duration', -1),
    ('turn_speed', True),
    ('turn_duration', '0.3'),
])
def test_unsafe_motion_parameters_are_rejected(argument, value):
    with pytest.raises(ValueError, match=argument):
        motion_plan_for_signal(
            ScenarioSignal(ScenarioSignalKind.READY), **{argument: value})
