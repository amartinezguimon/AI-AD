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

from .db import get_session
from .models import Device
from .security import hash_api_key

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
