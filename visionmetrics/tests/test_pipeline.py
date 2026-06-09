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


class FakeHeadPoseSequence:
    """Returns None for the first `none_for` analyze calls, then a fixed pose.

    Simulates a person who approaches with their back turned (no face) and only
    later turns to look at the display.
    """
    def __init__(self, pose, none_for):
        self._pose = pose
        self._none_for = none_for
        self._calls = 0

    def analyze(self, frame, bbox, tid, frame_idx, focal_px):
        self._calls += 1
        return None if self._calls <= self._none_for else self._pose

    def forget(self, tid):
        pass


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
        ghost_recheck_every=1,
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


def test_unconfirmed_track_never_counted():
    # A detection that never yields a face (e.g. a chair) is never counted.
    det = Detection(track_id=9, bbox=(0, 0, 50, 200), confidence=0.9)
    pipe = make_pipeline(FakeDetector([det]), FakeHeadPose(None), 1.0)
    for i in range(30):
        r = pipe.process_frame(FRAME, frame_idx=i, now=float(i))
    assert pipe.tracker.total_passersby == 0
    assert r.persons == []


def test_track_confirmed_when_face_appears_later():
    # The real-store scenario: person approaches with back turned (no face) for a
    # while, THEN looks at the display. Must still be detected, counted, scored.
    det = Detection(track_id=4, bbox=(100, 50, 200, 400), confidence=0.9)
    pipe = make_pipeline(FakeDetector([det]),
                         FakeHeadPoseSequence(STRAIGHT, none_for=15), 1.0,
                         count_threshold_s=2.0)
    for i in range(40):
        r = pipe.process_frame(FRAME, frame_idx=i, now=float(i))
    assert pipe.tracker.total_passersby == 1   # confirmed once the face appeared
    assert pipe.tracker.total_engaged == 1     # engagement scored after confirmation
    assert r.persons and r.persons[0].is_engaged


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
