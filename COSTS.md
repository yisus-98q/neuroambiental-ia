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
| MapLibre GL JS | Mapa | BSD-3-Clause | 0 |
| Natural Earth 1:110m países (mapa base local, `frontend/public/basemap/paises.geojson`) | Fondo del mapa por defecto; funciona sin Internet | Dominio público | 0 |
| OpenStreetMap (teselas, capa opcional desactivada por defecto) | Detalle adicional del mapa | Datos ODbL; teselas gratuitas bajo su política de uso | 0, con condiciones |

Condiciones de OpenStreetMap: atribución obligatoria y **uso moderado**. Su servidor público de teselas no está pensado para tráfico intensivo y puede rechazar peticiones: durante las pruebas respondió 403 «Access blocked» a la aplicación local. Por eso el mapa base por defecto es local; OpenStreetMap solo se usa si el usuario marca «Detalle OpenStreetMap». Si se necesita detalle fiable, habría que cambiar de proveedor (ver abajo).

Las licencias indicadas son las habituales de cada proyecto; conviene confirmarlas al actualizar versiones.

## Costos futuros posibles

Ninguno está contratado ni es necesario hoy.

| Posible costo | Cuándo aparecería | Alternativa gratuita |
|---|---|---|
| Hosting / servidor | Si se quiere acceso desde otros equipos o Internet (hoy solo `127.0.0.1`) | Ejecutar en un equipo propio dentro de la red local |
| Dominio y certificado HTTPS | Al publicar en Internet | Let's Encrypt (certificados gratuitos); acceso solo por red local |
| PostgreSQL/PostGIS gestionado | Muchos usuarios o análisis espaciales pesados | PostgreSQL/PostGIS autoalojado, o seguir con SQLite |
| Almacenamiento de imágenes satelitales | Al integrar Sentinel-2 (cada escena pesa cientos de MB) | Descargar solo recortes y bandas necesarias; disco local; purgar originales |
| GPU para entrenamiento | Modelos de visión profunda | scikit-learn en CPU para modelos ligeros; cuotas gratuitas de notebooks con límites |
| Servidor de teselas propio | Si el uso supera la política de OSM | Teselas autoalojadas con datos OSM/Natural Earth; proveedores con plan gratuito (revisar límites) |
| Servicios de voz | Reconocimiento y síntesis de voz | Vosk (reconocimiento) y Piper (síntesis), libres y locales; verificar calidad en español |
| Servicios de IA en la nube | Modelo de lenguaje para NEUROVOICE | Reglas actuales; modelos abiertos locales si el equipo lo permite |

## Regla

**Nada se contrata ni se activa sin aprobación explícita.** Cualquier propuesta de gasto debe indicar costo, alternativa gratuita y riesgo de depender del proveedor.
