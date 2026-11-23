"""Importación diferida de módulos pesados (scikit-learn, OpenCV, scipy, rasterio).

Medido en este equipo: importar todo al arrancar costaba ~19 s y ~212 MB de RAM en reposo, aunque no se
usara ninguna función pesada. Con este proxy, cada librería se carga la PRIMERA vez que se usa su servicio.
"""
from __future__ import annotations

import importlib
import threading
from types import ModuleType
from typing import Any


class LazyModule:
    """Se comporta como el módulo `name`, pero lo importa al acceder al primer atributo."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._module: ModuleType | None = None
        self._lock = threading.Lock()

    def _load(self) -> ModuleType:
        if self._module is None:
            with self._lock:
                if self._module is None:
                    self._module = importlib.import_module(self._name)
        return self._module

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._load(), attr)

    def __repr__(self) -> str:
        return f"<LazyModule {self._name} {'cargado' if self._module else 'sin cargar'}>"


def lazy(name: str) -> LazyModule:
    return LazyModule(name)
