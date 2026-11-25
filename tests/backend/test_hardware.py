"""Fase 8 (2.0): perfiles de hardware, control de memoria, cancelación y recursos."""
from __future__ import annotations

import pytest

from app.core import hardware, jobs


def test_profile_detection_and_env_override(monkeypatch):
    for var in ("NEURO_PROFILE", "NEURO_RAM_TARGET_GB", "NEURO_RAM_MAX_GB", "NEURO_N_JOBS"):
        monkeypatch.delenv(var, raising=False)          # la detección automática no depende del entorno
    monkeypatch.setattr(hardware, "memory_bytes", lambda: (4 * hardware.GB, 1 * hardware.GB))
    p = hardware.detect_profile()
    assert p.name == "ligero" and not p.training_allowed and p.ram_max_gb <= 3.0
    monkeypatch.setattr(hardware, "memory_bytes", lambda: (32 * hardware.GB, 20 * hardware.GB))
    p = hardware.detect_profile()
    assert p.name == "potente" and p.ram_max_gb == 20.0 and 10 <= p.ram_target_gb <= 16
    monkeypatch.setenv("NEURO_PROFILE", "estandar")
    monkeypatch.setenv("NEURO_RAM_MAX_GB", "5")
    p = hardware.detect_profile()
    assert p.name == "estandar" and p.ram_max_gb == 5.0          # se cambia el perfil sin tocar el código


def test_memory_guard_refuses_jobs_that_do_not_fit(monkeypatch):
    monkeypatch.setattr(hardware, "memory_bytes", lambda: (4 * hardware.GB, 300 * 2**20))
    with pytest.raises(jobs.InsufficientMemory):
        with jobs.exclusive("prueba", estimate_mb=400):
            pass
    assert not jobs.LOCK.locked()                                  # el candado se libera aunque falle
    with pytest.raises(jobs.InsufficientMemory):
        with jobs.exclusive("prueba", estimate_mb=50_000):          # supera el tope del perfil
            pass
    with jobs.exclusive("pequeño", estimate_mb=50):
        assert jobs.current()["nombre"] == "pequeño"


def test_cooperative_cancel_and_resources():
    assert jobs.request_cancel() is False                          # nada en curso
    with pytest.raises(jobs.Cancelled):
        with jobs.exclusive("largo"):
            assert jobs.request_cancel() is True
            jobs.check_cancel()
    with jobs.resources() as r:
        pass
    assert r["duracion_s"] >= 0 and "perfil" in r


def test_resources_endpoint(client, reader_h, analyst_h):
    r = client.get("/api/system/resources", headers=reader_h).json()
    assert r["perfil"]["name"] in ("ligero", "estandar", "potente") and r["trabajo_en_curso"] is None
    assert client.post("/api/system/jobs/cancel", headers=reader_h).status_code == 403
    assert client.post("/api/system/jobs/cancel", headers=analyst_h).json()["cancelacion_pedida"] is False
