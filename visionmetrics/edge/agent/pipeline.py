"""EngagementPipeline — orchestrates the 7 layers, returns data, draws nothing.

This is the heart of the agent, lifted out of main.py's monolithic while-loop.
Crucially it has NO OpenCV window, NO HUD drawing, and NO file I/O: it consumes
a frame and returns a structured result. Drawing (viewer.py), metric emission
(emitter.py), and the run loop (service.py) are separate concerns built on top.

Vision components are injected, so the whole orchestration is unit-testable with
fakes — no models, no camera, no GPU.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .camera_model import focal_length_px
from .engagement import EngagementTracker, EngagementParams
from .zone import EngagementZone, zone_confidence

ENGAGE_THRESHOLD = 0.50


@dataclass
class PersonResult:
    track_id: int
    bbox: tuple[int, int, int, int]
    yaw: float | None = None
    pitch: float | None = None
    dist_m: float | None = None
    engage_prob: float = 0.0
    zone_conf: float = 1.0
    torso_conf: float = 1.0
    rel_yaw: float | None = None
    nose_px: tuple[int, int] | None = None
    is_engaged: bool = False
    total_engage_s: float = 0.0
    tier: str = "LOW"
    newly_counted: bool = False


@dataclass
class FrameResult:
    persons: list[PersonResult] = field(default_factory=list)
    active_ids: set[int] = field(default_factory=set)
    qr_triggered: bool = False


def _tier(prob: float) -> str:
    if prob >= 0.80:
        return "HIGH"
    if prob >= ENGAGE_THRESHOLD:
        return "MED"
    return "LOW"


class EngagementPipeline:
    def __init__(
        self, *, detector, head_pose, torso, classifier,
        zone: EngagementZone | None,
        engagement_params: EngagementParams,
        fov_h_deg: float,
        ghost_frame_trial: int,
        zone_soft_margin: float = 0.30,
    ):
        self.detector = detector
        self.head_pose = head_pose
        self.torso = torso
        self.classifier = classifier
        self.zone = zone
        self.fov_h_deg = fov_h_deg
        self.ghost_frame_trial = ghost_frame_trial
        self.zone_soft_margin = zone_soft_margin
        self.tracker = EngagementTracker(engagement_params)
        self._focal_px: float | None = None
        self._ghost_ids: set[int] = set()
        self._seen: dict[int, int] = {}          # track_id -> frames processed
        self._faces: dict[int, int] = {}          # track_id -> frames a face was found
        self._qr_fired_this_frame = False

    def process_frame(self, frame, frame_idx: int, now: float) -> FrameResult:
        if self._focal_px is None:
            self._focal_px = focal_length_px(frame.shape[1], self.fov_h_deg)

        self._qr_fired_this_frame = False
        result = FrameResult()
        for det in self.detector.detect(frame):
            tid = det.track_id
            if tid in self._ghost_ids:
                continue

            self._seen[tid] = self._seen.get(tid, 0) + 1
            pose = self.head_pose.analyze(frame, det.bbox, tid, frame_idx, self._focal_px)

            if pose is not None:
                self._faces[tid] = self._faces.get(tid, 0) + 1
            elif self._is_ghost(tid):
                self._blacklist(tid)
                continue

            result.active_ids.add(tid)
            torso = self.torso.analyze(frame, det.bbox, tid, frame_idx)
            person = self._score(tid, det.bbox, pose, torso, now)
            result.persons.append(person)

        # QR fires when any tracked person crosses the reward threshold this frame.
        result.qr_triggered = self._qr_fired_this_frame
        return result

    # ── scoring ──────────────────────────────────────────────────
    def _score(self, tid, bbox, pose, torso, now) -> PersonResult:
        person = PersonResult(track_id=tid, bbox=bbox)
        person.torso_conf = torso.confidence
        person.rel_yaw = torso.rel_yaw

        raw_engaged = False
        engage_prob = 0.0
        zone_conf = 1.0
        if pose is not None:
            prob = self.classifier.probability(pose.yaw, pose.pitch, pose.distance)
            torso_weight = 0.40 + 0.60 * torso.confidence
            prob *= torso_weight
            zone_conf = zone_confidence(
                pose.yaw, pose.pitch, pose.distance, self.zone,
                pose.dist_m, soft_margin=self.zone_soft_margin,
            )
            engage_prob = prob * zone_conf
            raw_engaged = engage_prob >= ENGAGE_THRESHOLD
            person.yaw, person.pitch, person.dist_m = pose.yaw, pose.pitch, pose.dist_m
            person.nose_px = pose.nose_px

        update = self.tracker.update(tid, raw_engaged, now, prob=engage_prob)
        if update.qr_triggered:
            self._qr_fired_this_frame = True

        person.engage_prob = engage_prob
        person.zone_conf = zone_conf
        person.is_engaged = update.is_engaged
        person.total_engage_s = update.total_engage_s
        person.newly_counted = update.newly_counted
        person.tier = _tier(engage_prob)
        return person

    # ── ghost handling ───────────────────────────────────────────
    def _is_ghost(self, tid: int) -> bool:
        return self._seen.get(tid, 0) >= self.ghost_frame_trial and self._faces.get(tid, 0) == 0

    def _blacklist(self, tid: int) -> None:
        self._ghost_ids.add(tid)
        self.tracker.forget(tid)
        self.head_pose.forget(tid)
        self.torso.forget(tid)
