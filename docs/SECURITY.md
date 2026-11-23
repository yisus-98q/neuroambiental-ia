# Seguridad

Pensada para **uso local** (`127.0.0.1`). No ha tenido auditoría externa.

## Medidas implementadas

- **Contraseñas:** PBKDF2-SHA256 con 310 000 iteraciones y sal aleatoria por usuario; comparación en tiempo constante. Exigencia: mínimo 10 caracteres combinando letras con números o símbolos.
- **Sesiones:** token aleatorio (`secrets.token_urlsafe(32)`); en la base solo se guarda su SHA-256. Expiración de 12 h por defecto (`NEURO_SESSION_HOURS`). Cierre de sesión revoca el token. En el navegador el token está en `sessionStorage` (se pierde al cerrar la pestaña/navegador).
- **Roles:** `lector` (consulta), `analista` (carga datos, alertas, modelos), `admin` (además, usuarios). Se verifican en el servidor en cada endpoint (ver [API.md](API.md)). Las conversaciones de NEUROVOICE son privadas por usuario.
- **Fuerza bruta:** 5 intentos fallidos de login por usuario cada 5 minutos (después, 429).
- **Archivos cargados:** extensión permitida (`.csv .geojson .json .png .jpg .jpeg .pdf`) **y** contenido: firma de PNG/JPG/PDF, parseo real de CSV y GeoJSON, rangos de coordenadas (lat ±90, lon ±180), máx. de filas CSV (50 000). Tamaño máximo 10 MB, leído por trozos para cortar a tiempo.
- **Nombres de archivo:** se toma solo el nombre base y se guarda en disco con el id UUID (`data/uploads/AAAA/MM/<id>.<ext>`); el nombre original solo se conserva como metadato. La descarga comprueba que la ruta quede dentro de la carpeta de cargas.
- **Auditoría:** tabla `audit_logs` con inicios de sesión (también fallidos), cargas (también rechazadas), alertas, usuarios, modelos, etc. Nunca se guardan contraseñas ni tokens. En un login fallido no se guarda el texto tecleado como usuario (podría ser una contraseña escrita en el campo equivocado): solo el ID del usuario si existe, o «desconocido» (cubierto por la prueba `test_failed_login_never_stores_typed_text`).
- **Cabeceras:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`. Nota: al activar la capa opcional de OpenStreetMap, el navegador contacta a sus servidores y les envía como referencia solo el origen (`http://127.0.0.1:8000`) más su IP.
- **CORS:** restringido a `http://localhost:5173` y `http://127.0.0.1:5173` (configurable), sin credenciales, solo GET y POST.
- **XSS en el mapa:** los popups se construyen con `textContent`, sin inyectar HTML de los datos.
- **Acceso remoto de la Fase 2 (SSRF y TLS):** el módulo ambiental solo contacta `earth-search.aws.element84.com` y `sentinel-cogs.s3.us-west-2.amazonaws.com` por HTTPS; cualquier otro host se rechaza. El identificador de escena se valida con una expresión regular estricta. **No se desactiva la verificación TLS**: GDAL/curl fallaba con «schannel: the certificate chain is incomplete» por la inspección HTTPS del antivirus, y se resolvió leyendo por rangos desde Python (`urllib`) con el almacén de certificados de Windows. Límites contra abuso de recursos: área máx. 0,5° x 0,5°, malla máx. 1600 x 1600 px, un solo procesamiento a la vez (409), y solo rol analista puede lanzar descargas.
- **DEM remoto (NEURO 3D LAB):** reutiliza la misma lectura por rangos con TLS validado y lista de hosts permitidos; el área máxima es 0,5° x 0,5° y solo el rol analista puede descargar o lanzar el escenario D8.
- **Procesamiento de imágenes (NEUROVISION):** se rechazan imágenes de más de 25 megapíxeles leyendo la cabecera antes de decodificar y las corruptas (422); se trabaja con máx. 2048 px por lado y un solo procesamiento pesado a la vez. OpenCV decodifica archivos subidos por usuarios: una vulnerabilidad en sus decodificadores sería un riesgo (mantenerlo actualizado).
- **Artefactos de modelos:** el archivo `.joblib` se lee **una sola vez en memoria**, se verifica su SHA-256 contra la base y se carga desde esos mismos bytes (sin ventana entre la comprobación y la carga); la ruta debe quedar dentro de la carpeta de datos. La validación de un modelo exige un administrador distinto de quien lo entrenó y queda atada a su versión y hash.
- **NEUROVISION:** `GET /api/neurovision/operations` exige sesión; la comparación de fotos rechaza homografías no plausibles (422).
- **Privacidad de la voz (NEUROVOICE):** el reconocimiento usa la Web Speech API de Chrome/Edge, que **envía el audio a servidores de Google**; este servidor nunca recibe audio, solo el texto transcrito. El botón «Hablar» queda **deshabilitado hasta que la persona acepta un consentimiento explícito**. El consentimiento se recuerda en `localStorage` del navegador y se puede retirar desmarcándolo. La síntesis de voz es local. El texto transcrito se guarda en el historial de la conversación (privado por usuario). Evite dictar información sensible. Alternativa sin Google (Vosk/Whisper local): pendiente, requiere autorización.
- **Cobertura de pruebas de acceso:** `tests/backend/test_integration.py` recorre todas las rutas `/api/...` y comprueba que, salvo una lista pública explícita (`/api/health`, `/api/auth/login`, `/api/neurocore`, `/api/neurocore/modules[/{key}]`, `/api/neurodata/limits`, `/api/environmental/defaults`, `/api/neurovoice/capabilities`), todas exigen sesión, y que el rol lector no puede escribir salvo `POST /api/auth/logout`, `/api/neurovoice/chat` y `/api/neurocore/interpret`.
- **Errores internos:** respuesta genérica al usuario; el detalle va al registro del servidor.
- **Secretos:** en `.env` (en `.gitignore`, nunca versionado); `.env.example` no contiene secretos. La contraseña del administrador se pide oculta y no se guarda en historial.

