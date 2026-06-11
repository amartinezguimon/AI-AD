"""Ingest API — the cloud side of the edge agent's uplink.

The edge POSTs metric buckets and heartbeats here, authenticating as a device.
Tenant safety: org_id/store_id come from the authenticated *device row*, not the
request body, so a device cannot write data for another store or org.

Buckets are idempotent on (device_id, window_start): re-sending a buffered
bucket after a network outage updates it in place rather than double-counting.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import authenticate_device
from ..models import Device, Heartbeat, MetricBucket
from ..schemas import Ack, HeartbeatIn, MetricBucketIn

router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post("/metrics", response_model=Ack)
def ingest_metrics(
    bucket: MetricBucketIn,
    device: Device = Depends(authenticate_device),
    db: Session = Depends(get_session),
) -> Ack:
    existing = db.execute(
        select(MetricBucket).where(
            MetricBucket.device_id == device.id,
            MetricBucket.window_start == bucket.window_start,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(MetricBucket(
            org_id=device.org_id,
            store_id=device.store_id,
            device_id=device.id,
            window_start=bucket.window_start,
            window_end=bucket.window_end,
            passersby=bucket.passersby,
            engaged=bucket.engaged,
            engagement_rate=bucket.engagement_rate,
            total_attention_s=bucket.total_attention_s,
        ))
        detail = "created"
    else:
        existing.window_end = bucket.window_end
        existing.passersby = bucket.passersby
        existing.engaged = bucket.engaged
        existing.engagement_rate = bucket.engagement_rate
        existing.total_attention_s = bucket.total_attention_s
        existing.received_at = dt.datetime.now(dt.timezone.utc)
        detail = "updated"

    db.commit()
    return Ack(detail=detail)


@router.post("/heartbeat", response_model=Ack)
def ingest_heartbeat(
    hb: HeartbeatIn,
    device: Device = Depends(authenticate_device),
    db: Session = Depends(get_session),
) -> Ack:
    db.add(Heartbeat(
        org_id=device.org_id,
        device_id=device.id,
        sent_at=hb.sent_at,
        agent_version=hb.agent_version,
        camera_ok=hb.camera_ok,
        fps_display=hb.fps_display,
        fps_analysis=hb.fps_analysis,
        people_tracked=hb.people_tracked,
    ))
    # Latest heartbeat drives fleet-health: mark the device online + seen now.
    device.last_seen_at = dt.datetime.now(dt.timezone.utc)
    device.status = "online"
    if hb.agent_version:
        device.agent_version = hb.agent_version
    db.commit()
    return Ack(detail="ok")
