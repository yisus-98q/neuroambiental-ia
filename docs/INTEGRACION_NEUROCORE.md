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
| 4 | `terrain` | NEUROTERRAIN | especializado | 0/5 | en desarrollo | neurodata |
| 5 | `biodiversity` | (sin codename) | especializado | 0/6 | en desarrollo | neurodata, environmental |
| 6 | `neurogeo` | NEUROGEO | especializado | 0/5 | en desarrollo | neurodata |
| 7 | `mining` | NEUROMINING | especializado | 0/5 | en desarrollo | neurodata, environmental, terrain |
| 8 | `disasters` | NEURODISASTER | especializado | 0/5 | en desarrollo | neurodata, environmental, terrain, alerts |
| 9 | `construction` | NEUROCONSTRUCTION | especializado | 1/6 | parcial | neurodata, disasters, terrain |
| 10 | `neurotraining` | NEURAL TRAINING ENGINE | núcleo | 7/10 | parcial | neurodata |
| 11 | `neurovision` | NEUROVISION | especializado | 3/6 | parcial | neurodata, neurotraining |
| 12 | `neuroindustrial` | NEUROINDUSTRIAL | especializado | 0/3 | en desarrollo | neurodata, neurovision |
| 13 | `neuro3d` | NEURO 3D SIMULATION ENGINE | simulación | 5/5 | **operativo** (capacidades demostrativas por definición: no calibradas ni validadas) | neurodata, terrain |
| 14 | `neuroprediction` | NEURO PREDICTION ENGINE | núcleo | 2/4 | parcial (catálogo de tipos implementado; sin probabilidad calibrada ni horizonte temporal) | neurodata, neurotraining |
| 15 | `neurovoice` | NEUROVOICE IA | núcleo | 3/7 | parcial | neurocore |

Los conteos y estados salen de los descriptores del código en el momento de escribir este documento; la fuente de verdad es `GET /api/neurocore/modules`. NEUROCORE mismo no es un módulo del registro.

Nota: `mining` (NEUROMINING) ya no incluye geología: pasó a `neurogeo`. `neuroprediction` y `neurotraining` comparten el prefijo de API `/api/neurotraining`; `neuroprediction` no tiene endpoints propios.

## Cómo se comunican los módulos hoy

| Mecanismo | Realidad |
|---|---|
| API HTTP por módulo | Sí: `/api/neurodata`, `/api/alerts`, `/api/environmental`, `/api/neurotraining`, `/api/neurovision`, `/api/neuro3d`, `/api/simulation`, `/api/neuroprediction`, `/api/neurovoice`, `/api/neurocore` ([API.md](API.md)) |
| Datos compartidos | Sí: todo pasa por NEURODATA (`data_records`) y la base SQLite; el módulo ambiental produce rásters como registros; NEUROTRAINING consume CSV |
| Un proceso pesado a la vez | Sí: `core/jobs.py` (raster y entrenamiento) |
| Auditoría | Sí: `audit_logs` y `runs` |
| Llamadas entre módulos orquestadas por NEUROCORE | **No** |
| Cola/eventos entre módulos | **No** |
| Alertas automáticas desde modelos | **No** (capacidad pendiente) |

## Interfaz (menú agrupado)

`frontend/src/modules/menu.ts`: **General** (Inicio, Mapa territorial, Centro de alertas), **Núcleo inteligente** (NEUROCORE IA, NEURODATA ENGINE, NEURAL TRAINING CENTER, NEUROVOICE IA), **Modelos especializados** (NEUROVISION, NEUROTERRAIN, NEUROGEO, NEUROMINING, NEUROENVIRONMENT, NEURODISASTER, NEUROINDUSTRIAL, NEUROCONSTRUCTION, Fauna y flora), **Simulación** (NEURO 3D LAB), **Sistema** (Informes, Configuración).

Los módulos «en desarrollo» muestran una ficha honesta (capacidades pendientes, limitaciones) y ningún resultado.

## Intérprete de solicitudes

Reglas por palabras clave, sin modelo de lenguaje (ver [ARQUITECTURA_NEUROVOICE.md](ARQUITECTURA_NEUROVOICE.md)). Sirve para sugerir el módulo adecuado; no ejecuta acciones.

## Cómo integrar un módulo nuevo

1. Crear `backend/app/modules/<clave>/descriptor.py` con `ModuleDescriptor` (todas las capacidades pendientes salvo las realmente implementadas y probadas).
2. Registrarlo en `build_registry()` **después** de sus dependencias.
3. Si tiene API, añadir su router en `main.py` y documentarlo en [API.md](API.md).
4. Añadirlo al menú y a la documentación; actualizar las pruebas del registro.
5. Cambiar `implemented=True` solo cuando exista código **y** pruebas; el estado se recalcula solo.

## Pendiente

Orquestación real de flujos (p. ej. imagen → NEUROVISION → NEUROTRAINING → NEUROALERTS), eventos entre módulos, herramientas de NEUROVOICE que invoquen a NEUROCORE, alertas automáticas, informes multimódulo. Hoja de ruta: [ROADMAP.md](../ROADMAP.md).
