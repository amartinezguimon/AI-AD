"""Person detection + tracking (YOLOv8) — Layer 1, with second-pass filters.

Wraps Ultralytics YOLO.track and applies the cheap false-positive filters that
ran inline in the prototype: confidence floor and aspect-ratio (people are
taller than wide; chairs/bags are not). The ghost-track blacklist lives in the
pipeline because it needs cross-frame face feedback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    track_id: int
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float


class PersonDetector:
    def __init__(self, model_path: str, *, conf_min: float, aspect_ratio_min: float):
        from ultralytics import YOLO  # imported lazily so tests can mock the class
        self._model = YOLO(model_path)
        self.conf_min = conf_min
        self.aspect_ratio_min = aspect_ratio_min

    def detect(self, frame) -> list[Detection]:
        """Track persons in a BGR frame and return filtered detections."""
        results = self._model.track(frame, classes=[0], persist=True, verbose=False)
        return self._parse(results)

    def _parse(self, results) -> list[Detection]:
        out: list[Detection] = []
        r0 = results[0]
        if r0.boxes is None or r0.boxes.id is None:
            return out
        boxes = r0.boxes.xyxy.cpu().numpy().astype(int)
        ids = r0.boxes.id.cpu().numpy().astype(int)
        confs = r0.boxes.conf.cpu().numpy()
        for box, track_id, conf in zip(boxes, ids, confs):
            if conf < self.conf_min:
                continue
            x1, y1, x2, y2 = (int(v) for v in box)
            w = x2 - x1
            h = y2 - y1
            if w > 0 and (h / w) < self.aspect_ratio_min:
                continue  # too wide to be a standing person
            out.append(Detection(int(track_id), (x1, y1, x2, y2), float(conf)))
        return out
