# Hoja de ruta

Las Fases 1, 2 y 3 describen lo ya construido (con lo pendiente de cada una); lo de la Fase 4 en adelante, y lo marcado como pendiente, son **propuestas**, no compromisos ni funciones existentes. Las cifras de RAM son estimaciones a validar con mediciones en el equipo objetivo (4 GB).

## Fase 1 (hecha)

- API central FastAPI con autenticación por token, roles (lector, analista, admin) y auditoría.
- Base SQLite con 20 tablas y migración inicial Alembic; roles semilla.
- NEUROCORE: registro de 10 módulos con contrato `ModuleDescriptor`, estado derivado, intérprete por palabras clave.
- NEURODATA: carga y validación de CSV, GeoJSON, PNG/JPG y PDF; registro manual; procedencia, calidad y marca obligatoria `is_simulated`; capas GeoJSON para el mapa.
- Alertas experimentales con ubicación, evidencia, fuente, incertidumbre, estados de validación, seguimiento e informe Markdown; registro de eventos.
- NEUROTRAINING: registro de modelos (siempre «planificado») y consulta de ejecuciones.
- NEUROVOICE: chat de texto en español con intérprete por reglas e historial por usuario (en la Fase 7 se agregó la voz en el navegador).
- Interfaz React con 15 secciones de menú, mapa territorial (MapLibre con mapa base local Natural Earth; OpenStreetMap opcional), panel de inicio con cifras reales.
- Scripts `.bat` de instalación, arranque, desarrollo, parada y verificación; pruebas de backend (hoy 146 en total, incluidas las de las Fases 2, 3, 6, 7, 8 y 9 y las de NEUROVISION y NEURO 3D LAB).
- Muestras simuladas en `data/samples`.

Pendiente dentro de lo ya construido: alertas automáticas, recuperación de contraseña, HTTPS, pruebas automáticas del frontend, informes más allá de alertas.

## Fase 2 (hecha en lo implementado): Sentinel-2, NDVI y cambios

Módulo ambiental: **parcial, 5 de 9 capacidades**.

Hecho:
- Búsqueda de escenas Sentinel-2 L2A en el catálogo STAC Earth Search (Element 84) y lectura de **recortes** de los COG públicos en AWS Open Data. Sin cuenta ni claves, gratis.
- Área máxima 0,5° x 0,5°, resolución por defecto ~33 m (0,0003°), malla máxima 1600 x 1600 px; lectura solo de la ventana y a resolución reducida; cálculo por bloques de 256 filas.
- NDVI con máscara de nubes y sombras (SCL) y exclusión de reflectancias ≤ 0; GeoTIFF int16 (NDVI x 10000) y PNG de vista previa.
- Decisión automática sobre el desplazamiento radiométrico (ver [ARCHITECTURE.md](ARCHITECTURE.md)).
- Comparación de dos fechas y detección de cambios (disminución / aumento con umbral configurable), con áreas en km² y advertencia de incertidumbre; resultados «sin validar».
- Capas raster en el mapa, panel en «Predicción ambiental», historial de análisis en la tabla `runs`.
- Un solo procesamiento a la vez (409 si hay otro).
- Atribución «Contiene datos modificados de Copernicus Sentinel [año]» en la procedencia de cada NDVI.

Pendiente de la Fase 2:

| Elemento | RAM estimada | Riesgos |
|---|---|---|
| Series temporales con muchas fechas | Baja a media (un NDVI a la vez) | Tiempo de descarga acumulado; nubosidad andina frecuente |
| Sentinel-1 (radar) | Media | Procesamiento más complejo; sin pruebas aún |
| Procesamiento en segundo plano con avance (hoy la petición HTTP espera ~2 min por NDVI) | Baja | Más complejidad; hoy no hay cola ni procesos en segundo plano |
| Integración de fuentes públicas peruanas (SENAMHI, INGEMMET, MINAM, etc.) | Baja | Licencias y términos por verificar; ver [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) |
| Validación de los cambios detectados (campo o imágenes de alta resolución) | — | Sin validación, los cambios no deben interpretarse como deforestación |

