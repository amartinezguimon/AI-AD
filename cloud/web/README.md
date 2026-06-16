# web/ — VisionMetrics dashboard (Phase 4)

The client-facing dashboard. A faithful build of the agreed design (Hector's
mockup), rebuilt as a proper, scalable SPA: **React + Vite + TypeScript +
Tailwind**, charts with **Chart.js** (same engine as the mockup, so it looks
identical). It talks to the cloud API over relative `/v1` URLs.

## Architecture
```
src/
  lib/        api.ts (typed client, token + 401 handling), auth.tsx (session),
              types.ts (mirror of the API schemas), format.ts, ranges.ts, chartSetup.ts
  hooks/      useDashboard.ts (per-store month cache; one fetch = month + prev month)
  components/ TopBar, MiniCalendar, RangeCalendar, LoadingOverlay, charts/*
  pages/      LoginPage, DashboardLayout (shell), HomePage, AnalysisPage
```
- **Auth**: email + password → JWT (kept in `localStorage`). A 401 anywhere drops
  back to `/login`. Routes are guarded.
- **Data contract**: everything comes from `GET /v1/dashboard?store_id&year&month`
  (`{ daily, dailyPrev, hourly, store, has_data }`). No mock data, no invented
  numbers — every figure traces back to real metric buckets.
- **Multi-store**: if the account owns more than one store, a selector appears in
  the top bar automatically; with one store it's hidden (identical to the mockup).
- **Empty state**: a brand-new store (no data yet) shows a friendly "aún no hay
  datos" instead of breaking.
- **Timezone**: aggregation happens server-side in the store's timezone, so days
  and hours match what the owner experiences.

## Develop
```bash
npm install
npm run dev      # http://localhost:5173 ; proxies /v1 to http://localhost:8000
```
Point it at a different backend with `VM_API_TARGET` (see `.env.example`). Seed
demo data first (`python -m cloud.scripts.seed_demo`) and log in with
`demo@visionmetrics.app` / `demo1234`.

```bash
npm run build      # type-check + production bundle into dist/
npm run typecheck  # types only
```

## Production
Not served from here directly — `cloud/web/Dockerfile` builds `dist/` and Caddy
serves it while proxying `/v1` to the API (same origin, no CORS). Brought up by
`cloud/docker-compose.yml` (`docker compose up -d`).

## Honest note — the "Mín. Xs" slider on Analysis
The look-mode toggle (Pasando / +Mirando / Solo mirando) and the comparisons are
backed by real data. The seconds slider above 2s is **an estimate**: today the
edge emits an engaged *count* + total attention, not a per-second dwell histogram,
so "only people who looked ≥ 7s" can't be computed exactly yet. The `+2s` baseline
is real (that's how "engaged" is defined). Making the slider exact needs the edge
to emit dwell-time buckets — tracked in `ROADMAP.md`.
