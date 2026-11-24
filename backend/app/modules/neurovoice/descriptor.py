from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurovoice",
    codename="NEUROVOICE IA",
    group="nucleo",
    name="NEUROVOICE IA",
    version="0.2.0",
    description="Asistente conversacional: texto y voz en español que consulta NEUROCORE y explica resultados reales.",
    capabilities=[
        cap("texto_espanol", "Conversación escrita en español", implemented=True),
        cap("consulta_datos", "Consultar datos reales: alertas, datos, terreno y escenarios, NDVI, modelos y "
            "catálogo de predicciones", implemented=True),
        cap("historial", "Guardar conversaciones y memoria de sesión (preguntas de seguimiento)", implemented=True),
        cap("reconocimiento_voz", "Reconocimiento de voz en Chrome (Web Speech API; el audio se procesa en "
            "servidores de Google, con consentimiento previo)", implemented=True),
        cap("sintesis_voz", "Respuestas habladas con las voces del navegador (local), interrumpibles",
            implemented=True),
        cap("asistente_flotante", "Asistente flotante en toda la plataforma con el contexto de la pantalla, estados "
            "de escucha/proceso/respuesta, volumen y voz activable", implemented=True),
        cap("modelo_lenguaje", "Comprensión con modelo de lenguaje"),
        cap("otros_idiomas", "Inglés, quechua, aimara, portugués"),
        cap("acciones_sensibles", "Ejecutar análisis o simulaciones por voz con confirmación"),
    ],
    dependencies=["neurocore"],
    inputs=["texto en español", "voz en español (Chrome)"],
    outputs=["respuesta en texto", "respuesta hablada", "módulo consultado"],
    possible_errors=["intencion_no_reconocida", "navegador_sin_reconocimiento_de_voz", "microfono_denegado"],
    limitations=[
        "No usa un modelo de lenguaje: interpreta palabras clave. Puede no entender frases complejas.",
        "El reconocimiento de voz solo funciona en Chrome/Edge y envía el audio a Google; sin internet no funciona.",
        "Solo español. Quechua y aimara no están soportados (requieren hablantes competentes y datos propios).",
        "Solo consulta y explica: no ejecuta análisis ni simulaciones por voz.",
    ],
    keywords=["voz", "hablar", "conversacion", "asistente", "idioma", "quechua", "aimara"],
    api_prefix="/api/neurovoice",
)
