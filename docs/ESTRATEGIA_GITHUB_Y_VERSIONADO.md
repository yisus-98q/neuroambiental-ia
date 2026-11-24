# Estrategia de GitHub y versionado

**Repositorio central:** https://github.com/yisus-98q/neuroambiental-ia (**privado**), rama `master`. Se creó el 25 nov. 2026 tras revisar que no había secretos ni archivos grandes.

## Qué se versiona en Git y qué no

| Se versiona (Git normal) | NO se versiona |
|---|---|
| Código: backend, frontend, pruebas y scripts | `.env`, credenciales y tokens |
| Migraciones de base de datos | `data/*.db`, `data/uploads/`, `data/backups/` (datos y copias locales) |
| Documentación, protocolo, informes y fichas | `backend/.deps/`, `.venv/`, `node_modules/` |
| **Metadatos de datasets** (`datasets/manifiestos/*.json`, con SHA-256, procedencia y licencia) | `frontend/dist/` (se compila) |
| Configuración de perfiles y de modelos (código) | Artefactos `.joblib`, rásteres `.tif` |
| Fichas de modelos (`model_card.json`) cuando haya modelos aprobados | Datos de INGEMMET (sin licencia abierta: **no se publican**) |

## Archivos grandes y Git LFS

- **Medida actual:** el archivo versionado más grande pesa 192 KB y `.git` ocupa menos de 1 MB. **Git LFS no hace falta hoy.**
- GitHub rechaza archivos de más de 100 MB. El script de sincronización bloquea los de más de 50 MB.
- Git LFS gratuito tiene una cuota limitada de almacenamiento y de transferencia mensual. **Solo** se usaría para modelos aprobados que superen unos 50 MB, y nunca para datasets.
- **Los datasets se reproducen, no se suben.** Hay comandos de descarga por recorte (`importar-ingemmet`, `descargar-dem`, `importar-geologia`, NDVI) y el manifiesto con el SHA-256 permite verificar que el dato descargado es el mismo.

## Procedimiento de sincronización (`scripts\sincronizar_github.bat`)

1. Muestra la rama, el remoto y los cambios.
2. **Bloquea** secretos (tokens, claves, contraseñas), archivos prohibidos (`.env`, `.db`, `.joblib`, `.tif`, claves) y archivos de más de 50 MB.
3. Ejecuta las pruebas y la compilación (`scripts/comprobar.py`). Si fallan, no publica.
4. Pide el mensaje del commit y una confirmación explícita antes de publicar.
5. Trae el remoto. Si GitHub tiene commits que no están en local, **se detiene**: nunca hace *force push* ni sobrescribe trabajo remoto.
6. Publica y **verifica** que el remoto quedó en el mismo commit que el local.

## Después de cada fase importante

Pruebas → resultados guardados → commit identificable («Fase N (2.0): …») → sincronización → verificación. Así se hizo en esta etapa: cada fase tiene su commit publicado en GitHub.

## Continuar desde otra computadora autorizada

```
gh auth login                       (una vez; cuenta autorizada)
gh repo clone yisus-98q/neuroambiental-ia D:\Proyectos\neuroambiental-ia
```

Después:
1. Instalar las dependencias (`INSTALAR_DEPENDENCIAS.bat` del paquete portátil, o `backend\.deps` / `.venv` con `requirements-lock.txt`).
2. `npm ci && npm run build` en `frontend/`.
3. `python -m app.cli migrate` y `create-admin`.
4. Descargar los datasets por recorte.

## Punto de restauración

- Antes de cada cambio de esquema se copia la base a `data/backups/` (local, excluida de Git).
- El historial de Git permite volver a cualquier fase con `git checkout <commit>`, sin borrar nada.

## GitHub Actions (cómputo en la nube, 0 USD)

Para el trabajo que no cabe en el equipo de 4 GB.

| Flujo | Cuándo | Qué hace |
|---|---|---|
| `Pruebas` (`.github/workflows/pruebas.yml`) | Cada subida a `master` y cada PR | Pytest del backend con las versiones exactas de `backend/requirements-lock.txt`, más la compilación del frontend |
| `Validación externa` (`.github/workflows/validacion-externa.yml`) | **Solo a mano**: Actions → «Validación externa» → Run workflow, eligiendo la zona N o E | Pruebas, luego `scripts/ci_validacion_externa.py`: descarga los recortes oficiales de Huaraz y de la zona y ejecuta el protocolo prerregistrado |

- **Coste:** los repositorios privados del plan gratuito tienen una cuota mensual de minutos de Actions. Con el límite de gasto en 0 USD, que es el valor por defecto, al agotarla los flujos se detienen en lugar de cobrar. Un flujo de pruebas dura unos 5 minutos y una validación externa unos 15–25.
- **Datos y licencias:**
  - Los datos de INGEMMET y Copernicus se descargan **dentro** de la máquina temporal de GitHub, que se destruye al terminar. Es procesamiento para uso interno en el repositorio privado.
  - **No** se suben al repositorio ni a los artefactos. El artefacto contiene solo métricas, el resumen y las huellas SHA-256.
- **Reproducibilidad:**
  - El resumen compara el SHA-256 de cada dataset descargado con su manifiesto versionado.
  - Si INGEMMET cambió su inventario, se marca «fuente cambiada» y los resultados ya no son directamente comparables.
- **Riesgo conocido:** el servidor de INGEMMET podría responder lento o bloquear el acceso desde fuera de Perú. Si ocurre, el flujo falla con el mensaje de red y no se inventa nada.
- **Resultados:** se descargan desde la pestaña Actions → ejecución → Artifacts. Para incorporarlos al repositorio se copian a `datasets/resultados/` en un commit identificable.
