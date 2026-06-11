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


# ── dashboard / auth ──────────────────────────────────────────────
class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: str
    email: str
    role: str
    org_id: str
    store_id: str | None = None


class StoreOut(BaseModel):
    id: str
    name: str
    address: str | None = None
    timezone: str


class DeviceOut(BaseModel):
    id: str
    store_id: str
    status: str                       # provisioned | online | offline
    agent_version: str | None = None
    last_seen_at: str | None = None   # ISO, or None if never seen


class MetricSummaryOut(BaseModel):
    passersby: int
    engaged: int
    engagement_rate: float            # engaged / passersby * 100
    total_attention_s: float


class BucketOut(BaseModel):
    store_id: str
    device_id: str
    window_start: str
    window_end: str
    passersby: int
    engaged: int
    engagement_rate: float
    total_attention_s: float


class UserCreateIn(BaseModel):
    email: str
    password: str = Field(min_length=6)
    role: str = "viewer"              # admin | viewer
    store_id: str | None = None       # None => whole org


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    store_id: str | None = None
