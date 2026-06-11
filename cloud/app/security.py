"""Hashing + token helpers.

Two distinct secrets, two distinct treatments:

* **User passwords** — low entropy, chosen by humans -> bcrypt (slow, salted).
* **Device API keys** — high-entropy random tokens we generate -> SHA-256 is
  sufficient and lets us look a device up by hash on every ingest call without
  a slow per-row bcrypt check.

JWTs sign short-lived dashboard sessions.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

import bcrypt
from jose import jwt

from .config import get_settings


# ── user passwords ────────────────────────────────────────────────
# bcrypt directly (passlib is unmaintained and breaks with bcrypt 4.x). bcrypt
# only considers the first 72 bytes, so we SHA-256 pre-hash to support arbitrarily
# long passwords without the >72-byte error, then bcrypt the digest.
def _prep(plain: str) -> bytes:
    return hashlib.sha256(plain.encode("utf-8")).digest()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prep(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ── device API keys ───────────────────────────────────────────────
def generate_api_key() -> str:
    """A fresh opaque device key (shown once at provisioning, never stored raw)."""
    return "vmk_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ── JWT (dashboard sessions) ──────────────────────────────────────
def create_access_token(subject: str, claims: dict | None = None) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + dt.timedelta(minutes=s.access_token_ttl_min),
        **(claims or {}),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
