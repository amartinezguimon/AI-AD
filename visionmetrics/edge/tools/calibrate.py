"""
calibrate.py — Store-Specific Engagement Zone Calibration
----------------------------------------------------------
PURPOSE:
    This script is run ONCE per store installation. It generates a
    store_config.json file that defines the physical boundaries of a
    specific display (vitrina, poster, shelf, etc.) relative to where the
    camera is mounted.

    The Universal AI Brain (trained by train.py) does NOT change between
    stores. Only this config file changes. This is what makes the system
    scalable to any store without retraining the AI.

HOW TO RUN:
    python visionmetrics/edge/tools/calibrate.py

SETUP BEFORE RUNNING:
    1. Mount your camera (iPhone via Iriun/Camo, or laptop webcam) exactly
       where it will stay permanently. Do NOT move it after calibration.
    2. Make sure the display/vitrina you want to track is in the camera's view.
    3. Run this script and follow the on-screen instructions.

OUTPUT:
    configs/store_config.json  ← Generated automatically.

CONTROLS DURING CALIBRATION:
    '1'  →  Capture LEFT edge of the display (look at the far left)
    '2'  →  Capture CENTER of the display (look straight at the center)
    '3'  →  Capture RIGHT edge of the display (look at the far right)
    '4'  →  Capture the closest customer distance (stand 0.3-0.5m away)
    '5'  →  Capture the farthest useful customer distance (stand 2-3m away)
    'S'  →  Save config and exit
    'Q'  →  Quit without saving
"""

import cv2
import mediapipe as mp
import urllib.request
import os
import json
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MODEL_PATH      = "models/face_landmarker.task"
MODEL_POSE_PATH = "models/pose_landmarker_lite.task"
MODEL_YOLO_PATH = "yolov8n.pt"
CONFIG_DIR      = "configs"
CONFIG_PATH     = f"{CONFIG_DIR}/store_config.json"
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs("models",   exist_ok=True)

CAMERA_FOV_H_DEG = 70.0   # Typical webcam / smartphone horizontal FOV
FACE_WIDTH_M     = 0.16   # Average adult face width in metres
YOLO_CONF_MIN    = 0.40   # Minimum YOLO confidence to use a detection
HEAD_CROP_FRAC   = 0.45   # Top fraction of YOLO box used as head region
HEAD_UPSCALE     = 4      # Upscale factor on head crop (matches main.py)
FULL_UPSCALE     = 3      # Fallback upscale when YOLO finds no person

# ─────────────────────────────────────────────
# DOWNLOAD MODEL (if needed)
# ─────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print("Downloading Face Landmarker model (one-time, ~3MB)...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/face_landmarker"
        "/face_landmarker/float16/latest/face_landmarker.task",
        MODEL_PATH
    )

# ─────────────────────────────────────────────
# INITIALIZE MEDIAPIPE
# ─────────────────────────────────────────────
base_opts = python.BaseOptions(model_asset_path=MODEL_PATH)
options   = vision.FaceLandmarkerOptions(
    base_options=base_opts,
    num_faces=1,
    min_face_detection_confidence=0.4,
    min_face_presence_confidence=0.4,
)
detector = vision.FaceLandmarker.create_from_options(options)

# Pose model for relative neck-to-torso yaw (optional)
pose_detector = None
if os.path.exists(MODEL_POSE_PATH):
    pose_opts = python.BaseOptions(model_asset_path=MODEL_POSE_PATH)
    pose_detector = vision.PoseLandmarker.create_from_options(
        vision.PoseLandmarkerOptions(
            base_options=pose_opts,
            num_poses=1,
            min_pose_detection_confidence=0.4,
            min_pose_presence_confidence=0.4,
        )
    )
    print("🦾 Pose model loaded — relative neck/torso yaw will be shown.")

# YOLO for head-crop pipeline (same as main.py — enables far-distance detection)
yolo_model = None
if os.path.exists(MODEL_YOLO_PATH):
    yolo_model = YOLO(MODEL_YOLO_PATH)
    print("🔍 YOLO loaded — head-crop pipeline active (far-distance calibration enabled).")
else:
    print("⚠️  yolov8n.pt not found — falling back to full-frame upscale (closer range only).")

