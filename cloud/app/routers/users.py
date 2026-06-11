"""User management — the owner-admin creates and lists users in their own org.

Admin-only. New users are always created inside the admin's org (org_id is taken
from the token, never the body), and a store_id, if given, must belong to that
org. This is how an owner grants a manager access to one store.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require_admin
from ..models import Store, User
from ..provisioning import create_user
from ..schemas import UserCreateIn, UserOut

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_user(body: UserCreateIn, admin: User = Depends(require_admin),
             db: Session = Depends(get_session)) -> UserOut:
    if body.role not in ("admin", "viewer"):
        raise HTTPException(status_code=422, detail="role must be admin or viewer")
    if body.store_id is not None:
        store = db.get(Store, body.store_id)
        if store is None or store.org_id != admin.org_id:
            raise HTTPException(status_code=404, detail="Store not found")
    try:
        user = create_user(db, admin.org_id, body.email, body.password,
                           role=body.role, store_id=body.store_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="A user with that email already exists in this org")
    return UserOut(id=user.id, email=user.email, role=user.role, store_id=user.store_id)


@router.get("", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin),
               db: Session = Depends(get_session)) -> list[UserOut]:
    rows = db.execute(select(User).where(User.org_id == admin.org_id)).scalars()
    return [UserOut(id=u.id, email=u.email, role=u.role, store_id=u.store_id) for u in rows]
