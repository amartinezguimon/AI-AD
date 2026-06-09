# visionmetrics/ — the product codebase

This is the productized monorepo that the prototype (`../src`, frozen) is being
migrated into. See [`../ROADMAP.md`](../ROADMAP.md) for the plan and status.

## Layout

```
visionmetrics/
├── edge/                     # runs in the store, on the edge box
│   ├── agent/
│   │   ├── geometry.py       # head-pose angles (shared, was duplicated)
│   │   ├── camera_model.py   # pinhole distance model
│   │   ├── zone.py           # soft engagement-zone confidence
│   │   ├── engagement.py     # per-person state machine (windows, counting, QR)
│   │   ├── classifier.py     # PyTorch EngagementNet load + scoring
│   │   ├── config.py         # typed loader for device.yaml
│   │   ├── capture.py        # video source: USB / RTSP / file, auto-reconnect
│   │   ├── vision/           # YOLO + MediaPipe wrappers (detector/face/pose)
│   │   ├── pipeline.py       # EngagementPipeline: 7 layers, draws nothing
│   │   ├── build.py          # DeviceConfig -> wired pipeline
│   │   ├── viewer.py         # optional debug overlay (separate from pipeline)
│   │   └── service.py        # headless run loop (entry point), no input()/imshow
│   ├── config/device.example.yaml   # copy to device.yaml per install
│   └── deploy/               # systemd unit / installer / Windows (NSSM) guide
├── cloud/                    # runs on the server VM (ingest, api, worker) — TODO
├── web/                      # SaaS dashboard — TODO
├── shared/schema.py          # the edge<->cloud data contract (single source of truth)
└── tests/                    # pure-logic unit tests (no camera/models needed)
```

## Design rules
1. **The pipeline draws nothing and does no I/O** — it consumes a frame and
   returns data. Drawing, metric emission and the run loop are separate.
2. **Everything per-camera/per-store lives in `device.yaml`,** never hardcoded.
3. **Vision components are dependency-injected** so the orchestration is testable
   with fakes — no camera, no models, no GPU.
4. **Video never leaves the store** — only anonymous aggregate metrics.

## Running

```bash
# Run the agent (foreground; --debug shows a preview window)
python -m visionmetrics.edge.agent.service --config <device.yaml> --debug

# Run the test suite (after: pip install -e ".[dev]")
pytest
```
