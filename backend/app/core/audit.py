from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(
    db: Session,
    action: str,
    *,
    user_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    success: bool = True,
    details: dict | None = None,
    commit: bool = True,
) -> None:
    """Registra una operación. Nunca guardar contraseñas ni tokens en details."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=success,
            details=details or {},
        )
    )
    if commit:
        db.commit()
