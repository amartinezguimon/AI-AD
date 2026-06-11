"""Wire-format schemas for the ingest API.

These mirror visionmetrics/shared/schema.py on the edge side (the producer), so
the contract is explicit and validated at the door. The cloud is the consumer;
if the edge ever sends a malformed bucket, FastAPI rejects it with a 422 instead
of corrupting the database.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricBucketIn(BaseModel):
    schema_version: int
    device_id: str
    store_id: str
    window_start: str
    window_end: str
    passersby: int = Field(ge=0)
    engaged: int = Field(ge=0)
    engagement_rate: float = Field(ge=0)
    total_attention_s: float = Field(ge=0)


class HeartbeatIn(BaseModel):
    schema_version: int
    device_id: str
    store_id: str
    sent_at: float
    agent_version: str | None = None
    camera_ok: bool = True
    fps_display: float = 0.0
    fps_analysis: float = 0.0
    people_tracked: int = 0


class Ack(BaseModel):
    ok: bool = True
    detail: str | None = None
