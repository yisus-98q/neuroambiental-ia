# Simulaciones y predicción

**Estado: existen escenarios demostrativos simplificados (trayectoria D8, susceptibilidad heurística, inundación de lámina local y un comparador) y un catálogo que separa los tipos de información. Ninguna simulación está calibrada ni validada con eventos reales, y ningún resultado es una predicción.** Las únicas «predicciones» son las de modelos scikit-learn ligeros registradas en `predictions` ([ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md)), ninguna entrenada con datos reales.

Código: `backend/app/modules/neuro3d/scenarios.py`, `backend/app/api/simulation.py` (prefijo `/api/simulation`), `backend/app/modules/neuroprediction/ledger.py`, `backend/app/api/neuroprediction.py`, interfaz `Neuro3DLab.tsx` y `PredictionPanel.tsx`; pruebas `tests/backend/test_scenarios.py` y `test_neuroprediction.py`.

## Tipos de información: el catálogo (implementado)

El catálogo (`GET /api/neuroprediction/catalog`, `/catalog/{tipo}/{id}`, `/kinds`; sin tablas nuevas, solo lectura de metadatos) clasifica cada elemento en **exactamente un tipo** con reglas disjuntas:

| Tipo | ¿Verificado? | Regla (resumen) |
|---|---|---|
| `observacion_real` | sí (declarado) | `data_records` con `is_simulated=False` que no sean procesamiento ni escenario (csv, geojson, imagen, documento, `medicion_manual`, `raster_dem`); eventos reales sin fecha pasada firme |
| `dato_historico` | sí (declarado) | Evento real con `occurred_at` anterior a hoy |
| `resultado_procesamiento` | no | `data_records` `raster_ndvi`, `raster_cambio`, `imagen_procesada` (cálculos deterministas, no modelos) |
| `estimacion_modelo` | no | Cualquier predicción de modelo que no cumpla todo lo de «predicción validada» |
| `simulacion` | no | `runs` de escenario (`escenario_*`), `raster_escenario` y **cualquier** registro o evento con `is_simulated=True` |
| `prediccion` (predicción validada) | sí | Predicción con `is_validated`, modelo en estado `validado`, modelo no entrenado con datos simulados y datos de entrada no simulados |
| `alerta_verificada` | sí | Alerta con `validation_status = validada` y no simulada (no es una emergencia oficial) |
| `alerta_experimental` | no | El resto de alertas (no validada, en revisión, descartada o simulada): **subtipo no verificado**, nunca se cuenta como verificada |

Son 8 categorías en el código (los 7 tipos del plan más «alerta experimental» como no verificada). Reglas clave: un elemento con `is_simulated=True` **jamás** es observación real, dato histórico, predicción ni alerta verificada (el código lo asevera); `horizonte_temporal` se devuelve siempre en `null` (el sistema no define horizontes y no los inventa); `probabilidad` solo aparece en una predicción validada y es la media de la probabilidad del modelo en la muestra, **no calibrada**. Cada elemento trae: ubicación, fechas, datos usados, modelo y versión, resultado, incertidumbre, evidencias, limitaciones y recomendaciones de verificación.

Limitaciones del catálogo: clasifica por reglas, **no valida nada por sí mismo**. «Verificado» significa «cumple las reglas», no «es cierto»: la condición «real» es una declaración de quien cargó el dato, y la validación de un modelo es una decisión humana con evidencia en texto libre (la definición de `prediccion` habla de «evidencia independiente», pero el sistema no comprueba que lo sea). Las predicciones se clasifican en memoria sobre las últimas 2 000.

## Escenarios simplificados (implementados; todos son SIMULACIÓN)

Todo escenario lleva el rótulo permanente **«SIMULACIÓN — escenario hipotético, no es una predicción»**, se guarda como `DataRecord` `raster_escenario` (con `is_simulated` heredado) y un `Run` `escenario_*`, y se muestra como capa «Escenario» en el visor 3D.

