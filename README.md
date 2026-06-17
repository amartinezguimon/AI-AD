# VisionMetrics AI

> **Privacy-preserving computer vision for retail shop-window engagement analytics.**

VisionMetrics measures how people interact with a shop window: foot traffic (who
walks past), attention (who stops to look) and dwell time — and shows it to the
store on a web dashboard. It is being built as a multi-tenant SaaS for a pilot in
real stores.

**Golden rule (privacy by design):** the video **never leaves the store**. All
processing happens on a small box next to the camera; only **anonymous aggregate
numbers** (counts per time window) travel to the cloud. No faces, no identities,
no images are stored or transmitted. Counting is done by **zone crossings, not by
recognising people** — see `SYSTEM_DESIGN.md`.

## Run it / test it
👉 **[`EMPEZAR_AQUI.md`](EMPEZAR_AQUI.md)** — one-click demo (`DEMO.bat` / `python run.py`):
a menu to run the live model, collect training data, or draw the counting zone, for
a non-technical colleague. Start there.

## Architecture (3 rings)
```
Camera ─► Edge box (mini-PC, the "brain")  ─►  Cloud (API + DB)  ─►  Web dashboard
          detect → track → head pose →           multi-tenant,        client panel +
          engagement model → count by zone       only aggregates      staff back-office
```

## Repository layout
```
visionmetrics/          # the product (edge + shared)
  edge/agent/           #   the edge pipeline (detection, tracking, engagement, counting)
  edge/tools/           #   operator tools: draw_zone, calibrate, check_cameras
  edge/config/          #   device.example.yaml (per-box config)
  training/             #   collect → build_dataset → train (the engagement model)
  tests/                #   ~100 unit tests (no camera/GPU needed)
cloud/                  # backend + dashboard
  app/                  #   FastAPI: ingest, auth, dashboard, admin (multi-tenant)
  web/                  #   React + Vite + TypeScript dashboard (client + /staff)
  scripts/              #   provision, seed_demo, import_report
configs/                # demo.yaml + store calibration template
data/  models/  fixtures/   # datasets, model weights, test clips
run.py  DEMO.bat  EMPEZAR_AQUI.md   # one-stop demo launcher + guide
SYSTEM_DESIGN.md  ROADMAP.md         # design blueprint + plan
```

## Develop
```bash
python -m venv venv && venv/Scripts/activate      # (source venv/bin/activate on mac/linux)
pip install -r requirements.txt                   # edge + training deps
pip install -r cloud/requirements.txt             # backend deps

python -m pytest visionmetrics/tests -q           # edge/training tests
python -m pytest cloud/tests -q                   # backend tests
```
- Edge agent: `python -m visionmetrics.edge.agent.service --config <device.yaml> [--debug]`
- Backend + dashboard: see [`cloud/README.md`](cloud/README.md).
- Training workflow: see [`visionmetrics/training/README.md`](visionmetrics/training/README.md).

## Status
Productization in progress toward a store pilot. See [`ROADMAP.md`](ROADMAP.md).
