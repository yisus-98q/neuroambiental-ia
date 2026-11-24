# API

Documentación interactiva (generada por FastAPI): <http://127.0.0.1:8000/docs>. Todos los mensajes de error están en español.

**Autenticación.** `POST /api/auth/login` devuelve un token; se envía en `Authorization: Bearer <token>`. Roles (de menor a mayor): `lector` < `analista` < `admin`. «Rol mínimo» indica el nivel necesario; un rol superior también puede.

- **público**: sin sesión.
- **lector**: cualquier usuario con sesión válida.
- **analista**: analista o admin.
- **admin**: solo admin.

Códigos habituales: 401 sin sesión o sesión expirada; 403 rol insuficiente; 422 datos inválidos; 429 demasiados intentos de login.

## Sistema

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/health` | público | Estado del servicio y de la base de datos. |
| GET | `/api/dashboard` | lector | Resumen del Inicio: alertas por nivel/estado, registros reales vs simulados, actividad reciente, fuentes, estado de módulos. Todo sale de la base. |

## Autenticación

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/auth/login` | público | Usuario y contraseña; devuelve token, expiración y usuario. Límite: 5 fallos por usuario cada 5 min. |
| POST | `/api/auth/logout` | lector | Revoca la sesión actual (204). |
| GET | `/api/auth/me` | lector | Datos del usuario actual. |
| GET | `/api/auth/users` | admin | Lista usuarios. |
| POST | `/api/auth/users` | admin | Crea usuario (contraseña mín. 10 caracteres, letras + números/símbolos; rol lector/analista/admin). |

## NEUROCORE

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neurocore` | público | Información del núcleo y cantidad de módulos registrados. |
| GET | `/api/neurocore/modules` | público | Contrato y estado de todos los módulos. |
| GET | `/api/neurocore/modules/{key}` | público | Contrato de un módulo (404 si no existe). |
| POST | `/api/neurocore/interpret` | lector | Interpreta un texto por palabras clave (`{"text": "..."}`). |
| GET | `/api/neurocore/operations?limit=` | analista | Últimas operaciones de auditoría (máx. 200). |

## NEURODATA

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/neurodata/upload` | analista | Carga de archivo (multipart): `file`, `source_name`, `is_simulated` (obligatorios), `source_license`, `title`, `observed_at`, `provenance`, `module_key`. Valida extensión y contenido; máx. 10 MB. |
| POST | `/api/neurodata/records/manual` | analista | Registro manual de una medición (`is_simulated` obligatorio). |
| GET | `/api/neurodata/records` | lector | Lista de registros; filtros `data_type`, `is_simulated`, `limit` (máx. 500), `offset`. |
| GET | `/api/neurodata/records/{id}` | lector | Metadatos de un registro. |
| GET | `/api/neurodata/records/{id}/file` | lector | Descarga el archivo original (404 sin archivo; 410 si ya no existe en disco). |
| GET | `/api/neurodata/records/{id}/preview` | lector | Vista previa PNG (RGBA, EPSG:4326, alineada con el `bbox` del registro) de un ráster NDVI o de cambio. 404 si el registro no es un ráster; 410 si el PNG ya no existe. |
| GET | `/api/neurodata/records/{id}/geojson` | lector | Elementos georreferenciados del registro como GeoJSON. |
| GET | `/api/neurodata/layers?include_simulated=` | lector | Capas para el mapa (hasta 50 registros válidos georreferenciados, 5000 elementos por capa). |
| GET | `/api/neurodata/sources` | lector | Fuentes registradas. |
| GET | `/api/neurodata/limits` | público | Límites de carga y extensiones permitidas. |

Extensiones permitidas: `.csv`, `.geojson`, `.json`, `.png`, `.jpg`, `.jpeg`, `.pdf`.

## Alertas y eventos (experimentales)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/alerts` | lector | Lista; filtros `level`, `validation_status`, `limit` (máx. 500). |
| POST | `/api/alerts` | analista | Crea una alerta (siempre `experimental`; exige nivel, fuente, incertidumbre e `is_simulated`). |
| GET | `/api/alerts/geojson` | lector | Alertas con ubicación como puntos GeoJSON (máx. 1000). |
| GET | `/api/alerts/events` | lector | Últimos 200 eventos. |
| POST | `/api/alerts/events` | analista | Registra un evento. |
| GET | `/api/alerts/{id}` | lector | Detalle con seguimientos. |
| POST | `/api/alerts/{id}/followups` | analista | Agrega nota; opcionalmente cambia el estado de validación. |
| POST | `/api/alerts/{id}/report` | analista | Genera y guarda un informe Markdown de la alerta. |

