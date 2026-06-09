"""Video source — one abstraction over USB index, RTSP stream, and file.

The prototype only knew how to open a webcam index and assumed it never failed.
A store deployment must also pull from an IP camera (RTSP) that drops and comes
back, and we want to replay recorded clips for offline testing. All three are
the same to OpenCV; the differences this class handles are:

* realtime sources (webcam / RTSP) -> a background thread always serves the
  NEWEST frame (stale frames are dropped) and the stream auto-reconnects;
* file sources -> frames are read sequentially in order (none dropped) and the
  stream simply ends.
"""

from __future__ import annotations

import threading
import time

import cv2


def _is_realtime(source) -> bool:
    """Webcam indices and network streams are realtime; file paths are not."""
    if isinstance(source, int):
        return True
    s = str(source).lower()
    return s.startswith(("rtsp://", "http://", "https://", "udp://"))


class VideoSource:
    def __init__(self, source, *, reconnect_delay_s: float = 2.0):
        self.source = source
        self.reconnect_delay_s = reconnect_delay_s
        self.realtime = _is_realtime(source)
        self._cap: cv2.VideoCapture | None = None
        self._frame = None
        self._ok = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_config(cls, camera_cfg) -> "VideoSource":
        return cls(camera_cfg.source, reconnect_delay_s=camera_cfg.reconnect_delay_s)

    # ── lifecycle ────────────────────────────────────────────────
    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            return False
        if self.realtime:
            self._stop.clear()
            self._thread = threading.Thread(target=self._pump, daemon=True)
            self._thread.start()
        return True

    def read(self):
        """Return ``(ok, frame)``. For realtime sources this is the newest frame."""
        if self.realtime:
            with self._lock:
                return self._ok, (self._frame.copy() if self._frame is not None else None)
        ok, frame = self._cap.read()
        return ok, frame

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._cap is not None:
            self._cap.release()

    # ── properties ───────────────────────────────────────────────
    @property
    def width(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self._cap else 0

    @property
    def height(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self._cap else 0

    @property
    def fps(self) -> float:
        return float(self._cap.get(cv2.CAP_PROP_FPS)) if self._cap else 0.0

    # ── background pump (realtime only) ──────────────────────────
    def _pump(self) -> None:
        while not self._stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                self._reconnect()
                continue
            ok, frame = self._cap.read()
            if not ok:
                self._reconnect()
                continue
            with self._lock:
                self._ok, self._frame = ok, frame

    def _reconnect(self) -> None:
        with self._lock:
            self._ok = False
        if self._cap is not None:
            self._cap.release()
        if self._stop.wait(self.reconnect_delay_s):
            return
        self._cap = cv2.VideoCapture(self.source)
