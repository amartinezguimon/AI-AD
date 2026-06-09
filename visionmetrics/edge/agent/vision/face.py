"""Head-pose analysis (MediaPipe Face Landmarker) — Layers 2 & 3.

Crops the head region (top fraction of the person bbox), upscales it so far
faces become detectable, runs MediaPipe, and converts landmarks into
(yaw, pitch, distance, dist_m) via the shared geometry + camera model.

Per-track frame-skip cache: MediaPipe is the expensive call, so we only run it
every N frames per person and reuse the last result in between (matches the
prototype's behavior).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .. import geometry
from ..camera_model import distance_metres


@dataclass
class HeadPose:
    yaw: float
    pitch: float
    distance: float            # normalised cheekbone width (classifier feature)
    dist_m: float              # real distance in metres
    nose_px: tuple[int, int]   # nose position in original-frame coords (for debug draw)


class HeadPoseAnalyzer:
    def __init__(
        self, model_path: str, *, face_width_m: float, head_crop_frac: float,
        head_upscale: int, skip_frames: int, pad: int = 30,
        min_detection_confidence: float = 0.25,
    ):
        base = python.BaseOptions(model_asset_path=model_path)
        opts = vision.FaceLandmarkerOptions(
            base_options=base, num_faces=1,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
        )
        self._detector = vision.FaceLandmarker.create_from_options(opts)
        self.face_width_m = face_width_m
        self.head_crop_frac = head_crop_frac
        self.head_upscale = head_upscale
        self.skip_frames = skip_frames
        self.pad = pad
        self._cache: dict[int, tuple[int, HeadPose | None]] = {}

    def head_region(self, frame, bbox) -> tuple[int, int, int, int]:
        """Compute the padded head ROI (top `head_crop_frac` of the bbox)."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        head_y2 = y1 + int((y2 - y1) * self.head_crop_frac)
        return (
            max(0, x1 - self.pad), max(0, y1 - self.pad),
            min(w, x2 + self.pad), min(h, head_y2 + self.pad),
        )

    def analyze(self, frame, bbox, track_id: int, frame_idx: int,
                focal_px: float) -> HeadPose | None:
        """Return the head pose for one person, using the frame-skip cache."""
        idx, cached = self._cache.get(track_id, (-(10**9), None))
        if frame_idx - idx < self.skip_frames:
            return cached

        rx1, ry1, rx2, ry2 = self.head_region(frame, bbox)
        roi = frame[ry1:ry2, rx1:rx2]
        pose = None
        if roi.size > 0:
            pose = self._detect(roi, (rx1, ry1, rx2, ry2), focal_px)
        self._cache[track_id] = (frame_idx, pose)
        return pose

    def _detect(self, roi, region, focal_px) -> HeadPose | None:
        rx1, ry1, rx2, ry2 = region
        roi_h, roi_w = roi.shape[:2]
        s = self.head_upscale
        up = cv2.resize(roi, (roi_w * s, roi_h * s), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(up, cv2.COLOR_BGR2RGB)
        result = self._detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not result.face_landmarks:
            return None
        lm = result.face_landmarks[0]
        yaw, pitch, distance = geometry.extract_face_angles(lm)
        dist_m = distance_metres(distance, rx2 - rx1, focal_px, face_width_m=self.face_width_m)
        nose_px = (rx1 + int(lm[geometry.NOSE].x * roi_w),
                   ry1 + int(lm[geometry.NOSE].y * roi_h))
        return HeadPose(yaw, pitch, distance, dist_m, nose_px)

    def forget(self, track_id: int) -> None:
        self._cache.pop(track_id, None)
