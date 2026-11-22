# NEUROAMBIENTAL IA

Plataforma local de inteligencia ambiental territorial para Perú. En la **Fase 1** es una base técnica sólida y honesta: recibe y valida datos, los muestra en un mapa, registra alertas experimentales con seguimiento, y declara con transparencia qué módulos funcionan y cuáles aún no.

> **Aviso importante.** Las alertas de esta plataforma son **experimentales**. No son emergencias oficiales ni sustituyen a INDECI, COEN, SENAMHI u otras autoridades. Ante un peligro real, siga las indicaciones oficiales.

## Estado real de la Fase 1

| Área | Estado |
|---|---|
| NEURODATA ENGINE (carga y validación de CSV, GeoJSON, PNG/JPG, PDF; registro manual; procedencia; capas para el mapa) | Operativo (7/7 capacidades) |
| Alertas y Prevención (alertas experimentales, eventos, seguimiento, informe Markdown) | Parcial (5/6): falta generar alertas automáticamente desde modelos |
| NEUROTRAINING (registro de modelos como «planificado», consulta de ejecuciones) | Parcial (2/4): no entrena ni evalúa nada |
| NEUROVOICE IA (chat de texto en español por palabras clave, con conteos reales) | Parcial (3/7): sin voz, sin modelo de lenguaje, sin otros idiomas |
| Construcción (solo carga de documentos vía NEURODATA) | Parcial (1/6): no analiza proyectos |
| Predicción ambiental, Minería, Biodiversidad, Movimientos territoriales, Catástrofes | En desarrollo (0 capacidades implementadas; solo existe el contrato del módulo) |
| Modelos de IA entrenados | **Ninguno** |
| Fuentes de datos reales integradas | **Ninguna** (solo muestras simuladas y un mapa base local de países derivado de Natural Earth; OpenStreetMap es una capa opcional, desactivada por defecto) |

El estado de cada módulo **se calcula** a partir de sus capacidades implementadas; no se escribe a mano (ver [ARCHITECTURE.md](ARCHITECTURE.md)).

## Requisitos

- Windows 10 u 11.
- Python 3.12 o superior (probado con 3.14.7), disponible como `python` en el PATH.
- Node.js 24 y npm.
- Opcional: `uv` (si está instalado, `instalar.bat` lo usa para instalar dependencias de Python más rápido).
- Pensado para equipos modestos (4 GB de RAM). Ver [docs/AI_MODELS.md](docs/AI_MODELS.md).

## Instalación

Desde la carpeta del proyecto:

```bat
scripts\instalar.bat
```

Hace tres cosas: instala las dependencias de Python en `backend\.deps`, aplica las migraciones a la base SQLite (`data\neuroambiental.db`) e instala y compila el frontend (`frontend\dist`).

## Crear el administrador

```bat
scripts\crear-admin.bat            (usuario "admin" por defecto)
scripts\crear-admin.bat mi_usuario
```

Pide la contraseña **sin mostrarla** y la repite para confirmar. Debe tener **mínimo 10 caracteres** y combinar letras con números o símbolos. Si el usuario ya existe, no lo modifica.

## Cargar muestras simuladas (opcional)

```bat
scripts\cargar-muestras.bat        (usa el usuario "admin"; admite otro nombre como argumento)
```

Carga `data\samples\mediciones_simuladas.csv` y `data\samples\area_estudio_simulada.geojson`. Quedan marcadas siempre como **simuladas** (`is_simulated = true`) con título «[MUESTRA] …». No son mediciones reales. Si ya están cargadas, no se duplican.

## Iniciar

```bat
scripts\iniciar.bat
```

Abre <http://127.0.0.1:8000>. Es **un solo proceso** que sirve la API y el frontend compilado (ahorra memoria). La documentación interactiva de la API está en <http://127.0.0.1:8000/docs>. Solo escucha en `127.0.0.1` (uso local).

## Modo desarrollo

```bat
scripts\iniciar-desarrollo.bat
```

Abre dos ventanas: backend en el puerto 8000 y Vite (recarga en caliente) en <http://localhost:5173>. Consume más memoria que el modo normal.

## Detener

- Ctrl+C en la ventana donde corre `iniciar.bat`, o
- `scripts\detener.bat`, que cierra **cualquier proceso** que escuche en los puertos 8000 y 5173.

## Verificar

```bat
scripts\comprobar.bat
```

Ejecuta las pruebas del backend (pytest), la verificación de tipos de TypeScript y la compilación del frontend.

## Configuración

Todo es opcional. Copie `.env.example` como `.env` para cambiar límites de carga, duración de sesión (12 h por defecto), base de datos o carpeta de archivos. El archivo `.env` nunca se versiona.

## Consumo de recursos

Mediciones reales en Windows 10, 4 GB de RAM, Intel i5-2410M:

| Concepto | Valor |
|---|---|
| Servidor en marcha (python + uvicorn, 1 worker, API + frontend compilado) | ~91 MB de memoria (working set), ~76 MB de memoria privada |
| Disco: `backend\.deps` | 47 MB |
| Disco: `frontend\node_modules` | 114 MB |
| Disco: código + datos de muestra | ~2 MB |
| Frontend compilado: JS principal | 273 KB (81 KB gzip) |
| Frontend compilado: MapLibre (chunk separado) | 1,09 MB (299 KB gzip); solo se descarga al abrir un mapa |
| Pruebas: 32 de backend | pasan en ~10 s |

Son mediciones puntuales en un solo equipo, no garantías. El navegador consume memoria aparte.

## Documentación

- [ARCHITECTURE.md](ARCHITECTURE.md): capas, contrato de módulos y decisiones técnicas.
- [COSTS.md](COSTS.md): licencias y costos (actual: 0 USD) y costos futuros posibles.
- [ROADMAP.md](ROADMAP.md): qué está hecho y qué se propone después.
- [docs/DATABASE.md](docs/DATABASE.md): tablas, migraciones y almacenamiento de archivos.
- [docs/API.md](docs/API.md): endpoints reales y roles.
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md): fuentes actuales y candidatas.
- [docs/AI_MODELS.md](docs/AI_MODELS.md): estado honesto de la IA.
- [docs/SECURITY.md](docs/SECURITY.md): medidas de seguridad y limitaciones conocidas.
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md): guía para usuarios no técnicos.
