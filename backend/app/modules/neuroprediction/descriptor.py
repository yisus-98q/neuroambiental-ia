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
        cap("separacion_tipos", "Separar observación, procesamiento, estimación, simulación y alerta verificada "
            "(hoy solo existen las marcas is_simulated / is_validated)"),
        cap("probabilidad_calibrada", "Probabilidades solo cuando el modelo está calibrado y validado"),
        cap("horizonte_temporal", "Estimaciones con horizonte temporal explícito"),
    ],
    dependencies=["neurodata", "neurotraining"],
    inputs=["resultados de modelos entrenados", "datos de NEURODATA"],
    outputs=["predicciones con incertidumbre y nivel de evidencia"],
    possible_errors=["modelo_no_entrenado", "artefacto_alterado"],
    limitations=["Si el modelo no está validado, la predicción se presenta como experimental."],
    keywords=["prediccion", "predicciones", "estimacion", "pronostico", "futuro", "probabilidad"],
    api_prefix="/api/neurotraining",
)
