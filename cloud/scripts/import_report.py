"""Import a demo session report (results/demo_*.json from the edge menu) into the
dashboard database, so a live test by a colleague shows up in the frontend as REAL
data for the demo store.

    python -m cloud.scripts.import_report results/demo_20260617-181500.json

The buckets are attached to a separate "live" device in the demo store, so re-running
seed_demo (which refreshes the demo HISTORY device) never wipes the real data. Upserts
on (device, window_start), so re-importing the same report is safe.

Flow for hosting the panel:
    python -m cloud.scripts.seed_demo                      # demo history (up to yesterday)
    python -m uvicorn cloud.app.main:app                   # backend   (one terminal)
    cd cloud/web && npm run dev                            # frontend  (another terminal)
    # when a colleague sends results/demo_*.json:
    python -m cloud.scripts.import_report results/demo_*.json  # then refresh the dashboard
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from sqlalchemy import select

from cloud.app.db import Base, SessionLocal, engine
from cloud.app.models import Device, MetricBucket
from cloud.app.security import generate_api_key, hash_api_key

HISTORY_DEVICE_ID = "demo-cam-01"   # created by seed_demo
LIVE_DEVICE_ID = "demo-cam-live"    # real test data lands here (survives re-seeding)


def main() -> int:
    ap = argparse.ArgumentParser(description="Import an edge session report into the dashboard DB.")
    ap.add_argument("report", help="path to a results/demo_*.json file")
    ap.add_argument("--store-device", default=HISTORY_DEVICE_ID,
                    help="an existing device in the target store (to resolve org/store)")
    args = ap.parse_args()

    path = Path(args.report)
    if not path.exists():
        raise SystemExit(f"Report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    buckets = data.get("buckets", [])
    if not buckets:
        print("Report has no buckets (the run was too short to close a window). Nothing to import.")
        return 0

    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        anchor = s.execute(select(Device).where(Device.id == args.store_device)).scalar_one_or_none()
        if anchor is None:
            raise SystemExit(
                f"Device {args.store_device!r} not found — run `python -m cloud.scripts.seed_demo` "
                "first (it creates the demo store + device).")

        live = s.execute(select(Device).where(Device.id == LIVE_DEVICE_ID)).scalar_one_or_none()
        if live is None:
            live = Device(id=LIVE_DEVICE_ID, org_id=anchor.org_id, store_id=anchor.store_id,
                          api_key_hash=hash_api_key(generate_api_key()), agent_version="demo-live")
            s.add(live)
            s.commit()

        n_new = n_upd = 0
        for b in buckets:
            ws = b["window_start"]
            existing = s.execute(
                select(MetricBucket).where(MetricBucket.device_id == live.id,
                                           MetricBucket.window_start == ws)
            ).scalar_one_or_none()
            fields = dict(
                passersby=int(b.get("passersby", 0)), engaged=int(b.get("engaged", 0)),
                engagement_rate=float(b.get("engagement_rate", 0.0)),
                total_attention_s=float(b.get("total_attention_s", 0.0)),
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                n_upd += 1
            else:
                s.add(MetricBucket(org_id=live.org_id, store_id=live.store_id, device_id=live.id,
                                   window_start=ws, window_end=b.get("window_end", ws), **fields))
                n_new += 1

        live.status = "online"
        live.last_seen_at = dt.datetime.now(dt.timezone.utc)
        s.commit()
        print(f"Imported {len(buckets)} bucket(s) ({n_new} new, {n_upd} updated) into the demo store.")
        print("Refresh the dashboard to see it (real data for today onward).")
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