Riesgos conocidos de lo hecho: nieve, sombras de relieve y estacionalidad alteran el NDVI en los Andes; la resolución se reduce a ~33 m; los términos de uso de la fuente deben ser re-verificados por el usuario.

## Fase 3 (hecha en lo implementado): NEURAL TRAINING ENGINE y arquitectura de integración

Hecho (detalle en [docs/ARQUITECTURA_NEURAL_TRAINING.md](docs/ARQUITECTURA_NEURAL_TRAINING.md)):
- Entrenamiento y evaluación de modelos ligeros de scikit-learn (random forest, regresión logística, ridge) sobre CSV de NEURODATA, `n_jobs=1`; métricas solo sobre datos de prueba con línea base; artefactos `.joblib` con SHA-256 verificado antes de cargar.
- Ciclo de vida planificado → entrenado (experimental) → validado (solo admin, con evidencia, nunca con datos simulados) → retirado; versiones; predicción experimental sobre CSV nuevos.
- Candado común de un proceso pesado a la vez (raster y entrenamiento).
- Interfaz NEURAL TRAINING CENTER; migración 2 de la base (columnas nuevas de `ai_models`); la validación de un modelo exige superar la línea base, un administrador distinto de quien entrenó y que coincidan versión y hash; mínimo 60 filas y evaluación sobre filas reservadas del mismo CSV (no independiente); 146 pruebas de backend en total (cifra actual).
- NEUROVISION (OpenCV, parcial 3/6) y NEURO 3D LAB (Three.js, escenarios simplificados): ver el mapa de fases abajo.
- Arquitectura de integración: 15 módulos registrados con `codename` y grupo; menú agrupado; contratos de NEUROVOICE y `GET /api/neurovoice/capabilities`.

Pendiente de la Fase 3: ningún modelo real entrenado ni validado; alertas automáticas desde modelos; susceptibilidad a huaycos/deslizamientos (requiere inventarios de eventos reales: se investigaron GEOCATMIN/INGEMMET, CENEPRED SIGRID y NASA COOLR, pero no se descargó nada porque no se encontraron licencias en fuentes oficiales); validación cruzada y partición espacial/temporal; calibración de probabilidades.

### Mapa de las 8 fases del «Prompt maestro de integración avanzada»

El usuario definió su propio plan de 8 fases. Estado real (no es lo mismo que la numeración de este documento):

