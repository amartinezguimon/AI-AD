"""Tests for soft engagement-zone confidence + gaze re-centring (pure)."""

import math

from visionmetrics.edge.agent.zone import (
    CountingRegion, EngagementZone, GazeReference, zone_confidence,
)


def test_counting_region_none_when_empty_or_too_few_points():
    assert CountingRegion.from_config(None) is None
    assert CountingRegion.from_config({}) is None
    assert CountingRegion.from_config({"polygon": [[0.0, 0.0], [1.0, 1.0]]}) is None  # < 3


def test_counting_region_contains_square():
    r = CountingRegion.from_config(
        {"polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]})
    assert r is not None
    assert r.contains(0.5, 0.5) is True
    assert r.contains(0.5, 1.5) is False   # below
    assert r.contains(-0.1, 0.5) is False  # left of it


def test_counting_region_contains_triangle():
    r = CountingRegion.from_config({"polygon": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]})
    assert r is not None
    assert r.contains(0.1, 0.1) is True
    assert r.contains(0.9, 0.9) is False   # outside the hypotenuse


def test_gaze_reference_defaults_to_no_shift():
    g = GazeReference()
    assert g.recenter(0.4, 0.1) == (0.4, 0.1)


def test_gaze_reference_subtracts_window_centre():
    g = GazeReference(yaw_center=0.4, pitch_center=0.12)
    # someone looking at the window centre (raw 0.4, 0.12) -> straight ahead for the model
    assert g.recenter(0.4, 0.12) == (0.0, 0.0)


def test_gaze_reference_from_config():
    g = GazeReference.from_config({"yaw_center": -0.3, "pitch_center": 0.1})
    assert (round(g.yaw_center, 3), round(g.pitch_center, 3)) == (-0.3, 0.1)
    assert GazeReference.from_config(None) == GazeReference()

ZONE = EngagementZone(
    yaw_min=-0.2, yaw_max=0.2, pitch_min=-0.1, pitch_max=0.1,
    dist_min=0.04, dist_max_m=3.0,
)


def test_no_zone_passes_everything():
    assert zone_confidence(5.0, 5.0, 0.1, None) == 1.0


def test_inside_zone_full_confidence():
    assert zone_confidence(0.0, 0.0, 0.1, ZONE, dist_m=1.0) == 1.0


def test_outside_decays_smoothly():
    # yaw 0.35 is 0.15 beyond yaw_max(0.2); with soft_margin 0.30 => 1 - 0.5 = 0.5
    conf = zone_confidence(0.35, 0.0, 0.1, ZONE, dist_m=1.0, soft_margin=0.30)
    assert math.isclose(conf, 0.5, rel_tol=1e-9)


def test_far_beyond_margin_is_zero():
    assert zone_confidence(1.0, 0.0, 0.1, ZONE, dist_m=1.0) == 0.0


def test_distance_hard_cutoff():
    # 3.0m limit * 1.2 buffer = 3.6m; 4m is beyond => hard zero regardless of gaze.
    assert zone_confidence(0.0, 0.0, 0.1, ZONE, dist_m=4.0) == 0.0


def test_zone_from_config_roundtrip():
    z = EngagementZone.from_config({
        "yaw_min": -0.5, "yaw_max": 0.5, "pitch_min": 0.0, "pitch_max": 0.2,
        "dist_min": 0.04, "dist_max_m": 2.5,
    })
    assert z is not None and z.dist_max_m == 2.5
    assert EngagementZone.from_config(None) is None
