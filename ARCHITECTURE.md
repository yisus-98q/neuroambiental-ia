# Arquitectura

## Capas

```
 Usuario (navegador, 127.0.0.1)
        |
        v
 +--------------------------------------------+
 | Interfaz web (React + TypeScript + Vite)   |  frontend/  -> compilado a frontend/dist
 | router por hash, MapLibre (chunk aparte)   |
 +--------------------------------------------+
        | HTTP JSON  (/api/...)  + token Bearer
        v
 +--------------------------------------------+
 | API central (FastAPI, un solo proceso)     |  backend/app/main.py, backend/app/api/
 | autenticación, roles, auditoría, cabeceras |
 +--------------------------------------------+
        |
        v
 +--------------------------------------------+
 | NEUROCORE IA                               |  backend/app/neurocore/
 | registro de módulos + intérprete por reglas|
 +--------------------------------------------+
        |
        v
 +----------+----------+----------+----------+
 | NEURODATA| Alertas  | Entrenam.| NEUROVOICE|   backend/app/neurodata, backend/app/modules/*
 | (opera-  | (parcial)| (parcial)| (parcial) |   + ambiental (parcial) y 4 módulos en desarrollo
 |  tivo)   |          |          |           |
 +----------+----------+----------+----------+
        |
        v
 +--------------------------------------------+
 | SQLite (data/neuroambiental.db) + Alembic  |  archivos cargados: data/uploads/
 +--------------------------------------------+
        |
        v
 Visualización: mapa territorial (MapLibre; mapa base local Natural Earth, OpenStreetMap opcional), tablas, informes Markdown
```

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| `frontend/` | Interfaz web. `src/pages`, `src/components`, `src/maps`, `src/services` (cliente HTTP, router, tipos). |
| `backend/app/` | API y lógica: `api/` (routers), `core/` (config, seguridad, auditoría), `database/`, `models/`, `schemas/`, `neurocore/`, `neurodata/`, `modules/*`. |
| `backend/migrations/` | Migraciones Alembic. |
| `data/` | Base SQLite (no versionada), `uploads/` (archivos cargados, no versionados) y `samples/` (muestras simuladas). |
| `ai/` | `datasets/`, `evaluation/`, `models/`: carpetas reservadas; hoy no hay modelos ni conjuntos de datos de entrenamiento. |
| `scripts/` | Archivos `.bat` de instalación, arranque y verificación. |
| `tests/backend/` | Pruebas pytest (105 pruebas). No hay pruebas automáticas del frontend; solo `tsc` y la compilación. |

Separación: el **frontend** nunca toca la base de datos (solo habla con `/api`); el **backend** guarda **metadatos** en SQLite y los **archivos** en disco (`data/uploads`); los **modelos de IA** irían en `ai/models` (vacío hoy).

## Contrato ModuleDescriptor

Todo módulo declara un `ModuleDescriptor` (`backend/app/neurocore/base.py`) con: `key`, `name`, `version`, `description`, `capabilities` (lista de `{key, description, implemented}`), `dependencies`, `inputs`, `outputs`, `possible_errors`, `limitations`, `keywords` (para el intérprete) y `api_prefix`.

El **estado no se declara: se deriva** de las capacidades:

- 0 capacidades implementadas: `en_desarrollo`
- algunas: `parcial`
- todas: `operativo`

Así es imposible que un módulo figure como operativo sin que sus capacidades lo estén. La API expone el contrato en `GET /api/neurocore/modules`; la interfaz lo muestra sin adornos (capacidades «Implementada» / «Pendiente», limitaciones).

## Registro y dependencias circulares

`ModuleRegistry.register()` (`neurocore/registry.py`) rechaza (a) claves duplicadas y (b) dependencias de módulos **aún no registrados** (se permite `neurocore`). El orden de registro es fijo en `build_registry()`:

`neurodata, alerts, environmental, terrain, biodiversity, mining, disasters, construction, neurotraining, neurovoice`

Como un módulo solo puede depender de los ya registrados, **un ciclo es imposible por construcción**. Hay una prueba que lo verifica (`test_registry_rejects_unknown_dependency_and_duplicates`).

## Intérprete por reglas (sin LLM)

