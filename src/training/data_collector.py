"""
data_collector.py — Universal Head Pose Data Collection Tool
--------------------------------------------------------------
PURPOSE:
    Collects UNIVERSAL training data — not specific to any store.
    Teaches the AI to measure head angles (Yaw, Pitch, Distance).

    Pipeline matches main.py EXACTLY:
      YOLO detects person → crop head ROI (top 45%) → 4x upscale → MediaPipe
    This ensures training distance (face_width) values match inference values.

HOW TO RUN:
    python src/training/data_collector.py

CONTROLS:
    'L'  →  Record ONE LOOKING sample (manual)
    'A'  →  Record ONE AWAY sample (manual)
    'T'  →  Toggle AUTO-RECORD (records every 8 frames — use for LOOK sessions)
    'M'  →  Switch auto-record label: LOOKING / AWAY
    'Q'  →  Quit and save

DISTANCE PROTOCOL:
    Walk through NEAR / MID / FAR / VERY-FAR distances.
    At each distance record LOOK (label=1) and AWAY (label=0) samples.
    Aim for ~200 samples per distance tier × label.
"""

import cv2
import mediapipe as mp
import urllib.request
import os
import pandas as pd
from ultralytics import YOLO
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ─────────────────────────────────────────────
# CONFIG  (mirrors main.py constants)
# ─────────────────────────────────────────────
MODEL_PATH        = "models/face_landmarker.task"
CSV_PATH          = "data/engagement_data.csv"
YOLO_WEIGHTS      = "yolov8n.pt"
YOLO_CONF_MIN     = 0.25    # very permissive — we only need to find the person to crop head
ASPECT_RATIO_MIN  = 0.30    # relaxed — girls/children have narrower bboxes
HEAD_CROP_FRAC    = 0.55    # slightly more than main.py (0.45) to include full head
PAD_PX            = 40      # more padding = more context for MediaPipe at far distances
UPSCALE           = 4       # must match main.py
FALLBACK_SCALE    = 4       # full-frame upscale when YOLO finds nobody
AUTO_RECORD_EVERY = 8       # frames between auto-saves
CAMERA_INDEX      = 2

os.makedirs("data",   exist_ok=True)
os.makedirs("models", exist_ok=True)

# ─────────────────────────────────────────────
# DOWNLOAD FACE MODEL (one-time)
# ─────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print("Downloading Face Landmarker model (~3MB)...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/face_landmarker"
        "/face_landmarker/float16/latest/face_landmarker.task",
        MODEL_PATH
    )
    print("Downloaded.")

# ─────────────────────────────────────────────
# INITIALIZE YOLO + MEDIAPIPE
# ─────────────────────────────────────────────
yolo_model = YOLO(YOLO_WEIGHTS)

base_opts = python.BaseOptions(model_asset_path=MODEL_PATH)
options   = vision.FaceLandmarkerOptions(
    base_options=base_opts,
    num_faces=1,
    min_face_detection_confidence=0.25,
    min_face_presence_confidence=0.25,
)
detector = vision.FaceLandmarker.create_from_options(options)

# ─────────────────────────────────────────────
# OPEN CAMERA
# ─────────────────────────────────────────────
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"ERROR: Could not open camera {CAMERA_INDEX}.")
    exit()

print("\n" + "="*55)
print("  UNIVERSAL DATA COLLECTION  (pipeline = main.py)")
print("="*55)
print("  L  →  Record LOOKING sample")
print("  A  →  Record AWAY sample")
print("  T  →  Toggle AUTO-RECORD (bulk LOOK sessions)")
print("  M  →  Switch auto-record label (LOOK / AWAY)")
print("  Q  →  Quit and save")
print("="*55 + "\n")

# ─────────────────────────────────────────────
# DISTANCE TIER CONFIG
# ─────────────────────────────────────────────
DIST_TIERS = [
    # (label,          face_w_min, face_w_max, color_bgr)
    ("NEAR  <0.5m",    0.25, 1.0,  (0,   200, 255)),
    ("MID  0.5-1.5m",  0.10, 0.25, (0,   230,  80)),
    ("FAR  1.5-3.5m",  0.04, 0.10, (255, 180,   0)),
    ("V-FAR >3.5m",    0.00, 0.04, (80,   80, 255)),
]

def get_tier(face_width):
    for name, lo, hi, color in DIST_TIERS:
        if lo <= face_width < hi:
            return name, color
    return "UNKNOWN", (180, 180, 180)

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
data_rows       = []
look_count      = 0
away_count      = 0
auto_mode       = False
auto_label      = 1
auto_frame_tick = 0
tier_counts     = {t[0]: {"look": 0, "away": 0} for t in DIST_TIERS}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def put(img, text, pos, color=(255,255,255), scale=0.60, thick=2):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)

