"""Tests for most_centred_face — picking the right face when two are in a crop."""

from __future__ import annotations

from visionmetrics.edge.agent import geometry
from visionmetrics.edge.agent.vision.face import most_centred_face


class _LM:
    def __init__(self, x):
        self.x = x
        self.y = 0.0


def _face(nose_x):
    """A fake landmark list where only the NOSE index's x matters here."""
    lm = [_LM(0.0) for _ in range(max(geometry.NOSE, geometry.RIGHT_CHEEK) + 1)]
    lm[geometry.NOSE] = _LM(nose_x)
    return lm


def test_single_face_is_returned_unchanged():
    f = _face(0.2)
    assert most_centred_face([f]) is f


def test_picks_the_centred_face_over_an_edge_one():
    centred = _face(0.52)     # near the crop centre (0.5) -> the box owner
    intruder = _face(0.05)    # off to the side -> an adjacent person
    assert most_centred_face([intruder, centred]) is centred
    assert most_centred_face([centred, intruder]) is centred


def test_ties_keep_the_first():
    a = _face(0.4)
    b = _face(0.6)            # equidistant from 0.5
    assert most_centred_face([a, b]) is a
