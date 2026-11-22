# Hoja de ruta

Las Fases 1 y 2 describen lo ya construido; lo de la Fase 3 en adelante, y lo marcado como pendiente, son **propuestas**, no compromisos ni funciones existentes. Las cifras de RAM son estimaciones a validar con mediciones en el equipo objetivo (4 GB).

## Fase 1 (hecha)

- API central FastAPI con autenticación por token, roles (lector, analista, admin) y auditoría.
- Base SQLite con 20 tablas y migración inicial Alembic; roles semilla.
- NEUROCORE: registro de 10 módulos con contrato `ModuleDescriptor`, estado derivado, intérprete por palabras clave.
- NEURODATA: carga y validación de CSV, GeoJSON, PNG/JPG y PDF; registro manual; procedencia, calidad y marca obligatoria `is_simulated`; capas GeoJSON para el mapa.
- Alertas experimentales con ubicación, evidencia, fuente, incertidumbre, estados de validación, seguimiento e informe Markdown; registro de eventos.
- NEUROTRAINING: registro de modelos (siempre «planificado») y consulta de ejecuciones.
- NEUROVOICE: chat de texto en español con intérprete por reglas e historial por usuario.
- Interfaz React con 15 secciones de menú, mapa territorial (MapLibre con mapa base local Natural Earth; OpenStreetMap opcional), panel de inicio con cifras reales.
- Scripts `.bat` de instalación, arranque, desarrollo, parada y verificación; pruebas de backend (hoy 41 en total, incluidas las de la Fase 2).
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

## Fase 3 (propuesta): modelos ligeros y validación

| Elemento | RAM estimada | Riesgos |
|---|---|---|
| scikit-learn ligero (árboles, regresión logística) entrenado desde NEUROTRAINING | Cientos de MB según el conjunto de datos | Pocos datos etiquetados; sobreajuste; sin validación un modelo no debe marcarse «validado» |
| Evaluación con datos separados y métricas guardadas | Baja | Fuga de datos entre entrenamiento y prueba |
| Alertas automáticas desde modelos (siempre experimentales) | Baja | Falsas alarmas o falsa tranquilidad; requiere validación humana |
| Susceptibilidad a huaycos/deslizamientos (amenaza, exposición, vulnerabilidad) | Media | Datos históricos insuficientes; no predice fechas exactas |

## Fase 4 (propuesta): escala y voz

| Elemento | RAM estimada | Riesgos |
|---|---|---|
| PostgreSQL/PostGIS (geometrías nativas, consultas espaciales) | Servidor adicional: del orden de 0,5 a 1 GB | Consume gran parte de un equipo de 4 GB; migraciones a probar |
| Voz libre: Vosk (reconocimiento) y Piper (síntesis) | Cientos de MB por modelo | Calidad en español peruano a evaluar; quechua/aimara requieren datos propios |
| Multiusuario por red local con HTTPS | Baja | Seguridad y mantenimiento; hoy solo uso local |
| Módulos de movimientos territoriales (series GPS/inclinómetros, InSAR) | Media a alta (InSAR es pesado) | Calibración de sensores; InSAR puede superar la capacidad del equipo |

## Principios

- Un módulo solo pasa a «operativo» cuando todas sus capacidades funcionan (estado derivado).
- Ningún modelo se declara validado sin evidencia y datos de prueba separados.
- Datos simulados siempre marcados como tales.
- Nada se contrata sin aprobación ([COSTS.md](COSTS.md)).
