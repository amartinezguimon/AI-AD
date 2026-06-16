"""Soft engagement-zone confidence.

Returns a multiplier in [0, 1] instead of a hard YES/NO gate, so a person
standing right at the calibrated boundary doesn't flicker between engaged and
away. Distance is still a hard cutoff (someone 6 m away is never a customer).

Extracted verbatim (behavior-preserving) from main.py `zone_confidence`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GazeReference:
    """Head-pose direction recorded when looking at the WINDOW CENTRE at calibration.

    The classifier was trained with subjects facing the camera (yaw≈0, pitch≈0 =
    looking). In a real store the camera sits off to one side / in a corner, so
    looking at the window is NOT looking at the camera — the head is turned by a
    fixed offset. Subtracting that offset (``recenter``) before the classifier maps
    "looking at the window" back onto the model's "straight ahead", so the same
    trained model works from any camera position.

    Defaults to (0, 0) = no shift (camera roughly on the display, or uncalibrated),
    which preserves the prior behaviour exactly.
    """
    yaw_center: float = 0.0
    pitch_center: float = 0.0

    @classmethod
    def from_config(cls, engagement_zone: dict | None) -> "GazeReference":
        """Build from the ``engagement_zone`` block of a calibration config."""
        if not engagement_zone:
            return cls()
        return cls(
            yaw_center=engagement_zone.get("yaw_center", 0.0),
            pitch_center=engagement_zone.get("pitch_center", 0.0),
        )

    def recenter(self, yaw: float, pitch: float) -> tuple[float, float]:
        """Shift live angles so the window direction becomes (0, 0) for the model."""
        return yaw - self.yaw_center, pitch - self.pitch_center


@dataclass(frozen=True)
class CountingRegion:
    """A calibrated polygon (normalised [0..1] image coords) that bounds where we
    count people at all. A person is counted — as a passerby AND for engagement —
    only if their reference point (feet: bbox bottom-centre) falls inside it.

    This is the operator-drawn "counting zone": it discards people too far to
    notice the window (e.g. across the street) and anyone outside the storefront
    area, fixing the "far people counted" problem at the source. Image-space, so
    it must be re-drawn if the camera is moved. ``None``/empty => count everywhere
    (prior behaviour preserved).
    """
    polygon: tuple[tuple[float, float], ...] = ()

    @classmethod
    def from_config(cls, region: dict | None) -> "CountingRegion | None":
        """Build from the ``counting_region`` block of a calibration config."""
        if not region:
            return None
        poly = region.get("polygon") or []
        if len(poly) < 3:                       # a polygon needs >= 3 vertices
            return None
        return cls(polygon=tuple((float(x), float(y)) for x, y in poly))

    def contains(self, x: float, y: float) -> bool:
        """Point-in-polygon (ray casting). x, y are normalised [0..1] image coords."""
        poly = self.polygon
        n = len(poly)
        if n < 3:
            return True                         # degenerate => don't filter
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            ):
                inside = not inside
            j = i
        return inside


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
