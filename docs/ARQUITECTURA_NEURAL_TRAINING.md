# Arquitectura del NEURAL TRAINING ENGINE

Estado: **implementado y probado para modelos ligeros de scikit-learn sobre CSV**. Las **redes neuronales profundas no existen** en el proyecto (ver «Pendiente»). El nombre «red neuronal» del plan original no debe leerse como que haya una red neuronal entrenada: hoy los algoritmos son bosques aleatorios, regresión logística y ridge.

Código: `backend/app/modules/neurotraining/{trainer.py, service.py, descriptor.py}`, `backend/app/api/neurotraining.py`, `backend/app/core/jobs.py`, interfaz `frontend/src/pages/TrainingCenter.tsx`, pruebas `tests/backend/test_training.py`.

## Flujo

```
CSV válido en NEURODATA --> registrar modelo (planificado) --> entrenar (analista)
        --> métricas SOLO sobre el 25 % reservado del mismo CSV --> artefacto .joblib + SHA-256 --> «entrenado» (experimental)
        --> [otro admin: evidencia + versión + SHA-256] validar --> «validado»   |  retirar --> «retirado»
        --> predecir sobre otro CSV (analista) --> fila en `predictions` con texto de incertidumbre
```

Los conjuntos de datos son **registros CSV de NEURODATA** (`data_type = csv`, `validation_status = valido`). No existe un «Dataset Manager» aparte ni datasets de imágenes (pendiente, ver [DOCUMENTACION_DATASETS.md](DOCUMENTACION_DATASETS.md)).

## Algoritmos

| Tarea | Algoritmos | Configuración fija |
|---|---|---|
| `clasificacion` | `random_forest`, `regresion_logistica` | RF: 100 árboles, profundidad máx. 12, `n_jobs=1`, semilla 42. Regresión logística: `StandardScaler` + `max_iter=1000` |
| `regresion` | `random_forest`, `ridge` | RF igual que arriba; ridge con `StandardScaler` |

Los hiperparámetros no son configurables desde la API ni la interfaz.

## Reglas de datos (`trainer.load_dataset`)

- Mínimo **60 filas completas** (con 25 % de prueba quedan ≥ 15 para evaluar); máximo **30 columnas de entrada**; máximo **20 clases**; la clasificación exige al menos 2 clases. Una clase con menos de 2 filas, o demasiadas clases para el número de filas (la prueba no podría incluirlas), da un **422 con mensaje claro**.
- La **columna objetivo no puede ser una entrada** (evita fuga de datos).
- Las entradas deben ser **numéricas** (admite coma decimal). Las filas con entradas vacías o no numéricas, o sin objetivo, se descartan y se informa cuántas (`dropped_rows`). Valores ambiguos como «1,234» (¿miles o decimal?) **se descartan** (la fila se elimina) en lugar de adivinar. No hay variables categóricas ni imputación.

## Evaluación

- Partición **75 % entrenamiento / 25 % prueba** (`random_state=42`), estratificada en clasificación si cada clase tiene al menos 2 ejemplos. Las métricas se calculan **solo sobre ese 25 % de filas reservadas del mismo CSV (corte aleatorio)**. **No es un conjunto independiente**: está sacado del mismo archivo, de la misma zona y época.
- `metrics.warnings` avisa si hay menos de 50 filas de prueba («las métricas son muy inciertas») y, siempre, que con autocorrelación espacial o temporal un corte aleatorio **sobrestima el rendimiento** y que la validación requiere datos externos.
- Clasificación: accuracy, precisión/recall/F1 macro, matriz de confusión, falsos positivos y negativos y soporte por clase, **línea base de clase mayoritaria**, y en el caso binario ROC-AUC y puntaje de Brier (la clase positiva es la segunda en orden alfabético). Importancia de variables en los bosques.
- Regresión: MAE, RMSE, R² y MAE de la línea base (predecir la media del entrenamiento).
- Limitaciones: una sola partición (sin validación cruzada, sin partición por zona ni por fecha, así que puede haber fuga espacial o temporal); no hay calibración de probabilidades; la línea base se compara solo al **validar** (un modelo que no la supere no puede validarse); al entrenar se muestra, pero no se rechaza el modelo.

## Ciclo de vida y gobernanza

