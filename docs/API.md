# API

Documentación interactiva (generada por FastAPI): <http://127.0.0.1:8000/docs>. Todos los mensajes de error están en español.

**Autenticación.** `POST /api/auth/login` devuelve un token; se envía en `Authorization: Bearer <token>`. Roles (de menor a mayor): `lector` < `analista` < `admin`. «Rol mínimo» indica el nivel necesario; un rol superior también puede.

- **público**: sin sesión.
- **lector**: cualquier usuario con sesión válida.
- **analista**: analista o admin.
- **admin**: solo admin.

Códigos habituales: 401 sin sesión o sesión expirada; 403 rol insuficiente; 422 datos inválidos; 429 demasiados intentos de login.

## Sistema

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/health` | público | Estado del servicio y de la base de datos. |
| GET | `/api/dashboard` | lector | Resumen del Inicio: alertas por nivel/estado, registros reales vs simulados, actividad reciente, fuentes, estado de módulos. Todo sale de la base. |

## Autenticación

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/auth/login` | público | Usuario y contraseña; devuelve token, expiración y usuario. Límite: 5 fallos por usuario cada 5 min. |
| POST | `/api/auth/logout` | lector | Revoca la sesión actual (204). |
| GET | `/api/auth/me` | lector | Datos del usuario actual. |
| GET | `/api/auth/users` | admin | Lista usuarios. |
| POST | `/api/auth/users` | admin | Crea usuario (contraseña mín. 10 caracteres, letras + números/símbolos; rol lector/analista/admin). |

## NEUROCORE

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neurocore` | público | Información del núcleo y cantidad de módulos registrados. |
| GET | `/api/neurocore/modules` | público | Contrato y estado de todos los módulos. |
| GET | `/api/neurocore/modules/{key}` | público | Contrato de un módulo (404 si no existe). |
| POST | `/api/neurocore/interpret` | lector | Interpreta un texto por palabras clave (`{"text": "..."}`). |
| GET | `/api/neurocore/operations?limit=` | analista | Últimas operaciones de auditoría (máx. 200). |

## NEURODATA

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/neurodata/upload` | analista | Carga de archivo (multipart): `file`, `source_name`, `is_simulated` (obligatorios), `source_license`, `title`, `observed_at`, `provenance`, `module_key`. Valida extensión y contenido; máx. 10 MB. |
| POST | `/api/neurodata/records/manual` | analista | Registro manual de una medición (`is_simulated` obligatorio). |
| GET | `/api/neurodata/records` | lector | Lista de registros; filtros `data_type`, `is_simulated`, `limit` (máx. 500), `offset`. |
| GET | `/api/neurodata/records/{id}` | lector | Metadatos de un registro. |
| GET | `/api/neurodata/records/{id}/file` | lector | Descarga el archivo original (404 sin archivo; 410 si ya no existe en disco). |
| GET | `/api/neurodata/records/{id}/geojson` | lector | Elementos georreferenciados del registro como GeoJSON. |
| GET | `/api/neurodata/layers?include_simulated=` | lector | Capas para el mapa (hasta 50 registros válidos georreferenciados, 5000 elementos por capa). |
| GET | `/api/neurodata/sources` | lector | Fuentes registradas. |
| GET | `/api/neurodata/limits` | público | Límites de carga y extensiones permitidas. |

Extensiones permitidas: `.csv`, `.geojson`, `.json`, `.png`, `.jpg`, `.jpeg`, `.pdf`.

## Alertas y eventos (experimentales)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/alerts` | lector | Lista; filtros `level`, `validation_status`, `limit` (máx. 500). |
| POST | `/api/alerts` | analista | Crea una alerta (siempre `experimental`; exige nivel, fuente, incertidumbre e `is_simulated`). |
| GET | `/api/alerts/geojson` | lector | Alertas con ubicación como puntos GeoJSON (máx. 1000). |
| GET | `/api/alerts/events` | lector | Últimos 200 eventos. |
| POST | `/api/alerts/events` | analista | Registra un evento. |
| GET | `/api/alerts/{id}` | lector | Detalle con seguimientos. |
| POST | `/api/alerts/{id}/followups` | analista | Agrega nota; opcionalmente cambia el estado de validación. |
| POST | `/api/alerts/{id}/report` | analista | Genera y guarda un informe Markdown de la alerta. |

## NEUROTRAINING

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/neurotraining/models` | lector | Modelos registrados. |
| POST | `/api/neurotraining/models` | analista | Registra un modelo; siempre queda `planificado`. No hay endpoint para entrenar ni para cambiar su estado. |
| GET | `/api/neurotraining/runs` | lector | Últimas 100 ejecuciones (hoy no hay ninguna que las cree). |

## Informes

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/reports` | lector | Informes guardados de todos los módulos (Fase 1: los generados desde alertas). |

## NEUROVOICE

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/neurovoice/chat` | lector | Envía un mensaje de texto; devuelve respuesta, intención y módulo. Crea o continúa una conversación propia. |
| GET | `/api/neurovoice/conversations` | lector | Conversaciones propias (últimas 50). |
| GET | `/api/neurovoice/conversations/{id}` | lector | Mensajes de una conversación propia (404 si es de otro usuario). |

## Territorios

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/territories` | lector | Lista de territorios. |
| POST | `/api/territories` | analista | Crea un territorio; la geometría GeoJSON se valida. La interfaz aún no usa estos endpoints. |

## Notas

- No existen endpoints para editar o borrar (solo GET y POST; CORS también permite solo esos métodos).
- Cualquier ruta `/api/...` inexistente devuelve 404 en JSON; el resto de rutas devuelve la interfaz web (si `frontend/dist` existe).
