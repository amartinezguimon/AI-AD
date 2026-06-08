"""Soft engagement-zone confidence.

Returns a multiplier in [0, 1] instead of a hard YES/NO gate, so a person
standing right at the calibrated boundary doesn't flicker between engaged and
away. Distance is still a hard cutoff (someone 6 m away is never a customer).

Extracted verbatim (behavior-preserving) from main.py `zone_confidence`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngagementZone:
    """Calibrated boundaries for one display, produced by calibration."""
    yaw_min: float
    yaw_max: float
    pitch_min: float
    pitch_max: float
    dist_min: float = 0.0           # normalised face-width proxy (legacy fallback)
    dist_max_m: float | None = None  # real-world far limit in metres (preferred)

    @classmethod
    def from_config(cls, derived: dict | None) -> "EngagementZone | None":
        """Build from the ``derived`` block of a calibration config, or None."""
        if not derived:
            return None
        return cls(
            yaw_min=derived["yaw_min"],
            yaw_max=derived["yaw_max"],
            pitch_min=derived["pitch_min"],
            pitch_max=derived["pitch_max"],
            dist_min=derived.get("dist_min", 0.0),
            dist_max_m=derived.get("dist_max_m"),
        )


def zone_confidence(
    yaw: float,
    pitch: float,
    distance: float,
    zone: EngagementZone | None,
    dist_m: float | None = None,
    *,
    soft_margin: float = 0.30,
    dist_buffer: float = 1.2,
) -> float:
    """Smooth [0, 1] confidence that the gaze falls inside the engagement zone.

    1.0 well inside; decays linearly to 0 across ``soft_margin`` normalised
    units beyond the yaw/pitch boundary. Distance is a hard cutoff with a
    ``dist_buffer`` margin beyond the calibrated far limit.

    With no calibration (``zone is None``) everything passes (returns 1.0), so
    the classifier alone decides — matching the prototype's behavior.
    """
    if zone is None:
        return 1.0

    # Hard distance cutoff.
    if dist_m is not None and zone.dist_max_m is not None:
        if dist_m > zone.dist_max_m * dist_buffer:
            return 0.0
    elif distance < zone.dist_min * 0.8:
        return 0.0

    # Soft angle penalty: how far outside each boundary are we?
    yaw_excess = max(0.0, zone.yaw_min - yaw, yaw - zone.yaw_max)
    pitch_excess = max(0.0, zone.pitch_min - pitch, pitch - zone.pitch_max)

    return max(0.0, 1.0 - (yaw_excess + pitch_excess) / soft_margin)
