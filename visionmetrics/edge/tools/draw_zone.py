"""Draw the counting zone for a store, on a frame from its camera.

This is the operator step that fixes "people too far away get counted": you trace
the area on the ground that actually belongs to your storefront (the pavement in
front of the window). Only people whose feet land inside it are ever counted —
for foot traffic AND for engagement.

    python -m visionmetrics.edge.tools.draw_zone --source 0 --config configs/store_config.json

Controls (in the window):
    left click  add a polygon point
    u           undo last point
    c           clear all points
    s / Enter   save the polygon into the store config and quit
    q / Esc     quit without saving

The polygon is stored in NORMALISED [0..1] image coordinates, so it survives a
camera-resolution change (but must be re-drawn if the camera is physically moved).

The pure helpers (normalise / merge / load) are unit-tested; the OpenCV window in
``main`` is not (it needs a display + a camera).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize_polygon(points_px: list[tuple[int, int]], frame_w: int, frame_h: int
                      ) -> list[list[float]]:
    """Pixel points -> normalised [0..1] coords, clamped to the frame."""
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("frame_w and frame_h must be positive")
    out: list[list[float]] = []
    for x, y in points_px:
        nx = min(1.0, max(0.0, x / frame_w))
        ny = min(1.0, max(0.0, y / frame_h))
        out.append([round(nx, 4), round(ny, 4)])
    return out


def load_config_dict(path: str | Path) -> dict:
    """Read a store-config JSON, or an empty dict if it doesn't exist yet."""
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def merge_counting_region(config: dict, polygon_norm: list[list[float]]) -> dict:
    """Return a copy of ``config`` with the counting_region polygon set/replaced.

    Every other key (engagement_zone, derived, …) is preserved untouched, so this
    can be run after the angular calibration without clobbering it.
    """
    updated = dict(config)
    updated["counting_region"] = {
        "_comment": "Normalised [0..1] image coords; a person's feet must fall "
                    "inside to be counted (foot traffic and engagement).",
        "polygon": polygon_norm,
    }
    return updated


def save_counting_region(config_path: str | Path, polygon_norm: list[list[float]]) -> None:
    merged = merge_counting_region(load_config_dict(config_path), polygon_norm)
    Path(config_path).write_text(json.dumps(merged, indent=2, ensure_ascii=False),
                                 encoding="utf-8")


def _grab_frame(source: str):
    """Read one frame from a camera index / RTSP url / video, or an image file."""
    import cv2  # lazy: keeps the module importable (and testable) without OpenCV

    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if Path(source).suffix.lower() in img_exts and Path(source).exists():
        frame = cv2.imread(source)
        if frame is None:
            raise SystemExit(f"Could not read image: {source}")
        return frame

    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise SystemExit(f"Could not grab a frame from source: {source}")
    return frame


def main() -> int:
    import cv2

    ap = argparse.ArgumentParser(description="Draw the per-store counting zone.")
    ap.add_argument("--source", default="0", help="camera index, RTSP url, video, or image path")
    ap.add_argument("--config", default="configs/store_config.json",
                    help="store config JSON to update (created if missing)")
    args = ap.parse_args()

    frame = _grab_frame(args.source)
    h, w = frame.shape[:2]
    points: list[tuple[int, int]] = []
    win = "VisionMetrics — draw counting zone (s=save, u=undo, c=clear, q=quit)"

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        canvas = frame.copy()
        if points:
            for i, p in enumerate(points):
                cv2.circle(canvas, p, 5, (0, 215, 240), -1)
                if i > 0:
                    cv2.line(canvas, points[i - 1], p, (0, 215, 240), 2)
            if len(points) >= 3:
                cv2.line(canvas, points[-1], points[0], (120, 120, 120), 1)
        cv2.putText(canvas, f"{len(points)} puntos  |  s=guardar  u=deshacer  c=limpiar  q=salir",
                    (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(win, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            print("Cancelled — nothing saved.")
            break
        if key == ord("u") and points:
            points.pop()
        elif key == ord("c"):
            points.clear()
        elif key in (ord("s"), 13):
            if len(points) < 3:
                print("Need at least 3 points to make a zone.")
                continue
            poly = normalize_polygon(points, w, h)
            save_counting_region(args.config, poly)
            print(f"Saved {len(poly)}-point counting zone to {args.config}")
            break

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
