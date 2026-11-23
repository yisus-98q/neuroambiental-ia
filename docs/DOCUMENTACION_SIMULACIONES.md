# Simulaciones y predicción

**Estado: existe un único escenario demostrativo (trayectoria de máxima pendiente D8 sobre un DEM real, en NEURO 3D LAB) y ninguna simulación física validada.** Este documento fija las reglas y el diseño pendiente. Las únicas «predicciones» que existen son las de modelos scikit-learn ligeros registradas en `predictions` (ver [ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md)), y ninguna se ha entrenado con datos reales.

## Tipos de información (política del proyecto)

La arquitectura exige distinguir siempre estos tipos y no mezclarlos en pantalla ni en informes:

| Tipo | Qué es | Dónde está hoy |
|---|---|---|
| Observación | Dato medido o recibido | `data_records`, `measurements`, `events` |
| Procesamiento | Resultado calculado de una observación | NDVI y cambios de Sentinel-2 (`raster_ndvi`, `raster_cambio`; sin validar) |
| Estimación / predicción | Salida de un modelo | `predictions` (experimental si el modelo no está validado) |
| Simulación | Escenario hipotético con supuestos | Solo el escenario demostrativo D8 de NEURO 3D LAB (en `runs`, rotulado como simulación) |
| Alerta verificada | Aviso revisado por una persona o autoridad | La plataforma solo emite alertas **experimentales**; las oficiales son de INDECI / COEN |

El módulo NEURO PREDICTION ENGINE (`neuroprediction`, parcial 1 de 4) declara la capacidad `separacion_tipos` como **pendiente** (corregido tras una revisión): en el código **no hay un campo ni una lógica que clasifique las salidas en estos cinco tipos**; hoy solo existen las marcas `is_simulated` e `is_validated` y el registro de predicciones con incertidumbre.

## Qué necesitaría una simulación válida (pendiente)

1. Un **modelo físico o estadístico** declarado (p. ej. flujo, talud, inundación por DEM) con sus supuestos y rango de validez.
2. **Datos de entrada reales** (DEM, lluvia, suelos, inventarios), con fuente y licencia.
3. **Calibración y validación** con eventos observados (ver [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md)).
4. **Incertidumbre explícita** y horizonte temporal (capacidad `horizonte_temporal` pendiente).
5. Presentación como «escenario», nunca como pronóstico de fecha.

## Escenarios demostrativos (NEURO 3D)

**Implementado:** trayectoria de máxima pendiente (D8) desde un punto sobre el DEM Copernicus GLO-30 (`POST /api/neuro3d/terrains/{id}/flow-path`, analista). Siempre rotulada: «Escenario demostrativo simplificado… no es una simulación geotécnica ni predice un evento». No modela material, agua, rugosidad ni volumen; no se ha validado contra eventos reales. El comparador de escenarios y las capas de NDVI/cambios sobre el terreno están **pendientes**.

**Propuestos (no implementados):**

| Escenario | Enfoque propuesto | Limitación |
|---|---|---|
| Deslizamiento | Umbrales de pendiente sobre el DEM (susceptibilidad geométrica simple) | No es un análisis de estabilidad geotécnica |
| Inundación | Relleno por cota (nivel de agua hipotético sobre el DEM) | No es un modelo hidráulico; ignora caudales y obstáculos |
| Fugas/incendio industrial | Escenarios ilustrativos (NEUROINDUSTRIAL) | Sin modelos de dispersión; solo demostrativo |

## Reglas innegociables

- No se predice la **fecha exacta** de terremotos, explosiones ni otros eventos.
- Una probabilidad solo se muestra si el modelo está **calibrado y validado** (capacidad `probabilidad_calibrada` pendiente; hoy `model_probability` de clasificación es la probabilidad máxima del modelo, **NO calibrada**, y así lo dice el texto de incertidumbre de cada predicción).
- Todo resultado de simulación o de modelo no validado se rotula como **experimental**.
- Los datos simulados jamás se presentan como reales (`is_simulated`).
- Ver [ARQUITECTURA_NEURO_3D.md](ARQUITECTURA_NEURO_3D.md) y [INTEGRACION_NEUROCORE.md](INTEGRACION_NEUROCORE.md).
