# Misión 2.1 — Datasets y procedencia

## Selección de la zona externa (regla prerregistrada, commit `610f756`)

Se contaron eventos con consultas de **solo conteo** al servicio de INGEMMET, sin descargar variables ni mirar resultados:

| Zona | 1100 | 1300 | 1500 | Total | ¿Elegible? (≥ 30 eventos en ≥ 2 procesos) |
|---|---|---|---|---|---|
| N Carhuaz–Yungay | 41 | 56 | 50 | 147 | Sí |
| S Recuay–Cátac | 72 | 21 | 37 | 130 | Sí |
| **E Callejón de Conchucos** | **39** | **82** | **27** | **148** | **Sí → elegida por mayor total** |
| O Cordillera Negra | 19 | 2 | 38 | 59 | No |

**Zona E (Callejón de Conchucos):** −77,205 / −9,60 / −76,705 / −9,10, en los distritos de Huari, Aczo, Ponto, Masin, Puños y Huachis. Está al otro lado de la Cordillera Blanca, con drenaje hacia el Marañón.
- Valles más bajos que Huaraz: DEM entre 2122 y 5045 m, media 3766 m (en Huaraz la media es 4166 m).
- 8 clases litológicas, frente a 7 en Huaraz.

**Limitación de la regla:** E ganó a N por un solo evento. E tiene solo 27 flujos, de modo que los flujos no pueden evaluarse con suficiencia.

## Independencia (comprobada antes de evaluar)

| Comprobación | Resultado |
|---|---|
| Separación entre recortes | ≥ 5 km por diseño (0,045°) |
| `COD_INV` compartidos | **0** |
| Coordenadas idénticas | **0** |
| Distancia mínima entre eventos de A y de E | **14,1 km** |
| Independencia **temporal** | Variables del terreno y la geología, estables a escala de décadas. **El NDVI se excluyó** (Sentinel-2 es posterior a los eventos) |
| Independencia **metodológica** | **NO.** 117 de 181 eventos de E vienen del mismo estudio de 2007 («Riesgo Geológico en la región Áncash») y comparten autores con Huaraz (Fidel, Zegarra, Zavala, Valderrama). Otros 32 vienen de un estudio de 2008 |

## Datasets nuevos (descargados el 24 nov. 2026, autorización del usuario)

| Dataset | Id | Fuente | Licencia y redistribución | Resolución / CRS | Tamaño | SHA-256 |
|---|---|---|---|---|---|---|
| Inventario de peligros (181 eventos) | `0e8516c4…` | INGEMMET GEOCATMIN `SERV_PELIGROS_GEOLOGICOS/0` | No declarada: **uso interno, no redistribuir** | Puntos, EPSG:4326 | 80,9 KB | `b75616af…242c` |
| Litología 1:50 000 (874 polígonos, 8 clases) | `733b8830…` | INGEMMET `SERV_GEOLOGIA_50K_INTEGRADA/7`, `TIPO_UNIDAD` | Sin licencia abierta: **uso interno** | Polígonos simplificados (≈20 m), EPSG:4326 | 1,33 MB | `2b146d9b…719f` |
| DEM Copernicus GLO-30 | `c556e14e…` | AWS Open Data, teselas S10 W078 y S10 W077 | Copernicus DEM, libre con atribución | 0,0003125° (≈34 m), 1600×1600, EPSG:4326 | 8,6 MB en disco; **27,8 MB transferidos** | `78cdd420…1321` |

- **Fechas del dato:**
  - eventos: 117 de 2007, 32 de 2008 y 31 entre 2016 y 2026; `FECHA` parece la fecha del estudio;
  - DEM: adquisición TanDEM-X de 2011 a 2015, según su documentación [no verificado en el registro].
- **Linaje y manifiesto completo:** `datasets/manifiestos/*.json`, con calidad, transformaciones y duplicados.
- **Integridad:** los datos originales quedan intactos en `data/uploads`.
- **Total en disco:** ≈10 MB nuevos; `data/uploads` pasa de 13 a 31 MB.
- **Nota:** la fuente «litología» reutiliza el registro de fuente creado en la misión 2.0, que conserva una licencia larga de más de 128 caracteres. SQLite lo admite; habrá que corregirlo antes de migrar a PostgreSQL.

## Disponibilidad de otras variables (evaluada; no usadas)

| Variable | Disponibilidad | Decisión |
|---|---|---|
| Orientación (aspecto) | Derivable del DEM | No prerregistrada: no se usó |
| Geomorfología | INGEMMET, uso interno | No usada: alto riesgo de circularidad (ver misión 2.0) |
| Cobertura terrestre | ESA WorldCover (CC BY 4.0), de 2020–2021 | Posterior a los eventos; no compatible temporalmente |
| NDVI histórico anterior a los eventos | Habría que usar Landsat 5/7 (2005–2007) | Fuera del alcance de esta misión |
