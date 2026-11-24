from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurotraining",
    codename="NEURAL TRAINING ENGINE",
    group="nucleo",
    name="NEURAL TRAINING ENGINE (NEUROTRAINING)",
    version="0.3.0",
    description="Datasets, entrenamiento, evaluación con filas de prueba reservadas y registro de versiones de modelos.",
    capabilities=[
        cap("registro_modelos", "Registro de modelos con estado honesto (planificado/entrenado/validado/retirado)",
            implemented=True),
        cap("registro_ejecuciones", "Historial de ejecuciones con parámetros y resultados", implemented=True),
        cap("entrenamiento_ligero", "Entrenamiento con scikit-learn sobre CSV de NEURODATA (n_jobs=1)",
            implemented=True),
        cap("evaluacion", "Métricas sobre datos de prueba separados: precisión, recall, F1, matriz de confusión, "
            "ROC-AUC, Brier, MAE, RMSE, R²", implemented=True),
        cap("versiones_artefactos", "Versionado de artefactos con SHA-256 verificado antes de cargar",
            implemented=True),
        cap("validacion_humana", "Validación solo por administrador con evidencia; nunca con datos simulados",
            implemented=True),
        cap("prediccion", "Predicción sobre nuevos CSV, marcada como experimental si el modelo no está validado",
            implemented=True),
        cap("reproducibilidad", "Semilla, hiperparámetros, versiones y SHA-256 del dataset registrados; reproducción "
            "verificable y exportación del modelo con su ficha (model_card.json)", implemented=True),
        cap("division_espacial", "División de prueba por bloques geográficos y algoritmos condicionados al tamaño de "
            "los datos (HistGradientBoosting ≥ 200 filas, MLP ≥ 1000 filas)", implemented=True),
        cap("redes_neuronales", "Redes neuronales (PyTorch) para imágenes y series: requiere autorización y hardware"),
        cap("datasets_imagenes", "Datasets de imágenes con anotaciones (Dataset Manager)"),
        cap("reanudar_entrenamiento", "Reanudar entrenamientos largos por épocas"),
    ],
    dependencies=["neurodata"],
    inputs=["CSV registrados en NEURODATA (columnas numéricas + columna objetivo)"],
    outputs=["modelos versionados", "métricas de prueba", "predicciones experimentales"],
    possible_errors=["dataset_insuficiente", "fuga_de_datos", "artefacto_alterado", "procesamiento_en_curso"],
    limitations=[
        "Solo modelos ligeros (bosques aleatorios, regresión logística, ridge). Sin redes neuronales todavía.",
        "Un modelo entrenado con datos simulados nunca puede validarse.",
        "La validación la decide un administrador con evidencia; terminar un entrenamiento no aprueba un modelo.",
    ],
    keywords=["entrenar", "entrenamiento", "modelo", "modelos", "metricas", "dataset", "datasets", "red", "neuronal"],
    api_prefix="/api/neurotraining",
)
