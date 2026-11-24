# Fuentes de datos

## Fuentes actuales

| Fuente | Qué es | Notas |
|---|---|---|
| Muestras de prueba (`data/samples`) | `mediciones_simuladas.csv` (6 puntos de ciudades con temperatura **inventada**) y `area_estudio_simulada.geojson` (polígono y punto de referencia aproximados en la Cordillera Blanca) | **Todos los valores son simulados.** Se cargan con `scripts\cargar-muestras.bat` y quedan marcados `is_simulated = true`, fuente «Muestras de prueba NEUROAMBIENTAL», licencia «CC0 (creado para pruebas)». El polígono no es un límite oficial. |
| **Copernicus Sentinel-2 L2A** (COG en AWS Open Data, catálogo STAC Earth Search de Element 84) | **Fuente real integrada (imágenes).** Catálogo: <https://earth-search.aws.element84.com/v1>; datos: <https://registry.opendata.aws/sentinel-2-l2a-cogs/>. Se leen solo recortes (bandas B04 rojo, B08 infrarrojo cercano y máscara SCL) del área pedida, bajo demanda (módulo Predicción ambiental). Área por defecto: Huaraz / Cordillera Blanca, bbox [-77.60, -9.60, -77.30, -9.35] | Gratis, sin cuenta ni claves. **Atribución obligatoria:** «Contiene datos modificados de Copernicus Sentinel [año]» (va en la procedencia del NDVI y en el mapa). Los términos deben ser re-verificados por el usuario. Se registra en `sources` con licencia «Copernicus: uso libre con atribución». Datos procesados: reproyectados a EPSG:4326 y **reducidos a ~33 m**; no son la imagen original. Solo hosts permitidos: `earth-search.aws.element84.com` y `sentinel-cogs.s3.us-west-2.amazonaws.com` |
| **Copernicus DEM GLO-30** (AWS Open Data) | Modelo digital de elevación para NEURO 3D LAB: se leen 1 a 4 teselas de 1°x1° por recorte (`raster_dem`), malla EPSG:4326 (por defecto ~100 m) | Gratis, sin cuenta. **Atribución obligatoria:** «Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, proporcionado bajo COPERNICUS por la UE y la ESA». Los términos deben ser re-verificados por el usuario. Es un DEM de superficie con errores verticales de varios metros. Medido (Huaraz): 74,8 s, 10,2 MB en 39 peticiones |
| Natural Earth 1:110m (admin-0, países) | Mapa base **local** por defecto: `frontend/public/basemap/paises.geojson` (~190 KB, propiedades nombre e iso, coordenadas a 3 decimales; Perú resaltado) | Dominio público (<https://www.naturalearthdata.com/>). Funciona sin Internet. Es un fondo de referencia, no un límite oficial. |
| OpenStreetMap | Capa **opcional**, desactivada por defecto (casilla «Detalle OpenStreetMap» en el Mapa; teselas `tile.openstreetmap.org`) | Atribución obligatoria. Uso moderado según su política; sus servidores pueden rechazar teselas (respondieron 403 «Access blocked» durante las pruebas). |
| Cargas de los usuarios | Archivos CSV, GeoJSON, PNG/JPG, PDF o registros manuales | Cada carga exige fuente, licencia (opcional, «desconocida» por defecto), procedencia y la marca real/simulado. La responsabilidad de que el dato sea legítimo es de quien lo carga. |

**Solo Sentinel-2 (imágenes) y Copernicus DEM GLO-30 (elevación) están integrados como fuentes públicas de datos**, y solo descargan recortes cuando un analista lo pide. Aparte de eso, el sistema no descarga nada de servicios externos (salvo las teselas de OpenStreetMap, si el usuario activa esa capa opcional). Ninguna fuente peruana (SENAMHI, INGEMMET, MINAM, IGP, INEI) está integrada.

### Notas técnicas sobre Sentinel-2

- **Escala y desplazamiento radiométrico.** Los metadatos de Earth Search declaran un desplazamiento de -0,1 (línea base de procesamiento 04.00 o posterior). Con datos reales de Huaraz, aplicarlo dejaba la vegetación con reflectancia roja negativa (≈ -0,026) y el NDVI se saturaba en 1,0. El sistema decide con los datos: si al aplicar el desplazamiento más del 20 % de los píxeles de superficie (SCL 4, 5 y 6) quedan con reflectancia ≤ 0, concluye que los COG ya vienen corregidos y **no lo aplica**. La decisión queda en `stats.radiometric_offset` y en la procedencia. Es una heurística: debe revisarse si cambian los metadatos de la fuente.
- **Máscara SCL.** Se consideran válidos: 4 vegetación, 5 suelo desnudo, 6 agua, 7 sin clasificar y 11 nieve/hielo. Se excluyen 0 sin datos, 1 saturado, 2 áreas oscuras, 3 sombras de nubes, 8 y 9 nubes, 10 cirros. También se excluyen píxeles con reflectancia ≤ 0.
- **Verificación con datos reales** (Huaraz, 2019-08-02 y 2025-07-16): el desplazamiento no se aplicó en ninguna de las dos escenas; con él, el 44 % y el 62 % de la superficie quedaba con reflectancia ≤ 0.
- **Nieve.** Se mantiene como válida; en zonas andinas altera el NDVI (el porcentaje de nieve se informa en las estadísticas).
- **Salidas.** `data/uploads/rasters/AAAA/MM/<id>_ndvi.tif` (int16, NDVI x 10000, sin dato = -32768), `<id>_cambio.tif` (clases 1 disminución, 2 aumento, 0 sin cambio, 255 sin dato) y un PNG RGBA de vista previa con el mismo nombre. Se registran como `data_records` de tipo `raster_ndvi` y `raster_cambio`.

### INGEMMET — GEOCATMIN «Peligros Geológicos del Perú» — integrada (uso interno)

- **Servicio:** `geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_PELIGROS_GEOLOGICOS/MapServer/0`. Es un servicio público, sin cuenta y sin costo.
- **Consulta:**
  - por recorte, con un máximo de 2,5° por lado;
  - primero se piden los OBJECTID y luego los eventos en lotes de 1000, porque el servidor no admite `resultOffset`;
  - solo se aceptan respuestas de ese host.
- **Licencia:** **no declarada** (`copyrightText` vacío). El usuario autorizó el uso **interno de investigación**, citando a INGEMMET y **sin redistribuir**.
- **Limitaciones:**
  - el título del servicio dice «Feb 2013», pero se sigue actualizando (en Huaraz: 158 registros de 2007 y 23 de 2018–2026); `FECHA` parece la fecha del estudio o registro, no la del evento;
  - está incompleto;
  - está sesgado hacia zonas pobladas y vías;
  - `TIP_PELIGRO` está codificado (el grupo 1000 se trata como movimientos en masa; la correspondencia exacta de los subcódigos está por confirmar con INGEMMET).

### INGEMMET — Litología 1:50 000 y Geomorfología regional — integradas (uso interno)

- **Servicios:** `SERV_GEOLOGIA_50K_INTEGRADA/MapServer/7` (campo `TIPO_UNIDAD`) y `SERV_GEOMORFOLOGIA/MapServer/0` (campo `SUBUNIDAD`), en `geocatmin.ingemmet.gob.pe`.
- **Licencia:** copyright de INGEMMET, sin licencia abierta declarada. Uso interno de investigación autorizado por el usuario; **no redistribuir**.
- **Consulta:**
  - por recorte, primero los OBJECTID y luego lotes de 100;
  - geometrías simplificadas en el servidor (≈20 m);
  - solo se aceptan respuestas de ese host.
- **Uso:** las clases se usan con su nombre oficial, sin reinterpretar.
- **Advertencias:** posible circularidad con el inventario. La clase «Sedimento» y unidades como abanicos o vertientes coluviales pueden contener los depósitos de los propios eventos.

## Fuentes públicas candidatas (NO integradas)

La licencia y los términos de uso **deben revisarse antes de usar cualquiera**; lo siguiente es orientativo y puede estar desactualizado o incompleto. La tabla `sources` tiene el campo `terms_reviewed` (falso por defecto) para registrar esa revisión.

| Fuente | Posible uso | Licencia / términos |
|---|---|---|
| Copernicus Sentinel-1 (radar) | InSAR y detección de cambios con radar | Política de datos abierta de Copernicus; verificar condiciones y atribución. (Sentinel-2 ya está integrado, ver arriba) |
| SENAMHI | Estaciones, precipitación, temperatura | Por verificar (acceso y reutilización) |
| INGEMMET (GEOCATMIN) | Geología, concesiones, peligros geológicos (inventario de eventos; servicio ArcGIS REST `SERV_PELIGROS_GEOLOGICOS` citado, **no abierto ni probado**) | **Licencia/términos no encontrados en fuentes oficiales**: no se descarga nada hasta confirmarlos |
| CENEPRED (SIGRID) | Información para la gestión del riesgo de desastres | Por verificar; sin explorar a fondo |
| NASA COOLR | Inventario global de deslizamientos (FeatureServer) | Por verificar; cobertura en Perú por evaluar |
| MINAM (GEOBOSQUES) | Deforestación y cobertura de bosque | Por verificar |
| IGP | Sismología y geofísica | Por verificar |
| INEI | Límites, población y censos | Por verificar |
| Natural Earth | Límites y capas de referencia | Dominio público (confirmar en su sitio) |
| GBIF | Registros de biodiversidad | Licencias por conjunto de datos (CC0, CC-BY, CC-BY-NC); verificar cada uno |

Antes de integrar una fuente: leer sus términos, registrarla en `sources` con su licencia, definir la atribución, comprobar el tamaño de descarga frente a la RAM y el disco disponibles, y marcar los datos como reales solo si provienen de la fuente oficial.