| Estado | Cómo se llega | Quién |
|---|---|---|
| `planificado` | Registrar un modelo | analista |
| `entrenado` | Entrenar (experimental) | analista |
| `validado` | `POST /models/{id}/validate` con `evidence` (**≥ 40 caracteres**), `version` y `artifact_sha256` que **coincidan con el modelo actual** | **solo admin, y distinto de quien lo entrenó** (`Run.parameters.trained_by`); **nunca** si `trained_with_simulated`; debe **superar la línea base** (clasificación: accuracy mayor que la clase mayoritaria; regresión: MAE menor que el de predecir la media) |
| `retirado` | `POST /models/{id}/retire` (422 si ya está retirado) | solo admin |

- Solo se entrena desde `planificado` o `entrenado`. Reentrenar sube la **versión** (1.0.0, 1.1.0, …) y **borra la validación** (vuelve a `entrenado`). Un modelo `validado` o `retirado` no se reentrena.
- La aprobación queda **atada a la versión y al hash** que el administrador revisó: si el modelo cambió (se reentrenó), la validación se rechaza (422). Separación de funciones: quien entrenó el modelo no puede validarlo.
- La evidencia es **texto libre**: el sistema no verifica que sea cierta ni que se hayan usado datos externos al CSV de entrenamiento. La validación es una decisión humana registrada (`validation_evidence`, `validated_by`) y auditada. Como la evaluación automática no es independiente, validar un modelo exige **datos externos** (otra zona o fecha) revisados fuera del sistema.
- Entrenar con datos simulados marca `trained_with_simulated` y se muestra en la interfaz.
- El estado `en_entrenamiento` existe en el esquema pero no se usa: mientras entrena, solo la fila de `runs` está `en_proceso`. Si el servidor se detuvo durante un entrenamiento, esa fila huérfana se cierra como `error` al iniciar el siguiente entrenamiento.

## Artefactos y seguridad

Se guardan en `data/uploads/models/<id_modelo>/v<versión>.joblib` (compresión 3) con su **SHA-256**. La carga es **atómica**: se leen los bytes del archivo **una sola vez**, se verifican con el SHA-256 de la base y el modelo se carga desde esos mismos bytes en memoria (sin ventana entre comprobar y cargar); la ruta debe quedar dentro de la carpeta de datos. Si el hash no coincide, **no se carga** (joblib/pickle puede ejecutar código al cargar). Esto protege contra alteración del archivo, **no** contra alguien que modifique archivo y base de datos a la vez.

## Un proceso pesado a la vez

`backend/app/core/jobs.py` tiene un candado común: entrenamiento y análisis raster (NDVI, cambios) comparten el mismo, y una segunda petición recibe **409**. El candado está en memoria del proceso, por lo que el servidor **debe correr con un solo worker** (`--workers 1`). Las peticiones esperan hasta terminar (no hay cola ni segundo plano ni barra de progreso).

## Predicción

`POST /models/{id}/predict` (analista) con otro CSV de NEURODATA: hasta 5 000 filas, filas incompletas se omiten, devuelve predicción por fila y, en clasificación, `model_probability` (probabilidad máxima del modelo; **NO calibrada**, no es la probabilidad real de que ocurra algo). Devuelve además `input_simulated` y `model_trained_with_simulated`. Se guarda una fila en `predictions` con el texto de incertidumbre:
- Modelo no validado: «Modelo NO validado: sus resultados son experimentales…».
- Entrenado con simulados: se agrega «Entrenado con datos SIMULADOS: solo sirve para probar el sistema».
- Datos de entrada simulados: se agrega que las predicciones no describen ningún lugar real.
- Clasificación: se aclara que la probabilidad mostrada es la del modelo y no está calibrada.

## Mediciones reales (i5-2410M, 4 GB de RAM)

| Prueba | Resultado |
|---|---|
| Importar scikit-learn | ~5-7 s |
| Random forest, 5 000 filas x 10 columnas | 1,5 s |
| Random forest, 50 000 filas x 10 columnas | 14 s, pico de 249 MB de memoria del proceso |

Son mediciones puntuales con datos sintéticos de prueba, no un benchmark.

## Pendiente (no implementado)

- Redes neuronales (PyTorch): requiere autorización del usuario; no es viable entrenarlas a gran escala en 4 GB. Visión por computador con redes: ver [DOCUMENTACION_OPENCV.md](DOCUMENTACION_OPENCV.md).
- Datasets de imágenes con anotaciones, reanudar entrenamientos por épocas, hiperparámetros configurables, validación cruzada, partición espacial/temporal, calibración, variables categóricas.
- Entrenamiento en segundo plano con avance real.
- Ningún modelo se ha entrenado con **datos reales**: el catálogo está en [CATALOGO_MODELOS_IA.md](CATALOGO_MODELOS_IA.md).
