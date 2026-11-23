# NEUROAMBIENTAL IA

Plataforma local de inteligencia ambiental territorial para Perú. La **Fase 1** es una base técnica sólida y honesta: recibe y valida datos, los muestra en un mapa, registra alertas experimentales con seguimiento, y declara con transparencia qué módulos funcionan y cuáles aún no. La **Fase 2** agrega el primer análisis con datos reales: NDVI y detección de cambios con imágenes Sentinel-2 (Copernicus) de un área acotada. La **Fase 3** agrega el **NEURAL TRAINING ENGINE**: entrenamiento y evaluación de modelos ligeros de scikit-learn sobre CSV, con validación humana obligatoria. También se definió la arquitectura de integración avanzada (15 módulos registrados); la mayoría son solo contratos en desarrollo.

> **Aviso importante.** Las alertas de esta plataforma son **experimentales**. No son emergencias oficiales ni sustituyen a INDECI, COEN, SENAMHI u otras autoridades. Ante un peligro real, siga las indicaciones oficiales.

## Estado real (Fases 1 a 3)

| Área | Estado |
|---|---|
| NEURODATA ENGINE (carga y validación de CSV, GeoJSON, PNG/JPG, PDF; registro manual; procedencia; capas para el mapa) | Operativo (7/7 capacidades) |
| Alertas y Prevención (alertas experimentales, eventos, seguimiento, informe Markdown) | Parcial (5/6): falta generar alertas automáticamente desde modelos |
| NEURAL TRAINING ENGINE / NEUROTRAINING (registro de modelos, entrenamiento ligero con scikit-learn sobre CSV de NEURODATA, métricas solo sobre datos de prueba, artefactos con SHA-256, validación por administrador, predicción experimental) | Parcial (7/10): faltan redes neuronales (PyTorch), datasets de imágenes y reanudar entrenamientos |
| NEURO PREDICTION ENGINE (registro de predicciones con incertidumbre) | Parcial (1/4): sin separación de tipos de salida, probabilidad calibrada ni horizonte temporal |
| NEUROVOICE IA (chat de texto en español por palabras clave, con conteos reales) | Parcial (3/7): sin voz, sin modelo de lenguaje, sin otros idiomas |
| Construcción (solo carga de documentos vía NEURODATA) | Parcial (1/6): no analiza proyectos |
| Predicción ambiental (Sentinel-2: búsqueda de escenas, NDVI con máscara de nubes, comparación de dos fechas, detección de cambios, capas en el mapa) | Parcial (5/9): faltan series temporales con muchas fechas, clasificación de cobertura, escenarios futuros y Sentinel-1 |
| NEUROVISION (OpenCV: Canny, CLAHE, Otsu + contornos, índice de verdor ExG, características; comparación de dos fotos con ORB + RANSAC) | Parcial (3/6): procesamiento **determinista**, sin confianza estadística; **sin clasificación ni detección de grietas** (requieren un modelo entrenado). El panel no se probó en navegador ([detalle](docs/DOCUMENTACION_OPENCV.md)) |
| NEURO 3D LAB (terreno 3D desde Copernicus DEM GLO-30, visor Three.js, trayectoria demostrativa de máxima pendiente) | Parcial (3/5): sin capas NDVI/cambios sobre el terreno ni comparador de escenarios. El escenario **no es una simulación geotécnica**. El visor no se probó en navegador ([detalle](docs/ARQUITECTURA_NEURO_3D.md)) |
| NEUROMINING, NEUROGEO, NEUROTERRAIN, NEURODISASTER, NEUROINDUSTRIAL, Fauna y flora | En desarrollo (0 capacidades implementadas; solo existe el contrato del módulo) |
| PyTorch (redes neuronales), voz (reconocimiento y síntesis) | **No instalados / no implementados**; requieren autorización |
| Modelos de IA | El mecanismo para entrenar y validar modelos ligeros funciona, pero **no hay ningún modelo entrenado con datos reales ni validado**. El NDVI y la detección de cambios son cálculos determinísticos, no aprendizaje automático |
| Fuentes de datos reales integradas | **Dos**: Sentinel-2 L2A (imágenes) y Copernicus DEM GLO-30 (elevación), ambas vía AWS Open Data, solo recortes pequeños y bajo demanda. Ningún inventario de eventos (INGEMMET, CENEPRED, NASA COOLR) está descargado: sus términos no se pudieron confirmar. Además: muestras simuladas y un mapa base local de países (Natural Earth); OpenStreetMap es una capa opcional, desactivada por defecto |

Los resultados de cambio (disminución/aumento de NDVI) quedan marcados **«sin validar»**: un cambio de NDVI **no confirma** deforestación ni daño ambiental.

El estado de cada módulo **se calcula** a partir de sus capacidades implementadas; no se escribe a mano (ver [ARCHITECTURE.md](ARCHITECTURE.md)).

## Requisitos

- Windows 10 u 11.
- Python 3.12 o superior (probado con 3.14.7), disponible como `python` en el PATH.
- Node.js 24 y npm.
- Opcional: `uv` (si está instalado, `instalar.bat` lo usa para instalar dependencias de Python más rápido).
- Pensado para equipos modestos (4 GB de RAM). Ver [docs/AI_MODELS.md](docs/AI_MODELS.md).
- Internet solo para el análisis Sentinel-2 (buscar escenas y descargar recortes de ~15-20 MB por fecha). El resto funciona sin conexión. No hacen falta cuentas ni claves.
- Dependencias nuevas de las Fases 2 y 3: numpy, rasterio (incluye GDAL) y scikit-learn (con scipy y joblib), y opencv-python-headless, instaladas por `scripts\instalar.bat` en `backend\.deps` (hoy ~462 MB). El frontend añade Three.js.

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