# ─────────────────────────────────────────────
# OPEN CAMERA
# Change CAMERA_INDEX to 1 if using iPhone via Iriun/Camo
# ─────────────────────────────────────────────
CAMERA_INDEX = 2
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print(f"ERROR: Cannot open camera {CAMERA_INDEX}. Try index 1 for iPhone.")
    exit()

# ─────────────────────────────────────────────
# CALIBRATION STATE
# ─────────────────────────────────────────────
calibration = {
    "store_name": input("Enter a name for this store/location: ").strip() or "default_store",
    "camera_index": CAMERA_INDEX,
    "engagement_zone": {
        "yaw_left":    None,   # Yaw when looking at far LEFT of display
        "yaw_center":  None,   # Yaw when looking at CENTER of display
        "yaw_right":   None,   # Yaw when looking at far RIGHT of display
        "pitch_center": None,  # Pitch when looking at center (handles heights)
        "dist_close":  None,   # Distance proxy when standing very close
        "dist_far":    None,   # Distance proxy when standing at max useful distance
    },
    "derived": {
        "yaw_min":    None,    # Computed from yaw_left + tolerance
        "yaw_max":    None,    # Computed from yaw_right + tolerance
        "pitch_min":  None,    # pitch_center - tolerance
        "pitch_max":  None,    # pitch_center + tolerance
        "dist_min":   None,    # Minimum inter-eye distance to count (too far = ignore)
    }
}

INSTRUCTIONS = {
    "1": "Look at the FAR LEFT edge of your display",
    "2": "Look at the CENTER of your display",
    "3": "Look at the FAR RIGHT edge of your display",
    "4": "Walk as CLOSE as a customer ever gets (0.3-0.5m away), look center",
    "5": "Walk as FAR as a customer ever gets (2-3m away), look center",
}
CAPTURE_KEYS = set("12345")
captured = {}

print("\n" + "="*55)
print("  STORE CALIBRATION MODE")
print("="*55)
for k, v in INSTRUCTIONS.items():
    print(f"  Press '{k}'  →  {v}")
print("  Press 'S'  →  Save & exit")
print("  Press 'Q'  →  Quit without saving")
print("="*55 + "\n")


def get_angles(lm, roi_w_orig, focal_px):
    """
    Extract yaw, pitch, face_width proxy, and real distance in metres.

    roi_w_orig: width of the SOURCE region in original (non-upscaled) pixels.
      - Head-crop mode : rx2 - rx1  (bounding box width)
      - Full-frame mode: frame width w
    Landmark coords are normalised [0,1] relative to whatever image was passed
    to MediaPipe — scale-invariant for angles, but dist_m needs roi_w_orig to
    convert back to real pixel size before applying the pinhole formula.

    Uses CHEEKBONE landmarks (234=left, 454=right) — identical to main.py.
    """
    nose    = lm[1]
    top     = lm[10]
    chin    = lm[152]
    l_cheek = lm[234]
    r_cheek = lm[454]

    face_mid_x = (l_cheek.x + r_cheek.x) / 2
    face_width = abs(r_cheek.x - l_cheek.x)
    yaw        = (nose.x - face_mid_x) / (face_width + 1e-6)

    face_mid_y = (l_cheek.y + r_cheek.y) / 2
    face_h     = abs(chin.y - top.y)
    pitch      = (nose.y - face_mid_y) / (face_h + 1e-6)

    # face_width normalised → original-frame pixels → real metres
    face_w_px = face_width * roi_w_orig
    dist_m    = float(np.clip((FACE_WIDTH_M * focal_px) / (face_w_px + 1e-6), 0.1, 8.0))

    return yaw, pitch, face_width, dist_m


# ─────────────────────────────────────────────
# MAIN CALIBRATION LOOP
# ─────────────────────────────────────────────
focal_px = None