| Fase del prompt | Estado | Detalle |
|---|---|---|
| 1. Arquitectura de integración | **Hecha (contratos)** | 15 módulos con codename y grupo, menú agrupado, orden de registro anticircular. La orquestación real entre módulos sigue pendiente ([docs/INTEGRACION_NEUROCORE.md](docs/INTEGRACION_NEUROCORE.md)) |
| 2. Datasets + OpenCV | **Parcial** | Datasets = CSV de NEURODATA (sin Dataset Manager ni imágenes anotadas). OpenCV instalado: procesamiento determinista y comparación de fotos (3/6); sin clasificación ni detección. Panel sin probar en navegador ([docs/DOCUMENTACION_OPENCV.md](docs/DOCUMENTACION_OPENCV.md), [docs/DOCUMENTACION_DATASETS.md](docs/DOCUMENTACION_DATASETS.md)) |
| 3. Entrenamiento inicial | **Hecha para modelos ligeros** | Mecanismo probado; sin modelos reales entrenados; sin redes neuronales profundas (PyTorch requiere autorización y no es viable a gran escala en 4 GB) |
| 4. Modelos especializados | **Pendiente** | Solo contratos; ningún modelo especializado. Faltan datos reales para entrenarlos ([docs/CATALOGO_MODELOS_IA.md](docs/CATALOGO_MODELOS_IA.md)) |
| 5. Simulación 3D con Three.js | **Hecha en lo implementado (6/6 declaradas)** | Terreno real desde Copernicus DEM GLO-30, visor Three.js, trayectoria D8, capa «Escenario» y, desde la Fase 9, capas de NDVI y de cambio de NDVI sobre el terreno (remuestreadas a ~100 m; no confirman deforestación); visor y paneles sin probar en navegador ([docs/ARQUITECTURA_NEURO_3D.md](docs/ARQUITECTURA_NEURO_3D.md)) |
| 6. Simulación y predicción | **Hecha en lo implementado (escenarios demostrativos)** | Susceptibilidad heurística, inundación de lámina local y comparador de 2 a 4 escenarios, siempre rotulados «SIMULACIÓN»; catálogo de 8 categorías que separa observación, procesamiento, estimación, simulación, predicción validada y alertas (NEURO PREDICTION ENGINE 2/4). **Pendiente:** probabilidad calibrada, horizonte temporal, modelos hidráulicos/geotécnicos, calibración y validación con eventos reales; ningún escenario predice nada ([docs/DOCUMENTACION_SIMULACIONES.md](docs/DOCUMENTACION_SIMULACIONES.md)) |
| 7. NEUROVOICE (voz) | **Hecha en lo implementado (parcial 5/8)** | Voz **en el navegador**: reconocimiento con Web Speech API de Chrome/Edge solo tras consentimiento explícito (**el audio se envía a Google**; el usuario eligió esta opción frente a Vosk local) y síntesis con las voces del navegador (local, interrumpible); memoria de sesión; explica escenarios (rotulados SIMULACIÓN), catálogo de predicciones, NDVI/cambios y modelos con cifras reales. **Pendiente:** el micrófono no se probó (solo la carga de la página, el botón deshabilitado sin consentimiento y que no hay errores de consola); sin modelo de lenguaje, sin quechua/aimara ni otros idiomas, sin acciones por voz; reconocimiento local (Vosk/Whisper) ([docs/ARQUITECTURA_NEUROVOICE.md](docs/ARQUITECTURA_NEUROVOICE.md)) |
| 8. Integración general | **Parcial** | **Hecho:** carga diferida de librerías pesadas (memoria en reposo 212 → 77 MB, arranque 19 → 5 s); pruebas de integración (todas las rutas no públicas exigen sesión con lista pública explícita, el lector no puede escribir salvo 3 rutas, arranque sin librerías pesadas, flujo NEURODATA → NEUROCORE → NEUROVOICE → catálogo y mapa); un solo worker documentado. **Pendiente:** orquestación real entre módulos, alertas automáticas, informes multimódulo, pruebas automáticas del frontend; validación con datos reales según [docs/PLAN_DE_VALIDACION.md](docs/PLAN_DE_VALIDACION.md) |

**Lo que sigue pendiente de todo el plan:** modelos especializados entrenados con datos reales (fase 4; faltan inventarios de eventos con licencia confirmada), clasificación y detección de imágenes (faltan imágenes anotadas), validación de cualquier modelo o escenario con eventos reales, redes neuronales (PyTorch), orquestación entre módulos y acciones sensibles por voz.

OpenCV y Three.js ya fueron autorizados e instalados. Siguen requiriendo autorización expresa del usuario antes de empezar: PyTorch, cualquier reconocedor de voz local o servicio adicional, y la descarga de nuevas fuentes de datos.

## Fase 9 (hecha en lo implementado): módulos especializados básicos

Tres módulos pasaron de contrato a funciones reales y básicas; ninguno usa modelos entrenados ni datos reales validados.

| Módulo | Estado | Qué hace | Pendiente |
|---|---|---|---|
| NEUROTERRAIN (`/api/terrain`) | Parcial 4/5 | Sensores y series de desplazamiento importadas por CSV (formato largo o ancho): acumulado, velocidad por regresión, saltos (MAD), aceleración por ventanas, clasificación experimental y alerta experimental a petición | InSAR (Sentinel-1); conexión en vivo con equipos; compensación de temperatura y calibración; umbrales validados con el sitio (los actuales son de ejemplo) |
| Biodiversidad (`/api/biodiversity`; migración 3) | Parcial 2/6 | Catálogo de especies (vacío al inicio) y observaciones georreferenciadas con validación por un administrador; capa en el mapa; resumen por especie, mes y estado | Reconocimiento de especies, análisis de fotografías, cambio de hábitat y fragmentación; integración de las observaciones al catálogo de NEURO PREDICTION |
| NEUROCONSTRUCTION (`/api/construction`) | Parcial 4/7 | Análisis de sitio (punto o polígono) sobre un DEM: elevación, pendiente, entorno, susceptibilidad heurística, inundación demostrativa opcional y observaciones por reglas fijas | Proximidad a ríos (falta una capa de ríos), compatibilidad territorial, CAD/BIM |

