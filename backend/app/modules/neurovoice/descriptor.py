from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurovoice",
    codename="NEUROVOICE IA",
    group="nucleo",
    name="NEUROVOICE IA",
    version="0.1.0",
    description="Interacción conversacional. Fase 1: texto en español con intérprete por reglas.",
    capabilities=[
        cap("texto_espanol", "Conversación escrita en español", implemented=True),
        cap("consulta_datos", "Consultar conteos reales de datos y alertas", implemented=True),
        cap("historial", "Guardar conversaciones", implemented=True),
        cap("reconocimiento_voz", "Reconocimiento de voz"),
        cap("sintesis_voz", "Síntesis de voz"),
        cap("modelo_lenguaje", "Comprensión con modelo de lenguaje"),
        cap("otros_idiomas", "Inglés, quechua, aimara, portugués"),
    ],
    dependencies=["neurocore"],
    inputs=["texto en español"],
    outputs=["respuesta en texto", "módulo sugerido"],
    possible_errors=["intencion_no_reconocida"],
    limitations=[
        "No usa un modelo de lenguaje: interpreta palabras clave. Puede no entender frases complejas.",
        "Solo español escrito. No se declaran capacidades en otros idiomas.",
    ],
    keywords=["voz", "hablar", "conversacion", "asistente", "idioma", "quechua", "aimara"],
    api_prefix="/api/neurovoice",
)
