# Plan de validación

Define cómo se comprueba que algo funciona (**verificación**) y cuándo un resultado puede considerarse fiable (**validación**). Son cosas distintas: que una prueba automática pase no valida un modelo.

Regla del proyecto: **no afirmar como operativo nada que no esté implementado y probado.**

## 1. Verificación del software (existe)

```bat
python scripts\comprobar.py
```

Desde la carpeta del proyecto. Ejecuta pytest (**105 pruebas de backend**) y `npm run build` (tipos de TypeScript + compilación de Vite). Archivos de prueba en `tests/backend/`:

| Archivo | Cubre |
|---|---|
| `test_auth.py` | Sesiones, roles, bloqueo por intentos, auditoría |
| `test_core.py` | Migraciones, registro de módulos, estado derivado, intérprete |
| `test_neurodata.py` | Cargas válidas e inválidas, límites, datos simulados obligatorios, rutas peligrosas |
| `test_modules.py` | Alertas, eventos, modelos, NEUROVOICE, territorios |
| `test_environmental.py` | NDVI y cambios con datos sintéticos y servidor remoto falso (**sin red**) |
| `test_training.py` | Entrenar/evaluar/predecir, validación por admin (incluida la línea base), fuga de datos, artefacto alterado, candado |
| `test_neurovision.py` (12) | Operaciones OpenCV, límites de imagen, imágenes corruptas, comparación de fotos |
| `test_neuro3d.py` (8) | DEM, pendiente, malla y trayectoria D8 con teselas locales (sin red) |
| `test_scenarios.py` | Susceptibilidad, inundación de lámina local, comparador y sus validaciones (DEM sintético, sin red) |
| `test_neuroprediction.py` | Catálogo de tipos: reglas disjuntas, un elemento simulado nunca es observación/predicción/alerta verificada |

Limitaciones: no hay pruebas automáticas del frontend; **el panel NEUROVISION y el visor 3D no se probaron en un navegador** (el Chrome del equipo dibuja por software y no permite capturas); las pruebas ambientales no usan la red ni escenas reales (la verificación con Sentinel-2 real fue manual); las pruebas de entrenamiento usan datos sintéticos.

## 2. Validación de resultados científicos (política)

### Análisis de Sentinel-2 (NDVI y cambios)

| Qué | Estado |
|---|---|
| Cálculo con datos reales (Huaraz, 2019 y 2025) | Ejecutado manualmente; resultados en el [README](../README.md) |
| Validación del cambio detectado | **No hecha**: sin verdad de campo ni imágenes de alta resolución. Los cambios quedan «sin validar» |
| Qué haría falta | Comparar con puntos de verificación de campo o imágenes de alta resolución, misma época del año, mismo sensor, y registrar la evidencia |

### Modelos de scikit-learn

Un modelo solo puede pasar a `validado` si cumple **todo** lo siguiente (el sistema fuerza lo marcado con *):

1. * Estado `entrenado` y **no** entrenado con datos simulados.
2. * Un administrador **distinto de quien entrenó** el modelo aporta evidencia escrita de **≥ 40 caracteres**, indicando la `version` y el `artifact_sha256` revisados (si el modelo cambió, se rechaza).
3. * El modelo debe **superar la línea base** en sus métricas de prueba (clasificación: accuracy mayor que la clase mayoritaria; regresión: MAE menor que el de predecir la media). **Aviso:** esas métricas salen del **25 % de filas reservadas del mismo CSV (corte aleatorio), no de un conjunto independiente**, y con datos autocorrelacionados en el espacio o el tiempo sobrestiman el rendimiento (`metrics.warnings` lo indica). Por eso la validación real requiere, fuera del sistema (el código no lo verifica): **datos externos** al CSV de entrenamiento (otra zona o fecha), matriz de confusión revisada con falsos negativos aceptables para el uso, y revisión por una persona experta del dominio.
4. Para probabilidades: calibración comprobada (hoy no existe).
5. Para riesgos: datos de eventos reales (inventarios) y revisión de que no hay fuga espacial o temporal.

Tras reentrenar, la validación se **pierde** y debe repetirse.

### Modelos de visión y simulaciones

No hay modelos de visión entrenados. NEUROVISION solo hace procesamiento determinista, sin confianza estadística (`confidence = null`); su salida no está validada contra inspecciones reales. NEURO 3D LAB solo tiene escenarios demostrativos (D8, susceptibilidad heurística, inundación de lámina local, comparador) **sin calibrar ni validar**: se verificaron con el DEM real de Huaraz solo para comprobar que el método no da resultados absurdos (la «bañera» pura daba 42,6 km² y 335 m con 2 m de subida; la lámina local, 0,29 km² y 3,85 m), **no** contra eventos reales. Para validarlos haría falta un inventario de eventos reales (hoy no disponible) y comparar áreas observadas con las simuladas. El catálogo de NEURO PREDICTION ENGINE clasifica por reglas y es verificable con pruebas, pero **no valida** los resultados que clasifica. Cuando se implementen modelos o simulaciones reales: conjunto anotado por expertos, partición independiente, métricas por clase y comparación con eventos observados.

## 3. Pruebas de rendimiento (equipo de 4 GB)

| Medición | Estado |
|---|---|
| Servidor en reposo (~100 MB), NDVI (~124 s, pico ~170 MB), entrenamiento RF (1,5 s a 14 s; pico 249 MB) | Medidas en el equipo de pruebas (ver [README](../README.md) y [ARQUITECTURA_NEURAL_TRAINING.md](ARQUITECTURA_NEURAL_TRAINING.md)) |
| Mapa con capas raster en Chrome sin driver de GPU | Lento; no hay medición formal |
| DEM 3D real de Huaraz (malla 334x278, 1 tesela) | 74,8 s y 10,2 MB en 39 peticiones; sin medición de memoria |
| Visor 3D y panel NEUROVISION en navegador | **Sin medir** (no se probaron en navegador) |
| Voz | **Sin medir (no existe)** |

## 4. Criterios de aceptación por fase

Una capacidad pasa a «implementada» solo si: (1) hay código; (2) hay pruebas automáticas que pasan en `comprobar.py`; (3) su comportamiento con datos reales, si aplica, se probó manualmente y se documentó; (4) sus límites quedan escritos. Los resultados de modelos o análisis llevan siempre incertidumbre y estado de validación.

## 5. Pruebas manuales recomendadas antes de usar el sistema con datos reales

1. Instalar en limpio con `scripts\instalar.bat` y crear administrador.
2. Cargar las muestras y comprobar que quedan marcadas como simuladas.
3. Intentar cargas inválidas (extensión falsa, coordenadas fuera de rango, archivo > 10 MB) y comprobar el rechazo.
4. Crear usuarios lector/analista/admin y verificar permisos.
5. Entrenar con un CSV sintético, comprobar que no se puede validar si es simulado.
6. Calcular un NDVI (necesita Internet) y revisar el porcentaje válido y la procedencia.
7. Alterar un artefacto `.joblib` y comprobar que no se carga.
