"""Tests for the pure helpers of the counting-zone drawing tool (no OpenCV)."""

from visionmetrics.edge.tools.draw_zone import (
    load_config_dict,
    merge_counting_region,
    normalize_polygon,
)


def test_normalize_polygon_scales_and_clamps():
    pts = [(0, 0), (640, 0), (640, 480), (0, 480), (700, 500)]  # last is out of frame
    norm = normalize_polygon(pts, 640, 480)
    assert norm[0] == [0.0, 0.0]
    assert norm[1] == [1.0, 0.0]
    assert norm[2] == [1.0, 1.0]
    assert norm[4] == [1.0, 1.0]   # clamped back into the frame


def test_merge_preserves_existing_keys_and_does_not_mutate():
    cfg = {"store_name": "X", "engagement_zone": {"yaw_center": 0.1}}
    out = merge_counting_region(cfg, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
    assert out["store_name"] == "X"
    assert out["engagement_zone"] == {"yaw_center": 0.1}
    assert out["counting_region"]["polygon"] == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
    assert "counting_region" not in cfg   # original untouched


def test_load_config_dict_missing_returns_empty(tmp_path):
    assert load_config_dict(tmp_path / "nope.json") == {}


def test_load_config_dict_reads_json(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text('{"store_name": "Y"}', encoding="utf-8")
    assert load_config_dict(p) == {"store_name": "Y"}