## Predicción ambiental (Fase 2)

Requiere Internet para buscar escenas y calcular NDVI (servicios públicos de Sentinel-2). Un solo procesamiento a la vez.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/environmental/defaults` | público | Área por defecto (Huaraz / Cordillera Blanca, `[-77.60, -9.60, -77.30, -9.35]`), resolución (0,0003°), lado máximo (0,5°), fuente y URL. |
| POST | `/api/environmental/scenes/search` | analista | Busca escenas Sentinel-2 L2A: `bbox`, `date_from`, `date_to` (no futura), `max_cloud` (0-100, 20 por defecto). Devuelve hasta 20, ordenadas por nubosidad. |
| POST | `/api/environmental/ndvi` | analista | Calcula el NDVI de una escena (`item_id`, `bbox`, `resolution_deg` 0,0001 a 0,005). Responde 201 con el registro `raster_ndvi`. Tarda de segundos a pocos minutos. |
| POST | `/api/environmental/change` | analista | Detecta cambios entre dos NDVI (`before_id`, `after_id`, `threshold` 0,05 a 0,8; 0,2 por defecto). Los ordena por fecha. 201 con el registro `raster_cambio` (sin validar). |
| GET | `/api/environmental/rasters` | lector | Últimos 100 registros `raster_ndvi` y `raster_cambio` (con estadísticas, incertidumbre y procedencia en `extra`). |
| GET | `/api/environmental/analyses` | lector | Últimos 50 análisis (tabla `runs` del módulo) con parámetros y resumen. |

Errores propios: 409 si ya hay un procesamiento en curso; 422 por área o malla inválida, escena que no cubre el área, sin píxeles válidos o NDVI incompatibles (distinta área/resolución); 502 si el servicio de imágenes no responde. El `bbox` debe ser `[minLon, minLat, maxLon, maxLat]` con lados de máximo 0,5°.

## NEUROVISION (OpenCV, determinista)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neurovision/operations` | lector | Operaciones disponibles con sus parámetros y rangos, límites (2048 px por lado, 25 MP), versión de OpenCV, nota de confianza y limitaciones. |
| POST | `/api/neurovision/analyze` | analista | Aplica una operación a una imagen ya cargada: `record_id` (registro `imagen`), `operation`, `params`. 201 con un registro `imagen_procesada` (con superposición). |
| POST | `/api/neurovision/compare` | analista | Compara dos fotos de la misma escena: `record_a`, `record_b` (alineación ORB + RANSAC; 422 si hay < 10 correspondencias o si la homografía no es plausible: inliers < 25 %, escala fuera de 0,5-2 o perspectiva > 0,002). No usa georreferenciación. |
| GET | `/api/neurovision/results` | lector | Últimos resultados `imagen_procesada` (hasta 100), **sin las regiones** (se ven por registro). |
| GET | `/api/neurovision/results/{id}/overlay` | lector | PNG de la superposición del resultado. |

Errores: 404 registro inexistente; 409 otro procesamiento pesado en curso; 422 imagen corrupta, > 25 MP o parámetros inválidos. `confidence` siempre es `null`: son operaciones deterministas, no un modelo. Ver [DOCUMENTACION_OPENCV.md](DOCUMENTACION_OPENCV.md).

## NEURO 3D LAB (DEM y escenario demostrativo)

