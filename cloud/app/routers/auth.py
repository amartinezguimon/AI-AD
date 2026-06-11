"""Dashboard authentication — email + password -> short-lived JWT.

The token carries the user's org_id / role / store_id as claims so the rest of
the API can scope every query without another DB hit. `typ: user` distinguishes
a dashboard session from a device API key.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import PlatformStaff, User
from ..schemas import LoginIn, TokenOut
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_session)) -> TokenOut:
    # Email identifies the user. (Provisioning keeps emails unique per platform in
    # the pilot; org-scoped login can be added later if two orgs reuse an email.)
    users = db.execute(
        select(User).where(User.email == body.email.lower().strip())
    ).scalars().all()
    user = users[0] if len(users) == 1 else None

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Wrong email or password")

    token = create_access_token(subject=user.id, claims={
        "typ": "user", "org_id": user.org_id, "role": user.role,
        "store_id": user.store_id,
    })
    return TokenOut(access_token=token)


@router.post("/staff/login", response_model=TokenOut)
def staff_login(body: LoginIn, db: Session = Depends(get_session)) -> TokenOut:
    """Login for platform staff (us). Cross-tenant — kept separate from clients."""
    staff = db.execute(
        select(PlatformStaff).where(PlatformStaff.email == body.email.lower().strip())
    ).scalar_one_or_none()
    if staff is None or not verify_password(body.password, staff.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Wrong email or password")
    token = create_access_token(subject=staff.id, claims={"typ": "staff"})
    return TokenOut(access_token=token)
