"""Utilidades comunes de los scripts de la versión portátil (sin dependencias externas)."""
from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]           # carpeta NEUROAMBIENTAL_IA_PORTABLE
CODIGO = RAIZ / "codigo"
BACKEND = CODIGO / "backend"
LOGS = RAIZ / "logs"
RUN = RAIZ / "run"


def log_path(nombre: str) -> Path:
    LOGS.mkdir(exist_ok=True)
    return LOGS / f"{nombre}_{_dt.datetime.now():%Y%m%d-%H%M%S}.log"


def python_backend() -> str:
    """Python con las dependencias instaladas: primero el entorno local .venv; si no existe, el Python actual."""
    venv = CODIGO / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(venv) if venv.is_file() else sys.executable


def entorno_backend() -> dict:
    env = dict(os.environ)
    deps = BACKEND / ".deps"
    if deps.is_dir():   # alternativa cuando un antivirus bloquea los .exe del entorno virtual
        env["PYTHONPATH"] = str(deps) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    cfg = RAIZ / "config" / "activo.env"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def titulo(t: str) -> None:
    print("\n" + "=" * 64 + f"\n {t}\n" + "=" * 64)