Requiere Internet para descargar el DEM (Copernicus GLO-30).

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neuro3d/defaults` | lector | Área por defecto (Huaraz), resolución (0,0009°), lado máximo (0,5°), fuente y atribución. |
| POST | `/api/neuro3d/terrain` | analista | Obtiene el DEM de un `bbox` (lado máx. 0,5°; con la resolución por defecto el tope real es ~0,46° por la malla máxima de 512 px) con `resolution_deg` (0,0003 a 0,01). 201 con un registro `raster_dem`. |
| GET | `/api/neuro3d/terrains` | lector | Terrenos ya obtenidos. |
| GET | `/api/neuro3d/terrains/{id}/mesh?max_size=` | lector | Malla (alturas) para el visor, hasta 512 x 512 (`max_size` 16 a 512), con pendiente y estadísticas, `valid` (máscara 0/1 de celdas con dato) y `valid_pct`. |
| POST | `/api/neuro3d/terrains/{id}/flow-path` | analista | Trayectoria de máxima pendiente (D8) desde `lon`, `lat`. Escenario **demostrativo**, no es simulación geotécnica. Incluye `end_reason` (`minimo_local` o `sin_dato`). |
| GET | `/api/neuro3d/scenarios` | lector | Escenarios guardados. |
| GET | `/api/neuro3d/scenarios/{id}` | lector | Un escenario. |

Errores: 409 proceso pesado en curso; 422 DEM no disponible o punto fuera del DEM; 502 servicio de DEM no disponible. Ver [ARQUITECTURA_NEURO_3D.md](ARQUITECTURA_NEURO_3D.md).

## Simulación: escenarios simplificados (`/api/simulation`)

Todo es **simulación demostrativa**, no una predicción; las respuestas incluyen `banner` («SIMULACIÓN — escenario hipotético, no es una predicción»). Los escenarios se guardan como registros `raster_escenario` (`is_simulated` heredado). Un solo proceso pesado a la vez (409). Detalle: [DOCUMENTACION_SIMULACIONES.md](DOCUMENTACION_SIMULACIONES.md).

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/simulation/susceptibility` | analista | Índice heurístico de susceptibilidad sobre un DEM: `dem_id`, `ndvi_id` opcional, `w_pendiente` y `w_vegetacion` (suman 1; 0,6/0,4 por defecto), `umbral_medio` y `umbral_alto` (0 < medio < alto < 1; 0,33/0,66). **No calibrado ni validado.** 201. |
| POST | `/api/simulation/flood` | analista | Inundación demostrativa de lámina local: `dem_id`, `lon`, `lat`, `rise_m` (0,5 a 50). Celdas conectadas con cota entre (cota del punto − subida) y (cota del punto + subida). No es una simulación hidráulica. 201. |
| POST | `/api/simulation/compare` | analista | Compara 2 a 4 configuraciones (`kind`: `susceptibilidad` o `inundacion_demostrativa`) frente al estado actual observado. Cálculo en memoria; **no guarda** (`saved: false`). |
| GET | `/api/simulation/scenarios?dem_id=` | lector | Escenarios guardados (opcionalmente de un DEM). |
| GET | `/api/simulation/scenarios/{id}/grid?max_size=` | lector | Malla del escenario para el visor (`max_size` 16 a 512). |
| GET | `/api/simulation/scenarios/{id}/preview` | lector | PNG de vista previa. |

Errores: 404 registro inexistente; 409 proceso pesado en curso; 422 parámetros inválidos, punto fuera del DEM o en celda sin dato.

## NEURO PREDICTION ENGINE: catálogo de tipos (`/api/neuroprediction`)

Solo lectura; sin tablas nuevas. Clasifica los resultados por reglas ([DOCUMENTACION_SIMULACIONES.md](DOCUMENTACION_SIMULACIONES.md)). Todos exigen sesión (lector).

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neuroprediction/kinds` | lector | Las 8 categorías con definición, regla, si son verificadas y limitaciones. |
| GET | `/api/neuroprediction/catalog?tipo=&limit=&offset=` | lector | Elementos unificados (`limit` 1 a 200) más `totales_por_tipo`. Cada elemento trae ubicación, fechas, datos usados, modelo, versión, incertidumbre, evidencias, limitaciones y `simulated`. `horizonte_temporal` siempre `null`. 422 si el tipo no existe. |
| GET | `/api/neuroprediction/catalog/{tipo}/{id}` | lector | Detalle de un elemento (404 si no pertenece a ese tipo). |

## NEUROTERRAIN (`/api/terrain`)

Series de desplazamiento de sensores **importadas por CSV** de NEURODATA (no hay conexión con equipos). Todo es un **indicador experimental por umbrales de ejemplo configurables**, no una predicción de falla ni criterio geotécnico.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/terrain/sensors` | analista | Crea un sensor: `name`, `kind` (gps, inclinometro, etc.), `latitude`/`longitude` juntas o ninguna, `territory_id` opcional. |
| GET | `/api/terrain/sensors` | lector | Sensores (hasta 500) con variables y rango de fechas. |
| GET | `/api/terrain/sensors/{id}` | lector | Un sensor. |
| POST | `/api/terrain/sensors/{id}/import` | analista | Importa mediciones desde un CSV registrado en NEURODATA: `data_record_id`, `format` (`largo` o `ancho`), columnas de fecha/variable/valor/unidad (o `value_columns` en formato ancho), `units`, `normalize` (ordena y descarta duplicados idénticos; los conflictivos se rechazan). 201. No se importa dos veces el mismo CSV al mismo sensor. |
| GET | `/api/terrain/sensors/{id}/series` | lector | Análisis de la serie: acumulado, velocidad por regresión, saltos (`k_mad` 2 a 50), aceleración por comparación de ventanas (`window_days`, `vel_threshold`, `acc_ratio`) y clasificación experimental; `max_points` 10 a 2000. |
| POST | `/api/terrain/sensors/{id}/alert` | analista | Crea una alerta **experimental** solo a petición explícita (nunca automática), con `level` opcional y `notes`. |

