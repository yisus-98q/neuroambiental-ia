# Catálogo de datasets y manifiestos (NEURODATA)

## Cómo consultarlo

- **Manifiesto de cada dataset:** `GET /api/neurodata/records/{id}/manifest`. Incluye:
  - procedencia, licencia y si los términos fueron revisados;
  - fechas de adquisición y del dato;
  - CRS, cobertura y resolución;
  - variables y etiquetas;
  - **calidad**: faltantes por columna, filas duplicadas, atípicos con IQR×3 y nulos y geometrías duplicadas en GeoJSON;
  - **linaje**: los registros citados en la procedencia;
  - **transformaciones**: las ejecuciones que lo produjeron o lo usaron;
  - **duplicados exactos** por SHA-256.
- **Catálogo:** `GET /api/neurodata/catalog`, sin la evaluación de calidad porque esa lee los archivos.
- **Versionado en Git (solo metadatos):** `python -m app.cli exportar-manifiestos` escribe un JSON por dataset en `datasets/manifiestos/`. Los datos no se suben a Git: se reproducen con los comandos de descarga, y el SHA-256 permite verificarlos.

## Datasets presentes (25 nov. 2026; zona piloto Huaraz, Cordillera Blanca)

| Dataset | Fuente | Licencia | Tamaño / cobertura | Estado |
|---|---|---|---|---|
| Inventario de peligros geológicos (181 eventos) | INGEMMET GEOCATMIN | No declarada; **uso interno, no redistribuir** | Recorte 0,5° | Real |
| Litología 1:50 000 (1104 polígonos) | INGEMMET | Sin licencia abierta; uso interno | ≈1,8 MB | Real |
| Geomorfología (473 polígonos) | INGEMMET | Sin licencia abierta; uso interno | ≈1,6 MB | Real |
| DEM GLO-30 a ≈35 m y a ≈110 m | Copernicus (AWS Open Data) | Copernicus DEM, con atribución | 1600² y 500² | Real |
| NDVI 16 jul. 2024 (S2A_18LTQ) | Copernicus Sentinel-2 L2A | Libre, con atribución | 1600²; 94 % válido; 39,8 MB descargados | Real |
| CSV de susceptibilidad (10) | Derivados de los anteriores | Hereda la licencia del inventario | 702–724 filas | Real. **7 son duplicados exactos** de validaciones repetidas con la misma semilla; se conservan (no se borran datos) |
| Escenario heurístico | Derivado del DEM | — | 1 ráster | Escenario hipotético, no observación |

## Fuentes públicas candidatas (no integradas todavía)

Cada una necesita revisar sus términos y obtener autorización de descarga antes de integrarla.

| Necesidad | Fuente candidata | Licencia declarada por el proveedor [verificar] | Observación |
|---|---|---|---|
| Deformación (InSAR) | ASF HyP3 (Sentinel-1) | Datos Copernicus, libres | Requiere cuenta NASA Earthdata (decisión del usuario) |
| Lluvia | CHIRPS (≈5 km); PISCO-SENAMHI (≈10 km) | CHIRPS: dominio público; PISCO: verificar | Muy gruesa para un recorte de 0,5° |
| Hidrografía | Red hídrica de la ANA; red derivada del DEM (ya disponible) | ANA: verificar | La red derivada ya se usa para la distancia a cauce |
| Cobertura terrestre | ESA WorldCover 10 m | CC BY 4.0 | Candidata para la máscara de agua, hielo y urbano |
| Registros de desastres | SINPAD / INDECI | Verificar | Fechas de eventos (falta en el inventario) |
| Biodiversidad | GBIF (ocurrencias) | Por conjunto (CC0, CC BY o CC BY-NC) | Filtrar por licencia antes de usar |
