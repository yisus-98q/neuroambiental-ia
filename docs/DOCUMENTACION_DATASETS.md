# Datasets

## Qué es un «dataset» hoy

En la Fase 3, un dataset de entrenamiento es **un registro CSV válido de NEURODATA** (`data_records` con `data_type = csv` y `validation_status = valido`). No existe un Dataset Manager separado, ni versionado de datasets, ni división guardada, ni anotaciones de imágenes (**pendiente**; capacidad `datasets_imagenes` de NEUROTRAINING sin implementar).

La interfaz NEURAL TRAINING CENTER lista esos CSV en «Datasets (CSV)» y enlaza a NEURODATA para importar más.

## Datasets existentes

| Dataset | Origen | Real o simulado | Sirve para |
|---|---|---|---|
| `data/samples/mediciones_simuladas.csv` | Creado a mano (6 filas) | **Simulado** | Probar la carga y el mapa. Tiene menos de 60 filas: **no se puede usar para entrenar** |
| NDVI y cambios de Sentinel-2 | Fase 2 | Real, pero son rásteres GeoTIFF, no CSV | No se pueden usar directamente como dataset de entrenamiento (no hay extracción a tablas) |
| CSV que suba el usuario | Usuario | Según la marca `is_simulated` que ponga quien lo carga | Entrenar si cumple las reglas |

**No hay hoy ningún dataset real adecuado para entrenar un modelo de riesgos** (huaycos, deslizamientos, etc.). Las pruebas de entrenamiento usan datos sintéticos generados por las pruebas y no representan fenómenos reales.

## Requisitos para entrenar (aplicados por el código)

Mínimo 60 filas completas; 1 a 30 columnas de entrada numéricas; una columna objetivo que no sea entrada; máx. 20 clases; ver [ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md). El archivo ya pasó la validación de NEURODATA (encabezados, filas, tamaño máx. 10 MB, máx. 50 000 filas).

## Reglas de calidad (obligatorias por política del proyecto)

1. Todo dato lleva `is_simulated` explícito; los modelos entrenados con simulados quedan marcados y **no pueden validarse**.
2. Cada dataset debe tener fuente, licencia y procedencia registradas.
3. Los datos de prueba nunca se usan para entrenar; el sistema separa 25 % automáticamente, pero **no** evita duplicados entre filas ni fuga espacial/temporal (ver limitaciones).
4. No mezclar datos simulados y reales en un mismo archivo.

## Lo que haría falta para modelos reales (pendiente)

| Fenómeno / tarea | Datos necesarios | Estado |
|---|---|---|
| Susceptibilidad a huaycos/deslizamientos | Inventario de eventos, pendientes/DEM, lluvia, litología | **Inventario no descargado ni integrado** (ver «Inventarios de eventos investigados» abajo). El DEM ya se obtiene (Copernicus GLO-30) |
| Cambios de vegetación validados | Verdad de campo o imágenes de alta resolución | No disponible |
| Clasificación de imágenes (grietas, corrosión) | Imágenes anotadas por expertos | No disponible |
| Anomalías de sensores | Series históricas de sensores | No disponible (tablas `sensors`/`measurements` existen sin análisis) |

## Inventarios de eventos investigados (nada descargado)

Para entrenar un modelo de huaycos o deslizamientos que pueda validarse hace falta un inventario de eventos reales. Se investigaron candidatos, **sin descargar ningún dato**:

| Candidato | Qué sería | Estado |
|---|---|---|
| GEOCATMIN / INGEMMET (recomendado) | Peligros geológicos; se citó un servicio ArcGIS REST `SERV_PELIGROS_GEOLOGICOS` | Citado por la investigación, **no se abrió ni se probó** |
| CENEPRED SIGRID | Sistema de información para la gestión del riesgo | Sin explorar a fondo |
| NASA COOLR (Cooperative Open Online Landslide Repository) | Inventario global de deslizamientos (FeatureServer) | Sin descargar; cobertura y calidad en Perú por evaluar |

**Las licencias o términos de uso NO se encontraron en ninguna fuente oficial consultada.** Por eso **no se descarga nada hasta confirmar los términos** (reutilización, atribución, uso en modelos). Aun con un inventario, validar un modelo exige datos independientes, partición espacial/temporal y revisión experta ([PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md)).

## Datasets de otros módulos (estado)

- **DEM** (NEURO 3D LAB): Copernicus GLO-30 como registros `raster_dem` (ráster, no CSV; no sirve directamente para NEUROTRAINING sin extraer tablas).
- **Imágenes** (NEUROVISION): los resultados `imagen_procesada` derivan de imágenes cargadas; no hay imágenes anotadas.

## Pendiente de diseñar

- Dataset Manager (catálogo, versiones, estadísticas, particiones guardadas).
- Extracción de muestras desde rásteres (NDVI por píxel o zona) a tablas.
- Anotación de imágenes y su formato.
- Particiones por zona o fecha para evitar fuga.
- Ver también [DOCUMENTACION_OPENCV.md](DOCUMENTACION_OPENCV.md).
