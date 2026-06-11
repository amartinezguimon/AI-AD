"""Tests for the metric emitter: windowing + delta correctness."""

from __future__ import annotations

from visionmetrics.edge.agent.emitter import MetricEmitter, SessionCounters

WIN = 3600.0


def _emitter():
    return MetricEmitter("dev-1", "store-1", window_s=WIN)


def test_no_bucket_on_first_sample():
    e = _emitter()
    assert e.sample(SessionCounters(passersby=2), now=10.0) == []


def test_no_bucket_within_same_window():
    e = _emitter()
    e.sample(SessionCounters(passersby=1), now=10.0)
    assert e.sample(SessionCounters(passersby=5), now=20.0) == []


def test_bucket_emitted_on_window_rollover_with_deltas():
    e = _emitter()
    e.sample(SessionCounters(passersby=2, engaged=1, total_attention_s=3.0), now=10.0)
    # Cross into the next hour. Counters grew during window 0.
    out = e.sample(
        SessionCounters(passersby=10, engaged=4, total_attention_s=30.0),
        now=WIN + 5.0,
    )
    assert len(out) == 1
    b = out[0]
    assert b.passersby == 8          # 10 - 2
    assert b.engaged == 3            # 4 - 1
    assert b.total_attention_s == 27.0
    assert b.engagement_rate == round(3 / 8 * 100, 1)


def test_window_start_is_aligned():
    e = _emitter()
    e.sample(SessionCounters(), now=WIN * 5 + 123.0)   # somewhere inside window 5
    out = e.sample(SessionCounters(passersby=1), now=WIN * 6 + 1.0)
    assert out[0].window_start.endswith("05:00:00+00:00")  # aligned to the hour
    assert out[0].idempotency_key == f"dev-1:{out[0].window_start}"


def test_baseline_resets_so_deltas_dont_double_count():
    e = _emitter()
    e.sample(SessionCounters(passersby=0), now=0.0)
    e.sample(SessionCounters(passersby=5), now=WIN + 1)        # window 0 -> bucket pax=5
    out = e.sample(SessionCounters(passersby=8), now=2 * WIN + 1)  # window 1 -> pax=3 not 8
    assert out[0].passersby == 3


def test_attention_delta_clamped_when_total_dips():
    e = _emitter()
    e.sample(SessionCounters(total_attention_s=50.0), now=0.0)
    # A person left; the tracker's summed attention dropped. Delta must not go negative.
    out = e.sample(SessionCounters(total_attention_s=10.0), now=WIN + 1)
    assert out[0].total_attention_s == 0.0


def test_flush_emits_partial_window():
    e = _emitter()
    e.sample(SessionCounters(passersby=1), now=10.0)
    b = e.flush(SessionCounters(passersby=4, engaged=2), now=30.0)
    assert b is not None
    assert b.passersby == 3
    assert b.engaged == 2


def test_flush_returns_none_when_empty():
    e = _emitter()
    e.sample(SessionCounters(passersby=2), now=10.0)
    assert e.flush(SessionCounters(passersby=2), now=20.0) is None


def test_flush_returns_none_before_first_sample():
    e = _emitter()
    assert e.flush(SessionCounters(passersby=5), now=10.0) is None
