# Modelos de IA: estado honesto

**Desde la Fase 3 el sistema puede entrenar modelos ligeros, pero no hay ningún modelo entrenado con datos reales ni validado.** El mecanismo (scikit-learn sobre CSV, métricas con datos de prueba, validación por un administrador) funciona y está probado con datos sintéticos; el catálogo real de modelos está vacío. Las carpetas `ai/datasets`, `ai/evaluation` y `ai/models` están vacías y reservadas (los artefactos se guardan en `data/uploads/models/`). No hay redes neuronales profundas. Ver [CATALOGO_MODELOS_IA.md](CATALOGO_MODELOS_IA.md) y [ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md).

## Qué hay hoy

| Componente | Cómo funciona realmente |
|---|---|
| NEUROCORE (intérprete) | Reglas: normaliza el texto y cuenta palabras clave por módulo. No aprende ni entiende contexto. |
| NEUROVOICE | Usa ese intérprete y responde con conteos reales de la base y el contrato del módulo. Solo texto en español. Sin voz, sin modelo de lenguaje, sin otros idiomas. Puede no entender frases complejas. |
| NEURAL TRAINING ENGINE (NEUROTRAINING) | Registra modelos (nacen `planificado`), **entrena** random forest, regresión logística y ridge con scikit-learn sobre CSV de NEURODATA, evalúa solo con datos de prueba separados (con línea base), guarda artefactos con SHA-256, permite validar (solo admin, con evidencia, nunca si se entrenó con datos simulados) y predice sobre CSV nuevos marcando la salida como experimental si no está validado. Parcial 7/10: sin redes neuronales, sin datasets de imágenes, sin reanudar entrenamientos. |
| NEURO PREDICTION ENGINE | Registro de predicciones con incertidumbre (parcial 1/4). Sin separación de tipos de salida, sin probabilidades calibradas ni horizonte temporal. |
| Predicción ambiental (Fase 2) | **Cálculos determinísticos, no IA ni aprendizaje automático:** NDVI = (NIR - Rojo) / (NIR + Rojo) con máscara de nubes (SCL) y detección de cambios por umbral sobre la diferencia de NDVI. No hay parámetros aprendidos de datos, ni entrenamiento, ni métricas de exactitud. Los cambios detectados quedan «sin validar» y **no confirman** deforestación ni daño. |
| NEUROVISION | Procesamiento **determinista** con OpenCV (Canny, CLAHE, Otsu, ExG, comparación de fotos ORB+RANSAC): no es aprendizaje ni un modelo; `confidence = null`. Parcial 3/6; sin clasificación ni detección ([DOCUMENTACION_OPENCV.md](DOCUMENTACION_OPENCV.md)). |
| NEURO 3D LAB | Terreno desde DEM real y trayectoria D8 de máxima pendiente: cálculos geométricos, no IA ni simulación física. Parcial 3/5 ([ARQUITECTURA_NEURO_3D.md](ARQUITECTURA_NEURO_3D.md)). |
| Catástrofes, minería, geología, biodiversidad, terreno, industrial | Sin análisis ni modelos entrenados: solo el contrato del módulo. |
| Alertas | Las crea una persona. No hay alertas automáticas. |

## Estados de un modelo

`planificado` → `entrenado` → `validado` → `retirado` (`en_entrenamiento` está definido en el esquema pero no se usa). `entrenado` significa **experimental**: no es una aprobación.

## Criterios para marcar un modelo como «validado»

El sistema obliga a: rol admin, estado `entrenado`, **no** entrenado con datos simulados, **superar la línea base** en las métricas de prueba (clasificación: accuracy mayor que la clase mayoritaria; regresión: MAE menor que el de predecir la media), que valide un admin **distinto de quien entrenó**, que indique la versión y el hash revisados (si el modelo cambió se rechaza) y evidencia escrita de ≥ 40 caracteres. **Las métricas de prueba salen del 25 % de filas reservadas del mismo CSV (corte aleatorio): no es un conjunto independiente** y pueden sobrestimar el rendimiento. El sistema **no verifica** que la evidencia sea cierta ni que se hayan usado datos externos: eso es responsabilidad de quien valida. Lo que debería cumplirse (política del proyecto; detalle en [PLAN_DE_VALIDACION.md](PLAN_DE_VALIDACION.md)):

1. Conjunto de datos descrito, con fuente, licencia y fecha, sin datos simulados mezclados con reales.
2. Separación de entrenamiento y prueba (y, si es posible, validación cruzada por zonas/fechas) para evitar fuga de datos. Hoy solo hay una partición 75/25 aleatoria del mismo CSV (mínimo 60 filas), con avisos en `metrics.warnings`.
3. Métricas apropiadas guardadas en `ai_models.metrics`, comparadas con una línea base simple.
4. Incertidumbre explícita en cada predicción (`predictions.uncertainty`, obligatoria).
5. Revisión por una persona experta del dominio; evidencia guardada (`validation_evidence`).
6. Versión y artefacto reproducibles.

Mientras no se cumpla, cualquier salida debe presentarse como experimental. Ningún modelo puede predecir la fecha exacta de terremotos, explosiones u otros eventos.

## Restricciones por 4 GB de RAM

- Sin modelos de lenguaje grandes ni redes profundas en el equipo.
- Preferir scikit-learn (árboles, regresión) con conjuntos tabulares pequeños (medido: random forest con 50 000 filas x 10 columnas tarda ~14 s con pico de ~249 MB).
- Imágenes satelitales por bloques, nunca completas en memoria.
- Un solo proceso pesado a la vez (entrenamiento o análisis raster); cerrar el navegador y otras aplicaciones.
- Si se necesita GPU o más memoria, ver costos y alternativas en [COSTS.md](../COSTS.md).
