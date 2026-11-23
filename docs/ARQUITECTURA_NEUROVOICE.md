# Arquitectura de NEUROVOICE IA

**Estado: parcial, 5 de 8 capacidades.** Texto en español por reglas y **voz en el navegador** (reconocimiento y síntesis) están implementados. **No hay modelo de lenguaje, detección de idioma, otros idiomas ni acciones por voz.** El asistente solo **consulta y explica**: no ejecuta análisis ni simulaciones.

Código: `backend/app/modules/neurovoice/{service.py, contracts.py, descriptor.py}`, `backend/app/api/neurovoice.py`, `frontend/src/pages/VoicePage.tsx`, pruebas `tests/backend/test_neurovoice.py`.

> **Privacidad: el reconocimiento de voz envía el audio a los servidores de Google.** Es el servicio Web Speech API de Chrome/Edge, no algo que haga este servidor. Por eso el botón «Hablar» está **deshabilitado hasta que la persona marca un consentimiento explícito**. El usuario eligió esta opción frente a un reconocedor local (Vosk), que sigue siendo una alternativa pendiente que no depende de Google.

> Limitación de la verificación: en Chrome se comprobó que la página carga, que el reconocimiento existe, que «Hablar» queda deshabilitado hasta aceptar el consentimiento y que no hay errores de consola. **El micrófono no se probó** (requiere hablar y enviar audio a Google), así que la precisión del reconocimiento en español peruano es desconocida.

## Capacidades (descriptor v0.2.0)

| Capacidad | Estado | Detalle |
|---|---|---|
| `texto_espanol` | Implementada | Chat escrito: `POST /api/neurovoice/chat` |
| `consulta_datos` | Implementada | Responde con cifras reales de alertas, datos, terreno y escenarios, NDVI, modelos y catálogo de predicciones |
| `historial` | Implementada | Conversaciones guardadas por usuario (privadas) y **memoria de sesión**: «explícame más», «continúa» retoman el módulo de la respuesta anterior |
| `reconocimiento_voz` | Implementada (en el navegador) | Web Speech API de Chrome/Edge; transcripción interina visible mientras se habla |
| `sintesis_voz` | Implementada (en el navegador) | `speechSynthesis` con las voces instaladas (local); respuestas interrumpibles. En el equipo de pruebas hay voces es-MX (Microsoft) y es-ES/es-US (Google) |
| `modelo_lenguaje` | **Pendiente** | No se usa un modelo de lenguaje |
| `otros_idiomas` | **Pendiente** | Inglés, portugués, quechua, aimara |
| `acciones_sensibles` | **Pendiente** | Ejecutar análisis o simulaciones por voz con confirmación |

## Cómo funciona

```
voz --(Web Speech, audio a Google, con consentimiento)--> texto --> POST /api/neurovoice/chat
   --> intérprete por palabras clave (NEUROCORE) --> consulta a la base con datos reales --> respuesta en texto
   --> speechSynthesis (voz local del navegador, opcional)
```

El intérprete normaliza el texto (minúsculas, sin tildes) y cuenta palabras clave por módulo; no entiende frases complejas. Si no reconoce la solicitud y la conversación tiene un módulo previo, palabras como «explica», «más», «eso», «significa», «continúa» o «sigue» retoman ese módulo.

### Qué responde (siempre con datos reales; nunca inventa cifras)

| Tema | Contenido |
|---|---|
| Estado de módulos | Lista con `codename` y estado derivado |
| Alertas | Conteos reales; recuerda que ninguna es una emergencia oficial |
| Datos | Registros reales y simulados |
| NEURO 3D / terreno / catástrofes | Último terreno real (elevaciones) y el escenario más reciente, **siempre nombrado «SIMULACIÓN… hipotético, no una predicción»** con su limitación |
| NEURO PREDICTION | Conteos del catálogo por tipo; aclara que sin predicciones validadas todo es experimental |
| Predicción ambiental | Último NDVI y última comparación; recuerda que un cambio de NDVI no confirma deforestación |
| NEUROTRAINING | Modelos por estado y cuántos están validados |

## Contratos (diseño para sustituir proveedores)

En `contracts.py` hay interfaces `Protocol` por etapa (`SpeechRecognizer`, `VoiceActivityDetector`, `LanguageDetector`, `IntentInterpreter`, `SpeechSynthesizer`) para poder cambiar de proveedor sin tocar el asistente. Las etapas de audio **no corren en este servidor**: `GET /api/neurovoice/capabilities` (sin sesión) lo informa así:

| Etapa | Proveedor actual | Dónde |
|---|---|---|
| `asr` | Web Speech API (Chrome) | Navegador; **el audio se envía a Google**; requiere consentimiento |
| `vad` | Incluido en Web Speech API | Navegador |
| `tts` | `speechSynthesis` (voces del sistema/navegador) | Navegador (local) |
| `language_detection` | **Ninguno** (`null`) | — |
| `intent` | Reglas por palabras clave (es) | Servidor |

## Herramientas

| Herramienta | Implementada | Sensible (exigiría confirmación) |
|---|---|---|
| `consultar_estado_modulos`, `consultar_alertas`, `consultar_datos`, `consultar_modelos`, `explicar_simulaciones`, `consultar_catalogo_predicciones`, `consultar_ndvi` | Sí (como respuestas de texto) | No |
| `activar_capa_mapa`, `analizar_imagen` | No | No |
| `ejecutar_analisis`, `iniciar_simulacion`, `generar_informe` | No | **Sí** |

Las herramientas sensibles deberán exigir permiso por rol y confirmación humana explícita; hoy el asistente no ejecuta ninguna.

## Idiomas

| Idioma | Texto | Voz | Nota |
|---|---|---|---|
| Español (`es`) | Sí (reglas) | Sí, en Chrome (variantes de voz del navegador, p. ej. es-PE si existe) | La calidad depende de Google y de las voces instaladas |
| Inglés, portugués | No | No | Pendiente |
| Quechua, aimara | No | No | **No soportados**: requieren hablantes competentes, datos propios y evaluar variantes regionales; no se promete |

## Limitaciones y riesgos

- **Solo Chrome/Edge** para reconocer voz; otros navegadores solo texto. **Sin Internet no hay reconocimiento** (la síntesis sí funciona sin conexión si hay voces instaladas).
- El consentimiento se guarda en `localStorage` del navegador (`neurovoice_asr_consent`): persiste hasta que la persona lo desmarque o borre los datos del sitio; no se pide de nuevo en cada sesión.
- El texto transcrito se guarda como mensaje de la conversación (historial del usuario); el audio no se guarda en este servidor, pero sí lo recibe Google.
- No usar la voz para información sensible o confidencial.
- No está probado el micrófono ni la precisión en español peruano.

## Alternativas locales (no implementadas)

Vosk o Whisper local (reconocimiento) y Piper (síntesis) evitarían enviar audio a Google, pero exigen instalar modelos (cientos de MB) y medir memoria en 4 GB; requieren autorización. Ver [COSTS.md](../COSTS.md) y [SECURITY.md](SECURITY.md).

## Criterios para dar por probada la voz

Prueba manual con micrófono real (medir errores de palabras en frases típicas del dominio), prueba en navegador sin soporte (degradación a texto), y registro en [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md).
