"""Un único proceso pesado a la vez (raster, entrenamiento): protege la memoria de equipos de 4 GB."""
from __future__ import annotations

import contextlib
import threading

LOCK = threading.Lock()


class Busy(Exception):
    pass


@contextlib.contextmanager
def exclusive():
    if not LOCK.acquire(blocking=False):
        raise Busy("Ya hay un procesamiento en curso. Espere a que termine (protege la memoria del equipo).")
    try:
        yield
    finally:
        LOCK.release()