## Fauna, Flora y Biodiversidad (`/api/biodiversity`)

El catálogo de especies **empieza vacío**. La identificación la declara el observador y no se verifica; no hay modelo de reconocimiento.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/biodiversity/species` | analista | Registra una especie: `nombre_cientifico` (único), `nombre_comun`, taxonomía, `categoria_conservacion` (tipo UICN, mostrada «según la fuente»; el sistema no la evalúa), `fuente_taxonomica` obligatoria. |
| GET | `/api/biodiversity/species` | lector | Lista; `q`, `limit` (máx. 500), `offset`. |
| POST | `/api/biodiversity/observations` | analista | Registra una observación georreferenciada: especie (o «no identificada»), `fecha_observacion` (no futura), `observador`, `cantidad` ≥ 1, `metodo`, `confianza_identificacion`, foto ya cargada en NEURODATA (solo se enlaza), `is_simulated` obligatorio. Nace `no_validada`. |
| GET | `/api/biodiversity/observations` | lector | Lista con filtros. |
| GET | `/api/biodiversity/observations/geojson` | lector | Capa GeoJSON para el mapa (`incluir_descartadas` opcional, `bbox`); cada elemento lleva `is_simulated`. |
| GET | `/api/biodiversity/observations/{id}` | lector | Una observación. |
| POST | `/api/biodiversity/observations/{id}/validate` | **admin** | Cambia el estado (`no_validada`, `validada`, `descartada`) con una nota (≥ 3 caracteres); queda auditado. No impide que el mismo admin valide una observación que él cargó. |
| GET | `/api/biodiversity/summary?is_simulated=` | lector | Resumen por especie, mes y estado. La riqueza de especies depende del esfuerzo de muestreo: no es un índice de biodiversidad. |

## NEUROCONSTRUCTION (`/api/construction`)

Análisis preliminar de sitio sobre un DEM ya obtenido. **No reemplaza evaluaciones profesionales ni autorizaciones oficiales**; susceptibilidad e inundación son escenarios simplificados no calibrados.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/construction/site-analysis` | analista | `dem_id` y **un** punto (`point`: `lon`, `lat`) **o** un polígono GeoJSON (máx. ~200 KB), `buffer_m` (0 a 5000; 500 por defecto), `flood` opcional (`lon`, `lat`, `rise_m` 0,5 a 50) y `name`. Devuelve elevación, pendiente, entorno, susceptibilidad heurística (solo pendiente), inundación demostrativa si se pide y observaciones por reglas fijas. 201; 409 si hay otro proceso pesado; 422 si el sitio cae fuera del DEM. |
| GET | `/api/construction/analyses` | lector | Análisis guardados (con `notice`). |

## NEURODISASTER (`/api/disasters`)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/disasters/inventory/import` | analista | Inventario INGEMMET por recorte (`bbox`, máx. 2,5° por lado). Uso interno. |
| POST | `/api/disasters/geology/import` | analista | `capa` (`litologia` o `geomorfologia`) y `bbox`. Uso interno, sin licencia abierta. |
| GET | `/api/disasters/inventories`, `/api/disasters/geology`, `/api/disasters/runs` | lector | Inventarios, capas geológicas y ejecuciones. |
| POST | `/api/disasters/susceptibility/validate` | analista | `dem_id`, `inventory_id`, `geology_ids` (máx. 2), `blocks` (0 = automático por variograma), `n_seeds`, `buffer_m`, `ratio`, `min_dist_m`, `seed`. Validación espacial por proceso. ≈1–2 min. |

## SCIENTIFIC VALIDATION ENGINE (`/api/validation`)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/validation/experiments` | lector | Experimentos con su `estado_cientifico`. |
| POST | `/api/validation/experiments` | analista | Crea el experimento y **congela** su protocolo, sus criterios (`auc_min`, `ic95_inf_min`, `mejora_min`, `referencia`) y su región de prueba (SHA-256). No hay edición. |
| GET | `/api/validation/experiments/{id}` | lector | Detalle con evaluaciones y decisiones. |
| POST | `/api/validation/experiments/{id}/evaluations` | analista | `run_id`, `model_ref` («grupo/modelo») y `partition` (`cv` o `test`). Las métricas se leen de la ejecución; rechaza fuga geográfica y una segunda prueba (sellada). |
| POST | `/api/validation/experiments/{id}/decisions` | admin | Aprobar o rechazar una evaluación `test` que cumple los criterios, con justificación (≥ 20 caracteres). Prohibido para los autores. |
| POST | `/api/validation/experiments/{id}/retire` | admin | Retira el experimento. |

