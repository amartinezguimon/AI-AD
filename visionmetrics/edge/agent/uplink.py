"""Cloud uplink — durable delivery of metric buckets, never blocks the pipeline.

Two parts:

  ``UplinkBuffer`` — a SQLite-backed FIFO of pending buckets. Survives reboots
      and network outages. Keyed by ``idempotency_key`` so a re-enqueued bucket
      (e.g. an updated partial hour) overwrites in place instead of duplicating.

  ``Uplink`` — owns the buffer and a background sender thread. The main loop
      only calls the cheap ``enqueue()`` (a local SQLite write); a daemon thread
      drains the buffer to the cloud every ``flush_interval_s``. A dead network
      never stalls frame processing, and nothing is lost while offline.

Transport is injectable (``transport=`` arg) so tests run without a network; the
default is a tiny stdlib ``urllib`` POST (no third-party HTTP dependency).

GDPR note: only ``MetricBucket`` / ``Heartbeat`` dicts ever leave here — no
frames, no per-person rows. The schema is the guarantee; this module just ships
what the schema allows.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from visionmetrics.shared.schema import Heartbeat, MetricBucket

from .config import UplinkConfig

METRICS_PATH = "/v1/metrics"
HEARTBEAT_PATH = "/v1/heartbeat"

# transport(url, payload_dict, api_key) -> True on 2xx, False otherwise.
Transport = Callable[[str, dict, str], bool]


def http_post(url: str, payload: dict, api_key: str, timeout: float = 5.0) -> bool:
    """Default transport: a short-timeout JSON POST with a bearer token."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return False


class UplinkBuffer:
    """A persistent, deduplicated queue of metric buckets (SQLite)."""

    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS buckets ("
            "  idem_key   TEXT PRIMARY KEY,"
            "  payload    TEXT NOT NULL,"
            "  created_at REAL NOT NULL,"
            "  attempts   INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.commit()

    def enqueue(self, bucket: MetricBucket) -> None:
        """Add (or update) a bucket. Dedup/upsert on idempotency_key."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO buckets(idem_key, payload, created_at, attempts) "
                "VALUES(?,?,?,0) "
                "ON CONFLICT(idem_key) DO UPDATE SET payload=excluded.payload",
                (bucket.idempotency_key, json.dumps(bucket.to_dict()), time.time()),
            )
            self._conn.commit()

    def pending(self, limit: int = 100) -> list[tuple[str, dict]]:
        """Oldest-first list of (idem_key, payload_dict) still awaiting delivery."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT idem_key, payload FROM buckets ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
        return [(k, json.loads(p)) for k, p in rows]

    def mark_sent(self, idem_key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM buckets WHERE idem_key=?", (idem_key,))
            self._conn.commit()

    def mark_failed(self, idem_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE buckets SET attempts=attempts+1 WHERE idem_key=?", (idem_key,)
            )
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM buckets").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class Uplink:
    """Buffers buckets locally and ships them to the cloud on a daemon thread."""

    def __init__(self, config: UplinkConfig,
                 buffer: UplinkBuffer | None = None,
                 transport: Transport | None = None):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.flush_interval_s = config.flush_interval_s
        self.buffer = buffer or UplinkBuffer(config.buffer_path)
        self._transport: Transport = transport or http_post
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ── producer side (called from the main loop; cheap, local only) ──
    def enqueue(self, bucket: MetricBucket) -> None:
        self.buffer.enqueue(bucket)

    def send_heartbeat(self, hb: Heartbeat) -> bool:
        """Best-effort, NOT buffered: a stale liveness ping is worthless."""
        try:
            return self._transport(self.base_url + HEARTBEAT_PATH, hb.to_dict(), self.api_key)
        except Exception:
            return False

    # ── delivery ──────────────────────────────────────────────────
    def flush_once(self) -> int:
        """Try to deliver pending buckets. Returns how many were sent.

        Stops at the first failure (network likely down) and leaves the rest
        buffered for the next cycle, preserving order.
        """
        sent = 0
        for key, payload in self.buffer.pending():
            try:
                ok = self._transport(self.base_url + METRICS_PATH, payload, self.api_key)
            except Exception:
                ok = False
            if ok:
                self.buffer.mark_sent(key)
                sent += 1
            else:
                self.buffer.mark_failed(key)
                break
        return sent

    # ── lifecycle ─────────────────────────────────────────────────
    def start(self) -> None:
        if not self.config.enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="uplink", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        # wait() returns True when stop is set -> exits promptly on shutdown.
        while not self._stop.wait(self.flush_interval_s):
            self.flush_once()

    def stop(self, final_flush: bool = True) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if final_flush and self.config.enabled:
            self.flush_once()
        self.buffer.close()
