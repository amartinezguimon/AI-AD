"""Tests for EngagementPipeline orchestration using fake vision components.

No models, no camera, no GPU — we inject fakes and assert the pipeline wires
the 7 layers together correctly (scoring, counting, ghost blacklisting, QR).
"""

import numpy as np

from visionmetrics.edge.agent.engagement import EngagementParams
from visionmetrics.edge.agent.pipeline import EngagementPipeline
from visionmetrics.edge.agent.vision.detector import Detection
from visionmetrics.edge.agent.vision.face import HeadPose
from visionmetrics.edge.agent.vision.pose import TorsoResult, NEUTRAL


class FakeDetector:
    def __init__(self, detections):
        self._dets = detections

    def detect(self, frame):
        return list(self._dets)


class FakeHeadPose:
    """Returns a fixed pose, or None to simulate 'no face found'."""
    def __init__(self, pose):
        self._pose = pose
        self.forgotten = []

    def analyze(self, frame, bbox, tid, frame_idx, focal_px):
        return self._pose

    def forget(self, tid):
        self.forgotten.append(tid)


class FakeTorso:
    def __init__(self, result=NEUTRAL):
        self._result = result

    def analyze(self, frame, bbox, tid, frame_idx):
        return self._result

    def forget(self, tid):
        pass


class FakeClassifier:
    def __init__(self, prob):
        self._prob = prob

    def probability(self, yaw, pitch, distance):
        return self._prob


FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
STRAIGHT = HeadPose(yaw=0.0, pitch=0.0, distance=0.19, dist_m=1.0, nose_px=(10, 10))


def make_pipeline(detector, head_pose, classifier_prob, **params):
    return EngagementPipeline(
        detector=detector,
        head_pose=head_pose,
        torso=FakeTorso(),
        classifier=FakeClassifier(classifier_prob),
        zone=None,
        engagement_params=EngagementParams(frame_buffer_size=1, frame_engage_min=1, **params),
        fov_h_deg=70.0,
        ghost_frame_trial=3,
    )


def test_engaged_person_is_scored_and_counted():
    det = Detection(track_id=5, bbox=(100, 50, 200, 400), confidence=0.9)
    pipe = make_pipeline(FakeDetector([det]), FakeHeadPose(STRAIGHT), 1.0,
                         count_threshold_s=2.0)
    pipe.process_frame(FRAME, frame_idx=0, now=0.0)
    pipe.process_frame(FRAME, frame_idx=1, now=1.0)
    r = pipe.process_frame(FRAME, frame_idx=2, now=2.0)

    assert len(r.persons) == 1
    p = r.persons[0]
    assert p.track_id == 5
    assert p.is_engaged
    assert p.tier == "HIGH"            # prob 1.0 * torso 1.0 * zone 1.0
    assert p.total_engage_s == 2.0
    assert pipe.tracker.total_engaged == 1


def test_away_person_not_counted():
    det = Detection(track_id=7, bbox=(0, 0, 50, 200), confidence=0.9)
    pipe = make_pipeline(FakeDetector([det]), FakeHeadPose(STRAIGHT), 0.10,
                         count_threshold_s=2.0)
    for i in range(5):
        r = pipe.process_frame(FRAME, frame_idx=i, now=float(i))
    assert not r.persons[0].is_engaged
    assert pipe.tracker.total_engaged == 0


def test_ghost_track_blacklisted_after_trial():
    det = Detection(track_id=9, bbox=(0, 0, 50, 200), confidence=0.9)
    # head pose never found -> after ghost_frame_trial (3) frames it's blacklisted
    pipe = make_pipeline(FakeDetector([det]), FakeHeadPose(None), 1.0)

    pipe.process_frame(FRAME, 0, 0.0)
    assert pipe.tracker.total_passersby == 1
    pipe.process_frame(FRAME, 1, 1.0)
    pipe.process_frame(FRAME, 2, 2.0)   # 3rd frame: seen==3 == trial, no face -> ghost

    assert 9 in pipe._ghost_ids
    assert pipe.tracker.total_passersby == 0       # passerby increment reversed
    assert 9 in pipe.head_pose.forgotten


def test_qr_fires_once_after_reward_threshold():
    det = Detection(track_id=3, bbox=(100, 50, 200, 400), confidence=0.9)
    pipe = make_pipeline(FakeDetector([det]), FakeHeadPose(STRAIGHT), 1.0,
                         count_threshold_s=2.0, reward_threshold_s=5.0, qr_duration_s=10.0)
    fired = []
    for i in range(7):
        r = pipe.process_frame(FRAME, frame_idx=i, now=float(i))
        fired.append(r.qr_triggered)
    assert fired[5] is True               # crosses 5.0s at now=5
    assert sum(1 for f in fired if f) == 1  # exactly once (cooldown)
