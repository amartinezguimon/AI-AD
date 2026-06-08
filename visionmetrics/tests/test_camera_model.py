"""Tests for the pinhole camera model (pure)."""

import math

from visionmetrics.edge.agent import camera_model as cm


def test_focal_length_known_value():
    # 90 deg FOV on a 1000px wide frame => focal = 500 / tan(45) = 500.
    assert math.isclose(cm.focal_length_px(1000, 90.0), 500.0, rel_tol=1e-9)


def test_distance_inverse_to_face_width():
    focal = cm.focal_length_px(1280, 70.0)
    near = cm.distance_metres(0.20, 640, focal, face_width_m=0.16)
    far = cm.distance_metres(0.05, 640, focal, face_width_m=0.16)
    assert far > near  # smaller normalised face => farther away


def test_distance_clamped_to_physical_range():
    focal = cm.focal_length_px(1280, 70.0)
    huge = cm.distance_metres(1e-9, 640, focal, face_width_m=0.16)
    tiny = cm.distance_metres(10.0, 640, focal, face_width_m=0.16)
    assert huge == cm.DIST_MAX_M
    assert tiny == cm.DIST_MIN_M