def record(yaw, pitch, distance, label, tier_name):
    global look_count, away_count
    data_rows.append([round(yaw, 5), round(pitch, 5), round(distance, 5), label])
    if label == 1:
        look_count += 1
        tier_counts[tier_name]["look"] += 1
        tag = "LOOK"
    else:
        away_count += 1
        tier_counts[tier_name]["away"] += 1
        tag = "AWAY"
    print(f"  [{tag}]  Yaw={yaw:+.3f}  Pitch={pitch:+.3f}  Dist={distance:.4f}  "
          f"Tier={tier_name}   Total: L={look_count} A={away_count}")

def get_largest_person_box(frame):
    """Run YOLO, return (x1,y1,x2,y2) of the largest valid person bbox, or None."""
    res = yolo_model(frame, classes=[0], conf=YOLO_CONF_MIN, verbose=False)
    best, best_area = None, 0
    for box in res[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        bw, bh = x2 - x1, y2 - y1
        if bh == 0 or (bw / bh) < ASPECT_RATIO_MIN:
            continue
        area = bw * bh
        if area > best_area:
            best_area = area
            best = (x1, y1, x2, y2)
    return best

def crop_head_roi(frame, box):
    """Crop top HEAD_CROP_FRAC of the YOLO bbox + PAD_PX, upscale UPSCALE×."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    box_h  = y2 - y1
    head_y2 = y1 + int(box_h * HEAD_CROP_FRAC)
    rx1 = max(0, x1 - PAD_PX)
    ry1 = max(0, y1 - PAD_PX)
    rx2 = min(w, x2 + PAD_PX)
    ry2 = min(h, head_y2 + PAD_PX)
    roi = frame[ry1:ry2, rx1:rx2]
    if roi.size == 0:
        return None, None, None
    roi_h, roi_w = roi.shape[:2]
    roi_up = cv2.resize(roi, (roi_w * UPSCALE, roi_h * UPSCALE), interpolation=cv2.INTER_LINEAR)
    return roi_up, (rx1, ry1, rx2, ry2), (roi_w, roi_h)

# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
while True:
    success, frame = cap.read()
    if not success:
        continue

    h, w = frame.shape[:2]
    yaw = pitch = distance = None
    tier_name, tier_color = "UNKNOWN", (180, 180, 180)
    pipeline_label = ""
    pipeline_color = (180, 180, 180)

    # ── Try YOLO head-crop path (matches main.py) ──────────────
    box = get_largest_person_box(frame)
    if box is not None:
        roi_up, roi_rect, roi_dims = crop_head_roi(frame, box)
        if roi_up is not None:
            rgb    = cv2.cvtColor(roi_up, cv2.COLOR_BGR2RGB)
            img_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(img_mp)

            if result.face_landmarks:
                lm          = result.face_landmarks[0]
                nose        = lm[1]
                top         = lm[10]
                chin        = lm[152]
                l_cheek     = lm[234]
                r_cheek     = lm[454]

                face_mid_x  = (l_cheek.x + r_cheek.x) / 2
                face_width  = abs(r_cheek.x - l_cheek.x)
                yaw         = (nose.x - face_mid_x) / (face_width + 1e-6)

                face_mid_y  = (l_cheek.y + r_cheek.y) / 2
                face_height = abs(chin.y - top.y)
                pitch       = (nose.y - face_mid_y) / (face_height + 1e-6)

                distance    = face_width
                tier_name, tier_color = get_tier(distance)
                pipeline_label = "YOLO crop 4x"
                pipeline_color = (0, 220, 80)

                # draw nose dot on original frame
                rx1, ry1, rx2, ry2 = roi_rect
                rw, rh = roi_dims
                nx = rx1 + int(nose.x * rw)
                ny = ry1 + int(nose.y * rh)
                cv2.circle(frame, (nx, ny), 6, (0, 255, 0), -1)

                # draw YOLO head-crop box
                x1, y1, x2, y2 = box
                head_y2 = y1 + int((y2 - y1) * HEAD_CROP_FRAC)
                cv2.rectangle(frame, (x1, y1), (x2, head_y2), (0, 200, 80), 1)

    # ── Fallback: full-frame upscale (no YOLO detection) ───────
    if yaw is None:
        frame_up = cv2.resize(frame, (w*FALLBACK_SCALE, h*FALLBACK_SCALE), interpolation=cv2.INTER_LINEAR)
        rgb      = cv2.cvtColor(frame_up, cv2.COLOR_BGR2RGB)
        img_mp   = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = detector.detect(img_mp)

        if result.face_landmarks:
            lm          = result.face_landmarks[0]
            nose        = lm[1]
            top         = lm[10]
            chin        = lm[152]
            l_cheek     = lm[234]
            r_cheek     = lm[454]

            face_mid_x  = (l_cheek.x + r_cheek.x) / 2
            face_width  = abs(r_cheek.x - l_cheek.x)
            yaw         = (nose.x - face_mid_x) / (face_width + 1e-6)

            face_mid_y  = (l_cheek.y + r_cheek.y) / 2
            face_height = abs(chin.y - top.y)
            pitch       = (nose.y - face_mid_y) / (face_height + 1e-6)

            distance    = face_width
            tier_name, tier_color = get_tier(distance)
            pipeline_label = f"full-frame {FALLBACK_SCALE}x"
            pipeline_color = (0, 140, 255)

            nx = int(nose.x * w)
            ny = int(nose.y * h)
            cv2.circle(frame, (nx, ny), 6, (0, 180, 255), -1)

    # ── Auto-record ────────────────────────────────────────────
    if auto_mode and yaw is not None:
        auto_frame_tick += 1
        if auto_frame_tick >= AUTO_RECORD_EVERY:
            auto_frame_tick = 0
            record(yaw, pitch, distance, auto_label, tier_name)

    # ── HUD ───────────────────────────────────────────────────
    if yaw is not None:
        put(frame, f"Yaw:   {yaw:+.3f}", (10, 30))
        put(frame, f"Pitch: {pitch:+.3f}", (10, 58))
        put(frame, f"Dist:  {distance:.4f}", (10, 86))
        put(frame, f"[{pipeline_label}]", (10, 114), pipeline_color, scale=0.50, thick=1)
    else:
        put(frame, "No face detected", (10, 30), (0, 0, 255))

    # Distance tier badge (top-center)
    badge = tier_name if yaw is not None else "---"
    bx = w//2 - 90
    cv2.rectangle(frame, (bx-4, 10), (bx+196, 36), (30, 30, 30), -1)
    put(frame, badge, (bx, 30), tier_color, scale=0.65, thick=2)

    # Auto-mode indicator (top-right)
    mode_str   = f"AUTO: {'LOOK' if auto_label==1 else 'AWAY'}" if auto_mode else "MANUAL"
    mode_color = (0, 220, 100) if auto_mode else (180, 180, 180)
    put(frame, mode_str, (w - 185, 30), mode_color, scale=0.65, thick=2)

    # Bottom counters
    put(frame, f"LOOK: {look_count}  AWAY: {away_count}",
        (10, h - 45), (0, 220, 255))
    put(frame, "[L]ook  [A]way  [T]oggle-auto  [M]ode  [Q]uit",
        (10, h - 15), (160, 160, 160), scale=0.50, thick=1)

    # Per-tier progress (right panel)
    rx = w - 220
    put(frame, "Tier progress (L/A):", (rx, 60), (200, 200, 200), scale=0.48, thick=1)
    for i, (tname, *_) in enumerate(DIST_TIERS):
        tc = tier_counts[tname]
        put(frame, f"{tname[:12]:12s} {tc['look']:3d}/{tc['away']:3d}",
            (rx, 82 + i*22), (180, 180, 180), scale=0.46, thick=1)

    cv2.imshow("VisionMetrics — Data Collection  [L=Look | A=Away | T=Auto | Q=Quit]", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('l') and yaw is not None:
        record(yaw, pitch, distance, 1, tier_name)
    elif key == ord('a') and yaw is not None:
        record(yaw, pitch, distance, 0, tier_name)
    elif key == ord('t'):
        auto_mode = not auto_mode
        auto_frame_tick = 0
        print(f"  [AUTO {'ON' if auto_mode else 'OFF'}]  label={'LOOK' if auto_label==1 else 'AWAY'}")
    elif key == ord('m'):
        auto_label = 1 - auto_label
        print(f"  [label → {'LOOK' if auto_label==1 else 'AWAY'}]")
    elif key == ord('q'):
        break

# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────
cap.release()
cv2.destroyAllWindows()

if data_rows:
    df = pd.DataFrame(data_rows, columns=["yaw", "pitch", "distance", "label"])
    if os.path.exists(CSV_PATH):
        existing = pd.read_csv(CSV_PATH)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"\n  Saved {len(data_rows)} new rows → {CSV_PATH}")
    print(f"  Total in file: {len(df)} rows  "
          f"(LOOK={int(df['label'].sum())}  AWAY={int((df['label']==0).sum())})")
    print("\n  Tier breakdown (this session):")
    for tname, counts in tier_counts.items():
        if counts['look'] + counts['away'] > 0:
            print(f"    {tname:20s}  L={counts['look']:3d}  A={counts['away']:3d}")
else:
    print("\n  No data recorded. File not modified.")