## NEUROTRAINING

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neurotraining/models` | lector | Modelos registrados (con estado, versión, métricas, `task`, `target`, `features`, `trained_with_simulated`, `artifact_sha256`, `validation_evidence`). |
| GET | `/api/neurotraining/models/{id}` | lector | Un modelo (404 si no existe). |
| POST | `/api/neurotraining/models` | analista | Registra un modelo; siempre nace `planificado`. |
| POST | `/api/neurotraining/models/{id}/train` | analista | Entrena o reentrena (sube la versión): `dataset_record_id` (CSV válido de NEURODATA), `task` (`clasificacion`/`regresion`), `target`, `features` (1-30), `algorithm` (`random_forest`, `regresion_logistica`, `ridge`). Deja el modelo `entrenado` (experimental). Espera hasta terminar. 409 si hay otro proceso pesado; 422 por datos inválidos, fuga (objetivo entre las entradas), < 60 filas, clase con < 2 filas, demasiadas clases para la prueba o estado no permitido. Las métricas salen del 25 % reservado del mismo CSV (no independiente) e incluyen `warnings`. |
| POST | `/api/neurotraining/models/{id}/validate` | **admin** | Marca `validado`. Cuerpo: `evidence` (≥ 40 caracteres), `version` y `artifact_sha256` (deben coincidir con el modelo actual). 422 si no está `entrenado`, si la versión o el hash no coinciden (el modelo cambió), si quien valida es quien lo entrenó, si se entrenó con datos simulados o si no supera la línea base (clasificación: accuracy ≤ clase mayoritaria; regresión: MAE ≥ el de la media). |
| POST | `/api/neurotraining/models/{id}/retire` | **admin** | Marca `retirado`. 422 si ya estaba retirado. |
| POST | `/api/neurotraining/models/{id}/predict` | analista | Predice sobre otro CSV (`dataset_record_id`); hasta 5 000 filas; verifica el SHA-256 del artefacto antes de cargarlo. Devuelve predicciones, `model_probability` (clasificación; **probabilidad del modelo NO calibrada**), `uncertainty`, `input_simulated` y `model_trained_with_simulated`; guarda la predicción en `predictions`. |
| GET | `/api/neurotraining/predictions` | lector | Últimas 50 predicciones con su incertidumbre y bandera `is_validated`. |
| GET | `/api/neurotraining/runs` | lector | Últimas 100 ejecuciones (entrenamientos y análisis del módulo ambiental), con resumen de resultados. |

Detalles y reglas del entrenamiento: [ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md).

## Informes

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/reports` | lector | Informes guardados de todos los módulos (Fase 1: los generados desde alertas). |

## NEUROVOICE

La voz (reconocimiento y síntesis) **no pasa por este servidor**: la hace el navegador (ver [ARQUITECTURA_NEUROVOICE.md](ARQUITECTURA_NEUROVOICE.md)). La API solo recibe texto.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/neurovoice/chat` | lector | Envía un mensaje de texto (escrito o transcrito por el navegador); devuelve respuesta, intención y módulo. Crea o continúa una conversación propia; con `conversation_id` usa la **memoria de sesión** (las preguntas de seguimiento como «explícame más» retoman el módulo anterior). Solo consulta y explica con datos reales; no ejecuta acciones. |
| GET | `/api/neurovoice/capabilities` | público | Qué etapas de voz existen y dónde corren: `asr` (Web Speech API de Chrome) y `tts` (`speechSynthesis`) se ejecutan **en el navegador**, `vad` incluido en la Web Speech API, `language_detection` es `null`. La entrada `asr` incluye la nota de privacidad: **el audio se envía a servidores de Google y requiere consentimiento**. También devuelve el intérprete (`reglas_palabras_clave (es)`), las herramientas (`implemented`, `sensitive`) y los idiomas. |
| GET | `/api/neurovoice/conversations` | lector | Conversaciones propias (últimas 50). |
| GET | `/api/neurovoice/conversations/{id}` | lector | Mensajes de una conversación propia (404 si es de otro usuario). |

## Territorios

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/territories` | lector | Lista de territorios. |
| POST | `/api/territories` | analista | Crea un territorio; la geometría GeoJSON se valida. La interfaz aún no usa estos endpoints. |

## Notas

- No existen endpoints para editar o borrar (solo GET y POST; CORS también permite solo esos métodos).
- Cualquier ruta `/api/...` inexistente devuelve 404 en JSON; el resto de rutas devuelve la interfaz web (si `frontend/dist` existe).
