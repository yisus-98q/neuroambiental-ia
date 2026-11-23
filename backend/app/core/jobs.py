"""Un único proceso pesado a la vez (raster, entrenamiento): protege la memoria de equipos de 4 GB.

IMPORTANTE: el candado es por proceso. El servidor DEBE ejecutarse con un solo worker
(scripts\\iniciar.bat usa --workers 1). Con varios workers no serializaría nada, y la limpieza de
ejecuciones huérfanas podría marcar como error una ejecución viva de otro worker.
"""
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
