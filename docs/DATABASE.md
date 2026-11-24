# Base de datos

Motor: SQLite (`data/neuroambiental.db`, modo WAL, claves foráneas activas). Esquema gestionado con Alembic. Modelos en `backend/app/models/`; migración inicial `backend/migrations/versions/79e40e3a19e0_esquema_inicial.py`. Hay 20 tablas más `alembic_version`.

Convenciones: los `id` son UUID hexadecimal de 32 caracteres (texto); casi todas las tablas tienen `created_at` (UTC con zona horaria). Geometrías: GeoJSON en EPSG:4326 (lon, lat) guardado como JSON.

## Identidad y auditoría (`models/identity.py`)

| Tabla | Columnas principales |
|---|---|
| `roles` | `key` (PK: admin, analista, lector), `name`, `description` |
| `users` | `id`, `username` (único, minúsculas), `full_name`, `password_hash` (`pbkdf2_sha256$iteraciones$sal$hash`), `role_key` (FK roles), `is_active` |
| `user_sessions` | `id`, `token_hash` (SHA-256 del token, único), `user_id`, `expires_at`, `revoked` |
| `audit_logs` | `id`, `at`, `user_id` (nulo si no hubo sesión), `action`, `target_type`, `target_id`, `success`, `details` (JSON) |

## Territorio y fuentes (`models/territory.py`)

| Tabla | Columnas principales |
|---|---|
| `territories` | `name`, `country_code` (PE), `level` (pais, region, provincia, distrito, cuenca, area_personalizada), `parent_id`, `geometry` (JSON GeoJSON), `description` |
| `coordinates` | `territory_id`, `label`, `latitude`, `longitude`, `elevation_m`, `crs` |
| `sources` | `name` (único), `kind` (carga_manual, archivo, sensor, satelite, servicio_publico, muestra_de_prueba), `url`, `license`, `terms_reviewed`, `notes` |

## Datos (`models/data.py`)

| Tabla | Columnas principales |
|---|---|
| `data_records` | `source_id`, `data_type` (csv, geojson, imagen, documento, medicion_manual, raster_ndvi, raster_cambio, raster_dem, imagen_procesada), `title`, `territory_id`, `latitude`, `longitude`, `bbox` (JSON `[minLon,minLat,maxLon,maxLat]`), `observed_at`, `received_at`, `unit`, `value`, `file_format`, `validation_status` (pendiente, valido, invalido), `validation_messages`, `quality` (sin_evaluar, baja, media, alta), `provenance`, **`is_simulated`**, `file_path`, `file_size`, `sha256`, `extra` (JSON), `created_by` |
| `sensors` | `name`, `kind` (gps, inclinometro, piezometro, pluviometro, estacion_meteorologica, otro), `latitude`, `longitude`, `territory_id`, `is_active` |
| `measurements` | `sensor_id`, `data_record_id`, `variable`, `value`, `unit`, `observed_at`, `is_simulated` |
| `documents` | `data_record_id`, `category`, `module_key`, `notes` |

## Biodiversidad (`models/biodiversity.py`; migración 3)

| Tabla | Columnas principales |
|---|---|
| `species` | `nombre_cientifico` (único), `nombre_comun`, `reino`, `clase`, `orden`, `familia`, `categoria_conservacion` (tipo UICN: EX, EW, CR, EN, VU, NT, LC, DD, NE; no evaluada por el sistema), `fuente_taxonomica` (obligatoria), `notas`, `created_by`. **Empieza vacía** |
| `observations` | `species_id` (nulo = «no identificada»; FK con SET NULL), `latitude`, `longitude`, `fecha_observacion`, `observador`, `cantidad` (≥ 1), `metodo` (avistamiento, camara_trampa, huella, audio, muestra, otro), `photo_record_id` (FK a `data_records`), `confianza_identificacion` (baja, media, alta; declarada por el observador), `estado_validacion` (no_validada, validada, descartada), `validation_note`, `validated_by`, `validated_at`, **`is_simulated`** (obligatorio), `territory_id`, `created_by`. Índices por especie, fecha y estado |

## Operaciones (`models/operations.py`)

| Tabla | Columnas principales |
|---|---|
| `events` | `event_type`, `title`, `description`, `latitude`, `longitude`, `occurred_at`, `source_name`, `is_simulated`, `created_by` |
| `alerts` | `title`, `description`, `module_key`, `level` (bajo, medio, alto), `alert_kind` (siempre `experimental`), `latitude`, `longitude`, `evidence`, `source_name`, `observed_at`, `uncertainty` (obligatoria), `validation_status` (no_validada, en_revision, validada, descartada), `event_id`, `is_simulated`, `created_by` |
| `alert_followups` | `alert_id`, `note`, `new_status`, `created_by` |
| `ai_models` | `name`, `module_key`, `algorithm`, `version`, `status` (planificado, entrenado, validado, retirado; `en_entrenamiento` existe en el esquema pero no se usa; siempre nace `planificado`), `metrics` (JSON), `dataset_description`, `artifact_path`. **Fase 3 (migración `efe6f2f7b71a`):** `task` (clasificacion/regresion), `target`, `features` (JSON, defecto `[]`), `dataset_record_id` (FK a `data_records`, SET NULL), `trained_with_simulated` (bool, defecto falso), `artifact_sha256`, `trained_at`, `validation_evidence` (texto, defecto vacío), `validated_by` (FK a `users`, SET NULL) |
| `runs` | `run_type`, `module_key`, `model_id`, `status` (esquema: pendiente, ok, error; el módulo ambiental además usa `en_proceso` mientras corre), `started_at`, `finished_at`, `parameters`, `result_summary` |
| `predictions` | `run_id`, `model_id`, `territory_id`, `target`, `value` (JSON), `uncertainty` (obligatoria), `is_validated`, `validation_evidence` |
| `reports` | `title`, `module_key`, `content_md`, `created_by` |
| `conversations` | `user_id`, `language` (es), `title` |
| `conversation_messages` | `conversation_id`, `role` (usuario, asistente), `content`, `meta` (JSON) |

