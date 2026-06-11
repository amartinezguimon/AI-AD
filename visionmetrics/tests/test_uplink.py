"""Tests for the cloud uplink: SQLite buffer durability + delivery/retry logic.

A fake transport stands in for the network so these run offline and fast.
"""

from __future__ import annotations

from visionmetrics.edge.agent.config import UplinkConfig
from visionmetrics.edge.agent.uplink import Uplink, UplinkBuffer
from visionmetrics.shared.schema import SCHEMA_VERSION, MetricBucket


def _bucket(window_start: str, passersby: int = 3) -> MetricBucket:
    return MetricBucket(
        schema_version=SCHEMA_VERSION,
        device_id="dev-1",
        store_id="store-1",
        window_start=window_start,
        window_end=window_start,
        passersby=passersby,
        engaged=1,
        engagement_rate=33.3,
        total_attention_s=5.0,
    )


# ── buffer ──────────────────────────────────────────────────────
def test_buffer_enqueue_and_pending(tmp_path):
    buf = UplinkBuffer(str(tmp_path / "b.sqlite"))
    buf.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    buf.enqueue(_bucket("2026-06-09T11:00:00+00:00"))
    assert buf.count() == 2
    keys = [k for k, _ in buf.pending()]
    assert keys == ["dev-1:2026-06-09T10:00:00+00:00", "dev-1:2026-06-09T11:00:00+00:00"]
    buf.close()


def test_buffer_dedups_on_idempotency_key(tmp_path):
    buf = UplinkBuffer(str(tmp_path / "b.sqlite"))
    buf.enqueue(_bucket("2026-06-09T10:00:00+00:00", passersby=3))
    buf.enqueue(_bucket("2026-06-09T10:00:00+00:00", passersby=9))  # same window, updated
    assert buf.count() == 1
    _, payload = buf.pending()[0]
    assert payload["passersby"] == 9   # the newer value won
    buf.close()


def test_buffer_mark_sent_removes(tmp_path):
    buf = UplinkBuffer(str(tmp_path / "b.sqlite"))
    buf.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    key = buf.pending()[0][0]
    buf.mark_sent(key)
    assert buf.count() == 0
    buf.close()


def test_buffer_persists_across_reopen(tmp_path):
    path = str(tmp_path / "b.sqlite")
    buf = UplinkBuffer(path)
    buf.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    buf.close()
    buf2 = UplinkBuffer(path)            # simulate an agent restart
    assert buf2.count() == 1
    buf2.close()


# ── delivery / retry ────────────────────────────────────────────
class _FakeTransport:
    def __init__(self, succeed=True):
        self.succeed = succeed
        self.calls = []

    def __call__(self, url, payload, api_key):
        self.calls.append((url, payload))
        return self.succeed


def _uplink(tmp_path, transport):
    cfg = UplinkConfig(enabled=True, base_url="https://api.example.com",
                       api_key="k", buffer_path=str(tmp_path / "b.sqlite"))
    return Uplink(cfg, transport=transport)


def test_flush_sends_all_on_success(tmp_path):
    fake = _FakeTransport(succeed=True)
    up = _uplink(tmp_path, fake)
    up.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    up.enqueue(_bucket("2026-06-09T11:00:00+00:00"))
    assert up.flush_once() == 2
    assert up.buffer.count() == 0
    assert fake.calls[0][0] == "https://api.example.com/v1/metrics"
    up.buffer.close()


def test_flush_keeps_buffered_on_failure(tmp_path):
    fake = _FakeTransport(succeed=False)
    up = _uplink(tmp_path, fake)
    up.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    up.enqueue(_bucket("2026-06-09T11:00:00+00:00"))
    assert up.flush_once() == 0
    assert up.buffer.count() == 2        # nothing lost while offline
    assert len(fake.calls) == 1          # stopped at the first failure
    up.buffer.close()


def test_flush_resumes_after_recovery(tmp_path):
    fake = _FakeTransport(succeed=False)
    up = _uplink(tmp_path, fake)
    up.enqueue(_bucket("2026-06-09T10:00:00+00:00"))
    up.flush_once()                      # offline: stays buffered
    assert up.buffer.count() == 1
    fake.succeed = True                  # network comes back
    assert up.flush_once() == 1
    assert up.buffer.count() == 0
    up.buffer.close()


def test_heartbeat_not_buffered_on_failure(tmp_path):
    fake = _FakeTransport(succeed=False)
    up = _uplink(tmp_path, fake)
    from visionmetrics.shared.schema import Heartbeat
    hb = Heartbeat(SCHEMA_VERSION, "dev-1", "store-1", 123.0, "0.2.0", True, 9.0, 9.0, 1)
    assert up.send_heartbeat(hb) is False
    assert up.buffer.count() == 0        # liveness pings never queue up
    up.buffer.close()
