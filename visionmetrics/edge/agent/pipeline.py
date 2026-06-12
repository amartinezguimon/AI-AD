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
from .tracking import ReconcileParams, TrackReconciler
from .zone import EngagementZone, GazeReference, zone_confidence

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
        passerby_min_frames: int = 8,
        passerby_motion_px: int = 40,
        zone_soft_margin: float = 0.30,
        reconcile_params: ReconcileParams | None = None,
        gaze_reference: GazeReference | None = None,
    ):
        self.detector = detector
        self.head_pose = head_pose
        self.torso = torso
        self.classifier = classifier
        self.zone = zone
        # Per-store re-centring of head angles onto the window direction. Defaults
        # to no shift (uncalibrated / camera on the display).
        self.gaze = gaze_reference or GazeReference()
        self.fov_h_deg = fov_h_deg
        self.passerby_min_frames = max(1, passerby_min_frames)
        self.passerby_motion_px = passerby_motion_px
        self.zone_soft_margin = zone_soft_margin
        self.tracker = EngagementTracker(engagement_params)
        # Heals ByteTrack id switches: a re-detected person keeps one stable id,
        # so they are not re-counted or their engagement reset.
        self.reconciler = TrackReconciler(reconcile_params)
        self._focal_px: float | None = None
        self._seen: dict[int, int] = {}            # canonical id -> frames seen
        self._first_center: dict[int, tuple[float, float]] = {}  # bbox centre when first seen
        self._moved: set[int] = set()              # canonical ids that have moved enough
        self._face_seen: set[int] = set()          # canonical ids that have shown a face
        self._passerby: set[int] = set()           # canonical ids confirmed as real people

    def process_frame(self, frame, frame_idx: int, now: float) -> FrameResult:
        if self._focal_px is None:
            self._focal_px = focal_length_px(frame.shape[1], self.fov_h_deg)

        result = FrameResult()
        dets = self.detector.detect(frame)
        # Resolve raw ByteTrack ids to stable canonical ids before anything else,
        # so a re-detected person is recognised as the same individual.
        canon = self.reconciler.reconcile([(d.track_id, d.bbox) for d in dets], frame_idx)
        for det, tid in zip(dets, canon):
            seen = self._seen[tid] = self._seen.get(tid, 0) + 1

            # Track movement since first seen (cheap, every frame): a real person
            # walks; furniture doesn't.
            x1, y1, x2, y2 = det.bbox
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            fx, fy = self._first_center.setdefault(tid, (cx, cy))
            if (cx - fx) ** 2 + (cy - fy) ** 2 >= self.passerby_motion_px ** 2:
                self._moved.add(tid)

            # Anti-flicker debounce: ignore boxes that haven't persisted yet.
            if seen < self.passerby_min_frames:
                continue

            pose = self.head_pose.analyze(frame, det.bbox, tid, frame_idx, self._focal_px)
            if pose is not None:
                self._face_seen.add(tid)

            # Count as a passerby (foot traffic) the FIRST time the track is a
            # confirmed real person: persisted + (moved OR shown a face). A static,
            # faceless box (a chair, a mannequin) is never counted.
            if tid not in self._passerby:
                if tid in self._moved or tid in self._face_seen:
                    self._passerby.add(tid)
                    self.tracker.register(tid, now)
                else:
                    continue   # persisted but static & faceless -> likely not a person

            result.active_ids.add(tid)
            torso = self.torso.analyze(frame, det.bbox, tid, frame_idx)
            result.persons.append(self._score(tid, det.bbox, pose, torso, now))

        # Forget tracks gone past the grace window: free their per-track state
        # everywhere. drop() banks a real person's attention into the session
        # total first, so counts/attention are preserved while memory is freed.
        for cid in self.reconciler.expire(frame_idx):
            self.tracker.drop(cid)
            self.head_pose.forget(cid)
            self.torso.forget(cid)
            self._seen.pop(cid, None)
            self._first_center.pop(cid, None)
            self._moved.discard(cid)
            self._face_seen.discard(cid)
            self._passerby.discard(cid)

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
            # Re-centre the head angles onto the calibrated window direction before
            # the classifier, which learned "straight ahead = looking". The zone
            # check below stays on RAW angles (its bounds are in camera space).
            yaw_c, pitch_c = self.gaze.recenter(pose.yaw, pose.pitch)
            prob = self.classifier.probability(yaw_c, pitch_c, pose.distance)
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

        person.engage_prob = engage_prob
        person.zone_conf = zone_conf
        person.is_engaged = update.is_engaged
        person.total_engage_s = update.total_engage_s
        person.newly_counted = update.newly_counted
        person.tier = _tier(engage_prob)
        return person
