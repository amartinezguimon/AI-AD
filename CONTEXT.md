# VisionMetrics AI — Project Context

> Keep this file updated after every code change. Read this instead of re-scanning source files.

---

## Run Commands (from project root)
```bash
python src/utils/calibrate.py          # one-time per store setup
python src/inference/main.py           # live analysis
python src/training/train.py           # retrain PyTorch model
python src/training/data_collector.py  # collect labelled training data
python -m http.server 8080             # serve dashboard + ad screen at localhost:8080
```

---

## File Map

| File | Purpose |
|---|---|
| `src/inference/main.py` | Main 7-layer pipeline (optimised for many people) |
| `src/inference/main_original.py` | Backup of main.py before performance optimisation |
| `src/utils/calibrate.py` | One-time per-store calibration wizard |
| `src/training/train.py` | PyTorch MLP trainer |
| `src/training/data_collector.py` | Live data labelling (L=look, A=away, T=toggle auto) — uses same YOLO+4x pipeline as main.py |
| `models/engagement_model.pth` | Trained PyTorch weights |
| `models/face_landmarker.task` | MediaPipe face model (auto-downloaded) |
| `models/pose_landmarker_lite.task` | MediaPipe pose model (auto-downloaded) |
| `yolov8n.pt` | YOLO weights |
| `data/engagement_data.csv` | ~20,600 labelled rows (yaw, pitch, distance, label) |
| `data/live_stats.json` | Live session metrics for dashboard |
| `configs/store_config.json` | Per-store calibration output |
| `dashboard.html` | Chart.js live analytics dashboard |
| `ad_screen.html` | Customer-facing ad screen with QR overlay (Screen 2 in demo) |
| `data/qr_discount.png` | Static QR code encoding `https://visionmetrics.ai/discount/20` |

---

## Architecture (main.py — 7 layers)

1. **YOLOv8** — detect & track persons, assign IDs
2. **Head crop + 4x upscale** — top 45% of YOLO bbox + 30px pad, upscaled 4x before MediaPipe (enables detection at 4m+)
3. **MediaPipe Face** — cheekbone landmarks 234/454 for yaw (glasses-safe); 1(nose), 10(top), 152(chin) for pitch
4. **PyTorch EngagementNet** — MLP 3→16→8→1+Sigmoid; input: (yaw, pitch, face_width_normalized)
5. **MediaPipe Pose** — shoulder span → `torso_conf`; nose vs shoulder midpoint → `rel_yaw`
6. **Soft zone filter** — `zone_confidence()` returns [0,1] multiplier, decays over 0.30 units outside boundary
7. **Frame buffer** — last 3 frames, ≥1 needed to count as engaged

**Final probability formula:**
```
engage_prob = pytorch_prob × torso_weight × zone_conf
torso_weight = 0.40 + 0.60 × torso_conf
engaged = engage_prob >= 0.50
```

---

## Key Constants (main.py)

```python
CAMERA_FOV_H_DEG  = 70.0   # pinhole camera model FOV
FACE_WIDTH_M      = 0.16   # average face width in metres
YOLO_CONF_MIN     = 0.45
ASPECT_RATIO_MIN  = 0.75   # CRITICAL: keep at 0.75 — lower values cause ghost detections
GHOST_FRAME_TRIAL = 20     # frames before non-face track is blacklisted
FRAME_BUFFER_SIZE = 3
FRAME_ENGAGE_MIN  = 1
TORSO_NEUTRAL_SPAN = 0.40
POSE_ENABLED      = True   # set False to save ~150ms/frame per person
POSE_SKIP_FRAMES  = 8      # run pose every 8 frames per person
FACE_SKIP_FRAMES  = 3      # run MediaPipe face every 3 frames per person
REWARD_THRESHOLD_S = 5.0
QR_DURATION_S     = 10.0   # seconds QR stays visible on ad_screen.html
SOFT_MARGIN       = 0.30   # zone_confidence decay width
```

---

## Camera Model (pinhole)

```python
_focal_px = (w/2) / tan(radians(CAMERA_FOV_H_DEG/2))   # computed on first frame
face_w_orig_px = distance * (rx2 - rx1)                  # distance = normalised face_width
dist_m = clip(FACE_WIDTH_M * focal_px / face_w_orig_px, 0.1, 8.0)
```

- `dist_m` used in zone filter distance gate
- `distance` (normalised) still fed to PyTorch (model was trained on it — do not change)

---

## Calibrate.py Pipeline

1. YOLO finds person (largest bbox = closest)
2. Crop head (top 45%) + 4x upscale → MediaPipe (same as main.py, far-distance capable)
3. Fallback: 3x full-frame upscale if YOLO finds nobody
4. Pose on full frame for live `rel_yaw` display during calibration
5. Saves `dist_close_m`, `dist_far_m` (metres) and `derived.dist_max_m` to `store_config.json`

---

## Debug HUD Format

```
Yaw:+0.02 Pitch:-0.00 Dist:2.4m  Torso:87% R-Yaw:+0.04
PyTorch:78%  Zone:75%  Buf:2/3
```

`Zone:%` is the soft zone confidence (was YES/NO before — caused flicker at boundaries).

---

## Critical Bug Fixed

