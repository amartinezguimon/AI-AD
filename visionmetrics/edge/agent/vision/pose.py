"""Torso orientation (MediaPipe Pose) — Layer 5, walk-by damping.

Estimates how squarely the torso faces the camera (a person walking past with
their body sideways is unlikely to be a genuine customer) plus the head-vs-torso
relative yaw. Runs on a per-track frame-skip schedule because pose is costly.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .. import geometry

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
POSE_NOSE = 0


@dataclass
class TorsoResult:
    confidence: float          # 1.0 facing camera, 0.0 edge-on
    span: float | None         # raw shoulder span (debug)
    rel_yaw: float | None      # head-vs-torso yaw, or None if unreliable


# When pose can't be trusted/run, assume facing the camera (no damping).
NEUTRAL = TorsoResult(confidence=1.0, span=None, rel_yaw=None)


class TorsoAnalyzer:
    def __init__(self, model_path: str, *, neutral_span: float, min_visibility: float,
                 skip_frames: int):
        base = python.BaseOptions(model_asset_path=model_path)
        opts = vision.PoseLandmarkerOptions(
            base_options=base, num_poses=1,
            min_pose_detection_confidence=0.4, min_pose_presence_confidence=0.4,
        )
        self._detector = vision.PoseLandmarker.create_from_options(opts)
        self.neutral_span = neutral_span
        self.min_visibility = min_visibility
        self.skip_frames = skip_frames
        self._cache: dict[int, tuple[int, TorsoResult]] = {}

    def analyze(self, frame, bbox, track_id: int, frame_idx: int) -> TorsoResult:
        idx, cached = self._cache.get(track_id, (-(10**9), NEUTRAL))
        if frame_idx - idx < self.skip_frames:
            return cached
        result = self._detect(frame, bbox)
        self._cache[track_id] = (frame_idx, result)
        return result

    def _detect(self, frame, bbox) -> TorsoResult:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if crop.size == 0:
            return NEUTRAL
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        res = self._detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not res.pose_landmarks:
            return NEUTRAL
        lm = res.pose_landmarks[0]
        l_s, r_s = lm[LEFT_SHOULDER], lm[RIGHT_SHOULDER]
        if l_s.visibility < self.min_visibility or r_s.visibility < self.min_visibility:
            return NEUTRAL
        conf = geometry.torso_confidence(l_s.x, r_s.x, neutral_span=self.neutral_span)
        rel_yaw = geometry.relative_neck_yaw(lm[POSE_NOSE].x, l_s.x, r_s.x)
        return TorsoResult(confidence=conf, span=l_s.x - r_s.x, rel_yaw=rel_yaw)

    def forget(self, track_id: int) -> None:
        self._cache.pop(track_id, None)
