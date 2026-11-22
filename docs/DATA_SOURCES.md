# Fuentes de datos

## Fuentes actuales

| Fuente | Qué es | Notas |
|---|---|---|
| Muestras de prueba (`data/samples`) | `mediciones_simuladas.csv` (6 puntos de ciudades con temperatura **inventada**) y `area_estudio_simulada.geojson` (polígono y punto de referencia aproximados en la Cordillera Blanca) | **Todos los valores son simulados.** Se cargan con `scripts\cargar-muestras.bat` y quedan marcados `is_simulated = true`, fuente «Muestras de prueba NEUROAMBIENTAL», licencia «CC0 (creado para pruebas)». El polígono no es un límite oficial. |
| Natural Earth 1:110m (admin-0, países) | Mapa base **local** por defecto: `frontend/public/basemap/paises.geojson` (~190 KB, propiedades nombre e iso, coordenadas a 3 decimales; Perú resaltado) | Dominio público (<https://www.naturalearthdata.com/>). Funciona sin Internet. Es un fondo de referencia, no un límite oficial. |
| OpenStreetMap | Capa **opcional**, desactivada por defecto (casilla «Detalle OpenStreetMap» en el Mapa; teselas `tile.openstreetmap.org`) | Atribución obligatoria. Uso moderado según su política; sus servidores pueden rechazar teselas (respondieron 403 «Access blocked» durante las pruebas). |
| Cargas de los usuarios | Archivos CSV, GeoJSON, PNG/JPG, PDF o registros manuales | Cada carga exige fuente, licencia (opcional, «desconocida» por defecto), procedencia y la marca real/simulado. La responsabilidad de que el dato sea legítimo es de quien lo carga. |

**No hay ninguna fuente pública integrada**: el sistema no descarga datos de ningún servicio externo (salvo las teselas de OpenStreetMap, y solo si el usuario activa esa capa opcional).

## Fuentes públicas candidatas (NO integradas)

La licencia y los términos de uso **deben revisarse antes de usar cualquiera**; lo siguiente es orientativo y puede estar desactualizado o incompleto. La tabla `sources` tiene el campo `terms_reviewed` (falso por defecto) para registrar esa revisión.

| Fuente | Posible uso | Licencia / términos |
|---|---|---|
| Copernicus Sentinel (Sentinel-1/2) | Imágenes para NDVI, cambios de cobertura, InSAR | Política de datos abierta de Copernicus; verificar condiciones y atribución exigidas |
| SENAMHI | Estaciones, precipitación, temperatura | Por verificar (acceso y reutilización) |
| INGEMMET (GEOCATMIN) | Geología, concesiones, peligros geológicos | Por verificar |
| MINAM (GEOBOSQUES) | Deforestación y cobertura de bosque | Por verificar |
| IGP | Sismología y geofísica | Por verificar |
| INEI | Límites, población y censos | Por verificar |
| Natural Earth | Límites y capas de referencia | Dominio público (confirmar en su sitio) |
| GBIF | Registros de biodiversidad | Licencias por conjunto de datos (CC0, CC-BY, CC-BY-NC); verificar cada uno |

Antes de integrar una fuente: leer sus términos, registrarla en `sources` con su licencia, definir la atribución, comprobar el tamaño de descarga frente a la RAM y el disco disponibles, y marcar los datos como reales solo si provienen de la fuente oficial.
