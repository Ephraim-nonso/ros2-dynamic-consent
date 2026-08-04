"""Pure parsing and motion plans for the Phase 6 Gazebo demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .scenario_logic import SCENARIO_STAGES, ScenarioStage


class ScenarioSignalKind(Enum):
    READY = auto()
    REQUESTED = auto()
    CAPABILITY_EXECUTED = auto()
    FALLBACK_EXECUTED = auto()
    COMPLETE = auto()


@dataclass(frozen=True)
class ScenarioSignal:
    kind: ScenarioSignalKind
    stage: ScenarioStage | None = None


@dataclass(frozen=True)
class MotionSegment:
    linear_x: float
    angular_z: float
    duration_seconds: float


@dataclass(frozen=True)
class MotionPlan:
    label: str
    segments: tuple[MotionSegment, ...]


_STAGES_BY_NUMBER = {stage.number: stage for stage in SCENARIO_STAGES}


def parse_scenario_status(value: object) -> ScenarioSignal | None:
    """Parse only status strings that exactly match the frozen scenario."""
    if value == 'scenario_ready':
        return ScenarioSignal(ScenarioSignalKind.READY)
    if value == 'scenario_complete':
        return ScenarioSignal(ScenarioSignalKind.COMPLETE)
    if not isinstance(value, str):
        return None

    parts = value.split(':')
    if len(parts) != 4 or not parts[0].startswith('stage_'):
        return None
    try:
        stage_number = int(parts[0].removeprefix('stage_'))
    except ValueError:
        return None
    if parts[0] != f'stage_{stage_number}':
        return None
    stage = _STAGES_BY_NUMBER.get(stage_number)
    if stage is None or parts[1] != stage.name:
        return None

    event_type, detail = parts[2], parts[3]
    expected = {
        'requested': (
            ScenarioSignalKind.REQUESTED, stage.capability_id),
        'capability_executed': (
            ScenarioSignalKind.CAPABILITY_EXECUTED,
            stage.capability_action),
        'fallback_executed': (
            ScenarioSignalKind.FALLBACK_EXECUTED,
            stage.fallback_action),
    }.get(event_type)
    if expected is None or detail != expected[1]:
        return None
    return ScenarioSignal(expected[0], stage)


def motion_plan_for_signal(
        signal: ScenarioSignal, *, forward_speed: float = 0.5,
        forward_duration: float = 0.8, turn_speed: float = 0.8,
        turn_duration: float = 0.3) -> MotionPlan:
    """Map a validated scenario signal to a bounded visual motion plan.

    Allowed outcomes move forward. A fallback performs an equal left/right
    acknowledgement without advancing, so refusing private-space access never
    carries the robot across the boundary.
    """
    forward_speed = _positive_number(forward_speed, 'forward_speed')
    forward_duration = _positive_number(
        forward_duration, 'forward_duration')
    turn_speed = _positive_number(turn_speed, 'turn_speed')
    turn_duration = _positive_number(turn_duration, 'turn_duration')

    stop = MotionSegment(0.0, 0.0, 0.0)
    if signal.kind in {
            ScenarioSignalKind.READY,
            ScenarioSignalKind.REQUESTED,
            ScenarioSignalKind.COMPLETE,
    }:
        return MotionPlan('stop', (stop,))
    if signal.kind is ScenarioSignalKind.CAPABILITY_EXECUTED:
        return MotionPlan(
            'allowed_forward',
            (MotionSegment(forward_speed, 0.0, forward_duration),),
        )
    if signal.kind is ScenarioSignalKind.FALLBACK_EXECUTED:
        return MotionPlan(
            'fallback_acknowledgement',
            (
                MotionSegment(0.0, turn_speed, turn_duration),
                MotionSegment(0.0, -turn_speed, turn_duration),
            ),
        )
    raise ValueError(f'unhandled scenario signal: {signal.kind!r}')


def _positive_number(value: object, label: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or value <= 0):
        raise ValueError(f'{label} must be a positive number')
    return float(value)
