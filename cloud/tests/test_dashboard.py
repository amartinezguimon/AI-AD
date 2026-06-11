"""Dashboard auth + read API, with the all-important tenant-isolation checks."""

from __future__ import annotations

from cloud.app import provisioning as prov
from cloud.app.models import MetricBucket


def _seed_org(db, name, email, password="pw123456", store="Centro"):
    org = prov.create_org(db, name)
    st = prov.create_store(db, org.id, store)
    prov.create_user(db, org.id, email, password, role="admin")
    return org, st


def _login(client, email, password="pw123456"):
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_bucket(db, org_id, store_id, device_id, ws, pax, eng):
    db.add(MetricBucket(org_id=org_id, store_id=store_id, device_id=device_id,
                        window_start=ws, window_end=ws, passersby=pax, engaged=eng,
                        engagement_rate=round(eng / pax * 100, 1) if pax else 0.0,
                        total_attention_s=float(eng * 5)))
    db.commit()


# ── auth ──────────────────────────────────────────────────────────
def test_login_and_me(client, db_session):
    org, _ = _seed_org(db_session, "Perez", "owner@perez.com")
    h = _login(client, "owner@perez.com")
    me = client.get("/v1/me", headers=h).json()
    assert me["email"] == "owner@perez.com" and me["org_id"] == org.id and me["role"] == "admin"


def test_login_wrong_password(client, db_session):
    _seed_org(db_session, "Perez", "owner@perez.com")
    r = client.post("/v1/auth/login", json={"email": "owner@perez.com", "password": "nope"})
    assert r.status_code == 401


def test_protected_endpoint_needs_token(client, db_session):
    assert client.get("/v1/me").status_code in (401, 403)


# ── tenant isolation (the critical property) ─────────────────────
def test_user_sees_only_their_org_stores(client, db_session):
    a, _ = _seed_org(db_session, "OrgA", "a@a.com", store="A-Centro")
    _seed_org(db_session, "OrgB", "b@b.com", store="B-Granvia")
    h = _login(client, "a@a.com")
    stores = client.get("/v1/stores", headers=h).json()
    names = {s["name"] for s in stores}
    assert names == {"A-Centro"}            # never sees OrgB's store


def test_summary_is_scoped_and_aggregated(client, db_session):
    a, sa = _seed_org(db_session, "OrgA", "a@a.com")
    b, sb = _seed_org(db_session, "OrgB", "b@b.com")
    da = prov.create_device(db_session, a.id, sa.id, "devA").device
    db_ = prov.create_device(db_session, b.id, sb.id, "devB").device
    _add_bucket(db_session, a.id, sa.id, da.id, "2026-06-11T10:00:00+00:00", 100, 20)
    _add_bucket(db_session, a.id, sa.id, da.id, "2026-06-11T11:00:00+00:00", 100, 10)
    _add_bucket(db_session, b.id, sb.id, db_.id, "2026-06-11T10:00:00+00:00", 999, 999)

    h = _login(client, "a@a.com")
    s = client.get("/v1/metrics/summary", headers=h).json()
    assert s["passersby"] == 200 and s["engaged"] == 30      # only OrgA, summed
    assert s["engagement_rate"] == 15.0                       # 30/200


def test_timeseries_date_range_filter(client, db_session):
    a, sa = _seed_org(db_session, "OrgA", "a@a.com")
    da = prov.create_device(db_session, a.id, sa.id, "devA").device
    _add_bucket(db_session, a.id, sa.id, da.id, "2026-06-10T10:00:00+00:00", 10, 1)
    _add_bucket(db_session, a.id, sa.id, da.id, "2026-06-11T10:00:00+00:00", 20, 2)
    h = _login(client, "a@a.com")
    rows = client.get("/v1/metrics/timeseries"
                      "?from=2026-06-11T00:00:00+00:00&to=2026-06-12T00:00:00+00:00",
                      headers=h).json()
    assert len(rows) == 1 and rows[0]["passersby"] == 20


def test_store_scoped_user_cannot_query_other_store(client, db_session):
    org = prov.create_org(db_session, "Org")
    s1 = prov.create_store(db_session, org.id, "S1")
    s2 = prov.create_store(db_session, org.id, "S2")
    prov.create_user(db_session, org.id, "mgr@s1.com", "pw123456", role="viewer", store_id=s1.id)
    h = _login(client, "mgr@s1.com")
    # asking for the other store in the same org is forbidden
    assert client.get(f"/v1/metrics/summary?store_id={s2.id}", headers=h).status_code == 403
    # their own store is fine
    assert client.get(f"/v1/metrics/summary?store_id={s1.id}", headers=h).status_code == 200
