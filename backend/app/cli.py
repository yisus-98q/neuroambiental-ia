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


def import_ingemmet(bbox_text: str, res: float, dem_id: str | None, validate: bool) -> int:
    """Importa el inventario INGEMMET (y opcionalmente DEM + validación) como acción del sistema (CLI, sin usuario)."""
    import json

    from app.database.session import SessionLocal
    from app.modules.disasters import service as disasters
    from app.modules.neuro3d import service as neuro3d

    bbox = [float(v) for v in bbox_text.split(",")]
    if len(bbox) != 4 or not (bbox[0] < bbox[2] and bbox[1] < bbox[3]) or max(bbox[2] - bbox[0], bbox[3] - bbox[1]) > 2.5:
        print("bbox inválido: minLon,minLat,maxLon,maxLat (máx. 2,5° por lado).")
        return 2
    with SessionLocal() as db:
        inv = disasters.import_inventory(db, None, bbox)
        print(f"Inventario: {inv.id} · {inv.extra.get('features')} eventos · {inv.extra.get('tipos_peligro')}")
        if not validate:
            return 0
        if dem_id is None:
            print("Descargando DEM Copernicus GLO-30 (puede tardar varios minutos)…")
            dem_id = neuro3d.fetch_dem(db, None, bbox=bbox, res=res).id
            print(f"DEM: {dem_id}")
        rep = disasters.validate(db, None, dem_id=dem_id, inventory_id=inv.id, ratio=3, min_dist_m=300.0,
                                 blocks=0, seed=42)
        keys = ("ausencias_libres", "ausencias_mismo_rango_elevacion", "conclusion_automatica", "dataset_record_id")
        print(json.dumps({k: rep[k] for k in keys}, ensure_ascii=False, indent=1, default=str))
    return 0


def download_dem(bbox_text: str, res: float) -> int:
    """Descarga un DEM GLO-30 para ANÁLISIS (hasta 1600 px por lado) como acción del sistema."""
    from app.database.session import SessionLocal
    from app.modules.neuro3d import dem as demlib
    from app.modules.neuro3d import service as neuro3d

    bbox = [float(v) for v in bbox_text.split(",")]
    if len(bbox) != 4:
        print("bbox inválido: minLon,minLat,maxLon,maxLat.")
        return 2
    with SessionLocal() as db:
        try:
            rec = neuro3d.fetch_dem(db, None, bbox=bbox, res=res, analysis=True)
        except demlib.DemError as exc:
            print(f"No se pudo: {exc}")
            return 2
        g = rec.extra["grid"]
        print(f"DEM: {rec.id} · {g['width']}x{g['height']} px a {g['res']}° · {rec.extra['elevation']}")
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
    g = sub.add_parser("importar-ingemmet", help="Importa el inventario INGEMMET de un recorte (uso interno)")
    g.add_argument("--bbox", required=True, help="minLon,minLat,maxLon,maxLat")
    g.add_argument("--validar", action="store_true", help="Descarga/usa un DEM y valida la susceptibilidad")
    g.add_argument("--dem-id", default=None, help="DEM ya registrado (si no, se descarga)")
    g.add_argument("--res", type=float, default=0.001, help="Resolución del DEM en grados")
    d = sub.add_parser("descargar-dem", help="Descarga un DEM GLO-30 para análisis (hasta 1600 px por lado)")
    d.add_argument("--bbox", required=True, help="minLon,minLat,maxLon,maxLat")
    d.add_argument("--res", type=float, default=0.0003125, help="Resolución en grados (≈35 m por defecto)")
    args = parser.parse_args(argv)
    if args.cmd == "migrate":
        migrate()
        print("Migraciones aplicadas.")
        return 0
    if args.cmd == "create-admin":
        return create_admin(args.username, args.password)
    if args.cmd == "descargar-dem":
        return download_dem(args.bbox, args.res)
    if args.cmd == "importar-ingemmet":
        return import_ingemmet(args.bbox, args.res, args.dem_id, args.validar)
    return load_samples(args.username)


if __name__ == "__main__":
    raise SystemExit(main())