## Limitaciones conocidas

- **Sin HTTPS**: el tráfico va en claro. No exponer el servicio fuera de `127.0.0.1` sin un proxy con TLS.
- El bloqueo de intentos de login está **en memoria**: se reinicia al reiniciar el servidor y no se comparte entre procesos. Por eso el servidor **debe correr con un solo worker** (`--workers 1`, como hace `iniciar.bat`): con varios, el bloqueo de login y el candado de «un proceso pesado a la vez» serían independientes en cada uno y se podrían eludir.
- **No hay recuperación de contraseña**; un admin puede crear usuarios, pero no hay cambio ni reinicio de contraseña por la interfaz ni la API (ni desactivar usuarios).
- **No hay expiración por inactividad**: solo expira a las 12 h desde el inicio de sesión. Las sesiones vencidas no se purgan de la tabla.
- La validación de PNG/JPG/PDF comprueba la firma, no analiza el archivo completo; un archivo con firma válida podría contener contenido malicioso. Los archivos se descargan, no se ejecutan.
- `scripts\detener.bat` detiene cualquier proceso que escuche en los puertos 8000 y 5173, aunque no sea de este proyecto.
- Cualquier usuario con sesión (incluido lector) puede descargar los archivos y ver todos los informes.
- Los datos de la base y los archivos no están cifrados en disco.
- El candado de «un procesamiento a la vez» está en memoria del proceso; si el servidor se cae durante un análisis, su fila en `runs` puede quedar en `en_proceso`.
- Cada análisis NDVI consume ancho de banda y tiempo de CPU en el equipo; un analista con sesión puede lanzar descargas repetidas (no hay límite por usuario ni por tiempo, solo el candado).
- Confianza en servicios de terceros (Element 84, AWS): si cambian sus metadatos o respuestas, el procesamiento puede fallar o dar resultados distintos.
- Sin pruebas automáticas de seguridad del frontend.