Estado de uso: la API escribe en `users`, `user_sessions`, `audit_logs`, `sources`, `data_records`, `documents`, `measurements` (solo con registro manual que incluya variable y valor), `events`, `alerts`, `alert_followups`, `territories`, `ai_models`, `reports`, `conversations`, `conversation_messages` y, desde la Fase 2, `runs` (un registro por NDVI o detección de cambios, con parámetros y resumen). Desde la Fase 3 también escribe en `predictions` (una fila por llamada a `/predict`) y en `runs` (entrenamientos, con `run_type = entrenamiento`). Desde la Fase 9 también escribe en `sensors` y `measurements` (NEUROTERRAIN, importación de CSV a series), en `species` y `observations` (biodiversidad) y en `alerts` (alertas experimentales de sensores, solo a petición); los análisis de sitio de NEUROCONSTRUCTION se guardan como `data_records` y `runs`. **Ninguna ruta escribe todavía** en `coordinates`. La Fase 2 no agregó tablas ni migraciones (los rásters son filas de `data_records`).

### Migraciones

1. `79e40e3a19e0_esquema_inicial`: 20 tablas y roles semilla.
2. `efe6f2f7b71a_fase_3_entrenamiento_de_modelos` (depende de la anterior): agrega las columnas nuevas de `ai_models` (modo batch de SQLite) con valores por defecto que cubren los modelos ya registrados. Tiene `downgrade`.
3. `f9ca7def1c5e_biodiversidad` (depende de la anterior): crea las tablas `species` y `observations` con sus claves foráneas, índices y la restricción `cantidad >= 1`.
4. `b3d8e2a41c07_motor_de_validacion_cientifica` (depende de la anterior): **solo añade** tres tablas.
   - `sv_experiments`: pregunta, protocolo, criterios, región de prueba, `protocol_sha256` y estado.
   - `sv_evaluations`: partición `cv` o `test`, ejecución, modelo, métricas copiadas de la ejecución, resultado de los criterios y SHA del protocolo.
   - `sv_approvals`: decisión de un revisor por evaluación (restricción única evaluación + revisor).
   - En la base real se aplicó el 24 nov. 2026, después de una copia en `data/backups/` (excluida de git).

Artefactos de modelos: `data/uploads/models/<id_modelo>/v<versión>.joblib`; `ai_models.artifact_path` es relativo a la carpeta de cargas y `artifact_sha256` guarda su hash.

Registros ráster (Fase 2): `data_type` = `raster_ndvi` o `raster_cambio`, `is_simulated = false`, `bbox` de la malla, `unit` (NDVI o clase), `file_format` `image/tiff`, `quality` `media` (NDVI) o `sin_evaluar` (cambio; fijos, no evaluados), y en `extra`: `kind`, `stats`, `grid`, `scene_id`, `mgrs_tile`, `cloud_cover`, `download` (bytes y peticiones), `preview` (nombre del PNG), `uncertainty` y, en los cambios, `before`, `after` y `validated: false`. La fuente es «Copernicus Sentinel-2 L2A (Earth Search / AWS Open Data)» (`kind` = `satelite`).

## Roles semilla

La migración inserta: `admin` (Administrador), `analista` (Analista: carga datos, registra alertas y modelos) y `lector` (solo consulta). No se crean usuarios automáticamente: el primer administrador se crea con `scripts\crear-admin.bat`.

## Archivos cargados

Los archivos **no** se guardan en SQLite; solo sus metadatos. Ruta en disco: `data/uploads/AAAA/MM/<id>.<ext>` (AAAA/MM = fecha de recepción en UTC; `<id>` = id del registro). `data_records.file_path` es relativa a la carpeta de cargas (`NEURO_UPLOADS_DIR`), y se guarda también el `sha256` y el nombre original en `extra.original_name`. Ni la base ni `data/uploads` se versionan.

Rásters de la Fase 2: `data/uploads/rasters/AAAA/MM/<id>_ndvi.tif` o `<id>_cambio.tif` (GeoTIFF) y un PNG de vista previa con el mismo nombre (`.png`). `file_path` apunta al `.tif`; el `.png` se deduce cambiando la extensión. No se guardan las escenas originales de Sentinel-2, solo el recorte procesado. No tienen `sha256`.

## Regla `is_simulated`

`data_records`, `measurements`, `events` y `alerts` tienen `is_simulated` **sin valor por defecto y no nulo**; la API lo exige explícitamente en cada carga o registro (no se puede omitir). Los datos de `data/samples` se cargan siempre con `is_simulated = true`. La interfaz y el informe de alertas muestran la marca.

## Crear una migración nueva

Tras modificar los modelos, desde la raíz del proyecto (cmd):

```bat
cd backend
set PYTHONPATH=.deps;.
python -m alembic revision --autogenerate -m "descripcion del cambio"
python -m app.cli migrate
```

Revise el archivo generado en `backend/migrations/versions/` antes de aplicarlo. `env.py` usa `render_as_batch=True`, necesario para `ALTER TABLE` en SQLite. Los scripts `iniciar.bat` e `instalar.bat` aplican las migraciones pendientes automáticamente.
