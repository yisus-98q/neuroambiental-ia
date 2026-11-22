from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.security import (
    create_session,
    get_current_user,
    hash_password,
    require_role,
    revoke_session,
    validate_password_strength,
    verify_password,
)
from app.database.session import get_db
from app.models import User
from app.schemas import LoginIn, TokenOut, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["autenticación"])

# Límite simple en memoria contra fuerza bruta: 5 fallos por usuario cada 5 minutos.
_FAILS: dict[str, deque[float]] = defaultdict(deque)
_MAX_FAILS, _WINDOW_S = 5, 300


def _too_many(username: str) -> bool:
    q, now = _FAILS[username], time.monotonic()
    while q and now - q[0] > _WINDOW_S:
        q.popleft()
    return len(q) >= _MAX_FAILS


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    username = body.username.strip().lower()
    if _too_many(username):
        raise HTTPException(429, "Demasiados intentos fallidos. Espere 5 minutos.")
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        _FAILS[username].append(time.monotonic())
        # Nunca se guarda el texto tecleado: podría ser una contraseña escrita en el campo equivocado.
        audit(db, "login", user_id=user.id if user else None, target_type="user",
              target_id=user.id if user else "desconocido", success=False)
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    _FAILS.pop(username, None)
    token, expires = create_session(db, user)
    audit(db, "login", user_id=user.id, target_type="user", target_id=user.id)
    return TokenOut(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    token = request.headers.get("authorization", "").split(" ", 1)[-1]
    revoke_session(db, token)
    audit(db, "logout", user_id=user.id)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)) -> User:
    try:
        validate_password_strength(body.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    username = body.username.lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "El usuario ya existe.")
    user = User(username=username, full_name=body.full_name, role_key=body.role_key,
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    audit(db, "crear_usuario", user_id=admin.id, target_type="user", target_id=user.id,
          details={"role": body.role_key}, commit=False)
    db.commit()
    return user
