"""Draw the counting zone for a store, on a frame from its camera.

This is the operator step that fixes "people too far away get counted": you trace
the area on the ground that actually belongs to your storefront (the pavement in
front of the window). Only people whose feet land inside it are ever counted —
for foot traffic AND for engagement.

    python -m visionmetrics.edge.tools.draw_zone --source 0 --config configs/store_config.json

Controls (in the window):
    SPACE       freeze the current live frame to draw on (wait until you see the image)
    left click  add a polygon point (once frozen)
    u           undo last point        c   clear all points
    r           back to live video (re-freeze)
    s / Enter   save the polygon into the store config and quit
    q / Esc     quit without saving

Showing the LIVE feed first (instead of grabbing one still) is deliberate: phone
webcams like Camo Studio stream intermittently / start black, so you freeze the
moment the picture looks right.

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


def main() -> int:
    import cv2
    import numpy as np

    from ..agent.capture import open_capture  # DirectShow on Windows so Camo/OBS open

    ap = argparse.ArgumentParser(description="Draw the per-store counting zone.")
    ap.add_argument("--source", default="0", help="camera index, RTSP url, video, or image path")
    ap.add_argument("--config", default="configs/store_config.json",
                    help="store config JSON to update (created if missing)")
    args = ap.parse_args()

    FONT = cv2.FONT_HERSHEY_SIMPLEX
    win = "VisionMetrics - zona de conteo"
    points: list[tuple[int, int]] = []
    frozen = {"img": None}     # the still we draw on (None = showing live video)

    # An image-file source is frozen immediately; a camera streams until you freeze it.
    cap = None
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if Path(args.source).suffix.lower() in img_exts and Path(args.source).exists():
        img = cv2.imread(args.source)
        if img is None:
            raise SystemExit(f"No pude leer la imagen: {args.source}")
        frozen["img"] = img
    else:
        cap = open_capture(args.source)
        if not cap.isOpened():
            raise SystemExit(f"No pude abrir la cámara {args.source}. Usa 'Ver cámaras'.")

    def on_mouse(event, x, y, _flags, _param):
        if frozen["img"] is not None and event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    print("[zona] ESPACIO=congelar  clic=esquina  S=guardar  U=deshacer  C=limpiar  R=en vivo  Q=salir")

    live = None
    while True:
        if frozen["img"] is None:                       # ── LIVE preview ──
            ok, f = cap.read()
            if ok and f is not None:
                live = f
            canvas = live.copy() if live is not None else np.zeros((480, 640, 3), np.uint8)
            if live is None or float(live.mean()) < 8:
                cv2.putText(canvas, "Imagen NEGRA: abre Camo y conecta el movil",
                            (12, 30), FONT, 0.6, (60, 60, 255), 2)
            else:
                cv2.putText(canvas, "Cuando se vea bien, pulsa ESPACIO para congelar",
                            (12, 30), FONT, 0.6, (0, 215, 255), 2)
        else:                                           # ── FROZEN: draw polygon ──
            canvas = frozen["img"].copy()
            for i, p in enumerate(points):
                cv2.circle(canvas, p, 5, (0, 215, 240), -1)
                if i > 0:
                    cv2.line(canvas, points[i - 1], p, (0, 215, 240), 2)
            if len(points) >= 3:
                cv2.line(canvas, points[-1], points[0], (120, 120, 120), 1)
            cv2.putText(canvas, f"{len(points)} puntos | clic=esquina  S=guardar  U=deshacer  R=en vivo",
                        (12, 30), FONT, 0.52, (255, 255, 255), 2)

        cv2.imshow(win, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            print("Cancelado — no se guardó nada.")
            break
        elif key == 32 and cap is not None:             # SPACE = freeze the current frame
            if live is not None and float(live.mean()) >= 8:
                frozen["img"] = live.copy()
                points.clear()
            else:
                print("  Aún no hay imagen (negra). Abre Camo / conecta el móvil.")
        elif key == ord("r") and cap is not None:       # back to live video
            frozen["img"] = None
            points.clear()
        elif key == ord("u") and points:
            points.pop()
        elif key == ord("c"):
            points.clear()
        elif key in (ord("s"), 13):
            if frozen["img"] is None:
                print("  Primero congela la imagen con ESPACIO.")
                continue
            if len(points) < 3:
                print("  Necesitas al menos 3 puntos.")
                continue
            h, w = frozen["img"].shape[:2]
            poly = normalize_polygon(points, w, h)
            save_counting_region(args.config, poly)
            print(f"Zona de {len(poly)} puntos guardada en {args.config}")
            break

    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
