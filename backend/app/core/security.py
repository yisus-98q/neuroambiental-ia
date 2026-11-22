"""Contraseñas (PBKDF2, librería estándar), sesiones con token y control de roles."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import User, UserSession

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 310_000
ROLE_LEVELS = {"lector": 1, "analista": 2, "admin": 3}

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if password.isdigit() or password.isalpha():
        raise ValueError("La contraseña debe combinar letras y números o símbolos.")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=settings.session_hours)
    db.add(UserSession(token_hash=_hash_token(token), user_id=user.id, expires_at=expires))
    db.commit()
    return token, expires


def revoke_session(db: Session, token: str) -> None:
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == _hash_token(token)))
    if sess:
        sess.revoked = True
        db.commit()


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión no válida o expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == _hash_token(creds.credentials)))
    if sess is None or sess.revoked or _as_aware(sess.expires_at) < datetime.now(UTC):
        raise unauthorized
    user = sess.user
    if not user.is_active:
        raise unauthorized
    return user


def require_role(minimum: str):
    """Dependencia: exige un rol con nivel >= minimum (lector < analista < admin)."""
    needed = ROLE_LEVELS[minimum]

    def _dep(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVELS.get(user.role_key, 0) < needed:
            raise HTTPException(status_code=403, detail=f"Se requiere el rol '{minimum}' o superior.")
        return user

    return _dep
