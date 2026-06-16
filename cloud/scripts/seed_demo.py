"""Seed a demo tenant with a month of realistic metrics — so you can log in and
see the dashboard fully populated, exactly like the mockup, end to end.

    python -m cloud.scripts.seed_demo

Creates (idempotently):
  * org    "Joyería Martínez"
  * store  "Joyería Martínez" (Europe/Madrid)
  * user   demo@visionmetrics.app / demo1234   (admin, whole org)
  * device demo-cam-01
  * hourly metric buckets for the previous full month + the current month to date

Re-running refreshes the buckets (old demo buckets are cleared first). This writes
to the configured database (default: local sqlite visionmetrics.db) and creates
tables if they don't exist yet — for a quick local demo without running Alembic.
Production data always comes from real devices, never from this script.
"""

from __future__ import annotations

import datetime as dt
import random
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from cloud.app.db import Base, SessionLocal, engine
from cloud.app.models import Device, Heartbeat, MetricBucket, Org, PlatformStaff, Store, User
from cloud.app.security import generate_api_key, hash_api_key, hash_password

DEMO_EMAIL = "demo@visionmetrics.app"
DEMO_PASSWORD = "demo1234"
DEMO_DEVICE_ID = "demo-cam-01"
STORE_NAME = "Joyería Martínez"
STAFF_EMAIL = "staff@visionmetrics.app"
STAFF_PASSWORD = "staff1234"
TZ = ZoneInfo("Europe/Madrid")

# Per-hour shape of a day (09h..20h), same silhouette as the mockup.
HOUR_BASE = [14, 32, 38, 28, 22, 18, 21, 29, 31, 26, 18, 9]
# Typical foot traffic by weekday (Mon..Sun); weekends busier.
WEEKDAY_BASE = {0: 150, 1: 160, 2: 165, 3: 175, 4: 230, 5: 300, 6: 120}


def _day_buckets(date: dt.date) -> list[dict]:
    total = int(WEEKDAY_BASE[date.weekday()] * random.uniform(0.8, 1.15))
    rate = random.uniform(0.22, 0.30)
    weight = sum(HOUR_BASE)
    out: list[dict] = []
    for i, hour in enumerate(range(9, 21)):
        passing = max(0, round(total * HOUR_BASE[i] / weight + random.uniform(-3, 3)))
        looking = round(passing * rate)
        attention = round(looking * random.uniform(5.0, 7.0), 1)
        local = dt.datetime(date.year, date.month, date.day, hour, tzinfo=TZ)
        out.append({
            "window_start": local.astimezone(dt.timezone.utc).isoformat(),
            "window_end": (local + dt.timedelta(hours=1)).astimezone(dt.timezone.utc).isoformat(),
            "passersby": passing,
            "engaged": looking,
            "engagement_rate": round(looking / passing * 100, 1) if passing else 0.0,
            "total_attention_s": attention,
        })
    return out


def _date_range() -> list[dt.date]:
    today = dt.datetime.now(TZ).date()
    first_this = today.replace(day=1)
    last_prev = first_this - dt.timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    days: list[dt.date] = []
    d = first_prev
    while d <= today:
        days.append(d)
        d += dt.timedelta(days=1)
    return days


def _get_or_create(session) -> tuple[Org, Store, Device]:
    user = session.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user:
        org = session.get(Org, user.org_id)
        store = session.execute(select(Store).where(Store.org_id == org.id)).scalars().first()
        device = session.execute(select(Device).where(Device.id == DEMO_DEVICE_ID)).scalar_one_or_none()
        if device is None:
            device = Device(id=DEMO_DEVICE_ID, org_id=org.id, store_id=store.id,
                            api_key_hash=hash_api_key(generate_api_key()))
            session.add(device)
            session.commit()
        return org, store, device

    org = Org(name=STORE_NAME)
    session.add(org)
    session.commit()
    store = Store(org_id=org.id, name=STORE_NAME, address="Calle Mayor 1, Madrid", timezone="Europe/Madrid")
    session.add(store)
    session.commit()
    session.add(User(org_id=org.id, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), role="admin"))
    device = Device(id=DEMO_DEVICE_ID, org_id=org.id, store_id=store.id,
                    api_key_hash=hash_api_key(generate_api_key()),
                    agent_version="demo", status="online",
                    last_seen_at=dt.datetime.now(dt.timezone.utc))
    session.add(device)
    session.commit()
    return org, store, device


def _seed_staff(session) -> None:
    if session.execute(select(PlatformStaff).where(PlatformStaff.email == STAFF_EMAIL)).scalar_one_or_none():
        return
    session.add(PlatformStaff(email=STAFF_EMAIL, password_hash=hash_password(STAFF_PASSWORD)))
    session.commit()


def _seed_extra_fleet(session) -> None:
    """A second client with an offline + a never-seen camera, so the staff fleet
    view shows the full range of states (not just one happy device)."""
    name = "Boutique Aimar"
    if session.execute(select(Org).where(Org.name == name)).scalar_one_or_none():
        return
    org = Org(name=name)
    session.add(org)
    session.commit()
    store = Store(org_id=org.id, name=name, address="Gran Vía 30, Bilbao", timezone="Europe/Madrid")
    session.add(store)
    session.commit()
    now = dt.datetime.now(dt.timezone.utc)
    session.add(Device(id="aimar-cam-01", org_id=org.id, store_id=store.id,
                       api_key_hash=hash_api_key(generate_api_key()), agent_version="demo",
                       status="offline", last_seen_at=now - dt.timedelta(hours=3)))
    session.add(Device(id="aimar-cam-02", org_id=org.id, store_id=store.id,
                       api_key_hash=hash_api_key(generate_api_key())))  # never seen
    session.commit()


def main() -> None:
    random.seed(42)
    Base.metadata.create_all(bind=engine)  # local demo convenience; prod uses Alembic
    session = SessionLocal()
    try:
        org, store, device = _get_or_create(session)
        # Mark the device live so the "En directo" pill lights up in the demo.
        now = dt.datetime.now(dt.timezone.utc)
        device.status = "online"
        device.last_seen_at = now
        device.agent_version = "1.0.0-demo"

        # A fresh heartbeat so the staff panel shows real camera health (FPS, ok).
        session.execute(delete(Heartbeat).where(Heartbeat.device_id == device.id))
        session.add(Heartbeat(org_id=org.id, device_id=device.id, sent_at=now.timestamp(),
                              agent_version="1.0.0-demo", camera_ok=True,
                              fps_display=25.0, fps_analysis=14.2, people_tracked=2))

        session.execute(delete(MetricBucket).where(MetricBucket.device_id == device.id))
        rows = 0
        for date in _date_range():
            for b in _day_buckets(date):
                session.add(MetricBucket(org_id=org.id, store_id=store.id, device_id=device.id, **b))
                rows += 1
        session.commit()

        _seed_staff(session)
        _seed_extra_fleet(session)

        print(f"Seeded {rows} hourly buckets for '{store.name}'.")
        print(f"Client login:  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
        print(f"Staff login :  {STAFF_EMAIL}  /  {STAFF_PASSWORD}   (panel at /staff)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
