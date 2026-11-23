# NEURO 3D SIMULATION ENGINE (NEURO 3D LAB)

**Estado: parcial, 3 de 5 capacidades.** Funcionan el terreno 3D desde un DEM real, el visor con Three.js y **un escenario demostrativo** de trayectoria de máxima pendiente. **No están implementadas** las capas de NDVI/cambios sobre el terreno ni el comparador de escenarios.

Código: `backend/app/modules/neuro3d/{dem.py, service.py, descriptor.py}`, `backend/app/api/neuro3d.py`, `frontend/src/maps/Terrain3D.tsx`, `frontend/src/pages/Neuro3DLab.tsx`, pruebas `tests/backend/test_neuro3d.py` (8). Three.js 0.187 (autorizado por el usuario).

> Limitación de la verificación: las pruebas de backend pasan y el cálculo se verificó con datos reales, pero **el visor 3D no se probó en un navegador** (el Chrome del equipo dibuja por software y no permite capturas). Su rendimiento real es desconocido.

## Capacidades

| Capacidad | Estado | Detalle |
|---|---|---|
| `terreno_dem` | Implementada | Malla del terreno desde **Copernicus DEM GLO-30** (AWS Open Data, sin cuenta), 1 a 4 teselas de 1°x1°; malla EPSG:4326, resolución por defecto 0,0009° (~100 m), máx. 512 x 512 en el visor; pendiente, estadísticas y clases de pendiente. La malla devuelve `valid` (máscara 0/1) y `valid_pct` (% de celdas con dato) |
| `visor_threejs` | Implementada (sin probar en navegador) | Three.js con render bajo demanda, exageración vertical 1 a 5x, capas de elevación y pendiente, OrbitControls, carga diferida (chunk aparte de ~560 KB, 138 KB gzip, paletas en `terrainPalette.ts`). **Las celdas sin dato se pintan en gris** y la leyenda lo indica |
| `escenarios_simplificados` | Implementada | Trayectoria de **máxima pendiente (D8)** desde un punto, siempre rotulada: «Escenario demostrativo simplificado… no es una simulación geotécnica ni predice un evento». Devuelve `end_reason`: `minimo_local` o **`sin_dato`** si se detiene junto a celdas sin dato. **No hay relleno de depresiones** (limitación): la trayectoria se detiene en el primer mínimo local |
| `capas_3d` | **Pendiente** | NDVI, cambios y riesgo dibujados sobre el terreno |
| `comparador_escenarios` | **Pendiente** | Comparar estado actual y escenarios |

## Datos y atribución

- Fuente: Copernicus DEM GLO-30 (~30 m nominales; por defecto se reduce a ~100 m). Registrada en `sources` y en la procedencia de cada terreno. Atribución obligatoria: «Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, proporcionado bajo COPERNICUS por la UE y la ESA». Los términos deben ser re-verificados por el usuario.
- Reutiliza la lectura remota por rangos con TLS validado, los hosts permitidos y el candado de un proceso pesado a la vez de la Fase 2 (`core/jobs.py`). Área máxima nominal 0,5° x 0,5°, pero con la resolución por defecto (0,0009°) y la malla máxima de 512 px el **tope real es de ~0,46° por lado**. Si falla la descarga del DEM, se borra el GeoTIFF huérfano.
- Se guarda como `DataRecord` de tipo `raster_dem` (con estadísticas de elevación y pendiente en `extra`); el escenario se guarda en `runs` (`module_key = neuro3d`).
- El DEM es de **superficie** (incluye vegetación y edificios) y tiene errores verticales de varios metros.

## Verificación con datos reales (Huaraz / Cordillera Blanca)

| Medida | Valor |
|---|---|
| Malla | 334 x 278 |
| Teselas | 1 |
| Tiempo | 74,8 s |
| Descarga | 10,2 MB en 39 peticiones |
| Elevación | 2720,7 a 6267,7 m (media 4216,7 m) |
| Pendiente | media 22,5°, máx. 69° |
| Clases de pendiente | 0-15° 29 %, 15-25° 32 %, 25-35° 24 %, >35° 15 % |

Es una ejecución puntual en el equipo de pruebas, no un benchmark.

## Endpoints (ver [API.md](API.md))

`GET /api/neuro3d/defaults`, `GET /terrains`, `GET /terrains/{id}/mesh`, `GET /scenarios`, `GET /scenarios/{id}` (lector); `POST /terrain` y `POST /terrains/{id}/flow-path` (analista).

## Reglas para las simulaciones

- Todo escenario se etiqueta **«simulación»**, se distingue de observaciones y alertas y no se llama «predicción» ([DOCUMENTACION_SIMULACIONES.md](DOCUMENTACION_SIMULACIONES.md)).
- La trayectoria D8 **no es un modelo geotécnico ni hidráulico**: ignora el material, el agua, la rugosidad y el volumen. Solo muestra por dónde bajaría algo siguiendo la mayor pendiente del DEM.
- Ninguna simulación es una alerta oficial; para emergencias, INDECI / COEN.

## Riesgos y pendiente

El visor puede ir muy lento sin aceleración gráfica (el equipo dibuja por software); resolución de ~100 m insuficiente para escala de obra; DEM de superficie; capas NDVI/cambios y comparador sin hacer; falta prueba del visor en navegador. Validación según [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md).
