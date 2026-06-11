"""Tests for the engagement state machine (pure, fake clock)."""

import math

from visionmetrics.edge.agent.engagement import EngagementParams, EngagementTracker


def fresh(**overrides):
    params = EngagementParams(**overrides)
    return EngagementTracker(params)


def test_register_counts_passerby_once():
    t = fresh()
    t.update(1, raw_engaged=False, now=0.0)
    t.update(1, raw_engaged=False, now=0.1)
    assert t.total_passersby == 1
    t.update(2, raw_engaged=False, now=0.2)
    assert t.total_passersby == 2


def test_attention_accumulates_over_time():
    t = fresh(frame_engage_min=1, count_threshold_s=999)
    t.update(1, raw_engaged=True, now=0.0)
    r = t.update(1, raw_engaged=True, now=2.5)
    assert math.isclose(r.total_engage_s, 2.5, rel_tol=1e-9)


def test_counted_once_at_threshold():
    t = fresh(frame_engage_min=1, count_threshold_s=2.0)
    t.update(1, raw_engaged=True, now=0.0)
    r1 = t.update(1, raw_engaged=True, now=1.0)
    assert not r1.newly_counted and t.total_engaged == 0
    r2 = t.update(1, raw_engaged=True, now=2.0)
    assert r2.newly_counted and t.total_engaged == 1
    # Crossing again must not double count.
    r3 = t.update(1, raw_engaged=True, now=3.0)
    assert not r3.newly_counted and t.total_engaged == 1


def test_attention_banks_across_multiple_windows():
    # buffer_size=1 disables temporal smoothing so we isolate the windowing math.
    t = fresh(frame_buffer_size=1, frame_engage_min=1, count_threshold_s=999)
    t.update(1, raw_engaged=True, now=0.0)             # open window 1 at t=0
    t.update(1, raw_engaged=True, now=3.0)             # still open: total 3s
    r_away = t.update(1, raw_engaged=False, now=4.0)   # close & bank 4s
    assert math.isclose(r_away.total_engage_s, 4.0, rel_tol=1e-9)
    t.update(1, raw_engaged=True, now=5.0)             # open window 2 at t=5
    r = t.update(1, raw_engaged=True, now=6.0)         # +1s on top of banked 4s
    assert math.isclose(r.total_engage_s, 5.0, rel_tol=1e-9)


def test_buffer_keeps_window_open_through_single_away_frame():
    # The anti-flicker guarantee: one stray 'away' frame does NOT end the window
    # while engaged frames remain in the 3-frame buffer.
    t = fresh(frame_buffer_size=3, frame_engage_min=1, count_threshold_s=999)
    t.update(1, raw_engaged=True, now=0.0)   # [1]
    t.update(1, raw_engaged=True, now=1.0)   # [1,1]
    r = t.update(1, raw_engaged=False, now=2.0)  # [1,1,0] -> still 2 of 3 -> engaged
    assert r.is_engaged
    assert math.isclose(r.total_engage_s, 2.0, rel_tol=1e-9)  # window never closed


def test_frame_buffer_voting_requires_quorum():
    t = fresh(frame_buffer_size=3, frame_engage_min=2)
    assert not t.update(1, True, now=0.0).is_engaged   # buffer [1]
    assert not t.update(1, False, now=0.1).is_engaged  # [1,0]
    assert t.update(1, True, now=0.2).is_engaged       # [1,0,1] -> 2 of 3
    assert not t.update(1, False, now=0.3).is_engaged  # [0,1,0] -> 1 of 3


def test_forget_reverses_passerby_count():
    t = fresh()
    t.update(1, raw_engaged=False, now=0.0)
    assert t.total_passersby == 1
    t.forget(1)
    assert t.total_passersby == 0
    assert not t.is_tracked(1)


def test_engagement_rate():
    t = fresh(frame_engage_min=1, count_threshold_s=1.0)
    for tid in (1, 2, 3, 4):                 # 4 passersby, none engaged yet
        t.update(tid, raw_engaged=False, now=0.0)
    t.update(1, raw_engaged=True, now=0.0)   # person 1 starts looking
    t.update(1, raw_engaged=True, now=1.0)   # crosses 1.0s threshold => counted
    assert t.total_passersby == 4
    assert t.total_engaged == 1
    assert t.engagement_rate() == 25.0