while True:
    ok, frame = cap.read()
    if not ok:
        continue

    h, w, _ = frame.shape

    if focal_px is None:
        focal_px = (w / 2.0) / np.tan(np.radians(CAMERA_FOV_H_DEG / 2.0))

    yaw = pitch = distance = dist_m = None
    rel_yaw = None
    tracking_label = ""

    # ── Strategy: YOLO head-crop (far range) → fallback full-frame upscale ──
    #
    # YOLO finds the person bounding box → we crop just the head region
    # (top 45% of box) and upscale 4x. At 4m this turns a ~15px face into
    # ~60px — well within MediaPipe's detection range.
    # Without YOLO (or if no person is detected) we fall back to a 3x
    # full-frame upscale, which works reliably up to ~2m.

    roi_x1 = roi_y1 = 0
    roi_x2, roi_y2 = w, h   # defaults for full-frame fallback

    if yolo_model is not None:
        yolo_res = yolo_model(frame, classes=[0], verbose=False)[0]
        best_box = None
        best_area = 0
        if yolo_res.boxes is not None:
            for box, conf in zip(yolo_res.boxes.xyxy.cpu().numpy().astype(int),
                                 yolo_res.boxes.conf.cpu().numpy()):
                if conf < YOLO_CONF_MIN:
                    continue
                x1, y1_b, x2, y2_b = box
                area = (x2 - x1) * (y2_b - y1_b)
                if area > best_area:   # take the largest (closest) person
                    best_area = area
                    best_box  = box

        if best_box is not None:
            x1, y1_b, x2, y2_b = best_box
            pad    = 20
            head_bottom = y1_b + int((y2_b - y1_b) * HEAD_CROP_FRAC)
            roi_x1 = max(0, x1 - pad)
            roi_y1 = max(0, y1_b - pad)
            roi_x2 = min(w, x2 + pad)
            roi_y2 = min(h, head_bottom + pad)
            cv2.rectangle(frame, (x1, y1_b), (x2, y2_b), (80, 80, 80), 1)
            tracking_label = "YOLO: person found"
        else:
            tracking_label = "YOLO: no person — move into frame"

    roi        = frame[roi_y1:roi_y2, roi_x1:roi_x2]
    roi_w_orig = roi_x2 - roi_x1   # original pixels — needed for dist_m
    upscale    = HEAD_UPSCALE if yolo_model is not None and tracking_label.startswith("YOLO: person") else FULL_UPSCALE

    if roi.size > 0:
        roi_h_px, roi_w_px = roi.shape[:2]
        roi_up = cv2.resize(roi, (roi_w_px * upscale, roi_h_px * upscale),
                            interpolation=cv2.INTER_LINEAR)
        rgb    = cv2.cvtColor(roi_up, cv2.COLOR_BGR2RGB)
        img    = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(img)

        if result.face_landmarks:
            lm = result.face_landmarks[0]
            yaw, pitch, distance, dist_m = get_angles(lm, roi_w_orig, focal_px)

            # Map normalised landmark coords back to original frame for dot
            nx = roi_x1 + int(lm[1].x * roi_w_orig)
            ny = roi_y1 + int(lm[1].y * (roi_y2 - roi_y1))
            cv2.circle(frame, (nx, ny), 6, (0, 255, 0), -1)

    # Pose for relative yaw (run on full frame — shoulders need full context)
    if pose_detector is not None and yaw is not None:
        rgb_pose = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pose_res = pose_detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_pose))
        if pose_res.pose_landmarks:
            pl  = pose_res.pose_landmarks[0]
            l_s = pl[11]
            r_s = pl[12]
            span = l_s.x - r_s.x
            if abs(span) > 0.02:
                shoulder_mid_x = (l_s.x + r_s.x) / 2.0
                rel_yaw = (pl[0].x - shoulder_mid_x) / (abs(span) + 1e-6)

    # ── HUD ──────────────────────────────────────────────────────
    if yaw is not None:
        cv2.putText(frame, f"Yaw:    {yaw:+.3f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Pitch:  {pitch:+.3f}", (10, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Dist:   ~{dist_m:.2f}m", (10, 86),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
        if rel_yaw is not None:
            cv2.putText(frame, f"R-Yaw: {rel_yaw:+.3f}", (10, 114),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 100), 2)
    else:
        msg = tracking_label if tracking_label else "No face — move into frame"
        cv2.putText(frame, msg, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # Show which points have been captured
    status_y = 145
    for k in "12345":
        color  = (0, 255, 0) if k in captured else (100, 100, 100)
        label  = f"[{'✓' if k in captured else ' '}] {k}: {INSTRUCTIONS[k][:40]}"
        cv2.putText(frame, label, (10, status_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        status_y += 22

    cv2.imshow("VisionMetrics — Store Calibration  [1-5=Capture | S=Save | Q=Quit]", frame)

    key = cv2.waitKey(1) & 0xFF

    if chr(key) in CAPTURE_KEYS and yaw is not None:
        k = chr(key)
        captured[k] = (yaw, pitch, distance)
        ryaw_str = f"  R-Yaw={rel_yaw:+.3f}" if rel_yaw is not None else ""
        if k == "2":
            calibration["engagement_zone"]["yaw_center"]  = round(yaw, 5)
            calibration["engagement_zone"]["pitch_center"] = round(pitch, 5)
            print(f"  ✓ CENTER  →  Yaw={yaw:+.3f}  Pitch={pitch:+.3f}{ryaw_str}")
        elif k == "1":
            calibration["engagement_zone"]["yaw_left"] = round(yaw, 5)
            print(f"  ✓ LEFT    →  Yaw={yaw:+.3f}{ryaw_str}")
        elif k == "3":
            calibration["engagement_zone"]["yaw_right"] = round(yaw, 5)
            print(f"  ✓ RIGHT   →  Yaw={yaw:+.3f}{ryaw_str}")
        elif k == "4":
            calibration["engagement_zone"]["dist_close"]   = round(distance, 5)
            calibration["engagement_zone"]["dist_close_m"] = round(dist_m, 2)
            print(f"  ✓ CLOSE   →  ~{dist_m:.2f}m  (proxy={distance:.4f})")
        elif k == "5":
            calibration["engagement_zone"]["dist_far"]   = round(distance, 5)
            calibration["engagement_zone"]["dist_far_m"] = round(dist_m, 2)
            print(f"  ✓ FAR     →  ~{dist_m:.2f}m  (proxy={distance:.4f})")

    elif key == ord('s'):
        # Compute derived boundaries with a small tolerance margin
        z = calibration["engagement_zone"]
        TOLERANCE_YAW   = 0.15   # ~15% buffer on each side in normalised units
        TOLERANCE_PITCH = 0.10

        if None in (z["yaw_left"], z["yaw_right"], z["pitch_center"]):
            print("⚠️  Please capture at least LEFT (1), CENTER (2), and RIGHT (3) before saving.")
            continue

        calibration["derived"]["yaw_min"]   = round(min(z["yaw_left"], z["yaw_right"]) - TOLERANCE_YAW, 5)
        calibration["derived"]["yaw_max"]   = round(max(z["yaw_left"], z["yaw_right"]) + TOLERANCE_YAW, 5)
        calibration["derived"]["pitch_min"] = round(z["pitch_center"] - TOLERANCE_PITCH, 5)
        calibration["derived"]["pitch_max"] = round(z["pitch_center"] + TOLERANCE_PITCH, 5)
        calibration["derived"]["dist_min"]  = round(z["dist_far"], 5) if z["dist_far"] else 0.03
        # Real-world distance limit in metres (used by main.py pinhole camera model)
        if z.get("dist_far_m") is not None:
            calibration["derived"]["dist_max_m"] = round(z["dist_far_m"], 2)

        # Merge into any existing store config so we don't wipe a counting_region
        # drawn with draw_zone (the two tools write different parts of the same file).
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    existing = json.load(f)
                for k, v in existing.items():
                    calibration.setdefault(k, v)
            except (json.JSONDecodeError, OSError):
                pass

        with open(CONFIG_PATH, "w") as f:
            json.dump(calibration, f, indent=2)

        print(f"\n✅  Calibration saved → {CONFIG_PATH}")
        print(f"   Engagement Yaw:   [{calibration['derived']['yaw_min']:+.3f}, {calibration['derived']['yaw_max']:+.3f}]")
        print(f"   Engagement Pitch: [{calibration['derived']['pitch_min']:+.3f}, {calibration['derived']['pitch_max']:+.3f}]")
        if calibration["derived"].get("dist_max_m"):
            print(f"   Max Distance:     {calibration['derived']['dist_max_m']:.1f}m (camera model)")
        else:
            print(f"   Min Distance:     {calibration['derived']['dist_min']:.4f} (proxy — run FAR capture for metres)")
        break

    elif key == ord('q'):
        print("Quit without saving.")
        break

cap.release()
cv2.destroyAllWindows()
