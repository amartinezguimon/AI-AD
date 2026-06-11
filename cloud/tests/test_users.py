"""User management: admin can create users in their org; viewers cannot."""

from __future__ import annotations

from cloud.app import provisioning as prov


def _login(client, email, password="pw123456"):
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_creates_user_in_own_org(client, db_session):
    org = prov.create_org(db_session, "Org")
    prov.create_user(db_session, org.id, "owner@org.com", "pw123456", role="admin")
    h = _login(client, "owner@org.com")
    r = client.post("/v1/users", headers=h,
                    json={"email": "mgr@org.com", "password": "pw123456", "role": "viewer"})
    assert r.status_code == 201 and r.json()["email"] == "mgr@org.com"
    # the new manager can now log in
    assert client.post("/v1/auth/login",
                       json={"email": "mgr@org.com", "password": "pw123456"}).status_code == 200


def test_viewer_cannot_create_users(client, db_session):
    org = prov.create_org(db_session, "Org")
    prov.create_user(db_session, org.id, "viewer@org.com", "pw123456", role="viewer")
    h = _login(client, "viewer@org.com")
    r = client.post("/v1/users", headers=h,
                    json={"email": "x@org.com", "password": "pw123456"})
    assert r.status_code == 403


def test_duplicate_email_in_org_conflict(client, db_session):
    org = prov.create_org(db_session, "Org")
    prov.create_user(db_session, org.id, "owner@org.com", "pw123456", role="admin")
    h = _login(client, "owner@org.com")
    client.post("/v1/users", headers=h, json={"email": "dup@org.com", "password": "pw123456"})
    r = client.post("/v1/users", headers=h, json={"email": "dup@org.com", "password": "pw123456"})
    assert r.status_code == 409
