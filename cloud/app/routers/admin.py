"""Platform back-office — cross-tenant operations for us (platform staff).

Unlike the dashboard (scoped to one org), these endpoints see ALL clients: list
orgs, the global device fleet, and onboard a new client (org → store → device,
issuing the device API key once). Every route requires a staff session.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..deps import get_current_staff
from ..models import Device, Heartbeat, MetricBucket, Org, PlatformStaff, Store
from ..provisioning import create_device, create_org, create_store
from ..schemas import (
    AdminDeviceOut, AdminOverviewOut, DeviceCreateIn, DeviceKeyOut, OrgCreateIn,
    OrgOut, StaffMeOut, StoreCreateIn, StoreOut,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(get_current_staff)])


def _device_status(last_seen_at, now, offline_after) -> str:
    if last_seen_at is None:
        return "provisioned"
    last = last_seen_at if last_seen_at.tzinfo else last_seen_at.replace(tzinfo=dt.timezone.utc)
    return "online" if (now - last).total_seconds() <= offline_after else "offline"


@router.get("/me", response_model=StaffMeOut)
def staff_me(staff: PlatformStaff = Depends(get_current_staff)) -> StaffMeOut:
    return StaffMeOut(id=staff.id, email=staff.email)


@router.get("/overview", response_model=AdminOverviewOut)
def overview(db: Session = Depends(get_session)) -> AdminOverviewOut:
    """Platform-wide counts for the summary cards."""
    offline_after = get_settings().device_offline_after_s
    now = dt.datetime.now(dt.timezone.utc)
    online = offline = never = 0
    for (last_seen,) in db.execute(select(Device.last_seen_at)).all():
        st = _device_status(last_seen, now, offline_after)
        if st == "online":
            online += 1
        elif st == "offline":
            offline += 1
        else:
            never += 1
    return AdminOverviewOut(
        orgs=int(db.scalar(select(func.count(Org.id))) or 0),
        stores=int(db.scalar(select(func.count(Store.id))) or 0),
        devices=int(db.scalar(select(func.count(Device.id))) or 0),
        online=online, offline=offline, never_seen=never,
    )


@router.get("/orgs", response_model=list[OrgOut])
def list_orgs(db: Session = Depends(get_session)) -> list[OrgOut]:
    out: list[OrgOut] = []
    for org in db.execute(select(Org).order_by(Org.created_at)).scalars():
        store_count = db.scalar(select(func.count(Store.id)).where(Store.org_id == org.id))
        device_count = db.scalar(select(func.count(Device.id)).where(Device.org_id == org.id))
        out.append(OrgOut(
            id=org.id, name=org.name, created_at=org.created_at.isoformat(),
            store_count=int(store_count or 0), device_count=int(device_count or 0),
        ))
    return out


@router.post("/orgs", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def add_org(body: OrgCreateIn, db: Session = Depends(get_session)) -> OrgOut:
    org = create_org(db, body.name)
    return OrgOut(id=org.id, name=org.name, created_at=org.created_at.isoformat(),
                  store_count=0, device_count=0)


@router.post("/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def add_store(body: StoreCreateIn, db: Session = Depends(get_session)) -> StoreOut:
    if db.get(Org, body.org_id) is None:
        raise HTTPException(status_code=404, detail="Org not found")
    s = create_store(db, body.org_id, body.name, address=body.address, timezone=body.timezone)
    return StoreOut(id=s.id, name=s.name, address=s.address, timezone=s.timezone)


@router.post("/devices", response_model=DeviceKeyOut, status_code=status.HTTP_201_CREATED)
def add_device(body: DeviceCreateIn, db: Session = Depends(get_session)) -> DeviceKeyOut:
    store = db.get(Store, body.store_id)
    if store is None or store.org_id != body.org_id:
        raise HTTPException(status_code=404, detail="Store not found in that org")
    if db.get(Device, body.device_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device_id already exists")
    pd = create_device(db, body.org_id, body.store_id, body.device_id)
    return DeviceKeyOut(device_id=pd.device.id, api_key=pd.api_key)


@router.get("/fleet", response_model=list[AdminDeviceOut])
def global_fleet(db: Session = Depends(get_session)) -> list[AdminDeviceOut]:
    """Every device across every client, with live status, camera health and a
    data-flow signal (last metric + traffic in the last 24h) — so staff can tell
    at a glance whether a store is genuinely healthy, not just powered on."""
    offline_after = get_settings().device_offline_after_s
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(hours=24)).isoformat()
    rows = db.execute(
        select(Device, Org.name, Store.name)
        .join(Org, Device.org_id == Org.id)
        .join(Store, Device.store_id == Store.id)
        .order_by(Org.name, Store.name)
    ).all()

    out: list[AdminDeviceOut] = []
    for d, org_name, store_name in rows:
        hb = db.execute(
            select(Heartbeat).where(Heartbeat.device_id == d.id)
            .order_by(Heartbeat.received_at.desc()).limit(1)
        ).scalar_one_or_none()
        last_metric_at = db.scalar(
            select(func.max(MetricBucket.window_start)).where(MetricBucket.device_id == d.id)
        )
        recent = db.scalar(
            select(func.coalesce(func.sum(MetricBucket.passersby), 0))
            .where(MetricBucket.device_id == d.id, MetricBucket.window_start >= cutoff)
        )
        out.append(AdminDeviceOut(
            id=d.id, org_id=d.org_id, org_name=org_name, store_id=d.store_id,
            store_name=store_name,
            status=_device_status(d.last_seen_at, now, offline_after),
            agent_version=d.agent_version,
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
            camera_ok=hb.camera_ok if hb else None,
            fps_analysis=hb.fps_analysis if hb else None,
            people_tracked=hb.people_tracked if hb else None,
            last_metric_at=last_metric_at,
            recent_passersby=int(recent or 0),
        ))
    return out
