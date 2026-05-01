# VisionMetrics AI

> **Privacy-preserving computer vision for real-world advertisement engagement analytics.**

VisionMetrics measures how people interact with physical advertisements (store windows, jewelry displays, product vitrinas) using a camera-based AI pipeline. It tracks foot traffic, attention time, gaze direction, and triggers live interactions — all without storing any images or identifying individuals.

---

## Architecture — 7-Layer Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Camera Feed                                                     │
│      ↓                                                           │
│  Layer 1: YOLOv8 ──────────── Detect & track persons by ID      │
│      ↓                                                           │
│  Layer 2: Head Crop + 4× Upscale ── Enable detection at 4m+     │
│      ↓                                                           │
│  Layer 3: MediaPipe Face ──── Extract yaw, pitch, distance       │
│      ↓                                                           │
│  Layer 4: PyTorch MLP ─────── Classify Engaged vs Away           │
│      ↓                                                           │
│  Layer 5: MediaPipe Pose ──── Torso orientation (walk-by filter) │
│      ↓                                                           │
│  Layer 6: Soft Zone Filter ── Calibrated engagement boundaries   │
│      ↓                                                           │
│  Layer 7: Frame Buffer ────── Temporal smoothing (3-frame vote)  │
│      ↓                                                           │
│  Analytics HUD + Live Dashboard                                  │
└─────────────────────────────────────────────────────────────────┘
```

### What It Measures
1. **Foot Traffic** — Count of unique people passing the display.
2. **Attention Time** — Duration each person spent looking at the display.
3. **Engagement Classification** — Real-time Engaged/Away status per person.
4. **Gaze Accuracy** — Quantitative yaw/pitch metrics on head orientation.

---

## Project Structure

```
├── src/
│   ├── inference/
│   │   ├── main.py              # Full 7-layer live inference pipeline
│   │   └── detect.py            # Standalone YOLO detection helper
│   ├── training/
│   │   ├── data_collector.py    # Live data labelling tool
│   │   ├── train.py             # PyTorch MLP trainer (produces engagement_model.pth)
│   │   └── train_report.py      # Evaluation script — reproduces all metrics & figures
│   └── utils/
│       ├── calibrate.py         # Per-store calibration wizard
│       └── check_cameras.py     # Lists available camera indices
│
├── models/
│   └── engagement_model.pth     # Trained PyTorch weights (included — ready to run)
│
├── configs/
│   └── store_config_template.json  # Example store calibration config
│
├── data/
│   └── engagement_data.csv      # 1,127 labelled rows (real, no augmentation)
│
├── dashboard.html               # Chart.js live analytics dashboard
├── ad_screen.html               # Customer-facing ad/QR screen
├── requirements.txt             # Python dependencies
└── .gitignore
```

---

## Three Runnable Components

Run all three together for the full demo:

**Terminal 1 — AI engine (required for everything below)**
```bash
python src/inference/main.py
```
On startup, the engine checks for a saved calibration and prompts:
- **`[1]` Use saved calibration** — recommended, uses the stored engagement zone
- **`[2]` Skip calibration** — runs the PyTorch model only, no zone filter
- **`[3]` Create new calibration** — quit and run `python src/utils/calibrate.py` first

If no calibration file exists, it skips automatically and runs with the PyTorch model only.

**Terminal 2 — Web server (required for dashboard and ad screen)**
```bash
python -m http.server 8080
```

Then open two browser tabs:

| # | What it does | URL |
|---|---|---|
| 1 | **Live Dashboard** — real-time analytics, charts, foot traffic | `http://localhost:8080/dashboard.html` |
| 2 | **Ad Screen** — customer-facing display, QR overlay triggers after 5s engagement | `http://localhost:8080/ad_screen.html` |

> Do NOT open the HTML files directly from your file system (`file://`) — use the URLs above or `fetch()` will be blocked by the browser.

All three work after the Quick Start setup below (install once, then run).

---

## Prerequisites

- **Python 3.10+**
- **Camera** — Laptop webcam, USB webcam, or iPhone (via [Iriun Webcam](https://iriun.com/))
- **Internet** — Required on first run only (to auto-download YOLOv8 and MediaPipe models)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/amartinezguimon/AI-AD.git
cd AI-AD

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the live system (models auto-download on first run)
python src/inference/main.py
```

> **First time?** Follow the Quick Start steps above. Change `CAMERA_INDEX = 0` in `src/inference/main.py` if the default camera does not open.

---

## Usage

### Live Inference
```bash
python src/inference/main.py
```
**Controls** (click the video window first):
| Key | Action |
|-----|--------|
| `T` | Toggle Training Mode |
| `L` | Label current frame as **LOOK** (training mode) |
| `A` | Label current frame as **AWAY** (training mode) |
| `Q` | Quit and save |

### Calibration (once per store/location)
```bash
python src/utils/calibrate.py
```
Follow the on-screen prompts to define the engagement zone boundaries.

### Training
```bash
# Collect labelled data
python src/training/data_collector.py

# Train the PyTorch model
python src/training/train.py
```

### Reproduce Results (Evaluation Metrics & Figures)
```bash
python src/training/train_report.py
```
Generates under `figures/` (created automatically): training/validation loss curves, confusion matrix, ROC curve, per-distance accuracy bar chart, `metrics.json`, and `classification_report.txt`.

The test set (226 rows) is held out from **real rows only** before any augmentation, preventing data leakage. Expected results: accuracy ~99.6%, F1 ~0.996, ROC-AUC ~0.999.

### Live Dashboard
```bash
# Terminal 1: Start the web server
python -m http.server 8080

# Terminal 2: Run the AI engine
python src/inference/main.py
```
Then open **http://localhost:8080/dashboard.html** in your browser.

> Do NOT open `dashboard.html` as a `file://` URL — `fetch()` will be blocked by browser CORS policy.

### Customer Ad Screen
```bash
python -m http.server 8080
```
Open **http://localhost:8080/ad_screen.html** on a second screen facing the customer. When a person stays engaged for 5 seconds, `main.py` triggers the QR discount overlay automatically on this screen.

---

## Camera Setup

| Camera | Quality | Range | Setup |
|--------|---------|-------|-------|
| iPhone (via Iriun/Camo) | ⭐⭐⭐⭐⭐ | Up to 4m | Download Iriun app, connect via Wi-Fi |
| USB Webcam (Logitech C920) | ⭐⭐⭐⭐ | Up to 3m | Plug in USB |
| Laptop Webcam | ⭐⭐ | Up to 1.5m | No setup needed |

Change `CAMERA_INDEX` in `src/inference/main.py` if using an external camera (typically `1` or `2`).  
Run `python src/utils/check_cameras.py` to discover available camera indices.

---

## Privacy & GDPR Compliance

VisionMetrics is built on **Privacy by Design** principles:
- ❌ No images or video are ever saved to disk
- ❌ No facial recognition or biometric identity processing
- ❌ No individual behavioural histories retained
- ✅ All processing is local (edge-only, no cloud)
- ✅ Only anonymous aggregate metrics are exported

The system processes only anonymous geometric data (head angles) and never stores images, video, or biometric identifiers.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Person Detection & Tracking | YOLOv8 (Ultralytics) |
| Head Pose Estimation | MediaPipe Face Landmarker |
| Body Orientation | MediaPipe Pose Landmarker |
| Engagement Classifier | PyTorch (custom MLP) |
| Live Dashboard | HTML + Chart.js |
| Camera Interface | OpenCV |
