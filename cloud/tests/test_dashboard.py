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


def _seed_with_device(db, name, email, tz="Europe/Madrid"):
    org = prov.create_org(db, name)
    st = prov.create_store(db, org.id, "Centro", timezone=tz)
    prov.create_user(db, org.id, email, "pw123456", role="admin")
    dev = prov.create_device(db, org.id, st.id, email.split("@")[0]).device
    return org, st, dev


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


# ── /v1/dashboard (the shape the frontend renders) ────────────────
def test_dashboard_aggregates_by_day_and_hour(client, db_session):
    org, st, dev = _seed_with_device(db_session, "Joyeria", "o@j.com")
    # June 2026, Madrid = UTC+2 (CEST). 07:00Z -> 09:00 local (idx 0); 08:00Z -> 10:00 (idx 1).
    _add_bucket(db_session, org.id, st.id, dev.id, "2026-06-11T07:00:00+00:00", 50, 10)
    _add_bucket(db_session, org.id, st.id, dev.id, "2026-06-11T08:00:00+00:00", 30, 6)
    h = _login(client, "o@j.com")
    d = client.get("/v1/dashboard?year=2026&month=6", headers=h).json()

    assert d["has_data"] is True
    assert d["daily"]["11"] == {"total": 80, "looking": 16, "rate": 20, "avg": 5.0}
    hb = d["hourly"]["11"]
    assert len(hb["passing"]) == 12 and len(hb["looking"]) == 12
    assert hb["passing"][0] == 50 and hb["passing"][1] == 30
    assert hb["looking"][0] == 10 and hb["looking"][1] == 6


def test_dashboard_buckets_use_store_local_day(client, db_session):
    org, st, dev = _seed_with_device(db_session, "X", "x@x.com")
    # 22:00Z on Jun 15 is 00:00 Jun 16 in Madrid — must land on local day 16, not 15.
    _add_bucket(db_session, org.id, st.id, dev.id, "2026-06-15T22:00:00+00:00", 40, 8)
    h = _login(client, "x@x.com")
    d = client.get("/v1/dashboard?year=2026&month=6", headers=h).json()
    assert "16" in d["daily"] and "15" not in d["daily"]
    assert d["daily"]["16"]["total"] == 40


def test_dashboard_includes_previous_month(client, db_session):
    org, st, dev = _seed_with_device(db_session, "X", "x@x.com")
    _add_bucket(db_session, org.id, st.id, dev.id, "2026-05-20T10:00:00+00:00", 12, 3)
    _add_bucket(db_session, org.id, st.id, dev.id, "2026-06-20T10:00:00+00:00", 24, 6)
    h = _login(client, "x@x.com")
    d = client.get("/v1/dashboard?year=2026&month=6", headers=h).json()
    assert d["daily"]["20"]["total"] == 24
    assert d["dailyPrev"]["20"]["total"] == 12


def test_dashboard_empty_store_reports_no_data(client, db_session):
    org, st, dev = _seed_with_device(db_session, "New", "n@n.com")
    h = _login(client, "n@n.com")
    d = client.get("/v1/dashboard?year=2026&month=6", headers=h).json()
    assert d["has_data"] is False
    assert d["daily"] == {} and d["hourly"] == {} and d["dailyPrev"] == {}
    assert d["store"]["name"] == "Centro"


def test_dashboard_is_tenant_scoped(client, db_session):
    a, sa, da = _seed_with_device(db_session, "OrgA", "a2@a.com")
    b, sb, dbv = _seed_with_device(db_session, "OrgB", "b2@b.com")
    _add_bucket(db_session, a.id, sa.id, da.id, "2026-06-11T10:00:00+00:00", 10, 1)
    _add_bucket(db_session, b.id, sb.id, dbv.id, "2026-06-11T10:00:00+00:00", 999, 999)
    h = _login(client, "a2@a.com")
    d = client.get("/v1/dashboard?year=2026&month=6", headers=h).json()
    assert d["daily"]["11"]["total"] == 10           # never OrgB's 999
