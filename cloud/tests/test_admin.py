"""Platform back-office (staff, cross-tenant): auth boundary + onboarding + fleet."""

from __future__ import annotations

import datetime as dt

from cloud.app import provisioning as prov
from cloud.app.models import Heartbeat, MetricBucket


def _staff_login(client, db, email="ops@visionmetrics.ai", password="staffpw123"):
    prov.create_platform_staff(db, email, password)
    r = client.post("/v1/auth/staff/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_requires_staff_token(client, db_session):
    # no token
    assert client.get("/v1/admin/orgs").status_code in (401, 403)
    # a CLIENT user token must NOT open the staff back-office
    org = prov.create_org(db_session, "Org")
    prov.create_user(db_session, org.id, "owner@org.com", "pw123456", role="admin")
    r = client.post("/v1/auth/login", json={"email": "owner@org.com", "password": "pw123456"})
    user_tok = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/v1/admin/orgs", headers=user_tok).status_code == 401


def test_staff_onboards_a_client_end_to_end(client, db_session):
    h = _staff_login(client, db_session)
    # create org -> store -> device, all via the API
    org = client.post("/v1/admin/orgs", headers=h, json={"name": "Joyeria Perez"}).json()
    store = client.post("/v1/admin/stores", headers=h,
                        json={"org_id": org["id"], "name": "Centro"}).json()
    dev = client.post("/v1/admin/devices", headers=h,
                      json={"org_id": org["id"], "store_id": store["id"],
                            "device_id": "dev-centro-01"})
    assert dev.status_code == 201
    body = dev.json()
    assert body["device_id"] == "dev-centro-01" and body["api_key"].startswith("vmk_")


def test_list_orgs_shows_counts(client, db_session):
    h = _staff_login(client, db_session)
    a = prov.create_org(db_session, "OrgA")
    sa = prov.create_store(db_session, a.id, "S1")
    prov.create_device(db_session, a.id, sa.id, "d1")
    prov.create_org(db_session, "OrgB")
    orgs = {o["name"]: o for o in client.get("/v1/admin/orgs", headers=h).json()}
    assert orgs["OrgA"]["store_count"] == 1 and orgs["OrgA"]["device_count"] == 1
    assert orgs["OrgB"]["store_count"] == 0


def test_global_fleet_spans_all_orgs(client, db_session):
    h = _staff_login(client, db_session)
    a = prov.create_org(db_session, "OrgA"); sa = prov.create_store(db_session, a.id, "SA")
    b = prov.create_org(db_session, "OrgB"); sb = prov.create_store(db_session, b.id, "SB")
    prov.create_device(db_session, a.id, sa.id, "devA")
    prov.create_device(db_session, b.id, sb.id, "devB")
    fleet = client.get("/v1/admin/fleet", headers=h).json()
    ids = {d["id"]: d for d in fleet}
    assert set(ids) == {"devA", "devB"}
    assert ids["devA"]["org_name"] == "OrgA" and ids["devA"]["status"] == "provisioned"


def test_staff_me_returns_identity(client, db_session):
    h = _staff_login(client, db_session, email="ops@vm.ai")
    me = client.get("/v1/admin/me", headers=h).json()
    assert me["email"] == "ops@vm.ai" and me["id"]


def test_overview_counts_by_status(client, db_session):
    h = _staff_login(client, db_session)
    now = dt.datetime.now(dt.timezone.utc)
    a = prov.create_org(db_session, "OrgA"); sa = prov.create_store(db_session, a.id, "SA")
    online = prov.create_device(db_session, a.id, sa.id, "dOnline").device
    offline = prov.create_device(db_session, a.id, sa.id, "dOffline").device
    prov.create_device(db_session, a.id, sa.id, "dNever")        # never seen
    online.last_seen_at = now
    offline.last_seen_at = now - dt.timedelta(hours=2)
    db_session.commit()

    ov = client.get("/v1/admin/overview", headers=h).json()
    assert ov["orgs"] == 1 and ov["stores"] == 1 and ov["devices"] == 3
    assert ov["online"] == 1 and ov["offline"] == 1 and ov["never_seen"] == 1


def test_fleet_includes_camera_health_and_dataflow(client, db_session):
    h = _staff_login(client, db_session)
    a = prov.create_org(db_session, "OrgA"); sa = prov.create_store(db_session, a.id, "SA")
    dev = prov.create_device(db_session, a.id, sa.id, "devA").device
    now = dt.datetime.now(dt.timezone.utc)
    db_session.add(Heartbeat(org_id=a.id, device_id=dev.id, sent_at=now.timestamp(),
                             camera_ok=True, fps_analysis=12.5, people_tracked=3))
    db_session.add(MetricBucket(org_id=a.id, store_id=sa.id, device_id=dev.id,
                                window_start=now.isoformat(), window_end=now.isoformat(),
                                passersby=42, engaged=10, engagement_rate=23.8,
                                total_attention_s=55.0))
    db_session.commit()

    d = {x["id"]: x for x in client.get("/v1/admin/fleet", headers=h).json()}["devA"]
    assert d["camera_ok"] is True and d["fps_analysis"] == 12.5 and d["people_tracked"] == 3
    assert d["recent_passersby"] == 42 and d["last_metric_at"] is not None


def test_device_id_conflict(client, db_session):
    h = _staff_login(client, db_session)
    org = client.post("/v1/admin/orgs", headers=h, json={"name": "Org"}).json()
    store = client.post("/v1/admin/stores", headers=h,
                        json={"org_id": org["id"], "name": "S"}).json()
    payload = {"org_id": org["id"], "store_id": store["id"], "device_id": "dup"}
    assert client.post("/v1/admin/devices", headers=h, json=payload).status_code == 201
    assert client.post("/v1/admin/devices", headers=h, json=payload).status_code == 409
