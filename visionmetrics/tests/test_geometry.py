"""Tests for head-pose geometry (pure, no camera)."""

import math
from dataclasses import dataclass

from visionmetrics.edge.agent import geometry as g


@dataclass
class P:
    x: float
    y: float


def make_landmarks(nose, top, chin, lcheek, rcheek):
    """Build a sparse landmark list indexed at the points geometry reads."""
    lm = [P(0, 0)] * 460
    lm[g.NOSE] = nose
    lm[g.TOP] = top
    lm[g.CHIN] = chin
    lm[g.LEFT_CHEEK] = lcheek
    lm[g.RIGHT_CHEEK] = rcheek
    return lm


def test_yaw_zero_when_nose_centered():
    lm = make_landmarks(
        nose=P(0.5, 0.5), top=P(0.5, 0.2), chin=P(0.5, 0.8),
        lcheek=P(0.4, 0.5), rcheek=P(0.6, 0.5),
    )
    yaw, pitch, width = g.extract_face_angles(lm)
    assert abs(yaw) < 1e-6
    assert abs(pitch) < 1e-6
    assert math.isclose(width, 0.2, rel_tol=1e-6)


def test_yaw_positive_when_nose_right_of_center():
    lm = make_landmarks(
        nose=P(0.55, 0.5), top=P(0.5, 0.2), chin=P(0.5, 0.8),
        lcheek=P(0.4, 0.5), rcheek=P(0.6, 0.5),
    )
    yaw, _, _ = g.extract_face_angles(lm)
    assert yaw > 0


def test_pitch_sign_follows_nose_vertical():
    lm = make_landmarks(
        nose=P(0.5, 0.6), top=P(0.5, 0.2), chin=P(0.5, 0.8),
        lcheek=P(0.4, 0.5), rcheek=P(0.6, 0.5),
    )
    _, pitch, _ = g.extract_face_angles(lm)
    assert pitch > 0  # nose below the cheek midline


def test_relative_neck_yaw_none_for_edge_on_shoulders():
    assert g.relative_neck_yaw(0.5, 0.50, 0.49) is None  # span 0.01 < 0.02


def test_relative_neck_yaw_zero_when_head_aligned():
    val = g.relative_neck_yaw(nose_x=0.5, left_shoulder_x=0.6, right_shoulder_x=0.4)
    assert abs(val) < 1e-6


def test_torso_confidence_clamps_to_unit_range():
    assert g.torso_confidence(0.7, 0.1, neutral_span=0.4) == 1.0   # wide -> full
    assert g.torso_confidence(0.5, 0.5, neutral_span=0.4) == 0.0   # edge-on -> 0
    assert math.isclose(g.torso_confidence(0.6, 0.4, neutral_span=0.4), 0.5)
