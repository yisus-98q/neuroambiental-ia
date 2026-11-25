"""Las pruebas usan una base SQLite y una carpeta de cargas temporales: nunca tocan data/."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="neuro_test_"))
os.environ["NEURO_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["NEURO_UPLOADS_DIR"] = str(_TMP / "uploads")
os.environ["NEURO_MAX_UPLOAD_MB"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.cli import migrate  # noqa: E402

migrate(os.environ["NEURO_DATABASE_URL"])

from app.core.security import hash_password  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

PASSWORD = "Clave-de-prueba-123"


def _ensure_user(username: str, role: str) -> None:
    with SessionLocal() as db:
        if not db.query(User).filter_by(username=username).first():
            db.add(User(username=username, role_key=role, password_hash=hash_password(PASSWORD)))
            db.commit()


for _name, _role in (("admin", "admin"), ("analista", "analista"), ("lector", "lector")):
    _ensure_user(_name, _role)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


def _token(client: TestClient, username: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_h(client):
    return _token(client, "admin")


@pytest.fixture(scope="session")
def analyst_h(client):
    return _token(client, "analista")


@pytest.fixture(scope="session")
def reader_h(client):
    return _token(client, "lector")


@pytest.fixture(autouse=True)
def _memoria_determinista(monkeypatch):
    """Las pruebas no deben depender de la RAM libre real del equipo (en uno de 4 GB varía de un minuto a otro).
    Se simulan 8 GB totales y 4 GB libres; el control de memoria se prueba aparte (test_hardware.py) con sus
    propios valores, que sobrescriben este."""
    from app.core import hardware
    monkeypatch.setattr(hardware, "memory_bytes", lambda: (8 * hardware.GB, 4 * hardware.GB))
