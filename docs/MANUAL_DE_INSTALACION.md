# Manual de instalación

Para Windows 10/11. El resumen corto está en el [README](../README.md); aquí van los detalles y la solución de problemas.

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10 u 11 |
| Python | 3.12 o superior (probado con 3.14.7), accesible como `python` en el PATH |
| Node.js y npm | Node 24 y npm |
| `uv` | Opcional; si existe, `instalar.bat` lo usa para instalar dependencias de Python |
| RAM | Pensado para 4 GB. El servidor ocupa ~100 MB en reposo; un NDVI llega a ~170 MB y un entrenamiento de 50 000 filas a ~250 MB (mediciones del equipo de pruebas) |
| Disco | `backend\.deps` ~462 MB (numpy, rasterio con GDAL, scikit-learn, scipy, opencv…) + `frontend\node_modules` ~114 MB + datos. Deje margen para rásters y modelos en `data\uploads` |
| Internet | Para instalar dependencias y para el análisis Sentinel-2. Después, el resto funciona sin conexión |
| Cuentas/claves | Ninguna |

## 2. Instalación

Desde la carpeta del proyecto:

```bat
scripts\instalar.bat
```

Hace: (1) instala las dependencias de Python en `backend\.deps` (no se crea `.venv`), (2) aplica las migraciones de la base SQLite (`data\neuroambiental.db`), (3) instala los paquetes de Node y compila el frontend en `frontend\dist`. Tarda varios minutos la primera vez.

**Por qué `backend\.deps` y no `.venv`:** el antivirus del equipo (Avast) elimina los `python.exe` y lanzadores `.exe` recién copiados. Se ejecuta con el Python del sistema y `PYTHONPATH=backend\.deps;backend` (lo configura `scripts\_entorno.bat`). Ver [ARCHITECTURE.md](../ARCHITECTURE.md).

## 3. Primer uso

```bat
scripts\crear-admin.bat            (pide la contraseña oculta: mín. 10 caracteres, letras y números/símbolos)
scripts\cargar-muestras.bat        (opcional: datos SIMULADOS de prueba)
scripts\iniciar.bat                (abre http://127.0.0.1:8000)
```

Documentación interactiva de la API: <http://127.0.0.1:8000/docs>. Para detener: Ctrl+C o `scripts\detener.bat` (cierra cualquier proceso en los puertos 8000 y 5173).

Modo desarrollo: `scripts\iniciar-desarrollo.bat` (backend 8000 + Vite 5173; más memoria).

**Un solo worker:** el servidor debe correr con un único worker de uvicorn (`iniciar.bat` ya pasa `--workers 1`). El candado de «un proceso pesado a la vez» y el bloqueo de intentos de login están en la memoria de cada proceso; con varios workers no se compartirían. Si inicia uvicorn a mano, use `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1` desde `backend`.

## 4. Verificar la instalación

```bat
python scripts\comprobar.py
```

Ejecuta pytest (105 pruebas) y la compilación del frontend. Es un script de Python porque el antivirus borró tres veces el verificador `.bat`.

## 5. Configuración opcional (`.env`)

Copie `.env.example` como `.env` en la raíz del proyecto. Variables (todas opcionales): `NEURO_DATABASE_URL`, `NEURO_UPLOADS_DIR`, `NEURO_MAX_UPLOAD_MB` (10), `NEURO_MAX_CSV_ROWS` (50 000), `NEURO_SESSION_HOURS` (12), `NEURO_CORS_ORIGINS`. **Nunca** suba `.env` a un repositorio.

## 6. Datos y copias de seguridad

Todo lo que importa está en `data\`: la base `neuroambiental.db` (y sus archivos `-wal`/`-shm` mientras el servidor corre) y `data\uploads\` (archivos cargados, rásters y modelos). Para copiar la base con seguridad, **detenga el servidor** antes. `data\samples\` son las muestras del repositorio. Ni la base ni `uploads` se versionan.

## 7. Actualizar

Tras actualizar el código, vuelva a ejecutar `scripts\instalar.bat` (instala dependencias nuevas, aplica migraciones y recompila). `scripts\iniciar.bat` también aplica migraciones pendientes.

## 8. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| «No se encontró Python en el PATH» | Python no instalado o sin PATH | Instale Python 3.12+ desde python.org y marque «Add to PATH» |
| `instalar.bat` falla al descargar con error de certificado | Inspección HTTPS del antivirus o red | El script usa `--system-certs` con `uv`; si usa `pip`, configure el almacén de certificados de Windows |
| Un `.bat` o `.exe` desaparece | El antivirus lo elimina | Use `python -m uvicorn`/`python -m alembic` (como hacen los scripts); para verificar use `python scripts\comprobar.py`; agregue la carpeta del proyecto a las exclusiones del antivirus si es posible |
| Los `.bat` fallan de forma errática | Finales de línea LF en vez de CRLF | `.gitattributes` fuerza CRLF; al editar, conserve CRLF |
| Pantalla sin la interfaz o aviso «No existe frontend\dist» | No se compiló el frontend | Ejecute `scripts\instalar.bat` o `npm run build` en `frontend` |
| «No se pudo conectar con el backend» | Servidor detenido | `scripts\iniciar.bat` |
| «Ya hay un procesamiento en curso» (409) | Otro NDVI o entrenamiento en ejecución | Espere a que termine; solo se permite uno a la vez |
| NDVI muy lento o error 502 | Sin Internet o servicio remoto caído | Reintente; revise la conexión; solo se contactan `earth-search.aws.element84.com` y `sentinel-cogs.s3.us-west-2.amazonaws.com` |
| El mapa va muy lento | Chrome dibujando por software (sin driver de GPU) o poca RAM libre | Instale el driver de gráficos del fabricante (en Intel HD 3000, desde Windows Update o Intel) y cierre otras aplicaciones |
| Disco C: casi lleno | Cachés de pip/uv/npm | Mueva las cachés a otro disco (por ejemplo `UV_CACHE_DIR`) o límpielas. En el equipo de pruebas se liberaron ~6,8 GB en C borrando las cachés de uv y pip (autorizado por el usuario); el proyecto vive en el disco D |
| Puerto 8000 ocupado | Otra instancia en marcha | `scripts\detener.bat` |

## 9. Software adicional

OpenCV (`opencv-python-headless`) y Three.js fueron autorizados por el usuario y ya forman parte de las dependencias (NEUROVISION y NEURO 3D LAB están parcialmente implementados; ver [DOCUMENTACION_OPENCV.md](DOCUMENTACION_OPENCV.md) y [ARQUITECTURA_NEURO_3D.md](ARQUITECTURA_NEURO_3D.md)). PyTorch y cualquier proveedor de voz **no están instalados** y no se instalarán sin autorización expresa. Ver [ROADMAP.md](../ROADMAP.md).
