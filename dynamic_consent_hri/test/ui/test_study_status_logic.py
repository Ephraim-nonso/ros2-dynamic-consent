import pytest

from dynamic_consent_hri.simulation.gazebo_motion_logic import (
    ScenarioSignal,
    ScenarioSignalKind,
)
from dynamic_consent_hri.simulation.scenario_logic import SCENARIO_STAGES
from dynamic_consent_hri.ui.study_status_logic import display_for_signal


def test_session_statuses_are_clear_and_stage_free():
    ready = display_for_signal(ScenarioSignal(ScenarioSignalKind.READY))
    complete = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.COMPLETE))
    assert ready.state == 'ready'
    assert ready.stage_number == 0
    assert complete.state == 'complete'
    assert complete.stage_number == 0


@pytest.mark.parametrize('stage', SCENARIO_STAGES)
def test_each_stage_has_waiting_allowed_and_fallback_copy(stage):
    waiting = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.REQUESTED, stage))
    allowed = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.CAPABILITY_EXECUTED, stage))
    fallback = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.FALLBACK_EXECUTED, stage))

    assert waiting.stage_number == stage.number
    assert waiting.state == 'waiting_for_consent'
    assert waiting.colour == 'yellow'
    assert allowed.state == 'permission_granted'
    assert allowed.colour == 'green'
    assert fallback.state == 'fallback_active'
    assert fallback.colour == 'orange'
    assert waiting.title == allowed.title == fallback.title
    assert stage.capability_id not in waiting.as_message()


def test_private_boundary_display_explains_both_physical_outcomes():
    stage = SCENARIO_STAGES[5]
    allowed = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.CAPABILITY_EXECUTED, stage))
    fallback = display_for_signal(ScenarioSignal(
        ScenarioSignalKind.FALLBACK_EXECUTED, stage))
    assert 'crosses the red line' in allowed.detail
    assert 'Waiting outside' in fallback.detail


def test_stage_status_without_a_stage_is_rejected():
    with pytest.raises(ValueError, match='requires a scenario stage'):
        display_for_signal(ScenarioSignal(ScenarioSignalKind.REQUESTED))
