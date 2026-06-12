"""Training-data collector built on the PRODUCTION vision pipeline.

Records `(yaw, pitch, distance, label)` rows for the engagement model using the
EXACT same person detector + head-pose extractor the live agent uses
(`visionmetrics.edge.agent.vision`). Two consequences that matter:

* **Same "eye" as inference** — whatever the running agent can resolve far away,
  this captures too. The old `src/training/data_collector.py` *looked* like it
  missed far subjects: it recorded a single snapshot on each key-press, and at
  range the face only resolves intermittently, so the press often landed on a
  miss. This tool captures CONTINUOUSLY (like the agent), catching the hits as
  they come.
* **No train/serve skew** — the features written here are computed by the very
  same code that computes them in production, so the model trains on exactly what
  it will see live (the legacy collector duplicated the logic and could drift).

Controls (OpenCV window):
    L  record one LOOKING (1)        A  record one AWAY (0)
    T  toggle continuous capture     M  switch the capture label
    Q  quit and save

Run:
    python -m visionmetrics.training.collect --camera 0
    python -m visionmetrics.training.collect --camera 1 --output data/eval_set.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

CSV_HEADER = ["yaw", "pitch", "distance", "label"]


def tier_for(face_width: float) -> str:
    """Coarse distance bucket from normalised face width (for live feedback)."""
    if face_width >= 0.25:
        return "near <0.5m"
    if face_width >= 0.10:
        return "mid 0.5-1.5m"
    if face_width >= 0.04:
        return "far 1.5-3.5m"
    return "v-far >3.5m"


class SampleWriter:
    """Buffers labelled samples and appends them to a CSV (header if new)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.rows: list[tuple] = []
        self.counts = {1: 0, 0: 0}
        self.tier_counts: dict[str, dict[int, int]] = {}

    def add(self, yaw: float, pitch: float, distance: float, label: int, tier: str) -> None:
        self.rows.append((round(yaw, 5), round(pitch, 5), round(distance, 5), int(label)))
        self.counts[label] += 1
        self.tier_counts.setdefault(tier, {1: 0, 0: 0})[label] += 1

    def save(self) -> int:
        """Append buffered rows to the CSV. Returns how many were written."""
        if not self.rows:
            return 0
        new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(CSV_HEADER)
            w.writerows(self.rows)
        return len(self.rows)


def _largest_box(detections):
    if not detections:
        return None
    d = max(detections, key=lambda d: (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]))
    return d.bbox


def run(camera, output, *, fov_h_deg=70.0, every=2, conf=0.25, aspect=0.30,
        config_path=None) -> int:
    # Heavy deps imported lazily so the pure helpers above stay cheap to import/test.
    import cv2

    from ..edge.agent.camera_model import focal_length_px
    from ..edge.agent.config import DeviceConfig
    from ..edge.agent.models_bootstrap import ensure_models
    from ..edge.agent.vision.detector import PersonDetector
    from ..edge.agent.vision.face import HeadPoseAnalyzer

    config = DeviceConfig.load(config_path) if config_path else DeviceConfig()
    ensure_models(config)
    v = config.vision

    # Permissive detection for collection (find far people); face extraction is the
    # SAME production code, so what gets recorded matches what inference sees.
    detector = PersonDetector(config.models.yolo, conf_min=conf, aspect_ratio_min=aspect)
    analyzer = HeadPoseAnalyzer(
        config.models.face, face_width_m=v.face_width_m, head_crop_frac=v.head_crop_frac,
        head_upscale=v.head_upscale, skip_frames=1,   # analyse EVERY frame (no skipping)
    )

    src = int(camera) if str(camera).isdigit() else camera
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"ERROR: cannot open camera {camera!r}")
        return 1

    writer = SampleWriter(output)
    auto = False
    label = 1
    focal_px = None
    frame_idx = 0
    print("[collect] L=look  A=away  T=toggle auto  M=switch label  Q=quit+save")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            if focal_px is None:
                focal_px = focal_length_px(frame.shape[1], fov_h_deg)

            box = _largest_box(detector.detect(frame))
            pose = analyzer.analyze(frame, box, 0, frame_idx, focal_px) if box else None
            frame_idx += 1

            tier = "—"
            if pose is not None:
                tier = tier_for(pose.distance)
                cv2.circle(frame, pose.nose_px, 5, (0, 255, 0), -1)
                if auto and frame_idx % max(1, every) == 0:
                    writer.add(pose.yaw, pose.pitch, pose.distance, label, tier)

            _draw_hud(cv2, frame, pose, tier, auto, label, writer)
            cv2.imshow("VisionMetrics — data collector", frame)
            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            elif k == ord("t"):
                auto = not auto
            elif k == ord("m"):
                label = 0 if label == 1 else 1
            elif k == ord("l") and pose is not None:
                writer.add(pose.yaw, pose.pitch, pose.distance, 1, tier)
            elif k == ord("a") and pose is not None:
                writer.add(pose.yaw, pose.pitch, pose.distance, 0, tier)
    finally:
        cap.release()
        cv2.destroyAllWindows()

    n = writer.save()
    print(f"[collect] saved {n} samples to {output} "
          f"(look={writer.counts[1]} away={writer.counts[0]})")
    for t, c in writer.tier_counts.items():
        print(f"          {t}: look={c[1]} away={c[0]}")
    return 0


def _draw_hud(cv2, frame, pose, tier, auto, label, writer):
    put = lambda txt, y, col=(255, 255, 255), s=0.6: cv2.putText(
        frame, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, s, col, 2)
    if pose is not None:
        put(f"yaw {pose.yaw:+.3f}  pitch {pose.pitch:+.3f}  dist {pose.distance:.4f}", 30)
        put(f"[{tier}]", 58, (0, 220, 80))
    else:
        put("no face", 30, (0, 0, 255))
    mode = f"AUTO: {'look' if label == 1 else 'away'}" if auto else "manual"
    put(mode, 86, (0, 220, 100) if auto else (180, 180, 180))
    put(f"look {writer.counts[1]}  away {writer.counts[0]}", 114, (0, 220, 255))


def main() -> int:
    ap = argparse.ArgumentParser(description="VisionMetrics training-data collector")
    ap.add_argument("--camera", default="0", help="camera index or path/RTSP url")
    ap.add_argument("--output", default="data/engagement_data.csv")
    ap.add_argument("--fov", type=float, default=70.0, help="camera horizontal FOV (deg)")
    ap.add_argument("--every", type=int, default=2, help="auto-capture every Nth frame")
    ap.add_argument("--conf", type=float, default=0.25, help="YOLO person confidence floor")
    ap.add_argument("--aspect", type=float, default=0.30, help="bbox height/width floor")
    ap.add_argument("--config", default=None, help="optional device.yaml for model paths")
    a = ap.parse_args()
    return run(a.camera, a.output, fov_h_deg=a.fov, every=a.every, conf=a.conf,
               aspect=a.aspect, config_path=a.config)


if __name__ == "__main__":
    raise SystemExit(main())
