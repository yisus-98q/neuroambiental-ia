"""Contrato común que todo módulo debe declarar ante NEUROCORE IA."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ModuleStatus(StrEnum):
    OPERATIVO = "operativo"          # todas sus capacidades declaradas funcionan
    PARCIAL = "parcial"              # algunas capacidades funcionan
    EN_DESARROLLO = "en_desarrollo"  # solo existe la interfaz/contrato


class Capability(BaseModel):
    key: str
    description: str
    implemented: bool = False


class ModuleDescriptor(BaseModel):
    key: str
    name: str
    codename: str | None = None  # nombre de la arquitectura avanzada (p. ej. NEUROTERRAIN)
    group: str = "especializado"  # nucleo, especializado, simulacion
    version: str
    description: str
    capabilities: list[Capability]
    dependencies: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    possible_errors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)  # usadas por el intérprete por reglas
    api_prefix: str | None = None

    @property
    def status(self) -> ModuleStatus:
        """El estado se DERIVA de las capacidades: nunca se declara a mano."""
        done = sum(c.implemented for c in self.capabilities)
        if done == 0:
            return ModuleStatus.EN_DESARROLLO
        if done == len(self.capabilities):
            return ModuleStatus.OPERATIVO
        return ModuleStatus.PARCIAL

    def public(self) -> dict:
        data = self.model_dump(exclude={"keywords"})
        data["status"] = self.status.value
        data["implemented_count"] = sum(c.implemented for c in self.capabilities)
        return data


def cap(key: str, description: str, implemented: bool = False) -> Capability:
    return Capability(key=key, description=description, implemented=implemented)
