"""The edge <-> cloud data contract — single source of truth.

Both the edge agent (producer) and the cloud ingest API (consumer) import these
types, so the wire format can never drift between them. Two message kinds:

  Heartbeat    — liveness + health, sent frequently (~30 s).
  MetricBucket — anonymous aggregate metrics for one time window. NO images,
                 NO per-person data, NO biometric identifiers ever cross the
                 wire. This is the GDPR guarantee, enforced by the schema.

Each MetricBucket carries (device_id, window_start) which together form an
idempotency key: re-sending a buffered bucket after a network outage updates
in place rather than double-counting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA_VERSION = 1


@dataclass
class Heartbeat:
    schema_version: int
    device_id: str
    store_id: str
    sent_at: float                 # unix seconds
    agent_version: str
    camera_ok: bool
    fps_display: float
    fps_analysis: float
    people_tracked: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricBucket:
    schema_version: int
    device_id: str
    store_id: str
    window_start: str              # ISO-8601, truncated to the bucket (e.g. the hour)
    window_end: str
    passersby: int
    engaged: int                   # people who crossed the attention threshold
    engagement_rate: float         # engaged / passersby * 100
    total_attention_s: float
    qr_triggers: int

    @property
    def idempotency_key(self) -> str:
        return f"{self.device_id}:{self.window_start}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MetricBucket":
        return cls(**d)
