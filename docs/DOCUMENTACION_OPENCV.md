# OpenCV y visión por computador (NEUROVISION)

**Estado: parcial, 3 de 6 capacidades.** Funcionan el procesamiento determinista con OpenCV, el análisis de una imagen y la comparación de dos fotos. **No hay clasificación, segmentación con modelo ni detección de grietas o infraestructura**: requieren un modelo entrenado y datos etiquetados que no existen. **No hay ningún modelo de visión entrenado.**

Código: `backend/app/modules/neurovision/{processing.py, service.py, descriptor.py}`, `backend/app/api/neurovision.py`, `frontend/src/pages/NeurovisionPanel.tsx`, pruebas `tests/backend/test_neurovision.py` (12). OpenCV: `opencv-python-headless` 4.14 (autorizado por el usuario).

> Limitación de la verificación: las pruebas automáticas pasan, pero **el panel de la interfaz no se probó en un navegador** (el Chrome del equipo dibuja por software y no permite capturas). La parte de backend sí está probada.

## Qué hace (todo determinista; no es una red neuronal ni aprendizaje)

| Capacidad | Estado | Detalle |
|---|---|---|
| `procesamiento_opencv` | Implementada | Bordes **Canny**, contraste **CLAHE**, segmentación **Otsu + contornos** (regiones con área, caja y centroide), índice de verdor **ExG** y características (media y desviación por canal, densidad de bordes, nitidez por varianza del Laplaciano). Parámetros validados por operación (`GET /api/neurovision/operations`) |
| `analisis_imagen` | Implementada | Entrega imagen original, imagen procesada (superposición), regiones, características y limitaciones |
| `cambios_imagenes` | Implementada | Comparación de **dos fotos de la misma escena**: alineación ORB + RANSAC (mínimo 10 correspondencias, si no 422), diferencia, umbral `max(Otsu, 25)` y morfología. La **homografía se rechaza (422) si no es plausible**: inliers < 25 % de las correspondencias, escala fuera de 0,5-2 o perspectiva > 0,002 (solo fotos casi frontales de la misma escena). **No considera georreferenciación**: no sirve para comparar imágenes satelitales por ubicación |
| `clasificacion` | **Pendiente** | Requiere modelo entrenado e imágenes etiquetadas |
| `segmentacion` (terreno, vegetación, agua) | **Pendiente** | Hay segmentación por umbral (Otsu) pero no la segmentación semántica declarada |
| `deteccion` (infraestructura, grietas) | **Pendiente** | Requiere modelo entrenado e imágenes anotadas |

## Entradas, límites y salidas

- Entrada: registros `imagen` (PNG/JPG) ya cargados en NEURODATA.
- Se trabaja con una imagen de **máximo 2048 px por lado** (la reducción queda en `extra.work_size`). Se rechazan imágenes de **más de 25 megapíxeles** (se lee la cabecera antes de decodificar) y las corruptas (422). Máx. 200 regiones por resultado.
- Salida: un `DataRecord` de tipo `imagen_procesada` en `data/uploads/vision/AAAA/MM/` con procedencia, `sha256` y `is_simulated` **heredado** de la imagen original, más una superposición PNG.
- **Confianza:** `confidence = null` con el texto «no aplica: procesamiento determinístico; requiere un modelo entrenado para clasificar». El sistema no inventa porcentajes de confianza.
- Un solo procesamiento pesado a la vez (candado común; 409 si hay otro).

## Endpoints (ver también [API.md](API.md))

`GET /api/neurovision/operations` (ahora exige sesión: lector), `POST /analyze` y `POST /compare` (analista), `GET /results` y `GET /results/{id}/overlay` (lector). `GET /results` **omite las regiones** (se ven por registro) y no quedan PNG huérfanos si un procesamiento falla.

## Qué NO debe leerse de estos resultados

- Una región detectada por umbral **no es** una grieta, un daño ni una especie: es una región con distinto brillo/color. Sin modelo validado no hay interpretación semántica.
- El ExG es un índice de verdor de fotos en color, **no** es NDVI ni se calibra contra vegetación real.
- La resolución y la compresión JPG limitan los detalles; las condiciones de luz cambian los resultados.
- Las inspecciones de corrosión, grietas o taludes (NEUROINDUSTRIAL, NEUROMINING, NEUROCONSTRUCTION) **no sustituyen una inspección profesional**.
- Los modelos profundos no son viables de entrenar en este equipo ([ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md)).

## Pendiente

Dataset de imágenes anotadas y Dataset Manager ([DOCUMENTACION_DATASETS.md](DOCUMENTACION_DATASETS.md)); clasificación y detección con modelo; segmentación semántica; comparación de imágenes georreferenciadas; prueba de la interfaz en un navegador con GPU. Validación según [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md).
