"""Tests for track reconciliation (IoU + lost-track adoption + expiry)."""

from __future__ import annotations

from visionmetrics.edge.agent.tracking import ReconcileParams, TrackReconciler, iou


# ── iou ──────────────────────────────────────────────────────────
def test_iou_identical_is_one():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_disjoint_is_zero():
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_iou_partial_overlap():
    # two 10x10 boxes overlapping in a 5x5 corner: inter=25, union=175
    assert abs(iou((0, 0, 10, 10), (5, 5, 15, 15)) - 25 / 175) < 1e-9


# ── reconcile ────────────────────────────────────────────────────
def _rec(**kw):
    return TrackReconciler(ReconcileParams(**kw))


def test_known_id_keeps_its_id():
    r = _rec()
    box = (0, 0, 10, 20)
    assert r.reconcile([(1, box)], 0) == [1]
    assert r.reconcile([(1, box)], 1) == [1]


def test_new_id_at_same_place_is_adopted_after_loss():
    r = _rec(grace_frames=45, min_iou=0.3)
    box = (100, 100, 150, 220)
    r.reconcile([(1, box)], 0)            # person id=1
    # id=1 vanishes for a few frames (occlusion / conf dip)
    for f in range(1, 6):
        r.reconcile([], f)
    # reappears at (almost) the same spot under a NEW id=2 -> adopted as 1
    out = r.reconcile([(2, (101, 102, 151, 221))], 6)
    assert out == [1]
    # and it sticks: id=2 keeps mapping to 1
    assert r.reconcile([(2, (101, 102, 151, 221))], 7) == [1]


def test_new_id_far_away_is_a_new_person():
    r = _rec(min_iou=0.3)
    r.reconcile([(1, (0, 0, 50, 100))], 0)
    r.reconcile([], 1)
    out = r.reconcile([(2, (500, 300, 550, 400))], 2)   # nowhere near
    assert out == [2]


def test_no_adoption_after_grace_expires():
    r = _rec(grace_frames=3, min_iou=0.3)
    box = (0, 0, 50, 100)
    r.reconcile([(1, box)], 0)
    for f in range(1, 10):
        r.reconcile([], f)
    out = r.reconcile([(2, box)], 10)     # same place but far too late
    assert out == [2]


def test_two_live_detections_never_collapse():
    # If id=1 is still present this frame, a new id overlapping it must NOT steal it.
    r = _rec(min_iou=0.1)
    a, b = (0, 0, 50, 100), (10, 0, 60, 100)   # overlapping boxes
    r.reconcile([(1, a)], 0)
    out = r.reconcile([(1, a), (2, b)], 1)
    assert out[0] == 1
    assert out[1] == 2                          # stays distinct, not merged into 1


def test_ambiguous_adoption_is_declined():
    # Two people standing together (overlapping boxes), both briefly lost. A new
    # id appears overlapping BOTH -> ambiguous -> must NOT be merged into either.
    r = _rec(grace_frames=45, min_iou=0.2, ambiguity_margin=0.15)
    a = (0, 0, 100, 200)
    b = (40, 0, 140, 200)        # heavily overlaps a
    r.reconcile([(1, a), (2, b)], 0)
    r.reconcile([], 1)           # both lost
    # new id over the overlap region, similar IoU to both -> decline adoption
    out = r.reconcile([(3, (20, 0, 120, 200))], 2)
    assert out == [3]            # treated as a new person, not fused into 1 or 2


def test_unambiguous_adoption_still_works_with_a_distant_other():
    # One clear candidate (overlapping) + one far track -> adopt the clear one.
    r = _rec(grace_frames=45, min_iou=0.3, ambiguity_margin=0.15)
    near = (0, 0, 100, 200)
    far = (500, 0, 600, 200)
    r.reconcile([(1, near), (2, far)], 0)
    r.reconcile([], 1)
    out = r.reconcile([(9, (5, 0, 105, 200))], 2)   # clearly matches `near`
    assert out == [1]


def test_expire_drops_stale_tracks():
    r = _rec(grace_frames=3)
    r.reconcile([(1, (0, 0, 10, 10))], 0)
    assert r.expire(2) == []                    # still within grace
    assert r.expire(10) == [1]                  # now stale -> dropped
    # after expiry a far-future reappearance is a brand-new person
    assert r.reconcile([(1, (0, 0, 10, 10))], 11) == [1]  # id reused, but treated fresh
