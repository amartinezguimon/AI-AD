"""Dashboard read API — the data the frontend (Phase 4) will consume.

Every query is scoped to the authenticated user's org (and pinned to their store
if they are a store-scoped user), so a user can only ever read their own tenant's
data. Numbers are returned in plain business terms — no yaw/pitch jargon.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..deps import get_current_user, resolve_store_scope
from ..models import Device, MetricBucket, Store
from ..models import User as UserModel
from ..schemas import (
    BucketOut, DashboardOut, DayStat, DeviceOut, HourBreakdown, MeOut,
    MetricSummaryOut, StoreOut,
)

router = APIRouter(prefix="/v1", tags=["dashboard"])

# The dashboard's hourly chart spans these store-local hours (12 bars, 9h..20h).
HOUR_START = 9
HOUR_END = 20  # inclusive
N_HOURS = HOUR_END - HOUR_START + 1


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


def _store_tz(store: Store) -> ZoneInfo:
    try:
        return ZoneInfo(store.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Europe/Madrid")


def _parse_utc(iso: str) -> dt.datetime:
    """Parse a bucket window_start. Edge emits UTC ISO-8601; assume UTC if naive."""
    ts = dt.datetime.fromisoformat(iso)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts


def _aggregate_month(buckets, tz: ZoneInfo, year: int, month: int
                     ) -> tuple[dict[str, DayStat], dict[str, HourBreakdown]]:
    """Roll hourly buckets up into per-day summaries and per-day hourly breakdowns,
    bucketing by the store's *local* calendar day and hour (not UTC)."""
    daily_acc: dict[int, dict] = {}
    hourly: dict[str, HourBreakdown] = {}

    for b in buckets:
        local = _parse_utc(b.window_start).astimezone(tz)
        if local.year != year or local.month != month:
            continue
        day = local.day
        acc = daily_acc.setdefault(day, {"total": 0, "looking": 0, "attention": 0.0})
        acc["total"] += b.passersby
        acc["looking"] += b.engaged
        acc["attention"] += b.total_attention_s

        if HOUR_START <= local.hour <= HOUR_END:
            hb = hourly.setdefault(str(day), HourBreakdown(
                passing=[0] * N_HOURS, looking=[0] * N_HOURS))
            idx = local.hour - HOUR_START
            hb.passing[idx] += b.passersby
            hb.looking[idx] += b.engaged

    daily: dict[str, DayStat] = {}
    for day, a in daily_acc.items():
        rate = round(a["looking"] / a["total"] * 100) if a["total"] else 0
        avg = round(a["attention"] / a["looking"], 1) if a["looking"] else 0.0
        daily[str(day)] = DayStat(total=a["total"], looking=a["looking"],
                                  rate=rate, avg=avg)
    return daily, hourly


def _utc_window_for_local_month(tz: ZoneInfo, year: int, month: int
                                ) -> tuple[str, str]:
    """UTC ISO bounds [start, end) that safely cover the given local month.
    Padded by a day each side so DST/offset edges never drop boundary buckets."""
    local_start = dt.datetime(year, month, 1, tzinfo=tz)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    local_end = dt.datetime(next_year, next_month, 1, tzinfo=tz)
    pad = dt.timedelta(days=1)
    start = (local_start - pad).astimezone(dt.timezone.utc).isoformat()
    end = (local_end + pad).astimezone(dt.timezone.utc).isoformat()
    return start, end


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    store_id: str | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DashboardOut:
    """One month of a store's metrics, pre-shaped for the frontend charts.

    Buckets are aggregated in the *store's* timezone so days/hours line up with
    how the owner experiences them. A store with no data yet returns empty maps
    and `has_data=False` (the frontend renders a friendly empty state)."""
    scope = resolve_store_scope(user, store_id, db)
    if scope is None:                                  # org-wide user, no store picked
        scope_store = db.execute(
            select(Store).where(Store.org_id == user.org_id)
            .order_by(Store.created_at, Store.id)
        ).scalars().first()
        if scope_store is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="No stores for this account")
        scope = scope_store.id
    else:
        scope_store = db.get(Store, scope)

    tz = _store_tz(scope_store)
    if year is None or month is None:
        now_local = dt.datetime.now(tz)
        year, month = now_local.year, now_local.month

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)

    # One DB read spanning both months (current + previous), then bucket locally.
    win_start, _ = _utc_window_for_local_month(tz, prev_year, prev_month)
    _, win_end = _utc_window_for_local_month(tz, year, month)
    buckets = db.execute(
        select(MetricBucket)
        .where(MetricBucket.org_id == user.org_id)
        .where(MetricBucket.store_id == scope)
        .where(MetricBucket.window_start >= win_start)
        .where(MetricBucket.window_start < win_end)
    ).scalars().all()

    daily, hourly = _aggregate_month(buckets, tz, year, month)
    daily_prev, _ = _aggregate_month(buckets, tz, prev_year, prev_month)

    return DashboardOut(
        store=StoreOut(id=scope_store.id, name=scope_store.name,
                       address=scope_store.address, timezone=scope_store.timezone),
        year=year, month=month,
        has_data=bool(daily) or bool(daily_prev),
        daily=daily, dailyPrev=daily_prev, hourly=hourly,
    )


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
