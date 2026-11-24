# Misión 2.1 — Diagnóstico del equipo y versión congelada

**Medido en este equipo** el 24 nov. 2026, según el reloj del equipo. La misión está fechada el 25.

## Hardware y software

| Elemento | Valor medido |
|---|---|
| Windows | 10 Pro 10.0.19045, 64 bits |
| CPU | Intel Core i5-2410M a 2,30 GHz: 2 núcleos, 4 hilos |
| RAM | **3,94 GB** en total; 0,43–0,83 GB libres |
| GPU | Intel HD Graphics 3000 (≈1,8 GB compartidos): **sin CUDA, no se usa** |
| Discos | C: 4,4 GB libres · D: 185,5 GB libres · E: unidad óptica vacía |
| Python / Node / npm / Git | 3.14.7 / 24.20.0 / 12.2.0 / 2.55.0 |
| Dependencias | scikit-learn 1.9.1, numpy 2.5.5, scipy 1.18.1, rasterio 1.5.2 (en `backend/.deps`) |
| Repositorio | `yisus-98q/neuroambiental-ia`, rama `master`, **HEAD = `56424de`** al comenzar, sin cambios locales e igual al remoto |

## Desviación respecto a la misión

**La misión indica un equipo de 32 GB, pero se ejecutó en el equipo secundario de 4 GB.**
- El perfil «potente» (objetivo 16 GB, tope 20 GB) está preparado en `config/perfil_potente.env`, pero **no se puede activar aquí**: el código limita el tope al 75 % de la RAM física.
- Se trabajó con el perfil «ligero»: un trabajo pesado a la vez, comprobación de memoria antes de empezar, cancelación cooperativa y registro del pico de memoria.
- **El tamaño del trabajo no lo exigía:**
  - la evaluación externa completa tuvo un **pico de 413 MB de proceso** y duró unos 3 minutos;
  - para liberar memoria se detuvo temporalmente el servidor de desarrollo.

## Versión científica congelada

- **Etiqueta Git local `mision-2.0-congelada` → `56424de`.** Se publicará cuando el usuario lo autorice.
- **Pruebas al congelar:** **186 pasan**, igual que al cerrar la misión 2.0.
- **Modelos registrados:** 0. No hay modelos `.joblib` que proteger.
- **Ejecuciones históricas de validación, conservadas sin cambios:**
  - semilla 42 en todas;
  - ejecuciones `d33cd6d3`, `75a0e8d2`, `332ea8ed`, `5c5e36cc`, `5e5d40d0`, `12a39ce0`, `b272b66f`, `c229d09b`, `601e9c4a` y `235994a9`;
  - parámetros en la tabla `runs`.
- **Manifiestos** de datasets en `datasets/manifiestos/`: los anteriores se conservan **sin cambios** en Git (la exportación los había actualizado con la nueva ejecución y se restauraron); solo se añadieron los 3 nuevos. El linaje actualizado se consulta en vivo en `/api/neurodata/records/{id}/manifest`.
- **Informes científicos previos** sin cambios: `INFORME_RESULTADOS_ENTRENAMIENTO.md` y `PROTOCOLO_VALIDACION_CIENTIFICA.md`.
