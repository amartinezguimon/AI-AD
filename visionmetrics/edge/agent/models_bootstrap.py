"""Ensure model assets exist on disk, downloading the missing ones.

A fresh clone / new edge box does not ship the MediaPipe task files (they are
large and git-ignored). The legacy main.py auto-downloaded them on first run;
the agent must do the same so it is self-bootstrapping. YOLO weights are fetched
automatically by Ultralytics, and the trained engagement_model.pth is committed,
so only the two MediaPipe `.task` files are handled here.
"""

from __future__ import annotations

import os
import urllib.request

_MEDIAPIPE_URLS = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker"
        "/face_landmarker/float16/latest/face_landmarker.task"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker"
        "/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
}


def _ensure_one(path: str) -> None:
    if os.path.exists(path):
        return
    name = os.path.basename(path)
    url = _MEDIAPIPE_URLS.get(name)
    if url is None:
        return  # not a known auto-downloadable asset; let the caller fail clearly
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    print(f"[bootstrap] downloading {name} (one-time)...")
    urllib.request.urlretrieve(url, path)
    print(f"[bootstrap] saved {path}")


def ensure_models(config) -> None:
    """Download the MediaPipe face/pose task files if they are missing."""
    _ensure_one(config.models.face)
    _ensure_one(config.models.pose)
