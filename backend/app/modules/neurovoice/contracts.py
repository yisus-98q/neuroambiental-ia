"""Contratos de NEUROVOICE IA (arquitectura de voz desacoplada de los proveedores).

Cada etapa es una interfaz: se puede sustituir el proveedor (p. ej. Vosk, Whisper local, Piper,
el sintetizador del navegador) sin tocar la lógica del asistente ni NEUROCORE.

Estado actual: solo existe la ruta de TEXTO en español (intención por reglas). Las etapas de audio
están declaradas aquí pero NO implementadas; `available_providers()` lo informa con honestidad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Transcript:
    text: str
    language: str            # código BCP-47, p. ej. "es-PE"
    confidence: float | None  # None si el proveedor no la entrega


@dataclass
class Intent:
    name: str
    module_key: str | None
    slots: dict = field(default_factory=dict)
    method: str = "reglas_palabras_clave"


@dataclass
class ToolRequest:
    """Petición del asistente a NEUROCORE. Las herramientas sensibles exigen permiso y confirmación."""
    tool: str                # p. ej. "consultar_alertas", "activar_capa", "iniciar_simulacion"
    arguments: dict
    requires_confirmation: bool = False


class SpeechRecognizer(Protocol):      # ASR
    def transcribe(self, audio_pcm16: bytes, sample_rate: int, language_hint: str | None) -> Transcript: ...


class VoiceActivityDetector(Protocol):  # VAD
    def is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool: ...


class LanguageDetector(Protocol):
    def detect(self, text: str) -> str: ...


class IntentInterpreter(Protocol):
    def interpret(self, text: str, language: str) -> Intent: ...


class SpeechSynthesizer(Protocol):     # TTS
    def synthesize(self, text: str, language: str, voice: str | None = None) -> bytes: ...


# Herramientas que NEUROVOICE puede pedir a NEUROCORE y si requieren confirmación humana.
TOOLS: dict[str, dict] = {
    "consultar_estado_modulos": {"implemented": True, "sensitive": False},
    "consultar_alertas": {"implemented": True, "sensitive": False},
    "consultar_datos": {"implemented": True, "sensitive": False},
    "consultar_modelos": {"implemented": False, "sensitive": False},
    "activar_capa_mapa": {"implemented": False, "sensitive": False},
    "analizar_imagen": {"implemented": False, "sensitive": False},
    "ejecutar_analisis": {"implemented": False, "sensitive": True},
    "iniciar_simulacion": {"implemented": False, "sensitive": True},
    "generar_informe": {"implemented": False, "sensitive": True},
}

LANGUAGES = {
    "es": {"text": True, "voice": False, "note": "Español escrito: implementado (reglas)."},
    "en": {"text": False, "voice": False, "note": "Pendiente."},
    "pt": {"text": False, "voice": False, "note": "Pendiente."},
    "qu": {"text": False, "voice": False,
           "note": "Quechua: requiere evaluar variantes regionales con hablantes competentes y datos apropiados."},
    "ay": {"text": False, "voice": False,
           "note": "Aimara: requiere evaluar variantes regionales con hablantes competentes y datos apropiados."},
}


def available_providers() -> dict:
    """Informe honesto de qué etapas tienen proveedor real hoy."""
    return {
        "asr": None, "vad": None, "tts": None, "language_detection": None,
        "intent": "reglas_palabras_clave (es)",
        "tools": TOOLS, "languages": LANGUAGES,
    }
