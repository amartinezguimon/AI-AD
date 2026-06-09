"""Metric emitter — turns the tracker's running totals into time-windowed buckets.

The pipeline keeps *cumulative* session counters (passersby, engaged, attention,
qr_triggers). The cloud, however, wants **per-window aggregates** (e.g. one row
per hour) so a dashboard can plot a day. This module bridges the two: it watches
the cumulative counters and, every time a time window closes, emits one
``MetricBucket`` carrying the *delta* for that window.

This mirrors the old ``write_hourly_snapshot`` (engaged_delta / pax_delta) from
main.py, but as a pure, testable object with no file I/O.

Time source: the caller passes ``now`` (unix seconds for a live camera, or
video-time for a recorded clip). Windows are aligned to multiples of
``window_s`` so every device buckets on the same boundaries.

Caveat (documented, deferred): ``total_attention_s`` from the tracker is summed
over *currently tracked* people, so it is not strictly monotonic — when a track
is forgotten the sum can dip. Deltas are therefore clamped to >= 0, which can
slightly undercount attention right after a person leaves. Good enough for the
pilot; a monotonic lifetime-attention counter is a later hardening item.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from visionmetrics.shared.schema import SCHEMA_VERSION, MetricBucket

DEFAULT_WINDOW_S = 3600.0  # hourly buckets


@dataclass
class SessionCounters:
    """A snapshot of the tracker's cumulative session totals."""
    passersby: int = 0
    engaged: int = 0
    total_attention_s: float = 0.0
    qr_triggers: int = 0


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class MetricEmitter:
    """Emits one MetricBucket per closed time window, carrying window deltas."""

    def __init__(self, device_id: str, store_id: str,
                 window_s: float = DEFAULT_WINDOW_S):
        self.device_id = device_id
        self.store_id = store_id
        self.window_s = float(window_s)
        self._window_idx: int | None = None     # index of the currently-open window
        self._baseline = SessionCounters()       # counters at the start of that window

    def _idx(self, now: float) -> int:
        return math.floor(now / self.window_s)

    def sample(self, counters: SessionCounters, now: float) -> list[MetricBucket]:
        """Feed the latest cumulative counters. Returns a bucket iff a window closed.

        Returns a list (0 or 1 items) so the caller can iterate uniformly.
        """
        idx = self._idx(now)
        if self._window_idx is None:
            # First sample: open the window, remember the baseline, emit nothing.
            self._window_idx = idx
            self._baseline = counters
            return []
        if idx <= self._window_idx:
            return []                              # still inside the same window
        # One or more windows elapsed. Attribute the accumulated delta to the
        # window that was open, then jump to the current window.
        bucket = self._make_bucket(self._window_idx, self._baseline, counters)
        self._baseline = counters
        self._window_idx = idx
        return [bucket]

    def flush(self, counters: SessionCounters, now: float) -> MetricBucket | None:
        """Emit the final partial window on shutdown. None if nothing accumulated."""
        if self._window_idx is None:
            return None
        bucket = self._make_bucket(self._window_idx, self._baseline, counters)
        self._baseline = counters
        if bucket.passersby == 0 and bucket.engaged == 0 and bucket.qr_triggers == 0 \
                and bucket.total_attention_s == 0.0:
            return None                            # don't ship an empty bucket
        return bucket

    def _make_bucket(self, window_idx: int, base: SessionCounters,
                     cur: SessionCounters) -> MetricBucket:
        start = window_idx * self.window_s
        pax = max(0, cur.passersby - base.passersby)
        eng = max(0, cur.engaged - base.engaged)
        attn = max(0.0, cur.total_attention_s - base.total_attention_s)
        qr = max(0, cur.qr_triggers - base.qr_triggers)
        rate = round(eng / pax * 100, 1) if pax > 0 else 0.0
        return MetricBucket(
            schema_version=SCHEMA_VERSION,
            device_id=self.device_id,
            store_id=self.store_id,
            window_start=_iso(start),
            window_end=_iso(start + self.window_s),
            passersby=pax,
            engaged=eng,
            engagement_rate=rate,
            total_attention_s=round(attn, 1),
            qr_triggers=qr,
        )
