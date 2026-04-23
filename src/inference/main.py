"""
main.py — VisionMetrics AI: The Grand Integrator
-------------------------------------------------
PURPOSE:
    This is the final, complete system. It orchestrates all components:

    Layer 1: YOLOv8         → Detects and TRACKS each person by a unique ID.
    Layer 2: MediaPipe      → Extracts real-time head angles (Yaw, Pitch, Distance).
    Layer 3: PyTorch Brain  → Classifies if the person is "Engaged" or "Not Engaged".
    Layer 4: Store Config   → Defines the physical boundaries of THIS store's display.
    Layer 5: Analytics HUD  → Displays live metrics on screen.
    Layer 6: Reward Trigger → Fires a live "discount" overlay after 5 seconds of engagement.

HOW TO RUN:
    python src/inference/main.py

REQUIREMENTS:
    - Run src/training/data_collector.py first to collect data.
    - Run src/training/train.py next to generate the AI brain.
    - (Optional) Run src/utils/calibrate.py to generate a store-specific config.
"""

import csv
import cv2
import json
import os
import time
import threading
import numpy as np
import torch
import torch.nn as nn
import urllib.request
import mediapipe as mp
from datetime import datetime
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO

# ═══════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CAMERA_INDEX       = 2          # Change to 0 for laptop webcam
MODEL_YOLO_PATH    = "yolov8n.pt"
MODEL_FACE_PATH    = "models/face_landmarker.task"
MODEL_POSE_PATH    = "models/pose_landmarker_lite.task"
MODEL_ENGAGE_PATH  = "models/engagement_model.pth"
STORE_CONFIG_PATH  = "configs/store_config.json"
SESSION_LOG_PATH   = "data/session_log.csv"
REWARD_THRESHOLD_S = 5.0        # Seconds of engagement before reward triggers
CAMERA_FOV_H_DEG  = 70.0       # Horizontal FOV (degrees) — typical webcam / smartphone
FACE_WIDTH_M      = 0.16       # Average adult face width in metres (pinhole model)
os.makedirs("data",   exist_ok=True)
os.makedirs("models", exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# SECTION 2: THE PYTORCH NEURAL NETWORK (must match train.py)
# ═══════════════════════════════════════════════════════════════
class EngagementNet(nn.Module):
    def __init__(self):
        super(EngagementNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(3, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 1),  nn.Sigmoid()
        )
    def forward(self, x):
        return self.network(x)


# ═══════════════════════════════════════════════════════════════
# SECTION 3: SYSTEM STARTUP — Load all AI brains and configs
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("  VISIONMETRICS AI — Retail Engagement System")
print("="*60)

# -- Download face model if needed --
if not os.path.exists(MODEL_FACE_PATH):
    print("⬇️  Downloading Face Landmarker model (one-time)...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/face_landmarker"
        "/face_landmarker/float16/latest/face_landmarker.task",
        MODEL_FACE_PATH
    )

# -- Load YOLO (Person Detector + Tracker) --
print("🔍 Loading YOLOv8 person detector...")
yolo_model = YOLO(MODEL_YOLO_PATH)

# -- Load MediaPipe (Face Angle Extractor) --
print("🧩 Loading MediaPipe Face Landmarker...")
base_opts   = python.BaseOptions(model_asset_path=MODEL_FACE_PATH)
face_opts   = vision.FaceLandmarkerOptions(
    base_options=base_opts, num_faces=3,
    min_face_detection_confidence=0.25,   # Lowered to detect faces at 4m+
    min_face_presence_confidence=0.25,
)
face_detector = vision.FaceLandmarker.create_from_options(face_opts)

# -- Load MediaPipe Pose (Torso Angle Estimator) --
print("🦾 Loading MediaPipe Pose estimator (torso angle)...")
if not os.path.exists(MODEL_POSE_PATH):
    print("⬇️  Downloading Pose Landmarker model (one-time)...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
        MODEL_POSE_PATH
    )

pose_opts = python.BaseOptions(model_asset_path=MODEL_POSE_PATH)
pose_options = vision.PoseLandmarkerOptions(
    base_options=pose_opts,
    num_poses=1,
    min_pose_detection_confidence=0.4,
    min_pose_presence_confidence=0.4,
)
pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

# -- Load PyTorch Engagement Classifier --
print("🧠 Loading PyTorch Engagement Brain...")
if not os.path.exists(MODEL_ENGAGE_PATH):
    print(f"❌ ERROR: {MODEL_ENGAGE_PATH} not found! Please run train.py first.")
    exit()

engage_model = EngagementNet()
engage_model.load_state_dict(torch.load(MODEL_ENGAGE_PATH, weights_only=True))
engage_model.eval()

# -- Load Store Config (for engagement zone boundaries) --
store_config  = None
engagement_zone = None
if os.path.exists(STORE_CONFIG_PATH):
    with open(STORE_CONFIG_PATH, "r") as f:
        _raw = json.load(f)
    _name = _raw.get("store_name", "Unknown")
    print(f"\n📁 Found saved calibration: '{_name}'")
    print("   [1] Use this calibration")
    print("   [2] Skip calibration (PyTorch only, no zone filter)")
    print("   [3] Create new calibration (quit and run: python src/utils/calibrate.py)")
    _choice = input("\n   Your choice (1/2/3): ").strip()
    if _choice == "1":
        store_config    = _raw
        engagement_zone = _raw.get("derived")
        print(f"✅ Using calibration: '{_name}'")
    elif _choice == "3":
        print("\n   Run:  python src/utils/calibrate.py")
        print("   Then re-run main.py.\n")
        exit()
    else:
        print("⚠️  Skipping calibration. Using PyTorch model only (no zone filtering).")
else:
    print("⚠️  No store config found. Using PyTorch model only (no zone filtering).")
    print("   Run src/utils/calibrate.py to create a store-specific config.")

# -- Open Camera --
print(f"📷 Opening camera {CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"❌ Camera {CAMERA_INDEX} not found. Try changing CAMERA_INDEX.")
    exit()

_cam_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
_cam_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
_cam_fps = cap.get(cv2.CAP_PROP_FPS)
print(f"📐 Camera resolution: {_cam_w}x{_cam_h} @ {_cam_fps:.0f}fps")
print("\n✅ ALL SYSTEMS GO. Starting live analysis...\n")


# ═══════════════════════════════════════════════════════════════
# SECTION 4: HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def extract_face_angles(landmarks):
    """
    Glasses-resistant head pose extraction.
    Uses CHEEKBONE landmarks (234=left, 454=right) as the scale reference
    instead of eye corners, so glasses/sunglasses never interfere.
    """
    nose    = landmarks[1]
    top     = landmarks[10]
    chin    = landmarks[152]
    l_cheek = landmarks[234]   # left face edge (glasses-safe)
    r_cheek = landmarks[454]   # right face edge (glasses-safe)

    face_mid_x = (l_cheek.x + r_cheek.x) / 2
    face_width = abs(r_cheek.x - l_cheek.x)
    yaw        = (nose.x - face_mid_x) / (face_width + 1e-6)

    face_mid_y = (l_cheek.y + r_cheek.y) / 2
    face_h     = abs(chin.y - top.y)
    pitch      = (nose.y - face_mid_y) / (face_h + 1e-6)

    return yaw, pitch, face_width   # face_width as distance proxy


def zone_confidence(yaw, pitch, distance, zone, dist_m=None):
    """
    Soft zone multiplier in [0.0, 1.0] instead of a hard YES/NO gate.

    Returns 1.0 when well inside the calibrated zone and decays smoothly
    as angles drift outside the boundary.  This prevents the binary
    flicker that occurred when different-height people sat right at the
    zone edge (PyTorch 100% but Zone:NO → counted as AWAY).

    Distance is still a hard cutoff — someone 6m away is never a customer.
    """
    if zone is None:
        return 1.0

    # Distance: hard cutoff with a 20 % buffer beyond the calibrated far limit
    if dist_m is not None and zone.get("dist_max_m") is not None:
        if dist_m > zone["dist_max_m"] * 1.2:
            return 0.0
    elif distance < zone.get("dist_min", 0) * 0.8:
        return 0.0

    # Soft angle penalty: how far outside each boundary are we?
    yaw_excess   = max(0.0, zone["yaw_min"] - yaw,   yaw   - zone["yaw_max"])
    pitch_excess = max(0.0, zone["pitch_min"] - pitch, pitch - zone["pitch_max"])

    # Decay factor: 1 unit outside → conf = 0.  Tune divisor to widen the soft margin.
    # 0.30 means the soft edge extends ~0.30 normalised yaw units beyond the hard boundary.
    SOFT_MARGIN = 0.30
    conf = max(0.0, 1.0 - (yaw_excess + pitch_excess) / SOFT_MARGIN)
    return conf


def classify_with_pytorch(yaw, pitch, distance):
    """
    Pass angles to trained PyTorch model.
    DISTANCE-SCALED THRESHOLD: people far away (small face_width) require
    a higher confidence score before being counted as 'engaged'.
    This eliminates false positives from distant passers-by.
    """
    with torch.no_grad():
        x = torch.tensor([[yaw, pitch, distance]], dtype=torch.float32)
        prob = engage_model(x).item()

    # Flat 0.50 threshold — simpler and more reliable for now
    required_confidence = 0.50

    return prob, prob >= required_confidence


# ── TORSO ANGLE HELPER ────────────────────────────────────────────
# Tuning constants — adjust if needed:
TORSO_NEUTRAL_SPAN = 0.40   # Expected l_shoulder.x - r_shoulder.x when facing camera
TORSO_MIN_VIS      = 0.40   # Minimum MediaPipe landmark visibility to trust the result
POSE_ENABLED       = True   # Set False to disable torso angle (saves ~150ms/frame per person)
POSE_SKIP_FRAMES   = 8      # Only run pose every N frames (performance optimisation)
_pose_frame_count  = {}
FACE_SKIP_FRAMES   = 3      # Only run MediaPipe face every N frames per person
_face_cache        = {}     # track_id → {idx, yaw, pitch, distance, dist_m}

def get_torso_confidence(frame_bgr, track_id, x1, y1, x2, y2, frame_idx):
    """
    Estimates how directly the person's TORSO faces the camera and the
    relative angle between the neck and torso axis (professor feedback #4).

    Returns:
        torso_conf (float):  1.0 = torso faces camera squarely, 0.0 = sideways.
        span (float|None):   raw shoulder span for debug display.
        rel_yaw (float|None): (nose_x − shoulder_mid_x) / shoulder_span.
                              Near 0 = head aligned with torso.
                              Positive = head turned right relative to body.
                              Use this during calibration for a camera-position-
                              independent engagement signal.
    """
    _fallback = (1.0, None, None)

    last = _pose_frame_count.get(track_id, {"idx": -999, "result": _fallback})
    if frame_idx - last["idx"] < POSE_SKIP_FRAMES:
        return last["result"]

    if pose_detector is None:
        return _fallback

    crop = frame_bgr[max(0, y1):min(frame_bgr.shape[0], y2),
                     max(0, x1):min(frame_bgr.shape[1], x2)]
    if crop.size == 0:
        return _fallback

    rgb    = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res    = pose_detector.detect(mp_img)

    if not res.pose_landmarks:
        _pose_frame_count[track_id] = {"idx": frame_idx, "result": _fallback}
        return _fallback

    lm  = res.pose_landmarks[0]
    l_s = lm[11]  # LEFT_SHOULDER
    r_s = lm[12]  # RIGHT_SHOULDER

    if l_s.visibility < TORSO_MIN_VIS or r_s.visibility < TORSO_MIN_VIS:
        _pose_frame_count[track_id] = {"idx": frame_idx, "result": _fallback}
        return _fallback

    # Shoulder span: positive & large when facing camera, near 0 when sideways.
    span       = l_s.x - r_s.x
    torso_conf = max(0.0, min(span, TORSO_NEUTRAL_SPAN)) / TORSO_NEUTRAL_SPAN

    # Relative neck-to-torso yaw (professor feedback: torso angle − neck angle).
    # Pose landmark 0 is the nose — same crop space as the shoulders.
    shoulder_mid_x = (l_s.x + r_s.x) / 2.0
    nose_lm        = lm[0]
    rel_yaw = (nose_lm.x - shoulder_mid_x) / (abs(span) + 1e-6) if abs(span) > 0.02 else None

    out = (torso_conf, span, rel_yaw)
    _pose_frame_count[track_id] = {"idx": frame_idx, "result": out}
    return out




def write_live_stats(session_s, passersby, engaged, active_ids, store, qr_active_until=0.0):
    """Write current session metrics to a JSON file for the live dashboard."""
    currently_engaged = sum(
        1 for tid in active_ids
        if person_engagement.get(tid, {}).get("currently_engaged", False)
    )
    total_attention_s = sum(
        person_engagement.get(tid, {}).get("total_engage_s", 0.0)
        for tid in person_engagement
    )
    rate = round((engaged / passersby * 100), 1) if passersby > 0 else 0.0
    payload = {
        "timestamp":           time.time(),
        "store_name":          store,
        "session_min":         round(session_s / 60, 1),
        "passersby":           passersby,
        "engaged":             engaged,
        "engagement_rate":     rate,
        "total_attention_s":   round(total_attention_s, 1),
        "active_people":       len(active_ids),
        "currently_engaged":   currently_engaged,
        "qr_active_until":     qr_active_until,
    }
    try:
        with open(LIVE_STATS_PATH, "w") as f:
            json.dump(payload, f)
    except Exception:
        pass  # Never crash the main loop for a dashboard write


def write_hourly_snapshot(hour_dt, engaged_delta, pax_delta, attn_delta, rate):
    """Append a completed-hour bucket to hourly_log.json."""
    entry = {
        "hour":       hour_dt.strftime("%Y-%m-%dT%H:00"),
        "date":       hour_dt.strftime("%Y-%m-%d"),
        "engaged":    engaged_delta,
        "passersby":  pax_delta,
        "rate":       round(rate, 1),
        "attention_s": round(attn_delta, 1),
    }
    try:
        existing = []
        if os.path.exists(HOURLY_LOG_PATH):
            with open(HOURLY_LOG_PATH, "r") as f:
                existing = json.load(f)
        existing.append(entry)
        with open(HOURLY_LOG_PATH, "w") as f:
            json.dump(existing, f)
    except Exception:
        pass


def write_session_history(start_ts, end_ts, store, pax, engaged, attn_s):
    """Append a completed session row to session_history.json and session_log.csv."""
    start_dt  = datetime.fromtimestamp(start_ts)
    end_dt    = datetime.fromtimestamp(end_ts)
    rate      = round(engaged / pax * 100, 1) if pax > 0 else 0.0
    duration  = round((end_ts - start_ts) / 60, 1)
    entry = {
        "date":          start_dt.strftime("%Y-%m-%d"),
        "store":         store,
        "start_iso":     start_dt.isoformat(timespec="seconds"),
        "end_iso":       end_dt.isoformat(timespec="seconds"),
        "duration_min":  duration,
        "passersby":     pax,
        "engaged":       engaged,
        "rate":          rate,
        "attention_s":   round(attn_s, 1),
    }
    # JSON history (dashboard reads this)
    try:
        existing = []
        if os.path.exists(SESSION_HIST_PATH):
            with open(SESSION_HIST_PATH, "r") as f:
                existing = json.load(f)
        existing.append(entry)
        with open(SESSION_HIST_PATH, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass
    # CSV backup (human-readable)
    try:
        write_header = not os.path.exists(SESSION_LOG_PATH)
        with open(SESSION_LOG_PATH, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=entry.keys())
            if write_header:
                w.writeheader()
            w.writerow(entry)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# SECTION 5: ANALYTICS & TEMPORAL BUFFER STATE
# ═══════════════════════════════════════════════════════════════# ─────────────────────────────────────────────
FRAME_BUFFER_SIZE  = 3    # Look at last N frames
FRAME_ENGAGE_MIN   = 1    # Just 1 confident frame = ENGAGED (more responsive)

# ── SECOND-PASS FALSE-POSITIVE FILTERS ───────────────────────
YOLO_CONF_MIN      = 0.45  # Ignore YOLO detections below this confidence
ASPECT_RATIO_MIN   = 0.75  # Height/Width must be >= this (chairs are wide & short)
GHOST_FRAME_TRIAL  = 20    # After this many frames with no face found → blacklist
ghost_ids          = set() # Track IDs permanently identified as non-human

# ── TRAINING MODE STATE ───────────────────────────────────────
TRAINING_MODE     = False
TRAINING_CSV_PATH = "data/engagement_data.csv"
training_rows     = []
last_yaw = last_pitch = last_distance = None

# ── LIVE DASHBOARD STATE ────────────────────────────────────
LIVE_STATS_PATH   = "data/live_stats.json"
HOURLY_LOG_PATH   = "data/hourly_log.json"
SESSION_HIST_PATH = "data/session_history.json"
frame_count       = 0
_focal_px         = None   # Pinhole camera model — computed from first frame
store_name        = store_config.get("store_name", "VisionMetrics AI") if store_config else "VisionMetrics AI"

# ── HOURLY BUCKET STATE ──────────────────────────────────────
_current_hour    = None   # datetime truncated to the hour
_hour_pax_base   = 0      # passersby count at the start of this hour
_hour_eng_base   = 0      # engaged count at the start of this hour
_hour_attn_base  = 0.0    # attention seconds at the start of this hour

person_engagement  = {}   # {track_id: state_dict}
total_passersby    = 0
total_engaged      = 0
session_start      = time.time()

# QR trigger: Unix timestamp until which the customer-facing ad screen shows the QR.
# Single-slot pattern — while active, new 5s-crossings do NOT re-trigger.
_qr_active_until   = 0.0
QR_DURATION_S      = 10.0
_perf_t0           = time.time()
_perf_display_frames = 0
_perf_analysis_frames = 0
_perf_analysis_ms  = []


# ═══════════════════════════════════════════════════════════════
# SECTION 6: THE LIVE ANALYSIS LOOP
# ═══════════════════════════════════════════════════════════════

class _FrameReader:
    """Background thread that drains the camera buffer and always serves the newest frame."""
    def __init__(self, cap):
        self._cap   = cap
        self._frame = None
        self._ok    = False
        self._lock  = threading.Lock()
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        while True:
            ok, frame = self._cap.read()
            with self._lock:
                self._ok    = ok
                self._frame = frame

    def read(self):
        with self._lock:
            return self._ok, (self._frame.copy() if self._frame is not None else None)

_reader = _FrameReader(cap)

while True:
    ok, frame = _reader.read()
    if not ok or frame is None:
        continue

    h, w, _ = frame.shape
    now = time.time()
    frame_count += 1
    _perf_display_frames += 1

    # Print performance report every 5 seconds
    _perf_elapsed = now - _perf_t0
    if _perf_elapsed >= 5.0:
        disp_fps  = _perf_display_frames / _perf_elapsed
        anal_fps  = _perf_analysis_frames / _perf_elapsed
        avg_ms    = (sum(_perf_analysis_ms) / len(_perf_analysis_ms)) if _perf_analysis_ms else 0
        print(f"[PERF] Display: {disp_fps:.1f}fps | Analysis: {anal_fps:.1f}fps | "
              f"Avg analysis time: {avg_ms:.0f}ms | People tracked: {len(tracked_ids)}")
        _perf_t0 = now
        _perf_display_frames  = 0
        _perf_analysis_frames = 0
        _perf_analysis_ms     = []

    # Pinhole camera model — focal length in pixels, computed once from frame size
    if _focal_px is None:
        _focal_px = (w / 2.0) / np.tan(np.radians(CAMERA_FOV_H_DEG / 2.0))

    # Write live stats to JSON every 30 frames (~1 second)
    if frame_count % 30 == 0:
        write_live_stats(now - session_start, total_passersby,
                         total_engaged, tracked_ids, store_name,
                         qr_active_until=_qr_active_until)

        # ── Hourly bucket check ──────────────────────────────────
        now_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        total_attn_now = sum(s.get("total_engage_s", 0.0) for s in person_engagement.values())
        if _current_hour is None:
            _current_hour   = now_hour
            _hour_pax_base  = total_passersby
            _hour_eng_base  = total_engaged
            _hour_attn_base = total_attn_now
        elif now_hour != _current_hour:
            eng_delta  = total_engaged      - _hour_eng_base
            pax_delta  = total_passersby    - _hour_pax_base
            attn_delta = total_attn_now     - _hour_attn_base
            hr_rate    = (eng_delta / pax_delta * 100) if pax_delta > 0 else 0.0
            write_hourly_snapshot(_current_hour, eng_delta, pax_delta, attn_delta, hr_rate)
            _current_hour   = now_hour
            _hour_pax_base  = total_passersby
            _hour_eng_base  = total_engaged
            _hour_attn_base = total_attn_now

    # ── LAYER 1: YOLO — Detect & Track all persons ──────────────
    _analysis_t0 = time.time()
    _perf_analysis_frames += 1

    yolo_results = yolo_model.track(frame, classes=[0], persist=True, verbose=False)
    tracked_ids  = set()

    if yolo_results[0].boxes is not None and yolo_results[0].boxes.id is not None:
        boxes   = yolo_results[0].boxes.xyxy.cpu().numpy().astype(int)
        ids     = yolo_results[0].boxes.id.cpu().numpy().astype(int)
        confs   = yolo_results[0].boxes.conf.cpu().numpy()   # confidence scores

        for box, track_id, conf in zip(boxes, ids, confs):

            # ── SECOND PASS FILTER 1: YOLO Confidence ─────────────
            # Reject weak YOLO detections outright (chairs, bags, etc.)
            if conf < YOLO_CONF_MIN:
                cv2.putText(frame, f"LOW CONF ({conf:.0%})",
                            (box[0], box[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 80, 80), 1)
                continue

            x1, y1, x2, y2 = box
            box_w = x2 - x1
            box_h = y2 - y1

            # ── SECOND PASS FILTER 2: Aspect Ratio ────────────────
            # People are taller than wide. Chairs and furniture are not.
            if box_w > 0 and (box_h / box_w) < ASPECT_RATIO_MIN:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 60, 60), 1)
                cv2.putText(frame, "NOT HUMAN (shape)",
                            (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 80, 80), 1)
                continue

            # ── SECOND PASS FILTER 3: Ghost Track Blacklist ────────
            # If we've watched this ID for GHOST_FRAME_TRIAL frames and
            # MediaPipe has never once found a face → it's not a person.
            if track_id in ghost_ids:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 40, 40), 1)
                cv2.putText(frame, "GHOST (no face)",
                            (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 80, 80), 1)
                continue

            tracked_ids.add(track_id)

            # Register new person
            if track_id not in person_engagement:
                person_engagement[track_id] = {
                    "first_seen":          now,
                    "engage_start":        None,  # start of current engagement window
                    "cumulative_engage_s": 0.0,   # total across ALL windows (never resets)
                    "total_engage_s":      0.0,   # cumulative + current window (for display)
                    "counted_as_engaged":  False, # True once person crosses REWARD_THRESHOLD_S
                    "currently_engaged":   False,
                    "frame_buffer":        [],
                    "frames_seen":         0,
                    "faces_found":         0,
                    "last_prob":           0.0,   # most recent engage_prob for tier HUD
                }
                total_passersby += 1

            state = person_engagement[track_id]
            
            # ── LAYER 2: MediaPipe — Extract face angles ───────────
            # Strategy: crop only the HEAD region (top 35% of body box),
            # then upscale 4x. At 4m a face is ~20px wide; after this
            # it becomes ~80px — well within MediaPipe's detection range.
            pad = 30
            box_h = y2 - y1
            # Head = top 35% of bounding box
            head_y2 = y1 + int(box_h * 0.45)
            rx1 = max(0, x1 - pad)
            ry1 = max(0, y1 - pad)
            rx2 = min(w, x2 + pad)
            ry2 = min(h, head_y2 + pad)
            roi = frame[ry1:ry2, rx1:rx2]

            yaw = pitch = distance = dist_m = None
            # ── Ghost track accounting (always, not skipped) ───────
            state["frames_seen"] = state.get("frames_seen", 0) + 1

            # ── Face frame-skip cache ──────────────────────────────
            _fc = _face_cache.get(track_id, {})
            _use_face_cache = (frame_count - _fc.get("idx", -999)) < FACE_SKIP_FRAMES

            if _use_face_cache:
                yaw      = _fc.get("yaw")
                pitch    = _fc.get("pitch")
                distance = _fc.get("distance")
                dist_m   = _fc.get("dist_m")
            elif roi.size > 0:
                roi_h, roi_w = roi.shape[:2]
                # Upscale 4x for far detections
                scale  = 4
                roi_up = cv2.resize(roi, (roi_w * scale, roi_h * scale),
                                    interpolation=cv2.INTER_LINEAR)
                rgb_roi = cv2.cvtColor(roi_up, cv2.COLOR_BGR2RGB)
                mp_img  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_roi)
                face_result = face_detector.detect(mp_img)

                if face_result.face_landmarks:
                    lm = face_result.face_landmarks[0]
                    yaw, pitch, distance = extract_face_angles(lm)
                    state["faces_found"] = state.get("faces_found", 0) + 1

                    # Pinhole camera model: face_width (normalised in upscaled ROI)
                    # → original-frame pixels → real distance in metres.
                    face_w_orig_px = distance * (rx2 - rx1)
                    dist_m = float(np.clip(
                        (FACE_WIDTH_M * _focal_px) / (face_w_orig_px + 1e-6),
                        0.1, 8.0
                    ))

                    # Map nose back to original frame coords
                    nx = rx1 + int(lm[1].x * roi_w)
                    ny = ry1 + int(lm[1].y * roi_h)
                    cv2.circle(frame, (nx, ny), 5, (0, 255, 0), -1)

                    # Save latest values for training mode labelling
                    last_yaw, last_pitch, last_distance = yaw, pitch, distance

                    # Update face cache
                    _face_cache[track_id] = {
                        "idx": frame_count, "yaw": yaw, "pitch": pitch,
                        "distance": distance, "dist_m": dist_m
                    }

                # ── Promote to ghost if trial period is over with no faces ──
                elif state["frames_seen"] >= GHOST_FRAME_TRIAL and state.get("faces_found", 0) == 0:
                    ghost_ids.add(track_id)
                    # Remove from passersby count — it was never a person
                    total_passersby = max(0, total_passersby - 1)
                    if track_id in person_engagement:
                        del person_engagement[track_id]
                    continue

            # ── TORSO ANGLE CHECK (professor feedback #4) ─────────
            if POSE_ENABLED:
                torso_conf, torso_span, torso_rel_yaw = get_torso_confidence(
                    frame, track_id, x1, y1, x2, y2, frame_count
                )
            else:
                torso_conf, torso_span, torso_rel_yaw = 1.0, None, None

            # ── LAYER 3 & 4: PyTorch + Zone Check ─────────────────
            raw_engaged = False
            engage_prob = 0.0
            if yaw is not None:
                engage_prob, _ = classify_with_pytorch(yaw, pitch, distance)

                # Torso damping: fully sideways body lowers probability
                torso_weight = 0.40 + 0.60 * torso_conf
                engage_prob  = engage_prob * torso_weight

                # Soft zone: smoothly multiplies probability instead of hard YES/NO cutoff.
                # Prevents flicker when different-height people sit at the zone boundary.
                z_conf      = zone_confidence(yaw, pitch, distance, engagement_zone, dist_m)
                engage_prob = engage_prob * z_conf

                raw_engaged = engage_prob >= 0.50

            state["last_prob"] = engage_prob

            # ── TEMPORAL FRAME BUFFER (prevents flickering & false positives)
            # Only mark as engaged if M out of last N frames agree.
            buf = state["frame_buffer"]
            buf.append(1 if raw_engaged else 0)
            if len(buf) > FRAME_BUFFER_SIZE:
                buf.pop(0)
            is_engaged = sum(buf) >= FRAME_ENGAGE_MIN

            # ── Engagement Time Tracking ───────────────────────────
            if is_engaged:
                if state["engage_start"] is None:
                    state["engage_start"] = now          # start a new window
                # Accumulate: past windows + current window
                state["total_engage_s"] = (
                    state["cumulative_engage_s"] + (now - state["engage_start"])
                )
            else:
                if state["engage_start"] is not None:
                    # Close the window — bank it into cumulative
                    state["cumulative_engage_s"] += now - state["engage_start"]
                    state["engage_start"] = None
                state["total_engage_s"] = state["cumulative_engage_s"]

            # Count this person once as "engaged" when they cross the 5s threshold
            if (not state["counted_as_engaged"]
                    and state["total_engage_s"] >= REWARD_THRESHOLD_S):
                state["counted_as_engaged"] = True
                total_engaged += 1
                # Arm customer-facing QR screen — only if not already active (single-slot)
                if now > _qr_active_until:
                    _qr_active_until = now + QR_DURATION_S

            state["currently_engaged"] = is_engaged
            engaged_s = state["total_engage_s"]

            # ── Draw Bounding Box & Label ──────────────────────────
            # Tier derived from raw PyTorch probability (before zone/torso weighting)
            if engage_prob >= 0.80:
                tier, box_color = "HIGH", (0, 255, 80)
            elif engage_prob >= 0.50:
                tier, box_color = "MED",  (0, 215, 255)
            else:
                tier, box_color = "LOW",  (100, 100, 100)

            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            label = f"ID:{track_id}"
            if yaw is not None:
                label += f" {tier} ({engage_prob:.0%})"
            if engaged_s > 0:
                label += f" | {engaged_s:.1f}s"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)

            # ── LIVE DEBUG PANEL ───────────────────────────────────
            # Shows the raw AI numbers so you can see exactly what
            # is being measured and why ENGAGED fires or not.
            if yaw is not None:
                debug_y = y2 + 18
                if debug_y + 20 > h:
                    debug_y = y2 - 30  # Draw inside the box if touching bottom screen edge
                
                torso_str = f"{torso_conf:.0%}" if torso_span is not None else "N/A"
                dist_str  = f"{dist_m:.1f}m" if dist_m is not None else f"{distance:.3f}"
                ryaw_str  = f"{torso_rel_yaw:+.2f}" if torso_rel_yaw is not None else "N/A"
                cv2.putText(frame,
                    f"Yaw:{yaw:+.2f} Pitch:{pitch:+.2f} Dist:{dist_str}  Torso:{torso_str} R-Yaw:{ryaw_str}",
                    (x1, debug_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1)
                cv2.putText(frame,
                    f"PyTorch:{engage_prob:.0%}  Zone:{z_conf:.0%}  Buf:{sum(state['frame_buffer'])}/{FRAME_BUFFER_SIZE}",
                    (x1, debug_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 200, 0), 1)

    # ── LAYER 5: Analytics HUD ──────────────────────────────────
    session_s = now - session_start
    total_attn = sum(s.get("total_engage_s", 0.0) for s in person_engagement.values())

    # Tier counters across currently-tracked people
    n_high = sum(1 for tid in tracked_ids
                 if person_engagement.get(tid, {}).get("last_prob", 0.0) >= 0.80)
    n_med  = sum(1 for tid in tracked_ids
                 if 0.50 <= person_engagement.get(tid, {}).get("last_prob", 0.0) < 0.80)
    n_low  = sum(1 for tid in tracked_ids
                 if person_engagement.get(tid, {}).get("last_prob", 0.0) < 0.50)

    hud_bg = frame.copy()
    cv2.rectangle(hud_bg, (0, 0), (310, 158), (20, 20, 20), -1)
    cv2.addWeighted(hud_bg, 0.7, frame, 0.3, 0, frame)

    cv2.putText(frame, "VisionMetrics AI", (10, 22),
                cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 200, 255), 1)
    cv2.putText(frame, f"Session Time:    {session_s/60:.1f} min", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(frame, f"Total Passersby: {total_passersby}", (10, 73),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(frame, f"Engaged (5s+):   {total_engaged}", (10, 96),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 130), 1)
    cv2.putText(frame, f"Total Attn:      {total_attn:.1f}s", (10, 119),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1)
    cv2.putText(frame, f"High:{n_high}  Med:{n_med}  Low:{n_low}", (10, 142),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

    # ── TRAINING MODE HUD (must be BEFORE imshow to appear on screen) ──
    if TRAINING_MODE:
        look_n = sum(1 for r in training_rows if r[3] == 1)
        away_n = sum(1 for r in training_rows if r[3] == 0)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h-55), (420, h), (0, 60, 0), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        cv2.putText(frame, f"[TRAINING MODE]  L=Look({look_n})  A=Away({away_n})  T=Exit training",
                    (8, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 100), 2)

    _perf_analysis_ms.append((time.time() - _analysis_t0) * 1000)

    cv2.imshow("VisionMetrics AI — Retail Engagement System  [Q=Quit | T=Training Mode]", frame)

    key = cv2.waitKey(1) & 0xFF

    # ── TRAINING MODE CONTROLS ────────────────────────────────
    if key == ord('t'):
        TRAINING_MODE = not TRAINING_MODE
        status = "ON — press L (Look) or A (Away) to label. Click the VIDEO WINDOW first!" if TRAINING_MODE else "OFF"
        print(f"Training Mode: {status}")

    elif TRAINING_MODE and key == ord('l') and last_yaw is not None:
        training_rows.append([last_yaw, last_pitch, last_distance, 1])
        print(f"  ✅ Saved LOOK  (total: {len(training_rows)})")

    elif TRAINING_MODE and key == ord('a') and last_yaw is not None:
        training_rows.append([last_yaw, last_pitch, last_distance, 0])
        print(f"  ✅ Saved AWAY  (total: {len(training_rows)})")

    elif key == ord('q'):
        break

        cv2.putText(frame, f"[TRAINING MODE]  L=Look({look_n})  A=Away({away_n})  T=Exit",
                    (8, h-18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 2)

# ═══════════════════════════════════════════════════════════════
# SECTION 7: SESSION SUMMARY & LOG
# ═══════════════════════════════════════════════════════════════
cap.release()
cv2.destroyAllWindows()

# ── SAVE TRAINING DATA IF ANY WAS COLLECTED ──────────────────
if training_rows:
    import pandas as pd
    import os
    new_df = pd.DataFrame(training_rows, columns=['yaw', 'pitch', 'distance', 'label'])
    if os.path.exists(TRAINING_CSV_PATH):
        existing = pd.read_csv(TRAINING_CSV_PATH)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_csv(TRAINING_CSV_PATH, index=False)
    print(f"\n✅ Training data saved: {len(training_rows)} new rows → {TRAINING_CSV_PATH}")
    print(f"   Total rows in file: {len(combined)}")

print("\n" + "="*60)
print("  SESSION COMPLETE — ANALYTICS SUMMARY")
print("="*60)
print(f"  Session Duration:    {(time.time() - session_start)/60:.1f} minutes")
print(f"  Total Passersby:     {total_passersby}")
print(f"  Total Engaged (5s+): {total_engaged}")
total_attn_final = sum(s.get("total_engage_s", 0.0) for s in person_engagement.values())
print(f"  Total Attention:     {total_attn_final:.1f}s")
if total_passersby > 0:
    rate = (total_engaged / total_passersby) * 100
    print(f"  Engagement Rate:     {rate:.1f}%")
print("="*60)

# ── SAVE SESSION TO HISTORY (dashboard weekly comparison) ────
write_session_history(session_start, time.time(), store_name,
                      total_passersby, total_engaged, total_attn_final)
print(f"  Session saved → {SESSION_HIST_PATH}")
