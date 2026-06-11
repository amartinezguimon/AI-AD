# QUICKSTART — run the edge agent live (laptop + webcam)

A 5-minute local test of the VisionMetrics edge agent on a laptop, using the
built-in webcam or a phone-as-webcam (Camo Studio). This is **not** a production
install (that's a store box with a fixed camera) — it's to see the pipeline
detect, count, and score engagement live.

> Works on macOS, Windows, and Linux. On Apple-Silicon Macs it runs noticeably
> faster (PyTorch uses the GPU). On a CPU-only laptop it still runs at ~5–10 fps,
> which is plenty for retail analytics.

## 1. Prerequisites
- **Python 3.10+** — check with `python3 --version`.
- **Git**.
- *(Optional)* **Camo Studio** if you want to use your iPhone as the camera.
  Open the app and connect the phone before starting.

## 2. Get the code
```bash
git clone https://github.com/amartinezguimon/AI-AD.git
cd AI-AD
git checkout refactor/monorepo-edge-agent
```

## 3. Install
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Find your camera index
With your webcam (or Camo Studio) ready:
```bash
python src/utils/check_cameras.py
```
Note the index it reports (often `0` = built-in webcam, `1` = Camo — or the
reverse).

## 5. Create your config
Create `visionmetrics/edge/config/device.yaml` (this file is git-ignored, so it's
yours to edit). Set `source` to the index from step 4:
```yaml
device:
  device_id: "test-laptop"
  store_id: "test"
  store_name: "Live test"

camera:
  source: 0            # <-- index from check_cameras.py
  fov_h_deg: 70.0      # ~70 for a webcam / iPhone via Camo

calibration:
  config_path: null    # no zone filter — the classifier decides

uplink:
  enabled: false       # local only; nothing is sent anywhere
```

## 6. Run (with the debug window)
```bash
python -m visionmetrics.edge.agent.service --config visionmetrics/edge/config/device.yaml --debug
```
- **First run** downloads a couple of model files automatically (YOLO + MediaPipe) — give it a minute.
- A window opens showing the video, person boxes, and live counters
  (passersby / engaged / attention).
- **Quit** with `q` on the window, or `Ctrl-C` in the terminal. A summary
  (total passersby, engaged, attention, QR triggers) prints on exit.

## 7. What to try
- **Walk past without looking** → counts as a *passerby*, not *engaged*.
- **Stop and look at the camera** for a few seconds → flips to *engaged*, attention climbs.
- **Two people close together / hugging while looking** → check the boxes stay
  sane and engaged doesn't flicker (this was a fixed bug — worth re-checking live).

## Troubleshooting
- **Black window / no camera (macOS):** the first time, grant the Terminal camera
  access in System Settings → Privacy & Security → Camera, then re-run.
- **Camo not found:** make sure Camo Studio is open *before* launching, then
  re-run `check_cameras.py`.
- **Numbers look off:** remember this is a head-on webcam, not a store camera
  beside a display — the geometry differs, so the *counts* are for sanity-checking
  that it works, not real metrics.
