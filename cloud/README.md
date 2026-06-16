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
- ☑ Dashboard auth + read API (consumed by the `web/` SPA):
  - `POST /v1/auth/login` → JWT; `GET /v1/me`.
  - `GET /v1/stores`, `GET /v1/devices` (fleet health: online/offline/last-seen).
  - `GET /v1/dashboard?store_id&year&month` — one month pre-shaped for the charts
    (`daily`, `dailyPrev`, `hourly`), aggregated in the **store's timezone**, with
    `has_data:false` for a brand-new store. This is the dashboard's data contract.
  - `GET /v1/metrics/summary` and `/v1/metrics/timeseries` (?store_id&from&to).
  - `POST /v1/users` / `GET /v1/users` — owner-admin manages users.
  - Every query scoped to the user's org (and pinned to their store if limited).
- ☑ Tests on SQLite (no Docker needed): `29 passed` (incl. cross-org isolation
  and the dashboard aggregation/timezone/empty-store cases).
- ☑ Alembic migrations (`migrations/`) — the single source of truth for the
  schema, local and prod. `alembic -c cloud/alembic.ini upgrade head`.
- ☑ `docker-compose.yml` — API + PostgreSQL + Caddy (auto-HTTPS). One command,
  same file on a laptop and on the VM; only `.env` differs.
- ☑ Platform back-office (staff, cross-tenant): `POST /v1/auth/staff/login`,
  `GET /v1/admin/orgs` (with counts), `POST /v1/admin/orgs|stores|devices`
  (onboard a client via API; device key returned once), `GET /v1/admin/fleet`
  (every device across all clients with live status). Bootstrap a staff login
  with `python -m cloud.scripts.provision staff --email ... --password ...`.
- ☑ Phase 4 — client dashboard SPA in `web/` (React + Vite + TypeScript +
  Tailwind), a faithful build of the design, wired to the API above. Caddy serves
  it and proxies `/v1` (same origin → no CORS in prod). See `web/README.md`.
- ☑ Staff back-office (monitoring) — UI at `/staff` + API:
  `GET /v1/admin/me`, `/v1/admin/overview` (platform counts: online/offline/never),
  `/v1/admin/fleet` (every camera across all clients with status, camera health
  from the latest heartbeat — FPS/camera_ok — and a data-flow signal: last metric +
  passersby in the last 24h). View-only for now; remote config editing is next.
- ☐ Next: remote per-store config editing (server→edge config channel + a form UI).

## Run locally (SQLite, no Docker)
From the repo root:
```bash
venv/Scripts/python -m pip install -r cloud/requirements.txt   # first time
venv/Scripts/alembic -c cloud/alembic.ini upgrade head         # create/upgrade schema
venv/Scripts/python -m uvicorn cloud.app.main:app --reload
```
Interactive API docs at http://127.0.0.1:8000/docs

## Run the full stack (Docker — what the VM runs)
```bash
cd cloud
cp .env.example .env      # then edit secrets (POSTGRES_PASSWORD, VM_JWT_SECRET, VM_DOMAIN)
docker compose up -d      # Postgres + API (auto-migrates) + Caddy (HTTPS)
```
On the VM, point `VM_DOMAIN` at the real hostname and Caddy fetches a Let's
Encrypt certificate automatically. The edge agents then post to
`https://<VM_DOMAIN>/v1/metrics`.

### Provision a test store + device
```bash
python -m cloud.scripts.provision setup --org "Joyeria Perez" --store "Centro" --device dev-centro-01
```
Copy the printed `device_id` + `api_key` into that store's `device.yaml`
(`uplink.enabled: true`, `base_url: http://127.0.0.1:8000`) and the edge agent
will start posting real buckets.

### See the dashboard with demo data (end to end)
```bash
venv/Scripts/python -m cloud.scripts.seed_demo          # demo store + 1 month of metrics
venv/Scripts/python -m uvicorn cloud.app.main:app        # API on :8000  (one terminal)
cd cloud/web && npm install && npm run dev               # SPA on :5173  (another terminal)
```
Open http://localhost:5173 and log in with `demo@visionmetrics.app` / `demo1234`.
The dev server proxies `/v1` to the API, exactly like Caddy does in production.

Staff (us) panel: http://localhost:5173/staff — `staff@visionmetrics.app` / `staff1234`.
The seed also creates a second client with offline / never-seen cameras so the
fleet view shows the full range of states. (The demo camera reads "online" only
for ~2 min after seeding — there's no real device sending heartbeats.)

### Run the tests
```bash
venv/Scripts/python -m pytest cloud/tests -q
```

## Onboarding a new store (the whole flow)
1. **Provision** the tenant + device (staff):
   ```bash
   python -m cloud.scripts.provision setup --org "Joyeria Perez" --store "Centro" \
       --device dev-centro-01 --user owner@perez.com --password ******
   ```
   This prints the device `api_key` **once** — put it in that store's `device.yaml`.
2. **Connect the edge box** (camera → mini-PC) with that `device.yaml`
   (`uplink.enabled: true`, `base_url: https://<VM_DOMAIN>`). It starts posting
   anonymous hourly buckets.
3. **The owner logs in** at the dashboard URL. Their store appears automatically —
   empty ("aún no hay datos") until the first buckets arrive, then populated. No
   per-store frontend work: the dashboard reads whatever the account owns.

## Production (Docker — what the VM runs)
`docker compose up -d` brings up Postgres + API (auto-migrates) + Caddy, which now
also **builds and serves the dashboard SPA** and proxies `/v1` to the API. Same
file on a laptop and on the VM; only `.env` differs (set `VM_DOMAIN`,
`VM_JWT_SECRET`, `POSTGRES_PASSWORD`). Schema changes go through Alembic migrations.

## Design
See `../SYSTEM_DESIGN.md` for the actors, full schema, and roles. Golden rule:
**only anonymous aggregates ever reach here — no video, no per-person data.**
