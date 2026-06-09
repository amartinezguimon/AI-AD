"""Tests for VideoSource using a synthetic video file (no real camera)."""

import numpy as np
import cv2
import pytest

from visionmetrics.edge.agent.capture import VideoSource, _is_realtime


def test_source_kind_detection():
    assert _is_realtime(0) is True
    assert _is_realtime("rtsp://10.0.0.1/stream") is True
    assert _is_realtime("https://cam/feed") is True
    assert _is_realtime("fixtures/clip.mp4") is False
    assert _is_realtime("C:/videos/test.avi") is False


def _write_clip(path, n_frames=12, w=64, h=48):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (w, h))
    assert writer.isOpened(), "codec MJPG/.avi not available"
    for i in range(n_frames):
        frame = np.full((h, w, 3), i * 5 % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_file_source_reads_every_frame_in_order(tmp_path):
    clip = tmp_path / "clip.avi"
    _write_clip(clip, n_frames=12)

    src = VideoSource(str(clip))
    assert src.realtime is False
    assert src.open() is True

    count = 0
    while True:
        ok, frame = src.read()
        if not ok or frame is None:
            break
        assert frame.shape[:2] == (48, 64)
        count += 1
    src.release()

    assert count == 12  # sequential, nothing dropped


def test_open_returns_false_for_bad_source():
    src = VideoSource("does_not_exist_12345.avi")
    assert src.open() is False
