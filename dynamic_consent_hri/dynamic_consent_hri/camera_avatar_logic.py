"""Pure mapping from temporary face observations to avatar commands."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FaceObservation:
    """Normalized, non-identifying measurements from one video frame."""

    horizontal_offset: float
    eye_line_angle: float
    eyes_visible: int
    smile_detected: bool
    mouth_activity: float


@dataclass(frozen=True)
class AvatarCommand:
    """Bounded Gazebo joint targets derived from a face observation."""

    head_yaw: float
    head_roll: float
    eyelid_position: float
    jaw_angle: float


NEUTRAL_COMMAND = AvatarCommand(
    head_yaw=0.0,
    head_roll=0.0,
    eyelid_position=0.0,
    jaw_angle=0.0,
)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def command_for_observation(observation: FaceObservation) -> AvatarCommand:
    """Convert transient face signals to safe, bounded joint positions."""
    values = (
        observation.horizontal_offset,
        observation.eye_line_angle,
        observation.mouth_activity,
    )
    if any(not math.isfinite(value) for value in values):
        raise ValueError('face observation values must be finite')
    if observation.eyes_visible < 0:
        raise ValueError('eyes_visible must not be negative')

    yaw = _clamp(-observation.horizontal_offset * 0.9, -0.65, 0.65)
    roll = _clamp(observation.eye_line_angle, -0.45, 0.45)
    eyelid = -0.075 if observation.eyes_visible < 2 else 0.0
    activity = _clamp(observation.mouth_activity, 0.0, 1.0)
    jaw = activity * 0.38
    if observation.smile_detected:
        jaw = max(jaw, 0.16)
    return AvatarCommand(yaw, roll, eyelid, _clamp(jaw, 0.0, 0.40))
