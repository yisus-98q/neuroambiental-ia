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
| `data_records` | `source_id`, `data_type` (csv, geojson, imagen, documento, medicion_manual, raster_ndvi, raster_cambio), `title`, `territory_id`, `latitude`, `longitude`, `bbox` (JSON `[minLon,minLat,maxLon,maxLat]`), `observed_at`, `received_at`, `unit`, `value`, `file_format`, `validation_status` (pendiente, valido, invalido), `validation_messages`, `quality` (sin_evaluar, baja, media, alta), `provenance`, **`is_simulated`**, `file_path`, `file_size`, `sha256`, `extra` (JSON), `created_by` |
| `sensors` | `name`, `kind` (gps, inclinometro, piezometro, pluviometro, estacion_meteorologica, otro), `latitude`, `longitude`, `territory_id`, `is_active` |
| `measurements` | `sensor_id`, `data_record_id`, `variable`, `value`, `unit`, `observed_at`, `is_simulated` |
| `documents` | `data_record_id`, `category`, `module_key`, `notes` |

## Operaciones (`models/operations.py`)

| Tabla | Columnas principales |
|---|---|
| `events` | `event_type`, `title`, `description`, `latitude`, `longitude`, `occurred_at`, `source_name`, `is_simulated`, `created_by` |
| `alerts` | `title`, `description`, `module_key`, `level` (bajo, medio, alto), `alert_kind` (siempre `experimental`), `latitude`, `longitude`, `evidence`, `source_name`, `observed_at`, `uncertainty` (obligatoria), `validation_status` (no_validada, en_revision, validada, descartada), `event_id`, `is_simulated`, `created_by` |
| `alert_followups` | `alert_id`, `note`, `new_status`, `created_by` |
| `ai_models` | `name`, `module_key`, `algorithm`, `version`, `status` (planificado, en_entrenamiento, entrenado, validado, retirado; por API siempre nace `planificado`), `metrics`, `dataset_description`, `artifact_path` |
| `runs` | `run_type`, `module_key`, `model_id`, `status` (esquema: pendiente, ok, error; el módulo ambiental además usa `en_proceso` mientras corre), `started_at`, `finished_at`, `parameters`, `result_summary` |
| `predictions` | `run_id`, `model_id`, `territory_id`, `target`, `value` (JSON), `uncertainty` (obligatoria), `is_validated`, `validation_evidence` |
| `reports` | `title`, `module_key`, `content_md`, `created_by` |
| `conversations` | `user_id`, `language` (es), `title` |
| `conversation_messages` | `conversation_id`, `role` (usuario, asistente), `content`, `meta` (JSON) |

Estado de uso: la API escribe en `users`, `user_sessions`, `audit_logs`, `sources`, `data_records`, `documents`, `measurements` (solo con registro manual que incluya variable y valor), `events`, `alerts`, `alert_followups`, `territories`, `ai_models`, `reports`, `conversations`, `conversation_messages` y, desde la Fase 2, `runs` (un registro por NDVI o detección de cambios, con parámetros y resumen). **Ninguna ruta escribe todavía** en `coordinates`, `sensors` ni `predictions`: existen para fases futuras. La Fase 2 no agregó tablas ni migraciones: los rásters son filas de `data_records`.

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
