"""Admin authentication: bcrypt-hashed credentials from the environment,
server-side sessions in an HttpOnly signed cookie, and CSRF protection
(synchroniser token sent in the ``X-CSRF-Token`` header) for every
state-changing admin request.
"""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AdminSession

SESSION_COOKIE = "ro_admin_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_password_hash: bytes | None = None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def _configured_hash() -> bytes | None:
    global _password_hash
    if _password_hash is None:
        if settings.admin_password_hash:
            _password_hash = settings.admin_password_hash.encode("ascii")
        elif settings.admin_password:
            _password_hash = hash_password(settings.admin_password).encode("ascii")
    return _password_hash


def reset_password_cache() -> None:
    global _password_hash
    _password_hash = None


def admin_configured() -> bool:
    return _configured_hash() is not None


def verify_credentials(username: str, password: str) -> bool:
    h = _configured_hash()
    if h is None:
        return False
    user_ok = hmac.compare_digest(username.encode("utf-8"), settings.admin_username.encode("utf-8"))
    try:
        pw_ok = bcrypt.checkpw(password.encode("utf-8"), h)
    except ValueError:
        pw_ok = False
    return user_ok and pw_ok


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.secret_key, salt="ro-admin-session")


def create_session(db: Session, response: Response, username: str) -> AdminSession:
    now = datetime.now(timezone.utc)
    db.execute(delete(AdminSession).where(AdminSession.expires_at < now))
    sess = AdminSession(id=secrets.token_urlsafe(32), username=username, csrf_token=secrets.token_urlsafe(32),
                        created_at=now, expires_at=now + timedelta(hours=settings.session_hours))
    db.add(sess)
    db.commit()
    response.set_cookie(SESSION_COOKIE, _serializer().dumps(sess.id), httponly=True, samesite="strict",
                        secure=settings.cookie_secure, max_age=settings.session_hours * 3600, path="/api")
    return sess


def destroy_session(db: Session, response: Response, sess: AdminSession | None) -> None:
    if sess is not None:
        db.execute(delete(AdminSession).where(AdminSession.id == sess.id))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/api")


def _load_session(request: Request, db: Session) -> AdminSession | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        sid = _serializer().loads(raw)
    except BadSignature:
        return None
    sess = db.get(AdminSession, sid)
    if sess is None:
        return None
    expires = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    return sess


def optional_admin(request: Request, db: Session = Depends(get_db)) -> AdminSession | None:
    return _load_session(request, db)


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminSession:
    sess = _load_session(request, db)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin authentication required")
    if request.method not in SAFE_METHODS:
        token = request.headers.get(CSRF_HEADER, "")
        if not token or not hmac.compare_digest(token, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    return sess