`calibrate.py` previously used **eye corners** (landmarks 33, 263) for yaw.
`main.py` uses **cheekbones** (234, 454).
This caused systematic zone mismatch — calibrated boundaries didn't match inference angles.
**Both now use cheekbones. Must re-calibrate any existing store_config.json.**

---

## Professor Feedback — Status

| Feedback | Status |
|---|---|
| "Second pass, recortar" | ✅ head crop + 4x upscale in main.py |
| "Redes para false positives" | ✅ ghost track via MediaPipe, conf+aspect ratio filters |
| "Projective perspective" | ✅ pinhole camera model, dist_m in metres |
| "Ángulo torso menos cuello" | ✅ rel_yaw from Pose landmark 0 vs shoulder midpoint |
| "Vida real → camera model" | ✅ focal_px from FOV, dist_m computed each frame |

---

## Training Data

- ~20,600 rows: (yaw, pitch, distance, label)
- Augmented 4× with synthetic far-distance samples (distance scaled by 0.6, 0.35, 0.15)
- 80/20 train/test split, Adam lr=0.005, 50 epochs, BCE loss

---

## 3-Screen Demo Setup

| Screen | URL / Window | Audience |
|---|---|---|
| Screen 1 | `python src/inference/main.py` (OpenCV window) | Operator / professor |
| Screen 2 | `localhost:8080/ad_screen.html` | Customer-facing ad with QR overlay |
| Screen 3 | `localhost:8080/dashboard.html` | Manager / analytics |

**QR trigger:** when any person crosses 5s engagement, `_qr_active_until = now + 10s` is written to `live_stats.json`. ad_screen.html polls every 1s and fades the QR in/out. Only one QR active at a time regardless of how many people are engaged.  
**Re-trigger in demo:** step fully out of frame (new track ID) + wait 10s cooldown, then look again for 5s.  
**Browser on same laptop costs ~1fps** — use a second device on same WiFi for best performance.

---

## Dashboard (dashboard.html)

Run via: `python -m http.server 8080` → `localhost:8080/dashboard.html`  
**Do NOT open as file:// — fetch() is blocked by browser CORS.**

Sections:
1. KPI cards (live, 1s refresh)
2. Live engagement rate timeline (1s refresh, last 60 points)
3. Hourly bar chart — fetches `data/hourly_log.json` every 60s, filters to today, highlights current hour
4. Weekly comparison table — fetches `data/session_history.json` every 60s

Weekly table logic:
- **Today vs last week same day**: "today so far" vs "last week until same hour" (fair apple-to-apple) + "last week full day" column
- **This week vs last week**: Mon–today summed vs same days last week

New data files written by main.py:
- `data/live_stats.json` — written every 30 frames; includes `qr_active_until` Unix timestamp for ad_screen.html
- `data/hourly_log.json` — appended each time clock hour changes: `{hour, date, engaged, passersby, rate, attention_s}`
- `data/session_history.json` — appended at session end: `{date, store, start_iso, end_iso, duration_min, passersby, engaged, rate, attention_s}`
- `data/session_log.csv` — same as session_history but CSV backup

## Performance Notes

- Tested with Camo Studio virtual camera (phone via USB) at 720p. Realistic throughput: ~3fps with 1-2 people on CPU-only laptop.
- **Fix 1:** `FACE_SKIP_FRAMES=3` — face angles cached and reused every 3 frames per person.
- **Fix 2:** `POSE_SKIP_FRAMES=8` — pose/torso cached every 8 frames per person (pose changes over seconds, not frames).
- **Fix 3:** `_FrameReader` background thread — continuously drains Camo's camera buffer so main loop always gets the newest frame. Without this, 700ms processing × 30fps camera = 21-frame backlog causing severe stalls.
- **Critical:** keep `ASPECT_RATIO_MIN=0.75`. Lowering it (e.g. to 0.40) causes wide background objects to pass the YOLO filter, triggering MediaPipe on ghost detections and halving FPS.
- **Demo tip:** run browser tabs (dashboard + ad screen) on a second device at `http://YOUR_IP:8080/` — Chrome on the same laptop competes for CPU and costs ~1fps.
- To check real camera FPS: `python -c "import cv2; cap=cv2.VideoCapture(2); print(cap.get(cv2.CAP_PROP_FPS)); cap.release()"`.
- Production scaling options: (a) record video then process offline, (b) run on GPU server.

---

## Visual Upgrades Status (DEMO_UPGRADES_PLAN.md)

| Item | Status |
|---|---|
| #1 Reward overlay banner (operator screen) | ❌ Dropped — operator screen not part of real product |
| #2 Engagement duration ring | Pending |
| #3 Gaze direction arrow | Pending |
| #4 Engagement tier labels HIGH/MED/LOW | ✅ Complete |
| #5 Sound cue on reward | Pending |
| #6 Customer-facing ad screen + QR | ✅ Complete |

---

## Remaining TODO

- [ ] **Re-calibrate** — existing store_config.json used eye landmarks, must redo
- [ ] **Executive Report** — 5000+ words (35% of grade)
- [ ] **Presentation** — slides + demo (25% of grade)
- [ ] **Tune SOFT_MARGIN** — increase if zone still too strict for different-height people
