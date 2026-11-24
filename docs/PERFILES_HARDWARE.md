# Perfiles de ejecución y hardware

El mismo código y la misma base funcionan en los dos equipos. El perfil se detecta solo, según la RAM física (`app/core/hardware.py`), y se puede forzar sin tocar el código.

| Variable de entorno | Efecto |
|---|---|
| `NEURO_PROFILE` | `ligero`, `estandar` o `potente` (por defecto `auto`) |
| `NEURO_RAM_TARGET_GB` | Memoria objetivo de un trabajo pesado |
| `NEURO_RAM_MAX_GB` | Tope duro. Nunca supera el 75 % de la RAM física |
| `NEURO_N_JOBS` | Hilos de scikit-learn |

| Perfil | Cuándo | Objetivo / tope por trabajo | Hilos | DEM máx. | Árboles RF | Sorteos de ausencias | Entrenamiento mediano |
|---|---|---|---|---|---|---|---|
| ligero | < 8 GB (equipo secundario de 4 GB) | 0,6 / 1,0 GB | 1 | 1600 px | 100 | ≤ 5 | No |
| estandar | 8–24 GB | 3 / ≤ 6 GB | hasta 4 | 3000 px | 200 | ≤ 10 | Sí |
| potente | ≥ 24 GB (equipo principal de 32 GB) | **16 / 20 GB** | hasta 8 | 5000 px | 300 | ≤ 20 | Sí |

## Control de trabajos pesados (`app/core/jobs.py`)

- **Uno a la vez.** El servidor se ejecuta con un solo worker.
- **Memoria antes de empezar.** Cada trabajo estima su memoria:
  - validación: 100 MB + 60 MB por millón de celdas del DEM, medido;
  - DEM: 60 MB + 24 bytes por celda.

  El trabajo no se inicia si supera el tope del perfil o la memoria libre menos un margen de 150 MB. En ese caso responde **503**, con el motivo.
- **Cancelación cooperativa.** `POST /api/system/jobs/cancel` marca el trabajo actual, y la validación lo comprueba entre sorteos (**409**).
- **Recursos.** `GET /api/system/resources` muestra el perfil, la memoria total y libre, el proceso actual y su pico, y el trabajo en curso. Cada validación guarda en su informe `recursos` (pico del proceso, perfil y estimación).

## Qué funciona en cada equipo

| Función | Equipo de 4 GB (ligero) | Equipo de 32 GB (potente) |
|---|---|---|
| Interfaz, mapa, NEUROCORE, NEUROVOICE (navegador), consultas | Sí | Sí |
| Importar inventarios y capas por recorte | Sí | Sí |
| DEM de análisis de hasta 1600 px y validación NEURODISASTER | Sí, si hay ≈300 MB libres (cerrar pestañas) | Sí, con más sorteos y árboles |
| NDVI Sentinel-2 por recorte | Sí, recortes pequeños | Sí |
| NEURAL TRAINING de modelos pequeños (CSV) | Sí | Sí |
| Entrenamiento mediano, comparadores con muchas semillas, recortes de varios grados | No (lo impide el perfil) | Sí |
| Visor 3D | Sí, con limitaciones: el navegador usa render por software si no hay controlador gráfico | Sí |
| Voz local (Piper/Vosk) | No recomendado | Opcional (no instalado) |

**No se entrenan modelos grandes solo porque haya más RAM.** El tipo de modelo lo decide la cantidad y la calidad de los datos (ver `PROTOCOLO_VALIDACION_CIENTIFICA.md`).
