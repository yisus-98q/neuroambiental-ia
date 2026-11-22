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
- **Errores internos:** respuesta genérica al usuario; el detalle va al registro del servidor.
- **Secretos:** en `.env` (en `.gitignore`, nunca versionado); `.env.example` no contiene secretos. La contraseña del administrador se pide oculta y no se guarda en historial.

## Limitaciones conocidas

- **Sin HTTPS**: el tráfico va en claro. No exponer el servicio fuera de `127.0.0.1` sin un proxy con TLS.
- El bloqueo de intentos de login está **en memoria**: se reinicia al reiniciar el servidor y no se comparte entre procesos.
- **No hay recuperación de contraseña**; un admin puede crear usuarios, pero no hay cambio ni reinicio de contraseña por la interfaz ni la API (ni desactivar usuarios).
- **No hay expiración por inactividad**: solo expira a las 12 h desde el inicio de sesión. Las sesiones vencidas no se purgan de la tabla.
- La validación de PNG/JPG/PDF comprueba la firma, no analiza el archivo completo; un archivo con firma válida podría contener contenido malicioso. Los archivos se descargan, no se ejecutan.
- `scripts\detener.bat` detiene cualquier proceso que escuche en los puertos 8000 y 5173, aunque no sea de este proyecto.
- Cualquier usuario con sesión (incluido lector) puede descargar los archivos y ver todos los informes.
- Los datos de la base y los archivos no están cifrados en disco.
- Sin pruebas automáticas de seguridad del frontend.
