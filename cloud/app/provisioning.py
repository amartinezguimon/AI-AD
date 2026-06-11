"""Provisioning — create the tenant hierarchy and issue device credentials.

Pure data-layer functions (no HTTP), used by the CLI (scripts/provision.py) and
later by the platform back-office. ``create_device`` returns the **plaintext API
key exactly once** — only its hash is stored, so it can never be recovered. Write
it into the store's device.yaml and keep it safe.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import Device, Org, PlatformStaff, Store, User
from .security import generate_api_key, hash_api_key, hash_password


def create_org(db: Session, name: str) -> Org:
    org = Org(name=name)
    db.add(org)
    db.commit()
    return org


def create_store(db: Session, org_id: str, name: str,
                 address: str | None = None, timezone: str = "Europe/Madrid") -> Store:
    store = Store(org_id=org_id, name=name, address=address, timezone=timezone)
    db.add(store)
    db.commit()
    return store


@dataclass
class ProvisionedDevice:
    device: Device
    api_key: str            # plaintext — shown once, never stored


def create_device(db: Session, org_id: str, store_id: str, device_id: str) -> ProvisionedDevice:
    api_key = generate_api_key()
    device = Device(
        id=device_id, org_id=org_id, store_id=store_id,
        api_key_hash=hash_api_key(api_key),
    )
    db.add(device)
    db.commit()
    return ProvisionedDevice(device=device, api_key=api_key)


def rotate_device_key(db: Session, device: Device) -> str:
    """Issue a new key for an existing device (e.g. if one leaked). Returns plaintext."""
    api_key = generate_api_key()
    device.api_key_hash = hash_api_key(api_key)
    db.commit()
    return api_key


def create_user(db: Session, org_id: str, email: str, password: str,
                role: str = "admin", store_id: str | None = None) -> User:
    user = User(
        org_id=org_id, email=email.lower().strip(),
        password_hash=hash_password(password), role=role, store_id=store_id,
    )
    db.add(user)
    db.commit()
    return user


def create_platform_staff(db: Session, email: str, password: str) -> PlatformStaff:
    staff = PlatformStaff(email=email.lower().strip(), password_hash=hash_password(password))
    db.add(staff)
    db.commit()
    return staff
