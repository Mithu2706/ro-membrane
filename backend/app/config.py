"""Environment-based configuration.

Values are read from process environment variables, optionally pre-loaded from
``backend/.env`` (simple KEY=VALUE lines). No secrets are hard-coded: if no
admin password is configured, the admin console stays locked.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BACKEND_DIR / ".env")


def _database_url() -> str | None:
    """Hosted database URL (e.g. Neon / Vercel Postgres). Normalised to the psycopg 3 driver."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        return None
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@dataclass
class Settings:
    # When set, a hosted Postgres database is used instead of the local SQLite file (required on serverless hosts).
    database_url: str | None = field(default_factory=_database_url)
    # True on hosted deployments (e.g. Vercel sets VERCEL=1); enforces production-safe settings.
    hosted: bool = field(default_factory=lambda: bool(os.environ.get("VERCEL")) or os.environ.get("RO_ENV") == "production")
    database_path: Path = field(
        default_factory=lambda: Path(os.environ.get("RO_DATABASE_PATH", BACKEND_DIR / "data" / "ro_membrane.db"))
    )
    backup_dir: Path = field(default_factory=lambda: Path(os.environ.get("RO_BACKUP_DIR", BACKEND_DIR / "backups")))
    admin_username: str = field(default_factory=lambda: os.environ.get("RO_ADMIN_USERNAME", "admin"))
    # Either a bcrypt hash (preferred) or a plain password that is hashed in memory at startup.
    admin_password_hash: str | None = field(default_factory=lambda: os.environ.get("RO_ADMIN_PASSWORD_HASH") or None)
    admin_password: str | None = field(default_factory=lambda: os.environ.get("RO_ADMIN_PASSWORD") or None)
    # Signing key for session cookies. A random key is generated per process if unset
    # (sessions then do not survive a restart, which is acceptable for a local tool).
    secret_key: str = field(default_factory=lambda: os.environ.get("RO_SECRET_KEY") or secrets.token_urlsafe(48))
    session_hours: int = field(default_factory=lambda: int(os.environ.get("RO_SESSION_HOURS", "8")))
    cookie_secure: bool = field(default_factory=lambda: os.environ.get(
        "RO_COOKIE_SECURE", "true" if (os.environ.get("VERCEL") or os.environ.get("RO_ENV") == "production") else "false"
    ).lower() == "true")
    frontend_dist: Path = field(default_factory=lambda: PROJECT_DIR / "frontend" / "dist")
    # Optional AI explanation layer: disabled by default and never used for engineering decisions.
    ai_explanations_enabled: bool = field(
        default_factory=lambda: os.environ.get("RO_AI_EXPLANATIONS", "false").lower() == "true"
    )


settings = Settings()

if settings.hosted and not os.environ.get("RO_SECRET_KEY"):
    # Serverless instances each have their own memory: a per-process random key would invalidate admin sessions
    # whenever a request reaches a different instance.
    raise RuntimeError("RO_SECRET_KEY must be set for hosted deployments.")
