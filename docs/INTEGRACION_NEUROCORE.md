# Integración con NEUROCORE

NEUROCORE IA es el coordinador: **registra módulos** con un contrato común, **deriva su estado** de las capacidades implementadas e **interpreta solicitudes** por palabras clave. No ejecuta análisis por sí mismo ni orquesta flujos automáticos entre módulos: cada módulo expone su propia API y la interfaz los une. La orquestación general (que NEUROCORE llame a otros módulos para cumplir una orden compleja) está **pendiente**.

## Contrato (`backend/app/neurocore/base.py`)

`ModuleDescriptor`: `key`, `name`, `codename` (nombre de la arquitectura avanzada), `group` (`nucleo`, `especializado` o `simulacion`), `version`, `description`, `capabilities`, `dependencies`, `inputs`, `outputs`, `possible_errors`, `limitations`, `keywords`, `api_prefix`. El estado (`operativo`, `parcial`, `en_desarrollo`) **se calcula**; no se declara. Detalles en [ARCHITECTURE.md](../ARCHITECTURE.md).

## Registro (15 módulos, en este orden)

El orden impide dependencias circulares: un módulo solo puede depender de los ya registrados.

| # | key | Codename | Grupo | Capacidades | Estado | Depende de |
|---|---|---|---|---|---|---|
| 1 | `neurodata` | NEURODATA ENGINE | núcleo | 7/7 | **operativo** | — |
| 2 | `alerts` | NEUROALERTS | especializado | 5/6 | parcial | neurodata |
| 3 | `environmental` | NEUROENVIRONMENT | especializado | 5/9 | parcial | neurodata |
| 4 | `terrain` | NEUROTERRAIN | especializado | 4/5 | parcial (series por CSV, indicador experimental; sin InSAR) | neurodata |
| 5 | `biodiversity` | (sin codename) | especializado | 2/6 | parcial (especies y observaciones; sin reconocimiento ni análisis de fotos) | neurodata, environmental |
| 6 | `neurogeo` | NEUROGEO | especializado | 0/5 | en desarrollo | neurodata |
| 7 | `mining` | NEUROMINING | especializado | 0/5 | en desarrollo | neurodata, environmental, terrain |
| 8 | `disasters` | NEURODISASTER | especializado | 0/5 | en desarrollo | neurodata, environmental, terrain, alerts |
| 9 | `construction` | NEUROCONSTRUCTION | especializado | 4/7 | parcial (análisis preliminar de sitio; sin proximidad a ríos ni compatibilidad territorial) | neurodata, disasters, terrain |
| 10 | `neurotraining` | NEURAL TRAINING ENGINE | núcleo | 7/10 | parcial | neurodata |
| 11 | `neurovision` | NEUROVISION | especializado | 3/6 | parcial | neurodata, neurotraining |
| 12 | `neuroindustrial` | NEUROINDUSTRIAL | especializado | 0/3 | en desarrollo | neurodata, neurovision |
| 13 | `neuro3d` | NEURO 3D SIMULATION ENGINE | simulación | 6/6 | **operativo** (incluye las capas NDVI/cambio; los escenarios son demostrativos, no calibrados ni validados) | neurodata, terrain |
| 14 | `neuroprediction` | NEURO PREDICTION ENGINE | núcleo | 2/4 | parcial (catálogo de tipos implementado; sin probabilidad calibrada ni horizonte temporal) | neurodata, neurotraining |
| 15 | `neurovoice` | NEUROVOICE IA | núcleo | 5/8 | parcial (texto y voz en el navegador; sin modelo de lenguaje, otros idiomas ni acciones por voz) | neurocore |

Los conteos y estados salen de los descriptores del código en el momento de escribir este documento; la fuente de verdad es `GET /api/neurocore/modules`. NEUROCORE mismo no es un módulo del registro.

Nota: `mining` (NEUROMINING) ya no incluye geología: pasó a `neurogeo`. `neuroprediction` y `neurotraining` comparten el prefijo de API `/api/neurotraining`; `neuroprediction` no tiene endpoints propios.

## Cómo se comunican los módulos hoy

