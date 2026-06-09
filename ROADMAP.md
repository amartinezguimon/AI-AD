# VisionMetrics AI — Roadmap to Pilot (target: August 2026)

> Living source of truth for the productization effort. Claude maintains this file.
> Status legend: ☐ todo · ◐ in progress · ☑ done

## Goal
Turn the working uni prototype into a SaaS-ready product: an **edge agent** that runs
unattended in a store (reading from USB/RTSP camera), streams **anonymous aggregate
metrics** (never video) to a backend on Txema's VM, and a **web dashboard** where a
client sees their stores. Pilot in real stores by August.

## Golden rules
1. **Video never leaves the store.** Only anonymous aggregate metrics travel.
2. **Refactor preserves behavior first, improve second.** Verify against a recorded
   clip fixture before changing logic.
3. **All per-store/per-camera settings live in `device.yaml`,** never hardcoded.
4. **Everything in the cloud runs in one `docker-compose`** on the VM (no k8s).

## Architecture (3 rings)
`Camera (USB/RTSP) → Edge box (mini-PC, agent) → Cloud VM (ingest+DB+API) → Web dashboard`

---

## Phase 1 — Edge agent (Weeks 1–3) — *60% of the work, 90% of the risk*
- ☑ Monorepo structure under `visionmetrics/`
- ☑ Config system: `device.yaml` + typed loader (kills all hardcoded constants)
- ☑ Extract pure logic into tested modules:
  - ☑ `geometry.py` — face-angle extraction (shared by agent + calibrate; was duplicated)
  - ☑ `camera_model.py` — pinhole focal/distance (was duplicated)
  - ☑ `engagement.py` — per-person state machine, windows, thresholds, QR trigger
  - ☑ `zone.py` — soft engagement-zone confidence
  - ☑ `classifier.py` — EngagementNet load + classify (verified vs real trained weights)
- ☑ `vision/` glue: detector (YOLO), face (MediaPipe), pose (MediaPipe)
- ☑ `capture.py` — video source (USB/RTSP/**file**) with auto-reconnect
- ☑ `pipeline.py` — `EngagementPipeline` orchestrating the 7 layers, **returns data, draws nothing**
- ☑ `viewer.py` — optional OpenCV debug window (`--debug`), separate from the service
- ☑ `service.py` — headless run loop, **no `input()`, no `imshow`** (CLI: `--config`, `--debug`)
- ☑ `build.py` — wires DeviceConfig → ready EngagementPipeline
- ☑ Run as OS service: systemd unit + install script (Linux) + NSSM guide (Windows), auto-restart — see `edge/deploy/` *(install on real box pending)*
- ☑ Test fixture: recorded clip (45s, 1280x720) → pipeline runs headless against it
- ☑ Unit tests (38 total: pure logic + capture via synthetic video + pipeline via fakes)

### Clip verification findings (real footage)
- ☑ **Fixed a real product bug**: the ghost filter permanently blacklisted any
  track that showed no face in its first ~20 frames. A customer who approaches
  with their back turned and only later looks at the display was killed early
  and never recovered (engaged=0). Replaced the permanent veto with a
  *confirm-on-first-face* model (`ghost_recheck_every`): a track is counted only
  once a face confirms it's a person, and unconfirmed tracks keep being checked
  forever. Chairs (never a face) still never count. Verified: engaged 0 → 1.
- ☑ File playback now uses **video time** (frame/fps) for attention, not wall clock.
- ☐ Known, deferred: YOLO track-id instability counts one person as ~2 passersby
  (re-identification). Note for Phase 5 hardening.
- ☐ Known, deferred: MediaPipe finds a face ~54% of frames when subject is very
  close / filling the frame — revisit head-crop logic for close range.

## Phase 2 — Data contract + uplink (Weeks 3–4)
- ☑ `shared/schema.py` — the edge↔cloud contract (heartbeat + metric bucket) *(done early)*
- ☐ `emitter.py` — builds buckets (evolves current write_*_json)
- ☐ `uplink.py` — HTTPS POST + **offline buffer (SQLite) with retry + idempotency**

## Phase 3 — Minimal backend on the VM (Weeks 4–6)
- ☐ `cloud/` docker-compose: ingest API + worker + Postgres + Caddy (HTTPS)
- ☐ Multi-tenant schema day 1: `org → store → device → camera`, users/roles, `org_id` on every query
- ☐ One real test store sending live data to the VM
- ☐ Device provisioning: generate `device_id` + `api_key`

## Phase 4 — Minimal SaaS dashboard (Weeks 6–8)
- ☐ Web app: login, store selector, date range
- ☐ Live + historical views (day/week), business language (no yaw/pitch jargon)
- ☐ Fleet health panel (devices online, FPS, last metric)

## Phase 5 — Harden + validate 2nd store (Weeks 8–10)
- ☐ Install in a 2nd real store (different camera/lighting) — *model generalization truth surfaces here*
- ☐ Tune FOV/thresholds per camera via `device.yaml`
- ☐ Polish service start, camera reconnection, crash recovery

---

## Deferred until after August (scope discipline)
Stripe/billing · OTA auto-updates · self-service multi-tenant signup · model retrain from scratch.

## Human-in-the-loop (what only the founder can do)
- Provide a **recorded test clip** so Claude can verify the pipeline without a live camera.
- Run commands on Txema's VM (founder pastes output) — *Phase 3, not before*.
- Physically install the edge box + run calibration in real stores.
