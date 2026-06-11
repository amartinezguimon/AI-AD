"""Dashboard read API — the data the frontend (Phase 4) will consume.

Every query is scoped to the authenticated user's org (and pinned to their store
if they are a store-scoped user), so a user can only ever read their own tenant's
data. Numbers are returned in plain business terms — no yaw/pitch jargon.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..deps import get_current_user, resolve_store_scope
from ..models import Device, MetricBucket, Store
from ..models import User as UserModel
from ..schemas import (
    BucketOut, DeviceOut, MeOut, MetricSummaryOut, StoreOut,
)

router = APIRouter(prefix="/v1", tags=["dashboard"])


@router.get("/me", response_model=MeOut)
def me(user: UserModel = Depends(get_current_user)) -> MeOut:
    return MeOut(id=user.id, email=user.email, role=user.role,
                 org_id=user.org_id, store_id=user.store_id)


@router.get("/stores", response_model=list[StoreOut])
def list_stores(user: UserModel = Depends(get_current_user),
                db: Session = Depends(get_session)) -> list[StoreOut]:
    q = select(Store).where(Store.org_id == user.org_id)
    if user.store_id is not None:                      # store-scoped user
        q = q.where(Store.id == user.store_id)
    return [StoreOut(id=s.id, name=s.name, address=s.address, timezone=s.timezone)
            for s in db.execute(q).scalars()]


@router.get("/devices", response_model=list[DeviceOut])
def fleet(user: UserModel = Depends(get_current_user),
          db: Session = Depends(get_session)) -> list[DeviceOut]:
    """Fleet health — devices and whether they're reporting (online/offline)."""
    offline_after = get_settings().device_offline_after_s
    now = dt.datetime.now(dt.timezone.utc)

    q = select(Device).where(Device.org_id == user.org_id)
    if user.store_id is not None:
        q = q.where(Device.store_id == user.store_id)

    out: list[DeviceOut] = []
    for d in db.execute(q).scalars():
        status = d.status
        if d.last_seen_at is None:
            status = "provisioned"
        else:
            last = d.last_seen_at
            if last.tzinfo is None:                    # sqlite returns naive datetimes
                last = last.replace(tzinfo=dt.timezone.utc)
            status = "online" if (now - last).total_seconds() <= offline_after else "offline"
        out.append(DeviceOut(
            id=d.id, store_id=d.store_id, status=status,
            agent_version=d.agent_version,
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
        ))
    return out


def _bucket_query(user: UserModel, store_id: str | None, frm: str | None,
                  to: str | None, db: Session):
    scope = resolve_store_scope(user, store_id, db)
    q = select(MetricBucket).where(MetricBucket.org_id == user.org_id)
    if scope is not None:
        q = q.where(MetricBucket.store_id == scope)
    if frm is not None:                                # ISO strings sort chronologically
        q = q.where(MetricBucket.window_start >= frm)
    if to is not None:
        q = q.where(MetricBucket.window_start < to)
    return q


@router.get("/metrics/summary", response_model=MetricSummaryOut)
def metrics_summary(
    store_id: str | None = Query(None),
    frm: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MetricSummaryOut:
    base = _bucket_query(user, store_id, frm, to, db).subquery()
    row = db.execute(select(
        func.coalesce(func.sum(base.c.passersby), 0),
        func.coalesce(func.sum(base.c.engaged), 0),
        func.coalesce(func.sum(base.c.total_attention_s), 0.0),
    )).one()
    passersby, engaged, attention = int(row[0]), int(row[1]), float(row[2])
    rate = round(engaged / passersby * 100, 1) if passersby > 0 else 0.0
    return MetricSummaryOut(passersby=passersby, engaged=engaged,
                            engagement_rate=rate, total_attention_s=round(attention, 1))


@router.get("/metrics/timeseries", response_model=list[BucketOut])
def metrics_timeseries(
    store_id: str | None = Query(None),
    frm: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    limit: int = Query(500, le=5000),
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[BucketOut]:
    q = _bucket_query(user, store_id, frm, to, db).order_by(
        MetricBucket.window_start).limit(limit)
    return [BucketOut(
        store_id=b.store_id, device_id=b.device_id,
        window_start=b.window_start, window_end=b.window_end,
        passersby=b.passersby, engaged=b.engaged,
        engagement_rate=b.engagement_rate, total_attention_s=b.total_attention_s,
    ) for b in db.execute(q).scalars()]
