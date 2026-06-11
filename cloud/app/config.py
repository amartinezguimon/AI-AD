"""Backend configuration — everything tunable comes from the environment.

Twelve-factor style: the same image runs locally and on Txema's VM, configured
only by env vars (DATABASE_URL, JWT secret, ...). Nothing deployment-specific is
hardcoded. A local default DATABASE_URL (sqlite) is provided so the app and the
tests run with zero setup; production sets a real Postgres URL.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VM_", env_file=".env", extra="ignore")

    # Postgres in production, e.g. postgresql+psycopg2://user:pass@db:5432/visionmetrics
    database_url: str = "sqlite:///./visionmetrics.db"

    # Secret for signing dashboard JWTs. MUST be overridden in production (VM_JWT_SECRET).
    jwt_secret: str = "dev-only-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 60 * 12          # 12 h dashboard sessions

    # Heartbeats older than this mark a device "offline" in fleet health.
    device_offline_after_s: int = 120

    environment: str = "development"             # "production" on the VM


@lru_cache
def get_settings() -> Settings:
    return Settings()