Abre <http://127.0.0.1:8000>. Es **un solo proceso** que sirve la API y el frontend compilado (ahorra memoria). La documentación interactiva de la API está en <http://127.0.0.1:8000/docs>. Solo escucha en `127.0.0.1` (uso local). **Debe correr con un solo worker** (`iniciar.bat` ya usa `--workers 1`): el candado de «un proceso pesado a la vez» y el bloqueo de intentos de login están en la memoria de cada proceso y no se comparten entre varios workers.

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
python scripts\comprobar.py
```

Ejecútelo desde la carpeta del proyecto. Corre las pruebas del backend (pytest, 73 pruebas), la verificación de tipos de TypeScript y la compilación del frontend (`npm run build`). Es un script de Python y no un `.bat` porque el antivirus del equipo borró tres veces el `.bat` de verificación (ver [ARCHITECTURE.md](ARCHITECTURE.md)).

## Configuración

Todo es opcional. Copie `.env.example` como `.env` para cambiar límites de carga, duración de sesión (12 h por defecto), base de datos o carpeta de archivos. El archivo `.env` nunca se versiona.

## Consumo de recursos

Mediciones reales en Windows 10, 4 GB de RAM, Intel i5-2410M:

| Concepto | Valor |
|---|---|
| Servidor en marcha (python + uvicorn, 1 worker, API + frontend compilado) | ~91 MB de memoria (working set), ~76 MB de memoria privada |
| Disco: `backend\.deps` | ~462 MB (eran 47 MB en la Fase 1; rasterio incluye GDAL, scikit-learn trae scipy y se añadió OpenCV; eran 347 MB antes de OpenCV) |
| Disco: `frontend\node_modules` | 114 MB |
| Disco: código + datos de muestra | ~2 MB |
| Frontend compilado: JS principal | 273 KB (81 KB gzip) |
| Frontend compilado: MapLibre (chunk separado) | 1,09 MB (299 KB gzip); solo se descarga al abrir un mapa |
| Pruebas de backend | pasan en ~10 s (medido con 30-32 pruebas; hoy son 73) |

Son mediciones puntuales en un solo equipo, no garantías. El navegador consume memoria aparte.

### Análisis Sentinel-2 (Fase 2), mediciones reales

Área por defecto (Huaraz / Cordillera Blanca), resolución 0,0003° (malla de 1000 x 834 px). Escenas `S2A_18LTQ_20190802_1_L2A` y `S2B_18LTQ_20250716_0_L2A`.

| Concepto | Valor medido |
|---|---|
| Tiempo por NDVI | ~123-126 s |
| Descarga por NDVI | ~17 MB en ~65 peticiones por rangos |
| Detección de cambios | menos de 1 s |
| Memoria del servidor durante el proceso | pico de working set 166-171 MB; ~224 MB de memoria privada |
| Memoria del servidor en reposo | ~100 MB |
| Píxeles válidos / nubes y sombras enmascaradas / nieve | ~93 % / ~7 % / ~13,5 % |
| Desplazamiento radiométrico | **no aplicado** en ambas escenas (con él, 44 % y 62 % de la superficie quedaba con reflectancia ≤ 0) |

Resultados de ejemplo: NDVI medio 0,244 (2019-08-02) y 0,289 (2025-07-16). Cambio 2019 → 2025 con umbral 0,2: área comparable 841,7 km² (91,8 %), disminución de NDVI 2,56 km² (0,30 %), aumento 13,64 km² (1,62 %).

> **Advertencia.** Esas cifras de cambio comparan agosto de 2019 con julio de 2025, con sensores distintos (Sentinel-2A frente a 2B) y lluvias distintas entre años. **No se han validado en campo**: no deben leerse como deforestación ni como recuperación confirmada.

### Rendimiento del mapa

En el equipo de pruebas, Chrome usaba «Microsoft Basic Render Driver» (falta el driver de la GPU Intel HD 3000, así que el navegador dibuja por software). Con poca RAM libre el mapa puede ir muy lento. Recomendación: instalar el driver de gráficos de Intel (desde Windows Update o el fabricante) y cerrar otras aplicaciones pesadas.

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

Arquitectura de integración avanzada (la mayor parte es diseño pendiente; cada documento indica qué está implementado y qué no):

- [docs/ARQUITECTURA_NEURAL_TRAINING.md](docs/ARQUITECTURA_NEURAL_TRAINING.md): entrenamiento, evaluación, ciclo de vida de modelos (implementado para modelos ligeros).
- [docs/DOCUMENTACION_OPENCV.md](docs/DOCUMENTACION_OPENCV.md): visión por computador (no implementado).
- [docs/DOCUMENTACION_DATASETS.md](docs/DOCUMENTACION_DATASETS.md): datasets.
- [docs/ARQUITECTURA_NEURO_3D.md](docs/ARQUITECTURA_NEURO_3D.md): simulación 3D (no implementado).
- [docs/DOCUMENTACION_SIMULACIONES.md](docs/DOCUMENTACION_SIMULACIONES.md): simulaciones y tipos de información.
- [docs/ARQUITECTURA_NEUROVOICE.md](docs/ARQUITECTURA_NEUROVOICE.md): voz (solo contratos).
- [docs/CATALOGO_MODELOS_IA.md](docs/CATALOGO_MODELOS_IA.md): catálogo de modelos.
- [docs/INTEGRACION_NEUROCORE.md](docs/INTEGRACION_NEUROCORE.md): registro de los 15 módulos.
- [docs/PLAN_DE_VALIDACION.md](docs/PLAN_DE_VALIDACION.md): verificación y validación.
- [docs/MANUAL_DE_INSTALACION.md](docs/MANUAL_DE_INSTALACION.md): instalación y solución de problemas.
