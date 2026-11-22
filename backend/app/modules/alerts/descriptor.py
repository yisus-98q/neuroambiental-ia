from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="alerts",
    codename="NEUROALERTS",
    name="Alertas y Prevención",
    version="0.1.0",
    description="Registro de eventos y alertas EXPERIMENTALES con evidencia, fuente, incertidumbre y validación.",
    capabilities=[
        cap("registro_eventos", "Registrar eventos", implemented=True),
        cap("alertas_experimentales", "Crear alertas experimentales", implemented=True),
        cap("ubicacion_evidencia", "Ubicación, evidencia, fuente, fecha e incertidumbre", implemented=True),
        cap("estado_validacion", "Estado de validación y seguimiento", implemented=True),
        cap("informes", "Generar informe de una alerta (Markdown)", implemented=True),
        cap("alertas_automaticas", "Generar alertas automáticamente desde modelos"),
    ],
    dependencies=["neurodata"],
    inputs=["datos de la alerta registrados por un analista"],
    outputs=["alertas", "seguimientos", "informes"],
    possible_errors=["coordenadas_invalidas", "permiso_insuficiente"],
    limitations=[
        "Todas las alertas son experimentales. NO son emergencias oficiales.",
        "Para emergencias oficiales en Perú consulte INDECI / COEN.",
    ],
    keywords=["alerta", "alertas", "evento", "eventos", "prevencion", "emergencia", "aviso"],
    api_prefix="/api/alerts",
)
