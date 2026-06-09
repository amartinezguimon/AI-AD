# fixtures/ — test footage for offline verification

Drop a short recorded clip here (e.g. `test_store.mp4`) so the edge agent can be
run and verified without a live camera. Video files are git-ignored (they're
large and local-only); this README is tracked so the folder exists.

## How to record a good test clip (30–60 s)
Record however is easiest — Camo Studio's own recording, QuickTime, or your
phone — and export an `.mp4`. Aim to capture:

- you walking **up and looking at the camera** for ~6+ seconds (so it counts as
  engaged and fires the QR trigger at 5 s),
- looking **away / to the sides** (should read as not engaged),
- walking **away / out of frame**,
- if possible, **someone passing by in the background** without looking
  (tests the "passerby, not engaged" path).

Save it as `fixtures/test_store.mp4` (or edit `camera.source` in your
`device.yaml` to match the filename you used).

## Then run
```bash
python -m visionmetrics.edge.agent.service \
    --config visionmetrics/edge/config/device.yaml --debug
```
The `--debug` window shows detections; the console prints passersby / engaged
counts. Tell Claude once the clip is in place and it will verify the numbers.
