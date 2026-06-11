# cloud/ — VisionMetrics backend (Phase 3)

The multi-tenant backend that receives metrics from edge agents and (soon) serves
the dashboards. FastAPI + SQLAlchemy + PostgreSQL.

## Status
- ☑ Multi-tenant schema: `org → store → device → camera`, users/roles, metric
  buckets, heartbeats — `org_id` on every data row (`app/models.py`).
- ☑ Ingest API (the cloud side of the edge `uplink.py`):
  - `POST /v1/metrics` — device-authenticated, idempotent on `(device, window)`.
  - `POST /v1/heartbeat` — updates fleet-health (device online / last seen).
- ☑ Device auth via API key (hash stored, key shown once at provisioning).
- ☑ Provisioning CLI (`scripts/provision.py`) — create org/store/device/user.
- ☑ Dashboard auth + read API (the data the frontend will consume):
  - `POST /v1/auth/login` → JWT; `GET /v1/me`.
  - `GET /v1/stores`, `GET /v1/devices` (fleet health: online/offline/last-seen).
  - `GET /v1/metrics/summary` and `/v1/metrics/timeseries` (?store_id&from&to).
  - `POST /v1/users` / `GET /v1/users` — owner-admin manages users.
  - Every query scoped to the user's org (and pinned to their store if limited).
- ☑ Tests on SQLite (no Docker needed): `19 passed` (incl. cross-org isolation).
- ☐ Next: Alembic migrations, docker-compose (Postgres + Caddy/HTTPS) for the VM
  deploy, platform back-office (cross-tenant).

## Run locally (zero setup — SQLite)
From the repo root:
```bash
venv/Scripts/python -m pip install -r cloud/requirements.txt   # first time
venv/Scripts/python -m uvicorn cloud.app.main:app --reload
```
Interactive API docs at http://127.0.0.1:8000/docs

### Provision a test store + device
```bash
python -m cloud.scripts.provision setup --org "Joyeria Perez" --store "Centro" --device dev-centro-01
```
Copy the printed `device_id` + `api_key` into that store's `device.yaml`
(`uplink.enabled: true`, `base_url: http://127.0.0.1:8000`) and the edge agent
will start posting real buckets.

### Run the tests
```bash
venv/Scripts/python -m pytest cloud/tests -q
```

## Production (VM) — coming next
A `docker-compose` (Postgres + API + Caddy for HTTPS) will let the whole stack
come up with one command on Txema's VM, configured only by `.env` (see
`.env.example`). Schema changes will go through Alembic migrations.

## Design
See `../SYSTEM_DESIGN.md` for the actors, full schema, and roles. Golden rule:
**only anonymous aggregates ever reach here — no video, no per-person data.**