| Mecanismo | Realidad |
|---|---|
| API HTTP por módulo | Sí: `/api/neurodata`, `/api/alerts`, `/api/environmental`, `/api/neurotraining`, `/api/neurovision`, `/api/neuro3d`, `/api/simulation`, `/api/terrain`, `/api/biodiversity`, `/api/construction`, `/api/neuroprediction`, `/api/neurovoice`, `/api/neurocore` ([API.md](API.md)) |
| Datos compartidos | Sí: todo pasa por NEURODATA (`data_records`) y la base SQLite; el módulo ambiental produce rásters como registros; NEUROTRAINING consume CSV |
| Un proceso pesado a la vez | Sí: `core/jobs.py` (raster y entrenamiento) |
| Auditoría | Sí: `audit_logs` y `runs` |
| Llamadas entre módulos orquestadas por NEUROCORE | **No** |
| Cola/eventos entre módulos | **No** |
| Alertas automáticas desde modelos | **No** (capacidad pendiente). NEUROTERRAIN solo crea una alerta experimental **a petición explícita** de un analista |
| Observaciones de biodiversidad en el catálogo de NEURO PREDICTION | **No todavía** (propuesta: simuladas → simulación; reales no descartadas → observación real; descartadas → excluir) |
| NEUROCONSTRUCTION usa escenarios de NEURO 3D LAB | Sí: reutiliza susceptibilidad e inundación demostrativa sobre un DEM ya obtenido |
| NEUROVOICE → datos de otros módulos | Sí, **solo lectura**: consulta alertas, datos, terreno y escenarios, NDVI, modelos y catálogo; no ejecuta acciones |
| Arranque con carga diferida de librerías pesadas | Sí (`core/lazy.py`: scikit-learn, OpenCV, scipy, rasterio se importan al primer uso) |
| Prueba de integración entre módulos | Sí (`test_integration.py`): flujo NEURODATA → NEUROCORE → NEUROVOICE → catálogo y mapa; todas las rutas no públicas exigen sesión; el lector no puede escribir salvo `POST /api/auth/logout`, `/api/neurovoice/chat` y `/api/neurocore/interpret` |

## Interfaz (menú agrupado)

`frontend/src/modules/menu.ts`: **General** (Inicio, Mapa territorial, Centro de alertas), **Núcleo inteligente** (NEUROCORE IA, NEURODATA ENGINE, NEURAL TRAINING CENTER, NEUROVOICE IA), **Modelos especializados** (NEUROVISION, NEUROTERRAIN, NEUROGEO, NEUROMINING, NEUROENVIRONMENT, NEURODISASTER, NEUROINDUSTRIAL, NEUROCONSTRUCTION, Fauna y flora), **Simulación** (NEURO 3D LAB), **Sistema** (Informes, Configuración).

Los módulos «en desarrollo» muestran una ficha honesta (capacidades pendientes, limitaciones) y ningún resultado.

## Intérprete de solicitudes

Reglas por palabras clave, sin modelo de lenguaje (ver [ARQUITECTURA_NEUROVOICE.md](ARQUITECTURA_NEUROVOICE.md)). Sirve para sugerir el módulo adecuado y, en NEUROVOICE, para responder con datos reales; la entrada puede venir de texto o de voz transcrita en el navegador. No ejecuta acciones.

## Cómo integrar un módulo nuevo

1. Crear `backend/app/modules/<clave>/descriptor.py` con `ModuleDescriptor` (todas las capacidades pendientes salvo las realmente implementadas y probadas).
2. Registrarlo en `build_registry()` **después** de sus dependencias.
3. Si tiene API, añadir su router en `main.py` y documentarlo en [API.md](API.md).
4. Añadirlo al menú y a la documentación; actualizar las pruebas del registro.
5. Cambiar `implemented=True` solo cuando exista código **y** pruebas; el estado se recalcula solo.

## Pendiente

Orquestación real de flujos (p. ej. imagen → NEUROVISION → NEUROTRAINING → NEUROALERTS), eventos entre módulos, herramientas sensibles de NEUROVOICE (ejecutar análisis o simulaciones por voz con confirmación), capas de NDVI/cambios sobre el terreno 3D, alertas automáticas, informes multimódulo. Hoja de ruta: [ROADMAP.md](../ROADMAP.md).