`neurocore.registry.interpret()` normaliza el texto (minúsculas, sin tildes), lo parte en palabras y cuenta coincidencias con las `keywords` de cada módulo. El módulo con más coincidencias gana (empates: `alerts`, luego `neurodata`). Palabras como «estado/módulos» devuelven el estado de módulos; «cuántos/total/resumen» marcan una consulta de conteo. NEUROVOICE construye su respuesta solo con datos reales de la base y con el contrato del módulo. No hay modelo de lenguaje, ni entrenamiento, ni red.

## Decisiones técnicas

- **SQLite + Alembic (`render_as_batch=True`).** Sin servidor de base de datos que consuma RAM. `render_as_batch` permite `ALTER TABLE` en SQLite. Se activan `PRAGMA foreign_keys=ON` y `journal_mode=WAL`.
- **Migración futura a PostgreSQL/PostGIS.** El modelo usa SQLAlchemy y la URL se cambia con `NEURO_DATABASE_URL`. Lo que cambiaría: `territories.geometry` (hoy JSON GeoJSON EPSG:4326) pasaría a columna `geometry` de PostGIS con índice espacial; `data_records.bbox` también; los `JSON` pasarían a `JSONB`; habría que revisar las migraciones (hoy escritas para SQLite en modo batch). Aún no está probado contra PostgreSQL.
- **Un solo proceso uvicorn sirve `frontend/dist`.** Ahorra un servidor Node y su RAM. FastAPI monta `/assets` y devuelve `index.html` para cualquier ruta que no sea de la API. En desarrollo, Vite (5173) hace proxy de `/api` al 8000.
- **Un solo worker obligatorio.** El candado de «un proceso pesado a la vez» (`core/jobs.py`) y el bloqueo de intentos de login son por proceso (memoria). Con varios workers de uvicorn no se compartirían y se podrían ejecutar dos análisis pesados a la vez. `scripts\iniciar.bat` ya usa `--workers 1`; no cambiarlo sin mover ese estado a la base de datos.
- **Frontend con carga diferida.** Three.js va en un chunk aparte (Terrain3D ~560 KB, 138 KB gzip) y MapLibre en otro; el bundle principal pesa ~315 KB (92 KB gzip). Las paletas del terreno están en `frontend/src/maps/terrainPalette.ts`.
- **Router por hash (`#/ruta`) sin dependencias.** Funciona al servir archivos estáticos sin configurar reescrituras.
- **MapLibre en chunk separado.** Se carga con `lazy()` solo al abrir una vista con mapa (pesa ~1 MB).
- **Validación con la librería estándar.** CSV, GeoJSON y firmas de PNG/JPG/PDF se validan sin dependencias extra (bajo consumo de RAM). Desde la Fase 2 el proyecto sí depende de numpy y rasterio, pero solo el módulo ambiental los usa.
- **Dependencias Python en `backend\.deps` (no en `.venv`).** Se instalan con `uv pip install --target` (o `pip --target`) y se ejecuta con el Python del sistema y `PYTHONPATH=backend\.deps;backend` (ver `scripts\_entorno.bat`). Motivo: el antivirus del equipo (Avast) elimina los `python.exe` y lanzadores `.exe` recién copiados, lo que rompe un `.venv`. Consecuencia: no se usan los ejecutables `uvicorn.exe`/`alembic.exe`; se invoca `python -m uvicorn` y `python -m alembic`.
- **Verificación con `python scripts\comprobar.py` (no `.bat`).** El antivirus del equipo eliminó tres veces el script de verificación en formato `.bat` (`pruebas.bat`, `verificar.bat` y `comprobar.bat`; los que lanzan pytest). Se reemplazó por un script de Python, que sobrevivió a dos ejecuciones completas. Hace lo mismo: pytest (105 pruebas) y `npm run build` (tsc + vite). Es otro efecto de la misma causa que motivó `backend\.deps`: el antivirus es hostil con los ejecutables y lanzadores recién creados. Los demás `.bat` (instalar, iniciar, etc.) no han sido eliminados hasta ahora.
- **Archivos `.bat` con finales de línea CRLF.** `.gitattributes` fuerza `*.bat text eol=crlf` (y `*.cmd`); con LF, `cmd.exe` puede fallar de forma errática.

## Fase 2: módulo ambiental (Sentinel-2, NDVI, cambios)

