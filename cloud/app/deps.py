"""FastAPI dependencies — DB session + the two authentication paths.

* ``authenticate_device`` — for the ingest API. The edge box sends
  ``Authorization: Bearer <api_key>``; we hash it and look up the device. The
  device's own org_id/store_id are taken from the DB row, never from the request
  body, so a device can only ever write its own tenant's data.
* (user/JWT auth for the dashboard lives in the auth router, added next.)
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from jose import JWTError

from .db import get_session
from .models import Device, Store, User
from .security import decode_access_token, hash_api_key

_bearer = HTTPBearer(auto_error=True)


def authenticate_device(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_session),
) -> Device:
    device = db.execute(
        select(Device).where(Device.api_key_hash == hash_api_key(creds.credentials))
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device


# ── dashboard user auth (JWT) ─────────────────────────────────────
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_session),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(creds.credentials)
    except JWTError:
        raise cred_exc
    if payload.get("typ") != "user" or not payload.get("sub"):
        raise cred_exc
    user = db.get(User, payload["sub"])
    if user is None:
        raise cred_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin role required")
    return user


def resolve_store_scope(user: User, requested_store_id: str | None,
                        db: Session) -> str | None:
    """Return the store_id a query should be limited to, enforcing tenant rules.

    - A store-scoped user (user.store_id set) is always pinned to their store and
      cannot ask for another.
    - An org-wide user may pass a store_id (must belong to their org) or None
      (all stores in the org).
    """
    if user.store_id is not None:
        if requested_store_id not in (None, user.store_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Not allowed for this store")
        return user.store_id
    if requested_store_id is not None:
        store = db.get(Store, requested_store_id)
        if store is None or store.org_id != user.org_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Store not found")
        return requested_store_id
    return None
