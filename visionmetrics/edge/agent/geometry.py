"""Head-pose geometry — the single source of truth for face angles.

This logic was previously DUPLICATED in src/inference/main.py
(`extract_face_angles`) and src/utils/calibrate.py (`get_angles`). Having two
copies caused a real production bug once (calibrate used eye corners while main
used cheekbones, producing a systematic zone mismatch). It now lives here, once.

The functions are pure and framework-agnostic: they take any sequence of
landmarks where each landmark exposes ``.x`` and ``.y`` floats normalised to
the image that was fed to the face detector. That makes them unit-testable
without OpenCV, MediaPipe, or a camera.
"""

from __future__ import annotations

from typing import Protocol, Sequence

# MediaPipe Face Landmarker indices we rely on.
# Cheekbones (234/454) are used as the horizontal scale reference instead of eye
# corners so that glasses / sunglasses never interfere with the yaw estimate.
NOSE = 1
TOP = 10          # top of forehead
CHIN = 152
LEFT_CHEEK = 234
RIGHT_CHEEK = 454

_EPS = 1e-6


class Landmark(Protocol):
    """Anything with normalised x/y coordinates (e.g. a MediaPipe landmark)."""
    x: float
    y: float


def extract_face_angles(landmarks: Sequence[Landmark]) -> tuple[float, float, float]:
    """Return ``(yaw, pitch, face_width)`` from face landmarks.

    yaw    : horizontal head turn. 0 = facing the camera; sign follows nose
             displacement relative to the cheekbone midpoint, scaled by face width.
    pitch  : vertical head tilt, scaled by face height (chin..forehead).
    face_width : normalised cheekbone-to-cheekbone width — used as a distance
                 proxy and fed to the engagement classifier.

    All three are scale-invariant (ratios), so the same head orientation yields
    the same yaw/pitch at 0.5 m or 4 m — only ``face_width`` shrinks with range.
    """
    nose = landmarks[NOSE]
    top = landmarks[TOP]
    chin = landmarks[CHIN]
    l_cheek = landmarks[LEFT_CHEEK]
    r_cheek = landmarks[RIGHT_CHEEK]

    face_mid_x = (l_cheek.x + r_cheek.x) / 2.0
    face_width = abs(r_cheek.x - l_cheek.x)
    yaw = (nose.x - face_mid_x) / (face_width + _EPS)

    face_mid_y = (l_cheek.y + r_cheek.y) / 2.0
    face_height = abs(chin.y - top.y)
    pitch = (nose.y - face_mid_y) / (face_height + _EPS)

    return yaw, pitch, face_width


def relative_neck_yaw(
    nose_x: float, left_shoulder_x: float, right_shoulder_x: float,
    *, min_span: float = 0.02,
) -> float | None:
    """Head-vs-torso yaw: how far the head is turned relative to the body axis.

    Near 0 = head aligned with torso; positive = head turned right of the body.
    Returns ``None`` when the shoulders are nearly edge-on (span too small to
    trust). Camera-position independent — useful as a calibration signal.
    """
    span = left_shoulder_x - right_shoulder_x
    if abs(span) <= min_span:
        return None
    shoulder_mid_x = (left_shoulder_x + right_shoulder_x) / 2.0
    return (nose_x - shoulder_mid_x) / (abs(span) + _EPS)


def torso_confidence(
    left_shoulder_x: float, right_shoulder_x: float, *, neutral_span: float,
) -> float:
    """How squarely the torso faces the camera, in [0, 1].

    1.0 = shoulders fully facing the camera (wide span); 0.0 = edge-on.
    ``neutral_span`` is the expected shoulder span when facing the camera.
    """
    span = left_shoulder_x - right_shoulder_x
    return max(0.0, min(span, neutral_span)) / neutral_span
