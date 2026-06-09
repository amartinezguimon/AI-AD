"""Wire a DeviceConfig into a ready-to-run EngagementPipeline.

Keeps construction (which needs model files on disk) out of the pipeline itself,
so the pipeline stays unit-testable with fakes while this module handles the
real YOLO / MediaPipe / PyTorch wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

from .classifier import EngagementClassifier
from .config import DeviceConfig
from .models_bootstrap import ensure_models
from .pipeline import EngagementPipeline
from .vision.detector import PersonDetector
from .vision.face import HeadPoseAnalyzer
from .vision.pose import TorsoAnalyzer
from .zone import EngagementZone


def load_zone(config: DeviceConfig) -> EngagementZone | None:
    """Load the per-store calibration zone, or None if absent."""
    path = config.calibration_config_path
    if not path or not Path(path).exists():
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return EngagementZone.from_config(raw.get("derived"))


def build_pipeline(config: DeviceConfig) -> EngagementPipeline:
    ensure_models(config)   # self-bootstrap: fetch missing MediaPipe task files
    v = config.vision
    detector = PersonDetector(
        config.models.yolo, conf_min=v.yolo_conf_min, aspect_ratio_min=v.aspect_ratio_min,
    )
    head_pose = HeadPoseAnalyzer(
        config.models.face, face_width_m=v.face_width_m, head_crop_frac=v.head_crop_frac,
        head_upscale=v.head_upscale, skip_frames=v.face_skip_frames,
    )
    torso = TorsoAnalyzer(
        config.models.pose, neutral_span=v.torso_neutral_span,
        min_visibility=v.torso_min_visibility, skip_frames=v.pose_skip_frames,
    )
    classifier = EngagementClassifier.load(config.models.engagement)
    return EngagementPipeline(
        detector=detector, head_pose=head_pose, torso=torso, classifier=classifier,
        zone=load_zone(config),
        engagement_params=config.engagement,
        fov_h_deg=config.camera.fov_h_deg,
        ghost_frame_trial=v.ghost_frame_trial,
        zone_soft_margin=config.engagement.zone_soft_margin,
    )
