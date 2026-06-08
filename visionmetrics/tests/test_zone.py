"""Tests for soft engagement-zone confidence (pure)."""

import math

from visionmetrics.edge.agent.zone import EngagementZone, zone_confidence

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
