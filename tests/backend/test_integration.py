"""Fase 8 — Integración general: permisos de TODA la API, arranque ligero y flujo entre módulos."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from app.main import app

# Rutas que pueden usarse sin sesión (decisión explícita; cualquier otra debe exigir sesión).
PUBLIC = {
    ("GET", "/api/health"), ("POST", "/api/auth/login"),
    ("GET", "/api/neurocore"), ("GET", "/api/neurocore/modules"), ("GET", "/api/neurocore/modules/{key}"),
    ("GET", "/api/neurodata/limits"), ("GET", "/api/environmental/defaults"),
    ("GET", "/api/neurovoice/capabilities"),
}
# Escrituras permitidas a cualquier usuario con sesión (incluido el rol lector).
WRITE_FOR_READER = {
    ("POST", "/api/auth/logout"), ("POST", "/api/neurovoice/chat"), ("POST", "/api/neurocore/interpret"),
}
FAKE_ID = "0" * 32


def _routes():
    spec = app.openapi()
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/"):
            continue
        for method in methods:
            yield method.upper(), path


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", FAKE_ID, path)


def test_every_non_public_route_requires_session(client):
    checked = 0
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        r = client.request(method, _url(path), json={})
        assert r.status_code == 401, f"{method} {path} respondió {r.status_code} sin sesión"
        checked += 1
    assert checked > 40   # la API tiene decenas de rutas protegidas


def test_reader_cannot_write_except_whitelisted(client, reader_h):
    for method, path in _routes():
        if method == "GET" or (method, path) in PUBLIC or (method, path) in WRITE_FOR_READER:
            continue
        r = client.request(method, _url(path), json={}, headers=reader_h)
        assert r.status_code == 403, f"{method} {path} respondió {r.status_code} al rol lector"


def test_server_starts_without_heavy_libraries():
    """Optimización de memoria: scikit-learn, OpenCV, scipy y rasterio se cargan solo al usarse."""
    backend = Path(__file__).resolve().parents[2] / "backend"
    code = ("import sys; import app.main; "
            "print(','.join(m for m in ('sklearn','cv2','scipy','rasterio') if m in sys.modules))")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(backend / ".deps"), str(backend)])}
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, timeout=120,
                         env=env)
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip() == "", f"librerías cargadas al arrancar: {out.stdout.strip()}"


def test_cross_module_flow(client, analyst_h):
    """NEURODATA recibe → NEUROCORE interpreta → NEUROVOICE explica → NEURO PREDICTION cataloga."""
    raw = b"punto,latitud,longitud,valor\nA,-9.5,-77.5,1\nB,-9.6,-77.6,2\n"
    rec = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "Integración", "is_simulated": "false"},
                      files={"file": ("flujo.csv", raw)}).json()
    it = client.post("/api/neurocore/interpret", headers=analyst_h, json={"text": "¿cuántos datos hay?"}).json()
    assert it["module_key"] == "neurodata"
    reply = client.post("/api/neurovoice/chat", headers=analyst_h, json={"message": "¿cuántos datos hay?"}).json()
    assert "NEURODATA contiene" in reply["reply"]
    cat = client.get("/api/neuroprediction/catalog?tipo=observacion_real&limit=200", headers=analyst_h).json()
    assert any(i["id"] == rec["id"] for i in cat["items"])           # el CSV real aparece como observación real
    layers = client.get("/api/neurodata/layers", headers=analyst_h).json()
    assert any(layer["record_id"] == rec["id"] for layer in layers)  # y como capa del mapa
