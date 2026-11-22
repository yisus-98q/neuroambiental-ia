"""NEUROCORE IA: registro de módulos e intérprete de solicitudes por reglas."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.modules.alerts.descriptor import DESCRIPTOR as ALERTS
from app.modules.biodiversity.descriptor import DESCRIPTOR as BIODIVERSITY
from app.modules.construction.descriptor import DESCRIPTOR as CONSTRUCTION
from app.modules.disasters.descriptor import DESCRIPTOR as DISASTERS
from app.modules.environmental.descriptor import DESCRIPTOR as ENVIRONMENTAL
from app.modules.mining.descriptor import DESCRIPTOR as MINING
from app.modules.neuro3d.descriptor import DESCRIPTOR as NEURO3D
from app.modules.neurogeo.descriptor import DESCRIPTOR as NEUROGEO
from app.modules.neuroindustrial.descriptor import DESCRIPTOR as NEUROINDUSTRIAL
from app.modules.neuroprediction.descriptor import DESCRIPTOR as NEUROPREDICTION
from app.modules.neurovision.descriptor import DESCRIPTOR as NEUROVISION
from app.modules.neurotraining.descriptor import DESCRIPTOR as NEUROTRAINING
from app.modules.neurovoice.descriptor import DESCRIPTOR as NEUROVOICE
from app.modules.terrain.descriptor import DESCRIPTOR as TERRAIN
from app.neurocore.base import ModuleDescriptor
from app.neurodata.descriptor import DESCRIPTOR as NEURODATA


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, ModuleDescriptor] = {}

    def register(self, descriptor: ModuleDescriptor) -> None:
        if descriptor.key in self._modules:
            raise ValueError(f"Módulo duplicado: {descriptor.key}")
        unknown = [d for d in descriptor.dependencies if d not in self._modules and d != "neurocore"]
        if unknown:
            raise ValueError(f"{descriptor.key} depende de módulos no registrados: {unknown}")
        self._modules[descriptor.key] = descriptor

    def get(self, key: str) -> ModuleDescriptor | None:
        return self._modules.get(key)

    def all(self) -> list[ModuleDescriptor]:
        return list(self._modules.values())


def build_registry() -> ModuleRegistry:
    """El orden importa: un módulo solo puede depender de módulos ya registrados.
    Esto impide dependencias circulares por construcción."""
    reg = ModuleRegistry()
    for d in (NEURODATA, ALERTS, ENVIRONMENTAL, TERRAIN, BIODIVERSITY, NEUROGEO, MINING, DISASTERS,
              CONSTRUCTION, NEUROTRAINING, NEUROVISION, NEUROINDUSTRIAL, NEURO3D, NEUROPREDICTION, NEUROVOICE):
        reg.register(d)
    return reg


registry = build_registry()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


@dataclass
class Interpretation:
    intent: str                 # estado_modulos, consulta_conteo, modulo, desconocida
    module_key: str | None
    matched_keywords: list[str]
    method: str = "reglas_palabras_clave"


_STATUS_WORDS = {"estado", "modulos", "operativo", "operativos", "funciona", "disponible", "disponibles"}
_COUNT_WORDS = {"cuantos", "cuantas", "cantidad", "total", "numero", "resumen"}


def interpret(text: str, reg: ModuleRegistry = registry) -> Interpretation:
    words = set(re.findall(r"[a-z0-9]+", normalize(text)))
    scores: dict[str, list[str]] = {}
    for module in reg.all():
        hits = sorted(words.intersection(normalize(k) for k in module.keywords))
        if hits:
            scores[module.key] = hits
    if words & _STATUS_WORDS and not scores:
        return Interpretation("estado_modulos", None, sorted(words & _STATUS_WORDS))
    if not scores:
        return Interpretation("desconocida", None, [])
    best = max(scores, key=lambda k: len(scores[k]))
    tied = [k for k, v in scores.items() if len(v) == len(scores[best])]
    if len(tied) > 1:
        # Preferencia estable: alertas y datos primero (son los que tienen datos reales).
        for preferred in ("alerts", "neurodata"):
            if preferred in tied:
                best = preferred
                break
    intent = "consulta_conteo" if words & _COUNT_WORDS else "modulo"
    return Interpretation(intent, best, scores[best])
