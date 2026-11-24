# NEUROAMBIENTAL IA: versión portátil (USB)

## Contenido

| Carpeta / archivo | Qué es |
|---|---|
| `codigo/` | Código completo de la versión indicada en `MANIFESTO_ARCHIVOS.md`, con el frontend ya compilado |
| `dependencias/requirements-lock.txt` | Versiones exactas de los paquetes de Python (y `wheelhouse/` si se incluyó) |
| `config/` | Perfiles de ejecución: `perfil_ligero.env` (4 GB), `perfil_potente.env` (32 GB) y `activo.env` (por defecto `auto`) |
| `datasets/` | Manifiestos de los datasets (procedencia, licencia, SHA-256). Los datos se descargan por recorte |
| `modelos/` | Modelos exportados con su ficha, cuando existan. Hoy no hay ninguno validado |
| `docs/` | Documentación, protocolo científico e informes |
| `scripts/` | Lógica de los `.bat` (Python, sin dependencias externas) |
| `checksums/` | SHA-256 de cada archivo del paquete |
| `logs/` | Registros de cada script |

## Primer uso en una computadora nueva

1. **Python 3.14** de python.org (gratuito), marcando «Add python.exe to PATH».
2. `VERIFICAR_INTEGRIDAD.bat`: comprueba que nada se dañó al copiar.
3. `VERIFICAR_EQUIPO.bat`: RAM, disco, Python, dependencias y perfil recomendado.
4. `INSTALAR_DEPENDENCIAS.bat`: crea un **entorno local en esta computadora** (`codigo/.venv`) con las versiones fijadas. Si un antivirus borra el `python.exe` del entorno, usa automáticamente `codigo/backend/.deps`. Con `wheelhouse/`, instala sin internet.
5. `INICIAR_NEUROAMBIENTAL.bat`: abre http://127.0.0.1:8000. Para crear el primer administrador: `py -3 -m app.cli create-admin`, desde `codigo\backend`.
6. `DETENER_SISTEMA.bat`: detiene **solo** el servidor iniciado por estos scripts, comprobando su PID y su línea de comandos.

Otros scripts:
- `EJECUTAR_PRUEBAS.bat`: pruebas del backend, con el resultado en `logs/`.
- `DESCARGAR_DATASETS.bat`: menú con el tamaño y la licencia de cada dataset; pide confirmación una por una.
- `ENTRENAR_MODELOS.bat`: validación espacial de NEURODISASTER con los datos descargados, y regeneración de fichas y manifiestos.

## Dos equipos, una arquitectura

- **Equipo principal (32 GB):** descargar datos, validar y entrenar (perfil `potente`: objetivo 16 GB, tope 20 GB).
- **Equipo secundario (4 GB):** consulta, visualización e inferencia (perfil `ligero`). Recibe los modelos exportados (`.zip` con la ficha `model_card.json` y el SHA-256) y recortes de datos, nunca datasets completos.

Detalles: `docs/PERFILES_HARDWARE.md`.

## Licencias de datos

- El inventario, la litología y la geomorfología de INGEMMET **no tienen licencia abierta**: son de uso interno y **no se redistribuyen**.
- Copernicus DEM y Sentinel-2 son libres, con atribución.

## Importante

- No se copia ningún `.venv`, porque no es portable. El entorno se crea en cada computadora.
- Los modelos y las alertas son **experimentales** mientras no figuren como validados en el SCIENTIFIC VALIDATION ENGINE.
