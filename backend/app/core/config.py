"""Configuración central leída de variables de entorno (sin dependencias extra)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    """Carga un archivo .env simple (CLAVE=valor) sin sobrescribir el entorno."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "NEUROAMBIENTAL IA"
    version: str = "0.1.0"
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "NEURO_DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'data' / 'neuroambiental.db').as_posix()}"
        )
    )
    uploads_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("NEURO_UPLOADS_DIR", PROJECT_ROOT / "data" / "uploads"))
    )
    frontend_dist: Path = field(default_factory=lambda: PROJECT_ROOT / "frontend" / "dist")
    max_upload_mb: int = field(default_factory=lambda: _int("NEURO_MAX_UPLOAD_MB", 10))
    max_csv_rows: int = field(default_factory=lambda: _int("NEURO_MAX_CSV_ROWS", 50000))
    session_hours: int = field(default_factory=lambda: _int("NEURO_SESSION_HOURS", 12))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get(
                "NEURO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        )
    )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
