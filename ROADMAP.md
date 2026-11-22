# Hoja de ruta

Todo lo de la Fase 2 en adelante son **propuestas**, no compromisos ni funciones existentes. Las cifras de RAM son estimaciones a validar con mediciones en el equipo objetivo (4 GB).

## Fase 1 (hecha)

- API central FastAPI con autenticación por token, roles (lector, analista, admin) y auditoría.
- Base SQLite con 20 tablas y migración inicial Alembic; roles semilla.
- NEUROCORE: registro de 10 módulos con contrato `ModuleDescriptor`, estado derivado, intérprete por palabras clave.
- NEURODATA: carga y validación de CSV, GeoJSON, PNG/JPG y PDF; registro manual; procedencia, calidad y marca obligatoria `is_simulated`; capas GeoJSON para el mapa.
- Alertas experimentales con ubicación, evidencia, fuente, incertidumbre, estados de validación, seguimiento e informe Markdown; registro de eventos.
- NEUROTRAINING: registro de modelos (siempre «planificado») y consulta de ejecuciones.
- NEUROVOICE: chat de texto en español con intérprete por reglas e historial por usuario.
- Interfaz React con 15 secciones de menú, mapa territorial (MapLibre con mapa base local Natural Earth; OpenStreetMap opcional), panel de inicio con cifras reales.
- Scripts `.bat` de instalación, arranque, desarrollo, parada y verificación; 32 pruebas de backend.
- Muestras simuladas en `data/samples`.

Pendiente dentro de lo ya construido: alertas automáticas, recuperación de contraseña, HTTPS, pruebas automáticas del frontend, informes más allá de alertas.

## Fase 2 (propuesta): datos reales y análisis básico

| Elemento | RAM estimada | Riesgos |
|---|---|---|
| Descarga de Sentinel-2 (Copernicus) recortada por área de estudio | Baja si se descarga por recorte | Revisar términos de uso; tamaño en disco; nubosidad |
| Lectura raster **por bloques** con rasterio (nunca la imagen completa en memoria) | Controlada por el tamaño de bloque (decenas de MB) | Instalar rasterio/GDAL en Windows y con el antivirus; ver `backend\.deps` |
| Cálculo de NDVI y comparación de dos fechas (módulo ambiental) | Decenas a pocos cientos de MB por bloque | Interpretar mal nubes o sombras como cambio; exige validación visual |
| Capas raster/resultados publicadas en el mapa | Baja | Teselas o PNG recortados para no saturar el navegador |
| Integración de fuentes públicas (SENAMHI, INGEMMET, MINAM, etc.) | Baja | Licencias y términos por verificar; ver [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) |

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
