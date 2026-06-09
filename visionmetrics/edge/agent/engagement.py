"""Engagement state machine — temporal smoothing, attention windows, counting.

This is the analytics core: given a per-frame "raw engaged" boolean for each
tracked person, it maintains a smoothed engagement state, accumulates attention
time across multiple looking windows, counts each person once after they cross
the attention threshold, and decides when to fire the customer-facing reward
(QR) trigger.

It is deliberately pure: no camera, no torch, no OpenCV. It takes booleans and
timestamps. That makes every counting rule unit-testable with a fake clock.

Extracted behavior-preserving from main.py (the per-person block around the
frame buffer + engagement-time tracking + QR trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EngagementParams:
    frame_buffer_size: int = 3          # look at the last N frames
    frame_engage_min: int = 1           # >= this many engaged frames in the buffer => engaged
    count_threshold_s: float = 2.0      # attention before a person counts as "engaged"
    reward_threshold_s: float = 5.0     # attention before the QR/reward screen fires
    qr_duration_s: float = 10.0         # how long the QR stays up once fired
    zone_soft_margin: float = 0.30      # width of the soft engagement-zone edge (used by pipeline)


@dataclass
class PersonState:
    first_seen: float
    engage_start: float | None = None     # start of the current looking window
    cumulative_engage_s: float = 0.0      # banked time from all CLOSED windows
    total_engage_s: float = 0.0           # cumulative + current open window (for display)
    counted_as_engaged: bool = False      # crossed count_threshold_s once
    currently_engaged: bool = False
    last_prob: float = 0.0                # most recent engage probability (HUD/tiers)
    frame_buffer: list[int] = field(default_factory=list)


@dataclass
class FrameUpdate:
    """What the pipeline does to one person on one frame, plus side effects."""
    is_engaged: bool
    total_engage_s: float
    newly_counted: bool          # this person just crossed count_threshold_s
    qr_triggered: bool           # the reward screen should (re)appear now


class EngagementTracker:
    """Owns per-person engagement state and the session-wide counters."""

    def __init__(self, params: EngagementParams | None = None):
        self.params = params or EngagementParams()
        self.people: dict[int, PersonState] = {}
        self.total_passersby = 0
        self.total_engaged = 0
        self.qr_active_until = 0.0
        self.qr_trigger_count = 0

    # ── lifecycle ────────────────────────────────────────────────
    def register(self, track_id: int, now: float) -> PersonState:
        """Register a newly seen person (counts as a passerby)."""
        state = PersonState(first_seen=now)
        self.people[track_id] = state
        self.total_passersby += 1
        return state

    def forget(self, track_id: int) -> None:
        """Drop a track that turned out not to be a person (ghost).

        Reverses the passerby increment so false detections don't inflate counts.
        """
        if track_id in self.people:
            del self.people[track_id]
            self.total_passersby = max(0, self.total_passersby - 1)

    def is_tracked(self, track_id: int) -> bool:
        return track_id in self.people

    # ── per-frame update ─────────────────────────────────────────
    def update(self, track_id: int, raw_engaged: bool, now: float,
               prob: float = 0.0) -> FrameUpdate:
        """Advance one person's state by one frame. Pure given (raw_engaged, now)."""
        p = self.params
        state = self.people.get(track_id) or self.register(track_id, now)
        state.last_prob = prob

        # Temporal frame buffer: M-of-N vote prevents single-frame flicker.
        buf = state.frame_buffer
        buf.append(1 if raw_engaged else 0)
        if len(buf) > p.frame_buffer_size:
            buf.pop(0)
        is_engaged = sum(buf) >= p.frame_engage_min

        # Attention-time accounting across multiple looking windows.
        if is_engaged:
            if state.engage_start is None:
                state.engage_start = now              # open a new window
            state.total_engage_s = state.cumulative_engage_s + (now - state.engage_start)
        else:
            if state.engage_start is not None:        # close & bank the window
                state.cumulative_engage_s += now - state.engage_start
                state.engage_start = None
            state.total_engage_s = state.cumulative_engage_s

        # Count each person once after crossing the attention threshold.
        newly_counted = False
        if not state.counted_as_engaged and state.total_engage_s >= p.count_threshold_s:
            state.counted_as_engaged = True
            self.total_engaged += 1
            newly_counted = True

        # Fire the reward (QR) trigger once, with a cooldown (single-slot pattern).
        qr_triggered = False
        if state.total_engage_s >= p.reward_threshold_s and now > self.qr_active_until:
            self.qr_active_until = now + p.qr_duration_s
            self.qr_trigger_count += 1
            qr_triggered = True

        state.currently_engaged = is_engaged
        return FrameUpdate(
            is_engaged=is_engaged,
            total_engage_s=state.total_engage_s,
            newly_counted=newly_counted,
            qr_triggered=qr_triggered,
        )

    # ── aggregates (for metric buckets / HUD) ────────────────────
    def total_attention_s(self) -> float:
        return sum(s.total_engage_s for s in self.people.values())

    def currently_engaged_count(self, active_ids: set[int]) -> int:
        return sum(
            1 for tid in active_ids
            if self.people.get(tid, PersonState(0)).currently_engaged
        )

    def engagement_rate(self) -> float:
        if self.total_passersby <= 0:
            return 0.0
        return round(self.total_engaged / self.total_passersby * 100, 1)
