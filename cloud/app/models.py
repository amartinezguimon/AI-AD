"""The multi-tenant data model — the single most important design decision.

Hierarchy (matches SYSTEM_DESIGN.md):

    Org (the tenant boundary)
     ├── User           (owner-admin can create more, scoped to org or one store)
     └── Store
           └── Device   (the edge box; authenticates with an API key)
                 ├── Camera
                 ├── MetricBucket   (per-window aggregates — NO video, NO PII)
                 └── Heartbeat

Tenant isolation rule: **every row that holds data carries `org_id`**, and every
query is scoped by it. A device can only ever write rows for its own org/store
(enforced in the ingest path), so one client can never see or affect another.

IDs are app-generated UUID hex strings: portable across SQLite/Postgres,
non-guessable, and safe for a distributed/scalable system (no sequence
contention). `reseller_id` is kept nullable so a reseller layer can be added
later without a migration of existing rows (decision on record in SYSTEM_DESIGN).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reseller_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # future use
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="org", cascade="all, delete-orphan")
    stores: Mapped[list["Store"]] = relationship(back_populates="org", cascade="all, delete-orphan")


class PlatformStaff(Base):
    """Us (the company): cross-tenant operators. Outside the org hierarchy."""
    __tablename__ = "platform_staff"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    """A client-side user. role=admin (owner) can manage users; viewer is read-only.

    store_id NULL => access to the whole org; set => limited to that one store.
    """
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_user_org_email"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="admin")     # admin | viewer
    store_id: Mapped[str | None] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    org: Mapped[Org] = relationship(back_populates="users")


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Madrid")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    org: Mapped[Org] = relationship(back_populates="stores")
    devices: Mapped[list["Device"]] = relationship(back_populates="store", cascade="all, delete-orphan")


class Device(Base):
    """An edge box. Authenticates to the ingest API with an API key (hash stored)."""
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)   # the device_id (human-set)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="provisioned")  # provisioned|online|offline
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    store: Mapped[Store] = relationship(back_populates="devices")


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    fov_h_deg: Mapped[float] = mapped_column(Float, default=70.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MetricBucket(Base):
    """One time-window of anonymous aggregates. (device_id, window_start) is unique
    so a re-sent bucket (offline buffer replay) upserts instead of duplicating."""
    __tablename__ = "metric_buckets"
    __table_args__ = (
        UniqueConstraint("device_id", "window_start", name="uq_bucket_device_window"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    window_start: Mapped[str] = mapped_column(String(40), nullable=False)   # ISO-8601
    window_end: Mapped[str] = mapped_column(String(40), nullable=False)
    passersby: Mapped[int] = mapped_column(Integer, default=0)
    engaged: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_attention_s: Mapped[float] = mapped_column(Float, default=0.0)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Heartbeat(Base):
    """Liveness pings. Latest one per device also updates Device.last_seen_at/status."""
    __tablename__ = "heartbeats"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    sent_at: Mapped[float] = mapped_column(Float, nullable=False)          # unix seconds (from device)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    camera_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    fps_display: Mapped[float] = mapped_column(Float, default=0.0)
    fps_analysis: Mapped[float] = mapped_column(Float, default=0.0)
    people_tracked: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
