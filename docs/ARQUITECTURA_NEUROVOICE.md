# Arquitectura de NEUROVOICE IA

**Estado: solo texto en español con reglas está implementado y probado.** La voz (reconocimiento y síntesis), la detección de idioma, otros idiomas y el modelo de lenguaje **no existen**. Lo que sí existe son **contratos** (interfaces) para poder conectarlos después sin reescribir el asistente. El módulo está «parcial»: 3 de 7 capacidades implementadas.

Código: `backend/app/modules/neurovoice/{service.py, contracts.py, descriptor.py}`, `backend/app/api/neurovoice.py`, `backend/app/neurocore/registry.py` (intérprete).

## Implementado

| Capacidad | Detalle |
|---|---|
| `texto_espanol` | Chat escrito. `POST /api/neurovoice/chat` |
| `consulta_datos` | Responde con conteos **reales** de alertas y datos, el estado de los módulos y sus capacidades/limitaciones |
| `historial` | Conversaciones guardadas por usuario y privadas (`GET /conversations`, `/conversations/{id}`) |

El intérprete normaliza el texto (minúsculas, sin tildes), cuenta palabras clave por módulo y elige intención (`estado_modulos`, `consulta_conteo`, `modulo`, `desconocida`). No entiende frases complejas, no usa contexto de la conversación y no ejecuta acciones: solo informa.

## Contratos (diseño, sin proveedor real)

En `contracts.py` hay interfaces `Protocol` para cada etapa de la cadena de voz:

```
micrófono --> VAD --> ASR (SpeechRecognizer) --> LanguageDetector --> IntentInterpreter
   --> ToolRequest a NEUROCORE (con confirmación si es sensible) --> respuesta --> TTS (SpeechSynthesizer) --> audio
```

| Contrato | Firma resumida | Proveedor hoy |
|---|---|---|
| `SpeechRecognizer` (ASR) | `transcribe(audio_pcm16, sample_rate, language_hint) -> Transcript` | **ninguno** |
| `VoiceActivityDetector` | `is_speech(frame_pcm16, sample_rate) -> bool` | **ninguno** |
| `LanguageDetector` | `detect(text) -> str` | **ninguno** |
| `IntentInterpreter` | `interpret(text, language) -> Intent` | reglas por palabras clave (es), vía el registro de NEUROCORE |
| `SpeechSynthesizer` (TTS) | `synthesize(text, language, voice) -> bytes` | **ninguno** |

`GET /api/neurovoice/capabilities` (sin autenticación) informa con honestidad qué etapa tiene proveedor real: `asr`, `vad`, `tts` y `language_detection` devuelven `null`.

## Herramientas que el asistente podría pedir a NEUROCORE

| Herramienta | Implementada | Sensible (exige confirmación) |
|---|---|---|
| `consultar_estado_modulos`, `consultar_alertas`, `consultar_datos` | Sí (como respuestas de texto) | No |
| `consultar_modelos`, `activar_capa_mapa`, `analizar_imagen` | No | No |
| `ejecutar_analisis`, `iniciar_simulacion`, `generar_informe` | No | **Sí** |

Las herramientas sensibles deberán exigir permiso por rol y **confirmación humana** explícita antes de ejecutarse. Hoy el asistente no ejecuta ninguna herramienta; solo lee conteos.

## Idiomas

| Idioma | Texto | Voz | Nota |
|---|---|---|---|
| Español (`es`) | Sí (reglas) | No | |
| Inglés, portugués | No | No | Pendiente |
| Quechua, aimara | No | No | Requiere evaluar variantes regionales con hablantes competentes y datos apropiados; no se promete |

## Opciones de proveedores libres (propuestas, sin evaluar ni instalar)

| Etapa | Candidatos | Consideraciones |
|---|---|---|
| ASR | Vosk, Whisper local | Memoria y tiempo en 4 GB; calidad en español peruano a medir |
| TTS | Piper, voz del navegador | La voz del navegador no requiere instalar nada pero depende del sistema |
| VAD | WebRTC VAD | Ligero |
| Modelo de lenguaje | Modelos abiertos locales pequeños | Probablemente inviable en 4 GB junto al resto; requiere autorización |

Cualquier instalación necesita autorización explícita y medición de RAM antes de adoptarla.

## Seguridad y privacidad (a considerar al implementar audio)

El audio es dato personal: no guardarlo sin consentimiento, no enviarlo a servicios externos, pedir permiso del micrófono al navegador y servir sobre HTTPS (hoy no hay HTTPS; el navegador solo permite micrófono en `localhost`/`127.0.0.1` o HTTPS). Ver [SECURITY.md](SECURITY.md).

## Criterios para declarar capacidades implementadas

Reconocimiento y síntesis de voz: prueba automática de la tubería con audio de muestra, medición de error de palabras en español, consumo de memoria y latencia documentados en [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md).
