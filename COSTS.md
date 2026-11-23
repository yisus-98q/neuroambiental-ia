# Costos

**Costo actual: 0 USD.** Todo el software usado es libre o gratuito y corre en un equipo local.

## Componentes actuales

| Componente | Uso | Licencia | Costo |
|---|---|---|---|
| FastAPI | API | MIT | 0 |
| Uvicorn | Servidor ASGI | BSD | 0 |
| SQLAlchemy | Acceso a base de datos | MIT | 0 |
| Alembic | Migraciones | MIT | 0 |
| Pydantic | Validación de datos | MIT | 0 |
| python-multipart | Carga de archivos | Apache-2.0 | 0 |
| SQLite | Base de datos | Dominio público | 0 |
| React / React DOM | Interfaz | MIT | 0 |
| Vite | Compilación del frontend | MIT | 0 |
| TypeScript | Tipado | Apache-2.0 | 0 |
| numpy | Cálculo con arreglos (Fase 2) | BSD-3-Clause | 0 |
| rasterio (incluye GDAL) | Lectura/escritura de rásters (Fase 2) | BSD-3-Clause (rasterio); GDAL con licencia tipo MIT/X | 0 |
| scikit-learn (con scipy y joblib) | Modelos ligeros (Fase 3) | BSD-3-Clause | 0 |
| opencv-python-headless | Visión por computador (autorizado) | Apache-2.0 (OpenCV 4.5+; verificar) | 0 |
| Three.js | Visor 3D | MIT | 0 |
| Web Speech API de Chrome/Edge (reconocimiento) y `speechSynthesis` (síntesis) | Voz de NEUROVOICE, **en el navegador** | Funciones del navegador, sin instalación ni clave; el reconocimiento de Chrome usa servidores de Google (el audio sale del equipo; sin garantía de disponibilidad ni de gratuidad futura) | 0 hoy |
| Sentinel-2 L2A COG en AWS Open Data + catálogo STAC Earth Search (Element 84) | Imágenes satelitales (Fase 2) | Datos Copernicus: uso libre con atribución obligatoria; servicios gratuitos, sin cuenta ni claves | 0 |
| MapLibre GL JS | Mapa | BSD-3-Clause | 0 |
| Natural Earth 1:110m países (mapa base local, `frontend/public/basemap/paises.geojson`) | Fondo del mapa por defecto; funciona sin Internet | Dominio público | 0 |
| OpenStreetMap (teselas, capa opcional desactivada por defecto) | Detalle adicional del mapa | Datos ODbL; teselas gratuitas bajo su política de uso | 0, con condiciones |

Condiciones de OpenStreetMap: atribución obligatoria y **uso moderado**. Su servidor público de teselas no está pensado para tráfico intensivo y puede rechazar peticiones: durante las pruebas respondió 403 «Access blocked» a la aplicación local. Por eso el mapa base por defecto es local; OpenStreetMap solo se usa si el usuario marca «Detalle OpenStreetMap». Si se necesita detalle fiable, habría que cambiar de proveedor (ver abajo).

Sentinel-2: la atribución «Contiene datos modificados de Copernicus Sentinel [año]» es obligatoria y el sistema la incluye en la procedencia de cada NDVI y en el mapa. Los términos de uso de Copernicus y de los servicios de Element 84 / AWS Open Data **deben ser re-verificados por el usuario**; la gratuidad actual no está garantizada a futuro (los servicios podrían limitar o cobrar).

Espacio en disco: `backend\.deps` pasó de 47 MB a 192 MB al agregar rasterio/GDAL. Cada NDVI descarga ~17 MB (medido, área por defecto) y guarda un GeoTIFF y un PNG pequeños en `data/uploads/rasters/` (el tamaño en disco por registro aún no está medido).

Las licencias indicadas son las habituales de cada proyecto; conviene confirmarlas al actualizar versiones.

## Costos futuros posibles

Ninguno está contratado ni es necesario hoy.

| Posible costo | Cuándo aparecería | Alternativa gratuita |
|---|---|---|
| Hosting / servidor | Si se quiere acceso desde otros equipos o Internet (hoy solo `127.0.0.1`) | Ejecutar en un equipo propio dentro de la red local |
| Dominio y certificado HTTPS | Al publicar en Internet | Let's Encrypt (certificados gratuitos); acceso solo por red local |
| PostgreSQL/PostGIS gestionado | Muchos usuarios o análisis espaciales pesados | PostgreSQL/PostGIS autoalojado, o seguir con SQLite |
| Almacenamiento y ancho de banda de imágenes satelitales | Hoy solo se descargan recortes (~15-20 MB por fecha, sin guardar las escenas originales). Crecería con series largas o áreas mayores | Mantener recortes pequeños; purgar rásters antiguos; disco local |
| GPU para entrenamiento | Modelos de visión profunda | scikit-learn en CPU para modelos ligeros; cuotas gratuitas de notebooks con límites |
| Servidor de teselas propio | Si el uso supera la política de OSM | Teselas autoalojadas con datos OSM/Natural Earth; proveedores con plan gratuito (revisar límites) |
| Servicios de voz propios | Si Google cambia o limita el reconocimiento de Chrome, o se quiere voz sin enviar audio a terceros | Vosk o Whisper local (reconocimiento) y Piper (síntesis), libres; verificar calidad en español y memoria en 4 GB; requiere autorización |
| Servicios de IA en la nube | Modelo de lenguaje para NEUROVOICE | Reglas actuales; modelos abiertos locales si el equipo lo permite |

## Regla

**Nada se contrata ni se activa sin aprobación explícita.** Cualquier propuesta de gasto debe indicar costo, alternativa gratuita y riesgo de depender del proveedor.
