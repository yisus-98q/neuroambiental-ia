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
 | (opera-  | (parcial)| (parcial)| (parcial) |   + 5 módulos especializados en desarrollo
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
| `tests/backend/` | Pruebas pytest (32 pruebas). No hay pruebas automáticas del frontend; solo `tsc` y la compilación. |

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
- **Router por hash (`#/ruta`) sin dependencias.** Funciona al servir archivos estáticos sin configurar reescrituras.
- **MapLibre en chunk separado.** Se carga con `lazy()` solo al abrir una vista con mapa (pesa ~1 MB).
- **Validación con la librería estándar.** CSV, GeoJSON y firmas de PNG/JPG/PDF se validan sin dependencias extra (bajo consumo de RAM).
- **Dependencias Python en `backend\.deps` (no en `.venv`).** Se instalan con `uv pip install --target` (o `pip --target`) y se ejecuta con el Python del sistema y `PYTHONPATH=backend\.deps;backend` (ver `scripts\_entorno.bat`). Motivo: el antivirus del equipo (Avast) elimina los `python.exe` y lanzadores `.exe` recién copiados, lo que rompe un `.venv`. Consecuencia: no se usan los ejecutables `uvicorn.exe`/`alembic.exe`; se invoca `python -m uvicorn` y `python -m alembic`.
- **Archivos `.bat` con finales de línea CRLF.** `.gitattributes` fuerza `*.bat text eol=crlf` (y `*.cmd`); con LF, `cmd.exe` puede fallar de forma errática.

## Dependencias de ejecución

Backend: FastAPI, Uvicorn, SQLAlchemy 2, Alembic, Pydantic 2, python-multipart (pytest y httpx solo en desarrollo). Frontend: React 19, MapLibre GL, TypeScript, Vite. Ver [COSTS.md](COSTS.md).
