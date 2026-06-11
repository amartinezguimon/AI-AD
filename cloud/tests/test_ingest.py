"""Ingest API: auth, tenant isolation, idempotency."""

from __future__ import annotations

from cloud.app import provisioning as prov


def _bucket(window_start="2026-06-11T10:00:00+00:00", **over):
    b = {
        "schema_version": 1,
        "device_id": "dev-1",
        "store_id": "store-1",
        "window_start": window_start,
        "window_end": "2026-06-11T11:00:00+00:00",
        "passersby": 50, "engaged": 8, "engagement_rate": 16.0, "total_attention_s": 120.0,
    }
    b.update(over)
    return b


def _provision(db, device_id="dev-1"):
    org = prov.create_org(db, "Org")
    store = prov.create_store(db, org.id, "Store")
    return prov.create_device(db, org.id, store.id, device_id)


def test_metrics_rejected_without_key(client):
    assert client.post("/v1/metrics", json=_bucket()).status_code in (401, 403)


def test_metrics_rejected_with_bad_key(client):
    r = client.post("/v1/metrics", json=_bucket(),
                    headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_metrics_accepted_and_scoped_to_device_tenant(client, db_session):
    pd = _provision(db_session)
    from cloud.app.models import MetricBucket
    r = client.post("/v1/metrics", json=_bucket(),
                    headers={"Authorization": f"Bearer {pd.api_key}"})
    assert r.status_code == 200 and r.json()["detail"] == "created"
    row = db_session.query(MetricBucket).one()
    # org/store come from the device row, not the request body.
    assert row.org_id == pd.device.org_id
    assert row.store_id == pd.device.store_id
    assert row.passersby == 50


def test_bucket_idempotent_on_resend(client, db_session):
    pd = _provision(db_session)
    from cloud.app.models import MetricBucket
    h = {"Authorization": f"Bearer {pd.api_key}"}
    client.post("/v1/metrics", json=_bucket(passersby=50), headers=h)
    # same window, updated numbers (offline-buffer replay) -> update, not duplicate
    r = client.post("/v1/metrics", json=_bucket(passersby=77), headers=h)
    assert r.json()["detail"] == "updated"
    rows = db_session.query(MetricBucket).all()
    assert len(rows) == 1 and rows[0].passersby == 77


def test_heartbeat_marks_device_online(client, db_session):
    pd = _provision(db_session)
    from cloud.app.models import Device
    hb = {
        "schema_version": 1, "device_id": "dev-1", "store_id": "store-1",
        "sent_at": 1781000000.0, "agent_version": "0.2.0", "camera_ok": True,
        "fps_display": 9.1, "fps_analysis": 9.1, "people_tracked": 2,
    }
    r = client.post("/v1/heartbeat", json=hb, headers={"Authorization": f"Bearer {pd.api_key}"})
    assert r.status_code == 200
    dev = db_session.get(Device, "dev-1")
    assert dev.status == "online" and dev.last_seen_at is not None
    assert dev.agent_version == "0.2.0"
