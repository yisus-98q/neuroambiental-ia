from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neuroprediction",
    codename="NEURO PREDICTION ENGINE",
    group="nucleo",
    name="Motor de predicción",
    version="0.1.0",
    description="Estimaciones de los modelos con ubicación, modelo, versión, incertidumbre, evidencias y limitaciones.",
    capabilities=[
        cap("predicciones_registradas", "Registrar predicciones con modelo, versión e incertidumbre", implemented=True),
        cap("separacion_tipos", "Catálogo que separa observación real, dato histórico, procesamiento, estimación, "
            "simulación, predicción validada y alerta verificada (sin tablas nuevas; ver /api/neuroprediction/kinds)",
            implemented=True),
        cap("probabilidad_calibrada", "Probabilidades solo cuando el modelo está calibrado y validado"),
        cap("horizonte_temporal", "Estimaciones con horizonte temporal explícito"),
    ],
    dependencies=["neurodata", "neurotraining"],
    inputs=["resultados de modelos entrenados", "datos de NEURODATA"],
    outputs=["predicciones con incertidumbre y nivel de evidencia"],
    possible_errors=["modelo_no_entrenado", "artefacto_alterado"],
    limitations=["Si el modelo no está validado, la predicción se presenta como experimental.",
                 "Sin probabilidades calibradas ni horizonte temporal: probabilidad y horizonte_temporal quedan en null.",
                 "El catálogo es de solo lectura y clasifica por reglas; no valida nada por sí mismo."],
    keywords=["prediccion", "predicciones", "estimacion", "pronostico", "futuro", "probabilidad"],
    api_prefix="/api/neuroprediction",
)
