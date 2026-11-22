"""Comandos de administración.

Uso (desde backend/, con PYTHONPATH=.deps;.):
    python -m app.cli migrate
    python -m app.cli create-admin --username admin
    python -m app.cli load-samples --username admin
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]


def migrate(url: str | None = None) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    (BACKEND_DIR.parent / "data").mkdir(exist_ok=True)
    command.upgrade(cfg, "head")


def create_admin(username: str, password: str | None) -> int:
    from app.core.audit import audit
    from app.core.security import hash_password, validate_password_strength
    from app.database.session import SessionLocal
    from app.models import User

    password = password or os.environ.get("NEURO_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Contraseña del administrador (mín. 10 caracteres): ")
        if password != getpass.getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
    try:
        validate_password_strength(password)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username.lower())):
            print(f"El usuario '{username}' ya existe. No se modificó.", file=sys.stderr)
            return 1
        user = User(username=username.lower(), full_name="Administrador", role_key="admin",
                    password_hash=hash_password(password))
        db.add(user)
        db.flush()
        audit(db, "crear_admin_cli", user_id=user.id, target_type="user", target_id=user.id)
    print(f"Administrador '{username}' creado.")
    return 0


def load_samples(username: str) -> int:
    """Carga data/samples/* marcándolos SIEMPRE como simulados / de prueba."""
    from app.core.config import PROJECT_ROOT, settings
    from app.database.session import SessionLocal
    from app.models import DataRecord, User
    from app.neurodata.service import store_file
    from app.neurodata.validators import validate_file

    samples = PROJECT_ROOT / "data" / "samples"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username.lower()))
        if user is None:
            print(f"Usuario '{username}' no existe.", file=sys.stderr)
            return 1
        loaded = 0
        for path in sorted(samples.glob("*")):
            if path.suffix.lower() not in (".csv", ".geojson") or path.name.startswith("_"):
                continue
            title = f"[MUESTRA] {path.stem}"
            if db.scalar(select(DataRecord).where(DataRecord.title == title)):
                continue
            raw = path.read_bytes()
            result = validate_file(path.suffix, raw, settings.max_csv_rows)
            store_file(db, raw=raw, extension=path.suffix, original_name=path.name, result=result,
                       source_name="Muestras de prueba NEUROAMBIENTAL", source_license="CC0 (creado para pruebas)",
                       title=title, observed_at=None, is_simulated=True,
                       provenance="Archivo de muestra del repositorio. Valores SIMULADOS, no son mediciones reales.",
                       user_id=user.id)
            loaded += 1
        db.commit()
    print(f"Muestras cargadas: {loaded}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="Aplica las migraciones pendientes")
    p = sub.add_parser("create-admin", help="Crea el usuario administrador")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", help="Evite usarlo: queda en el historial. Use el prompt o NEURO_ADMIN_PASSWORD.")
    s = sub.add_parser("load-samples", help="Carga los datos de muestra (marcados como simulados)")
    s.add_argument("--username", default="admin")
    args = parser.parse_args(argv)
    if args.cmd == "migrate":
        migrate()
        print("Migraciones aplicadas.")
        return 0
    if args.cmd == "create-admin":
        return create_admin(args.username, args.password)
    return load_samples(args.username)


if __name__ == "__main__":
    raise SystemExit(main())
