import math

import pytest

from dynamic_consent_hri.camera_avatar_logic import (
    FaceObservation,
    NEUTRAL_COMMAND,
    command_for_observation,
)


def test_centered_open_eyes_and_still_mouth_are_neutral():
    observation = FaceObservation(0.0, 0.0, 2, False, 0.0)
    assert command_for_observation(observation) == NEUTRAL_COMMAND


def test_face_motion_maps_to_visible_avatar_joints():
    command = command_for_observation(
        FaceObservation(0.5, 0.2, 1, True, 0.8))
    assert command.head_yaw == pytest.approx(-0.45)
    assert command.head_roll == pytest.approx(0.2)
    assert command.eyelid_position < 0
    assert command.jaw_angle > 0.25


def test_commands_are_bounded_for_extreme_observations():
    command = command_for_observation(
        FaceObservation(20.0, -8.0, 0, True, 50.0))
    assert command.head_yaw == -0.65
    assert command.head_roll == -0.45
    assert command.eyelid_position == -0.075
    assert command.jaw_angle == 0.38


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test_non_finite_observations_fail_closed(value):
    with pytest.raises(ValueError):
        command_for_observation(
            FaceObservation(value, 0.0, 2, False, 0.0))


def test_negative_eye_count_is_invalid():
    with pytest.raises(ValueError):
        command_for_observation(
            FaceObservation(0.0, 0.0, -1, False, 0.0))
