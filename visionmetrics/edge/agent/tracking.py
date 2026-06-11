"""Track reconciliation — bridges YOLO/ByteTrack ID switches so one person is
not counted (or scored) twice.

ByteTrack gives each tracked person a numeric id. When a detection is lost for
too long — an occlusion, a confidence dip, the person stepping out and back —
the tracker can resurrect the same person under a BRAND-NEW id. Because the
pipeline counts passersby and accumulates engagement per id, that re-counts the
same person and resets their attention. This is the bug field-testing surfaced:
"a still person, if dropped for an instant, is counted again on re-detection."

This is the second line of defence; the first is a longer ByteTrack
`track_buffer` (see detector.py) that prevents most losses in the first place.
Here we keep a short memory of recently-lost tracks and, when a new id appears
in (almost) the same place, ADOPT it into the lost track rather than treating it
as a new person. Pure geometry (IoU on boxes) — no vision, no models — so it is
fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

Bbox = tuple[int, int, int, int]


def iou(a: Bbox, b: Bbox) -> float:
    """Intersection-over-union of two (x1, y1, x2, y2) boxes, in [0, 1]."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class ReconcileParams:
    grace_frames: int = 45        # how long a lost track stays adoptable (~1.5s @30fps)
    min_iou: float = 0.30         # spatial overlap required to adopt a new id
    ambiguity_margin: float = 0.15  # top candidate must beat the runner-up by this much


class TrackReconciler:
    """Maps raw ByteTrack ids to stable canonical ids, healing id switches."""

    def __init__(self, params: ReconcileParams | None = None):
        self.params = params or ReconcileParams()
        self._bbox: dict[int, Bbox] = {}        # canonical id -> last bbox seen
        self._last_frame: dict[int, int] = {}   # canonical id -> last frame seen
        self._alias: dict[int, int] = {}        # raw id -> canonical id

    def reconcile(self, detections: list[tuple[int, Bbox]],
                  frame_idx: int) -> list[int]:
        """Resolve a frame's detections to canonical ids (aligned to input).

        Two passes so ordering can't cause a mistake: first mark every already-
        known id present, only THEN try to adopt genuinely-new ids into tracks
        that are still missing this frame.
        """
        canon: list[int | None] = [None] * len(detections)
        present: set[int] = set()
        new: list[int] = []

        for i, (raw, bbox) in enumerate(detections):
            cid = self._alias.get(raw)
            if cid is None and raw in self._bbox:
                cid = raw
            if cid is None:
                new.append(i)
                continue
            canon[i] = cid
            self._bbox[cid] = bbox
            self._last_frame[cid] = frame_idx
            present.add(cid)

        for i in new:
            raw, bbox = detections[i]
            cid = self._adopt(raw, bbox, frame_idx, present)
            canon[i] = cid
            self._bbox[cid] = bbox
            self._last_frame[cid] = frame_idx
            present.add(cid)

        return [c for c in canon]  # type: ignore[return-value]

    def _adopt(self, raw: int, bbox: Bbox, frame_idx: int, present: set[int]) -> int:
        """Adopt `raw` into a recently-lost track, or keep it as a new person.

        Only adopts when there is ONE clear candidate. If two lost tracks both
        overlap the new box (e.g. a couple who were standing together, one of
        whom was briefly lost), adoption is ambiguous and we decline — counting a
        returning person twice is a smaller error than fusing two distinct people
        into one.
        """
        scored = []
        for cid, last in self._last_frame.items():
            if cid in present:                       # its own live detection exists
                continue
            if frame_idx - last > self.params.grace_frames:
                continue                             # lost too long ago
            score = iou(bbox, self._bbox[cid])
            if score >= self.params.min_iou:
                scored.append((score, cid))
        if not scored:
            return raw                               # genuinely new person
        scored.sort(reverse=True)
        # Ambiguity guard: the top match must clearly beat the runner-up.
        if len(scored) >= 2 and scored[0][0] - scored[1][0] < self.params.ambiguity_margin:
            return raw                               # too close to call -> treat as new
        self._alias[raw] = scored[0][1]
        return scored[0][1]

    def expire(self, frame_idx: int) -> list[int]:
        """Forget tracks unseen beyond the grace window. Returns dropped ids."""
        dead = [cid for cid, last in self._last_frame.items()
                if frame_idx - last > self.params.grace_frames]
        for cid in dead:
            self._bbox.pop(cid, None)
            self._last_frame.pop(cid, None)
        if dead:
            dead_set = set(dead)
            for raw, cid in list(self._alias.items()):
                if cid in dead_set:
                    self._alias.pop(raw, None)
        return dead
