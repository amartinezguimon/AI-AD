"""Person detection + tracking (YOLOv8) — Layer 1, with second-pass filters.

Wraps Ultralytics YOLO.track and applies the cheap false-positive filters that
ran inline in the prototype: confidence floor and aspect-ratio (people are
taller than wide; chairs/bags are not). The ghost-track blacklist lives in the
pipeline because it needs cross-frame face feedback.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass


@dataclass
class Detection:
    track_id: int
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float


class PersonDetector:
    def __init__(self, model_path: str, *, conf_min: float, aspect_ratio_min: float,
                 track_buffer: int = 30):
        from ultralytics import YOLO  # imported lazily so tests can mock the class
        self._model = YOLO(model_path)
        self.conf_min = conf_min
        self.aspect_ratio_min = aspect_ratio_min
        # Custom ByteTrack config: a larger track_buffer keeps a momentarily-lost
        # track alive (same id) for longer, which is the first defence against
        # re-counting a person after a brief detection gap.
        self._tracker_cfg = self._write_tracker_cfg(track_buffer)

    @staticmethod
    def _write_tracker_cfg(track_buffer: int) -> str:
        cfg = (
            "tracker_type: bytetrack\n"
            "track_high_thresh: 0.25\n"
            "track_low_thresh: 0.1\n"
            "new_track_thresh: 0.25\n"
            f"track_buffer: {int(track_buffer)}\n"
            "match_thresh: 0.8\n"
            "fuse_score: true\n"
        )
        fd, path = tempfile.mkstemp(prefix="vm_tracker_", suffix=".yaml")
        with os.fdopen(fd, "w") as f:
            f.write(cfg)
        return path

    def detect(self, frame) -> list[Detection]:
        """Track persons in a BGR frame and return filtered detections."""
        results = self._model.track(frame, classes=[0], persist=True, verbose=False,
                                    tracker=self._tracker_cfg)
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
