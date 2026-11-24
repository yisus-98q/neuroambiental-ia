"""Un único proceso pesado a la vez, con control de memoria, cancelación y registro de recursos.

IMPORTANTE: el candado es por proceso. El servidor DEBE ejecutarse con un solo worker
(scripts\\iniciar.bat usa --workers 1). Con varios workers no serializaría nada, y la limpieza de
ejecuciones huérfanas podría marcar como error una ejecución viva de otro worker.

Fase 8 (2.0):
- Antes de empezar se comprueba la memoria disponible frente a la estimación del trabajo y al perfil
  (app.core.hardware): si no alcanza, el trabajo NO se inicia (InsufficientMemory).
- Cancelación cooperativa: request_cancel() marca el trabajo actual; los bucles largos llaman check_cancel().
- resources(): duración y pico de memoria del proceso, para guardarlos en la ejecución.
"""
from __future__ import annotations

import contextlib
import threading
import time

from app.core import hardware

LOCK = threading.Lock()
_CANCEL = threading.Event()
_CURRENT: dict = {}
MARGIN_MB = 150   # memoria que se deja libre para el sistema y el servidor


class Busy(Exception):
    pass


class InsufficientMemory(Exception):
    pass


class Cancelled(Exception):
    pass


def check_memory(estimate_mb: float) -> None:
    prof = hardware.detect_profile()
    _, avail = hardware.memory_bytes()
    avail_mb = avail / 2**20 if avail else None
    limit_mb = prof.ram_max_gb * 1024
    if estimate_mb > limit_mb:
        raise InsufficientMemory(
            f"El trabajo necesita ≈{estimate_mb:.0f} MB y el perfil «{prof.name}» permite como máximo "
            f"{limit_mb:.0f} MB. Ejecútelo en el equipo principal o reduzca el área/resolución.")
    if avail_mb is not None and estimate_mb + MARGIN_MB > avail_mb:
        raise InsufficientMemory(
            f"Memoria libre insuficiente: hay ≈{avail_mb:.0f} MB y el trabajo necesita ≈{estimate_mb:.0f} MB "
            f"(+{MARGIN_MB} MB de margen). Cierre programas (p. ej. pestañas del navegador) y vuelva a intentarlo.")


@contextlib.contextmanager
def exclusive(name: str = "proceso", estimate_mb: float = 0.0):
    if not LOCK.acquire(blocking=False):
        raise Busy("Ya hay un procesamiento en curso. Espere a que termine (protege la memoria del equipo).")
    try:
        if estimate_mb:
            check_memory(estimate_mb)
        _CANCEL.clear()
        _CURRENT.clear()
        _CURRENT.update({"nombre": name, "inicio": time.time(), "estimacion_mb": estimate_mb})
        yield
    finally:
        _CURRENT.clear()
        _CANCEL.clear()
        LOCK.release()


def request_cancel() -> bool:
    """Pide cancelar el trabajo en curso; devuelve False si no hay ninguno."""
    if not LOCK.locked():
        return False
    _CANCEL.set()
    return True


def check_cancel() -> None:
    if _CANCEL.is_set():
        raise Cancelled("Trabajo cancelado por el usuario.")


def current() -> dict | None:
    if not _CURRENT:
        return None
    return {**_CURRENT, "duracion_s": round(time.time() - _CURRENT["inicio"], 1), "cancelacion_pedida": _CANCEL.is_set()}


@contextlib.contextmanager
def resources():
    """Mide duración y pico de memoria del proceso dentro del bloque: `with resources() as r: ...; r["..."]`."""
    out: dict = {}
    t0 = time.time()
    try:
        yield out
    finally:
        out["duracion_s"] = round(time.time() - t0, 1)
        out["pico_proceso_mb"] = round(hardware.process_peak_bytes() / 2**20, 1)
        out["perfil"] = hardware.detect_profile().name
