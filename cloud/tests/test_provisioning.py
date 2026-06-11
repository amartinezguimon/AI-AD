"""Provisioning + tenant-model invariants."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from cloud.app import provisioning as prov
from cloud.app.security import hash_api_key, verify_password


def test_setup_creates_hierarchy_and_one_time_key(db_session):
    org = prov.create_org(db_session, "Joyeria Perez")
    store = prov.create_store(db_session, org.id, "Centro")
    pd = prov.create_device(db_session, org.id, store.id, "dev-centro-01")

    assert pd.device.org_id == org.id and pd.device.store_id == store.id
    # The plaintext key is returned but only its hash is stored.
    assert pd.api_key.startswith("vmk_")
    assert pd.device.api_key_hash == hash_api_key(pd.api_key)
    assert pd.api_key not in pd.device.api_key_hash


def test_key_rotation_changes_hash(db_session):
    org = prov.create_org(db_session, "Org")
    store = prov.create_store(db_session, org.id, "S")
    pd = prov.create_device(db_session, org.id, store.id, "dev-1")
    old = pd.device.api_key_hash
    new_key = prov.rotate_device_key(db_session, pd.device)
    assert pd.device.api_key_hash != old
    assert pd.device.api_key_hash == hash_api_key(new_key)


def test_user_password_is_hashed(db_session):
    org = prov.create_org(db_session, "Org")
    user = prov.create_user(db_session, org.id, "Owner@Shop.com", "s3cret")
    assert user.email == "owner@shop.com"          # normalised
    assert user.password_hash != "s3cret"
    assert verify_password("s3cret", user.password_hash)


def test_duplicate_user_email_in_same_org_rejected(db_session):
    org = prov.create_org(db_session, "Org")
    prov.create_user(db_session, org.id, "a@b.com", "x")
    with pytest.raises(IntegrityError):
        prov.create_user(db_session, org.id, "a@b.com", "y")
