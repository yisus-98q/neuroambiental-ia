# Catálogo de modelos de IA

## Resumen honesto

| Hecho | Estado |
|---|---|
| Modelos entrenados con datos **reales** | **Ninguno** |
| Modelos **validados** | **Ninguno** |
| Modelos de ejemplo entrenados con datos **sintéticos o simulados** (solo en pruebas automáticas) | Existen únicamente en las pruebas; no se conservan como modelos del sistema |
| Redes neuronales profundas | No existen |
| Mecanismo para entrenar, evaluar, validar y retirar modelos ligeros | **Implementado y probado** ([ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md)) |

El catálogo vivo está en la base de datos (tabla `ai_models`, interfaz NEURAL TRAINING CENTER, `GET /api/neurotraining/models`); este documento no sustituye esa lista. Cada usuario puede registrar modelos «planificados», que no son modelos hasta que se entrenen.

## Algoritmos disponibles

| Algoritmo | Tarea | Para qué sirve | Limitaciones |
|---|---|---|---|
| `random_forest` | clasificación / regresión | Datos tabulares numéricos; robusto; da importancia de variables | Sin calibración (la `model_probability` no es una probabilidad real); no extrapola; sensible a fuga de datos |
| `regresion_logistica` | clasificación | Línea base lineal interpretable | Relaciones no lineales |
| `ridge` | regresión | Línea base lineal | Relaciones no lineales |

**Cómo leer las métricas de un modelo del catálogo:** salen del 25 % de filas reservadas del mismo CSV (corte aleatorio, mínimo 60 filas), **no de un conjunto independiente**, y pueden sobrestimar el rendimiento si los datos están autocorrelacionados en el espacio o el tiempo; `metrics.warnings` lo advierte. Un modelo solo se valida con revisión de otro administrador, versión y hash coincidentes, línea base superada y datos externos revisados ([PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md)).

## Qué NO es un modelo del catálogo

- Los **escenarios de NEURO 3D LAB** (trayectoria D8, susceptibilidad heurística, inundación de lámina local) son cálculos con reglas fijas y parámetros ajustables a mano: **no son modelos entrenados ni validados**, no aprenden de datos y se rotulan «SIMULACIÓN». En particular, la susceptibilidad (`w_pendiente·min(pendiente/45°,1) + w_vegetación·(1−NDVI)`) no es un modelo de riesgo.
- El **catálogo de tipos** de NEURO PREDICTION ENGINE (`/api/neuroprediction/catalog`) solo clasifica resultados existentes por reglas; una «predicción validada» exige un modelo del catálogo en estado `validado`, entrenado con datos no simulados, y hoy no hay ninguno.

## Modelos previstos por módulo (todos pendientes)

Ninguno de estos modelos existe. Son líneas de trabajo posibles, con lo que falta para que sean legítimas.

| Módulo | Modelo previsto | Requisitos que faltan | Estado |
|---|---|---|---|
| NEUROENVIRONMENT (`environmental`) | Cambio de vegetación (hoy: NDVI y umbral determinísticos, **no es un modelo entrenado**); clasificación de cobertura | Datos etiquetados con verdad de campo | Parcial 5/9 (cálculos, no IA) |
| NEURODISASTER (`disasters`) | Susceptibilidad a huaycos/deslizamientos | Inventario de eventos (INGEMMET/SIGRID), DEM, lluvia; sin ellos no se puede validar | En desarrollo 0/5 |
| NEUROTERRAIN (`terrain`) | Anomalías de desplazamiento (GPS/inclinómetros/InSAR) | Series de sensores reales | En desarrollo 0/5 |
| NEUROVISION (`neurovision`) | Clasificación/segmentación/detección en imágenes | Imágenes anotadas por expertos (no existen). Hoy solo hay procesamiento determinista con OpenCV (Canny, CLAHE, Otsu, ExG, comparación ORB+RANSAC), que **no es un modelo entrenado** | Parcial 3/6; sin modelos entrenados |
| NEUROGEO / NEUROMINING | Prospectividad (indicios, nunca reservas) | Datos geológicos y geoquímicos reales | En desarrollo |
| NEUROINDUSTRIAL | Anomalías de sensores; inspección visual | Series y fotos etiquetadas | En desarrollo 0/3 |
| Fauna y flora (`biodiversity`) | Reconocimiento de especies | Imágenes etiquetadas; GBIF (licencias por verificar) | En desarrollo 0/6 |

## Ficha mínima exigida a todo modelo antes de usarse

Nombre y versión; módulo; algoritmo; descripción y fuente del dataset (marcado real o simulado); variables de entrada y objetivo; métricas **sobre datos de prueba** y línea base; limitaciones; fecha; quién lo validó y con qué evidencia (si aplica); estado (`planificado`, `entrenado`, `validado`, `retirado`). La mayoría de estos campos ya los guarda `ai_models` ([DATABASE.md](DATABASE.md)).

## Criterios de validación

Ver [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md). Mientras un modelo no esté validado, toda salida se presenta como **experimental**.