Además: NEURO 3D LAB queda 6/6 declaradas (capas NDVI/cambio sobre el terreno) y el mapa decide el contorno «simulado» **por punto** (propiedad `is_simulated` de cada elemento). Detalle en [docs/API.md](docs/API.md), [docs/DATABASE.md](docs/DATABASE.md) y [docs/INTEGRACION_NEUROCORE.md](docs/INTEGRACION_NEUROCORE.md). 146 pruebas de backend en total.

## Fase 10 (hecha en lo implementado): validación con eventos REALES (NEURODISASTER)

Primera evaluación de la plataforma contra datos reales de campo.

- **Fuente:** inventario de peligros geológicos de INGEMMET (GEOCATMIN, feb. 2013), importado por recorte desde el servicio oficial (`POST /api/disasters/inventory/import`). La licencia no está declarada en el servicio, así que se usa **solo internamente para investigación**, citando la fuente y sin redistribuir.
- **Método** (`POST /api/disasters/susceptibility/validate`):
  - presencias tomadas del inventario y pseudo-ausencias a ≥ 300 m;
  - variables: pendiente y elevación del DEM GLO-30;
  - **validación cruzada espacial por bloques**; la aleatoria solo se muestra como referencia;
  - una segunda variante con ausencias en el **mismo rango de elevación** que los eventos, para corregir el sesgo de muestreo;
  - conclusiones automáticas conservadoras.
- **Resultado real** (Huaraz, recorte de 0,5° × 0,5°, 181 movimientos en masa):

| Indicador | Ausencias libres | Mismo rango de elevación |
|---|---|---|
| Índice heurístico (solo pendiente) | AUC **0,49** (azar) | 0,54 |
| Solo elevación | 0,81 | 0,70 |
| Regresión logística (pendiente + elevación), espacial | 0,83 ± 0,06 | **0,74 ± 0,09** |
| Bosque aleatorio, espacial | 0,82 ± 0,06 | 0,74 ± 0,08 |

- **Lectura honesta:**
  - El índice heurístico de pendiente que usaban 3D LAB y NEUROCONSTRUCTION **no discrimina** los eventos inventariados. Sus avisos ahora lo dicen expresamente.
  - El AUC alto se explica casi solo por la elevación, que probablemente refleja dónde se hizo el inventario (valles poblados y vías) y no el peligro físico.
  - **Ningún modelo de susceptibilidad queda validado.** Hacen falta litología, geomorfología, lluvia y cobertura.
- El dataset generado (CSV con la columna `evento`) puede entrenarse en NEURAL TRAINING. La validación final sigue siendo de un administrador, con evidencia y siempre por encima del valor de referencia.

## Fase 4 (propuesta): escala y voz

| Elemento | RAM estimada | Riesgos |
|---|---|---|
| PostgreSQL/PostGIS (geometrías nativas, consultas espaciales) | Servidor adicional: del orden de 0,5 a 1 GB | Consume gran parte de un equipo de 4 GB; migraciones a probar |
| Reconocimiento de voz **local** (Vosk/Whisper) y síntesis local (Piper) para no enviar audio a Google (hoy el reconocimiento es el de Chrome) | Cientos de MB por modelo | Calidad en español peruano a evaluar; quechua/aimara requieren datos propios y hablantes competentes |
| Multiusuario por red local con HTTPS | Baja | Seguridad y mantenimiento; hoy solo uso local |
| Módulos de movimientos territoriales (series GPS/inclinómetros, InSAR) | Media a alta (InSAR es pesado) | Calibración de sensores; InSAR puede superar la capacidad del equipo |

## Principios

- Un módulo solo pasa a «operativo» cuando todas sus capacidades funcionan (estado derivado).
- Ningún modelo se declara validado sin evidencia y datos de prueba separados.
- Datos simulados siempre marcados como tales.
- Nada se contrata sin aprobación ([COSTS.md](COSTS.md)).