| Escenario | Qué calcula | Límites |
|---|---|---|
| Trayectoria D8 (`POST /api/neuro3d/terrains/{id}/flow-path`) | Camino de máxima pendiente desde un punto | No rellena depresiones; no modela material, agua ni volumen |
| **Susceptibilidad** heurística (`POST /api/simulation/susceptibility`) | Índice `w_pendiente·min(pendiente/45°, 1) + w_vegetación·(1 − NDVI)`, con NDVI opcional (sin NDVI, solo pendiente); clases bajo/medio/alto por umbrales | Pesos (suman 1) y umbrales (por defecto 0,6/0,4 y 0,33/0,66) **ajustables, no calibrados ni validados** con inventarios de eventos; no predice deslizamientos ni fechas |
| **Inundación demostrativa** de lámina local (`POST /api/simulation/flood`) | Celdas conectadas al punto cuya cota está entre (cota del punto − subida) y (cota del punto + subida); subida de 0,5 a 50 m | Ignora caudal, cauce, rugosidad, tiempo y drenaje; **no representa flujo aguas abajo**; se trunca en el borde del DEM; no es una simulación hidráulica |
| **Comparador** (`POST /api/simulation/compare`) | 2 a 4 configuraciones lado a lado más una fila «Estado actual (observado)»; cálculo en memoria, **no guarda** | Hereda los límites de cada escenario |

### Por qué la inundación es de «lámina local» (verificado con datos reales)

Una «bañera» pura sobre el DEM de Huaraz inundaba todo el valle aguas abajo, porque el agua llena lo que está más bajo que el punto: con 2 m de subida daba **42,6 km² y 335 m de profundidad**, físicamente absurdo (el agua escurre). Con la banda ±subida alrededor de la cota del punto el resultado es acotado:

| Subida | Área inundada | Profundidad máx. |
|---|---|---|
| 2 m | 0,29 km² | 3,85 m |
| 5 m | 0,70 km² | 9,96 m |
| 10 m | 1,43 km² | 19,65 m |

Estas cifras son una ejecución puntual sobre un DEM de ~100 m: ilustran el comportamiento del método, **no son una estimación de inundación real**.

### Ejemplo de susceptibilidad (Huaraz, solo pendiente, umbrales 0,33/0,66)

Sobre 913 km²: bajo 28,9 %, medio 45,4 %, alto 25,7 %; cálculo en ~0,1 s. Es la distribución de un índice geométrico, no una probabilidad de deslizamiento.

## Qué necesitaría una simulación válida (pendiente)

1. Un **modelo físico o estadístico** declarado con sus supuestos y rango de validez.
2. **Datos de entrada reales** (DEM, lluvia, suelos, inventarios), con fuente y licencia ([DOCUMENTACION_DATASETS.md](DOCUMENTACION_DATASETS.md)).
3. **Calibración y validación** con eventos observados ([PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md)).
4. **Incertidumbre explícita** y horizonte temporal (capacidad `horizonte_temporal` pendiente).
5. Presentación como «escenario», nunca como pronóstico de fecha.

NEUROCONSTRUCTION reutiliza estos mismos escenarios (susceptibilidad solo con pendiente e inundación opcional) en su análisis preliminar de sitio, con las mismas limitaciones; ver [API.md](API.md).

Nota sobre el catálogo: las observaciones de biodiversidad aún **no se reflejan** en el catálogo de tipos (para ellas se propone: simuladas → simulación; reales no descartadas → observación real; descartadas → excluir).

Pendiente: escenarios de fugas/incendio industrial (NEUROINDUSTRIAL), modelos hidráulicos o geotécnicos, guardar los resultados del comparador. (Las capas de NDVI y de cambio sobre el terreno ya están, como capa observada, desde la Fase 9.)

## Reglas innegociables

- No se predice la **fecha exacta** de terremotos, explosiones ni otros eventos.
- Una probabilidad solo se muestra si el modelo está **calibrado y validado** (capacidad `probabilidad_calibrada` pendiente; hoy `model_probability` es la probabilidad máxima del modelo, **NO calibrada**, y el texto de incertidumbre lo dice).
- Todo resultado de simulación o de modelo no validado se rotula como **simulación o experimental**.
- Los datos simulados jamás se presentan como reales (`is_simulated`).
- Ver [ARQUITECTURA_NEURO_3D.md](ARQUITECTURA_NEURO_3D.md) y [INTEGRACION_NEUROCORE.md](INTEGRACION_NEUROCORE.md).
