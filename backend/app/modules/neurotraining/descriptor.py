from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurotraining",
    name="NEUROTRAINING",
    version="0.1.0",
    description="Administración de modelos de IA: registro, versiones, estado honesto y métricas.",
    capabilities=[
        cap("registro_modelos", "Registrar modelos y su estado real", implemented=True),
        cap("registro_ejecuciones", "Consultar ejecuciones", implemented=True),
        cap("entrenamiento_ligero", "Entrenar modelos pequeños con scikit-learn"),
        cap("evaluacion", "Evaluar modelos con métricas y datos separados"),
    ],
    dependencies=["neurodata"],
    inputs=["datasets registrados en NEURODATA"],
    outputs=["modelos versionados", "métricas"],
    possible_errors=["dataset_insuficiente", "memoria_insuficiente"],
    limitations=["No hay ningún modelo entrenado. Un modelo solo puede marcarse 'validado' con evidencia."],
    keywords=["entrenar", "entrenamiento", "modelo", "modelos", "metricas", "dataset"],
    api_prefix="/api/neurotraining",
)