Código en `backend/app/modules/environmental/` (`remote.py`, `raster.py`, `service.py`, `descriptor.py`) y `backend/app/api/environmental.py`. Flujo:

```
buscar escenas (STAC) -> NDVI de una escena (recorte) -> NDVI de otra fecha -> cambio (después - antes) -> capa en el mapa
```

- **Lectura remota (`remote.py`).** Catálogo STAC Earth Search y COG públicos en AWS. Solo se descarga el recorte. El `curl` interno de GDAL fallaba con «schannel: the certificate chain is incomplete» por la inspección HTTPS del antivirus; **no se desactivó TLS**. En su lugar, `HttpsOpener` (un `FileContainer` de rasterio) hace las peticiones HTTP por rangos desde Python (`urllib`), que valida TLS con el almacén de certificados de Windows. Mantiene una caché de bloques de 256 KB compartida por URL (hasta 48 bloques, ~12 MB por archivo), solo permite los hosts `earth-search.aws.element84.com` y `sentinel-cogs.s3.us-west-2.amazonaws.com` (protección contra SSRF; el identificador de escena se valida con una expresión regular) y responde «no existe» a los archivos auxiliares (`.aux.xml`, `.msk`) sin pedirlos.
- **Procesamiento de bajo consumo (`raster.py`).** Malla común EPSG:4326: área máx. 0,5° x 0,5°, resolución por defecto 0,0003° (~33 m), máx. 1600 x 1600 px. Se lee solo la ventana del área y a resolución reducida (vistas generales del COG), se reproyecta, y el NDVI y la detección de cambios se calculan por bloques de 256 filas.
- **Desplazamiento radiométrico.** `raster.choose_offset` decide con los datos si aplicar el desplazamiento -0,1 declarado por los metadatos (ver [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)). Los metadatos declaran -0,1, pero con datos reales de Huaraz aplicarlo dejaba reflectancia roja negativa (-0,026) y saturaba el NDVI en 1,0. Si más del 20 % de los píxeles de superficie (SCL 4, 5, 6) quedan con reflectancia ≤ 0, se concluye que los COG ya vienen corregidos y no se aplica. La decisión se guarda en `stats.radiometric_offset` y en la procedencia. Es una heurística, no una garantía.
- **NDVI.** `(NIR - Rojo) / (NIR + Rojo)` con máscara SCL (válidas 4, 5, 6, 7, 11) y exclusión de reflectancias ≤ 0. Salidas: GeoTIFF int16 (NDVI x 10000) y PNG RGBA de vista previa en `data/uploads/rasters/AAAA/MM/`.
- **Cambios.** Diferencia NDVI después - antes; clase 1 = disminución, 2 = aumento, con umbral configurable (0,05 a 0,8; 0,2 por defecto). Áreas en km² corregidas por latitud. Los dos NDVI deben tener la misma área y resolución (si no, 422); se ordenan por fecha automáticamente. El resultado se marca «sin validar» y lleva la advertencia: un cambio de NDVI **no confirma** deforestación ni daño.
- **Un procesamiento a la vez.** Un candado en memoria; una segunda petición recibe 409. Cada análisis queda en la tabla `runs` (tipos `ndvi` y `deteccion_cambios`) y en la auditoría. La petición HTTP espera hasta terminar (medido: ~2 min por NDVI, pico de memoria ~170 MB de working set); no hay segundo plano.
- **Interfaz.** Panel en «Predicción ambiental» (`EnvironmentalPanel.tsx`) y sección «Rásters Sentinel-2» en el Mapa. El mapa muestra los rásters como capas de imagen de MapLibre ubicadas con el `bbox` del registro; las vistas previas se descargan con la sesión (`GET /api/neurodata/records/{id}/preview`) y se convierten en URL temporales del navegador. Por defecto solo se muestra el ráster más reciente.
- **Pruebas.** `tests/backend/test_environmental.py`: sin red, con rásters sintéticos UTM 18S y un servidor de rangos falso.

## Dependencias de ejecución

Backend: FastAPI, Uvicorn, SQLAlchemy 2, Alembic, Pydantic 2, python-multipart, numpy 2.5.5 y rasterio 1.5.2 con GDAL 3.12.2 (pytest y httpx solo en desarrollo). Frontend: React 19, MapLibre GL, TypeScript, Vite. Ver [COSTS.md](COSTS.md).
