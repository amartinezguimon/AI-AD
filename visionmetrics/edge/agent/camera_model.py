"""Pinhole camera model — convert normalised face width to a real distance.

Previously duplicated between main.py and calibrate.py. The focal length is
derived once from the camera's horizontal field of view and frame width; the
distance estimate follows the standard pinhole relation:

    focal_px = (frame_width / 2) / tan(fov_h / 2)
    dist_m   = real_face_width_m * focal_px / face_width_px

``fov_h`` and ``face_width_m`` are per-camera/per-deployment values and must
come from device config — NOT hardcoded. A wrong FOV silently corrupts every
distance, which then corrupts the zone filter, so this is the #1 thing to get
right when onboarding a new camera.
"""

from __future__ import annotations

import math

# Clamp distance estimates to a sane physical range (metres).
DIST_MIN_M = 0.1
DIST_MAX_M = 8.0
_EPS = 1e-6


def focal_length_px(frame_width_px: int, fov_h_deg: float) -> float:
    """Focal length in pixels from horizontal FOV and frame width."""
    return (frame_width_px / 2.0) / math.tan(math.radians(fov_h_deg / 2.0))


def distance_metres(
    face_width_norm: float,
    source_region_width_px: int,
    focal_px: float,
    *,
    face_width_m: float,
) -> float:
    """Estimate real distance to the face, in metres.

    face_width_norm        : cheekbone width normalised to the region MediaPipe saw.
    source_region_width_px : width (original, non-upscaled pixels) of that region
                             — the head-crop bbox width, or the full frame width.
    focal_px               : from :func:`focal_length_px`.
    face_width_m           : assumed real face width (per-deployment config).
    """
    face_width_px = face_width_norm * source_region_width_px
    dist = (face_width_m * focal_px) / (face_width_px + _EPS)
    return float(min(max(dist, DIST_MIN_M), DIST_MAX_M))
