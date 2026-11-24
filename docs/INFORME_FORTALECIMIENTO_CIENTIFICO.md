# Informe de fortalecimiento científico — NEUROAMBIENTAL IA

- **Fecha:** 24 nov. 2026.
- **Base auditada:** commit `110ccb6`; 155 pruebas de backend pasan; el frontend compila.
- **Alcance:** solo diagnóstico y planificación. En esta auditoría no se modificó ningún módulo, no se descargaron datos (solo se consultaron metadatos públicos de INGEMMET) y no se entrenó ningún modelo. El único cálculo nuevo fue el AUC de la pendiente por tipo de evento, sobre datos ya registrados.

Convenciones:
- **[V] Verificado** en el código o con una ejecución.
- **[I] Inferencia razonada**, pendiente de confirmar.
- **[D] Desconocido**: no hay metadato disponible.

---

## 1. Estado real de la arquitectura

| Componente | Qué existe realmente | Estado | Evidencia |
|---|---|---|---|
| NEURODATA ENGINE | Registra CSV, GeoJSON y rásteres con validación, SHA-256, fuente, licencia, procedencia e `is_simulated` | Funciona | [V] `neurodata/service.py`, `validators.py`; 8 pruebas |
| NEURAL TRAINING ENGINE | Random Forest, regresión logística y Ridge (scikit-learn); un solo corte aleatorio 75/25; artefactos joblib con SHA-256; ciclo planificado → entrenado → validado → retirado | Funciona, pero la validación es **débil** (§3) | [V] `neurotraining/trainer.py`, `service.py`; 9 pruebas |
| NEUROCORE IA | Registro de 15 módulos; el estado se calcula a partir de las capacidades; intérprete por palabras clave (sin LLM); auditoría | Funciona | [V] `neurocore/registry.py` |
| NEURODISASTER | Importa el inventario de INGEMMET; validación espacial por bloques (GroupKFold 4×4) con dos variantes de pseudo-ausencias; solo AUC | Funciona; protocolo **incompleto** (§4, §6) | [V] `modules/disasters/*`; 6 pruebas |
| Sentinel-2 / NDVI | Búsqueda STAC (Earth Search) por nubosidad; lectura por recorte de B04, B08 y SCL; máscara SCL; elige el desfase radiométrico mirando los datos | Funciona; **no** está integrado como variable de NEURODISASTER | [V] `environmental/*`; 10 pruebas |
| DEM Copernicus GLO-30 | Recorte remuestreado a la resolución pedida (en Huaraz, 0,001° ≈ 110 m) | Funciona; resolución usada **inferior** a la nativa (≈30 m) | [V] `neuro3d/dem.py` |
| Registro de experimentos | Tabla `runs` (parámetros + resumen), `ai_models` (versión, métricas, SHA) y auditoría | **Parcial**: no hay experimentos, versiones de dataset ni criterios registrados de antemano | [V] `models/operations.py` |
| NEUROVOICE | Respuestas con plantillas a partir de la base de datos; Web Speech en el navegador; interfaces preparadas para STT, NLU y TTS | Funciona; **sin contexto de mapa** y con **2 defectos** (§4.5) | [V] `neurovoice/service.py` |
| Pruebas | 155 pruebas de backend; la integración se prueba con fetchers simulados (sin red) | Buena cobertura funcional; **no hay pruebas de propiedades científicas** (fuga de información, coherencia de divisiones) | [V] `tests/backend/` |

**Datos presentes en la base real** [V]:
- 1 inventario INGEMMET (181 eventos, real);
- 1 DEM GLO-30 (Huaraz, 500×500);
- 1 CSV de entrenamiento (181 eventos y 543 pseudo-ausencias);
- 1 escenario heurístico.

**No hay ningún modelo registrado ni ningún modelo validado.**

---

## 2. Inventario de datasets

### 2.1 Inventario INGEMMET (GEOCATMIN, `SERV_PELIGROS_GEOLOGICOS/0`)

| Campo | Valor |
|---|---|
| Fuente | INGEMMET, servicio ArcGIS público |
| Licencia | **No declarada** (`copyrightText` vacío). Uso interno autorizado por el usuario; no redistribuir |
| Fecha de adquisición | Importado el 24 nov. 2026 (consulta en vivo) |
| Fecha del dato | **Corrección:** el título del servicio dice «Feb 2013», pero el campo `FECHA` contiene 158 registros de 2007 y 23 de 2018–2026 [V]. El servicio sigue actualizándose, así que «2013» es incorrecto en el código y en la documentación |
| Significado de `FECHA` | **[D]** 158 eventos comparten el año del estudio «Riesgo Geológico en la región Áncash», así que probablemente es la fecha del estudio o del registro y **no la del evento** [I] |
| Cobertura | Recorte −77,75/−9,78/−77,25/−9,28. El 54 % está en los distritos de Independencia y Huaraz [V] |
| Geometría | Puntos; **[D]** no se sabe qué parte del evento representa el punto (escarpa, cuerpo o depósito) |
| Registros | 181, todos con `COD_INV` único; sin duplicados exactos; 28 eventos a menos de 300 m de otro; distancia mediana al vecino más próximo de 776 m [V] |
| Tipos (`TIP_PELIGRO`) | 1300: 68 · 1500: 55 · 1100: 33 · 1600: 17 · 1700: 8. **[D]** No hay diccionario oficial de códigos consultado |
| Faltantes | `FUENTE` 167/181, `NOM_PELIGRO` 10, `AUTOR` 6 |
| Método de obtención | Estudios de campo y gabinete (Fidel, Zegarra, Valderrama, Zavala…) y 9 reportes del COEN |
| Riesgos de sesgo | Concentración urbana y vial (sesgo de muestreo); 87 % procede de un solo estudio de 2007; mezcla de procesos distintos (§4.2); sin ausencias reales |

### 2.2 DEM Copernicus GLO-30

| Campo | Valor |
|---|---|
| Fuente | Copernicus DEM GLO-30 (AWS Open Data) |
| Licencia | Licencia Copernicus DEM: uso gratuito con atribución. **No se redistribuye** [I: revisar el texto exacto] |
| Fecha | **[D]** en el registro. Según su documentación, la adquisición TanDEM-X es de 2011–2015 [I] |
| Resolución | Nativa ≈1 segundo de arco (≈30 m); **usada a 0,001° (≈110 m)** [V] |
| Calidad | 100 % de celdas válidas; elevación de 2466 a 6269 m. Incluye glaciares y lagunas (superficie, no terreno estable) [V/I] |
| Riesgo | Al remuestrear se suavizan las pendientes y se pierden escarpes, que es lo que más afecta a las caídas |

### 2.3 Sentinel-2 L2A / NDVI

| Campo | Valor |
|---|---|
| Fuente | ESA Copernicus mediante Earth Search (STAC) |
| Licencia | Datos Copernicus Sentinel: libres y gratuitos, con atribución |
| Resolución | B04 y B08 a 10 m; SCL a 20 m; remuestreados a la rejilla pedida (promedio para las bandas y moda para SCL) [V] |
| Fecha | Por escena; se guarda en `observed_at` [V] |
| Máscara | SCL: excluye nubes, sombras, nieve y agua según `raster.compute_ndvi` [V] |
| Estado en la base real | **No hay NDVI registrado** en la base real [V] |
| Riesgo | Correspondencia temporal con los eventos (§6.3) |

### 2.4 CSV de susceptibilidad (derivado)

- **Columnas:** `latitud`, `longitud`, `pendiente_deg`, `elevacion_m` y `evento` [V].
- **Riesgo crítico:** si alguien lo entrena en NEURAL TRAINING con `latitud` y `longitud` como variables, el modelo memoriza la ubicación. Como allí la división es aleatoria, las métricas saldrían infladas (§3).

---

## 3. Auditoría del NEURAL TRAINING ENGINE

| Aspecto | Implementación actual [V] | Riesgo |
|---|---|---|
| Importación | Solo CSV válidos de NEURODATA. Las filas con números ambiguos (`1,234`) o faltantes se descartan y se cuentan | Bajo |
| Preparación | Columnas elegidas por el usuario; sin transformación salvo `StandardScaler` en los modelos lineales (dentro del pipeline, así que no hay fuga) | Bajo |
| División | **Un solo corte aleatorio estratificado 75/25**, `random_state=42` | **Alto** en datos espaciales: la autocorrelación infla las métricas. Con un solo corte la varianza es alta y no se informa |
| Fuga de información | Solo impide que el objetivo sea también una variable de entrada | **Alto**: no bloquea coordenadas como variables, ni detecta duplicados o casi-duplicados entre entrenamiento y prueba, ni permite agrupar (por bloque o evento) |
| Entrenamiento | Hiperparámetros fijos (RF: 100 árboles, profundidad 12); sin búsqueda | Medio: RF de profundidad 12 sobreajusta con pocos datos; al no ajustar sobre la prueba no hay fuga por tuning |
| Métricas | Accuracy, P/R/F1 macro, matriz de confusión, FP/FN por clase, AUC y Brier (binaria), línea base de clase mayoritaria | Medio: falta PR-AUC, curva de calibración, intervalos de confianza y umbral justificado (fijo en 0,5) |
| Versiones | `v{version}.joblib` por versión con SHA-256; métricas en `ai_models` (se sobrescriben) y en `runs` (historial) | Medio: el dataset no queda fijado por su SHA en el modelo; no hay linaje dataset → división → modelo |
| Validación | `entrenado → validado` exige: otro administrador, versión y SHA exactos, datos no simulados, superar la línea base y **≥40 caracteres de evidencia en texto libre** | **Alto**: puede «validarse» con las métricas del corte aleatorio del mismo CSV. Con clases 1:3 la línea base es 0,75 y superarla es fácil. **No exige un conjunto de prueba independiente ni criterios fijados de antemano** |
| Aprobación | Separación de funciones (quien entrena no aprueba) y auditoría | Bueno |
| Trazabilidad | Auditoría, `runs`, SHA del artefacto y procedencia del dataset | Bueno, pero incompleta (falta el linaje de divisiones y criterios) |

**Conclusión:** el motor es honesto en sus avisos y en la separación de funciones. Pero su compuerta de validación **no es científicamente suficiente** para datos geoespaciales. Es la deficiencia de mayor prioridad (P0).

---

## 4. Deficiencias científicas detectadas

### 4.1 En NEURODISASTER (validación actual)

1. **Sin zona de exclusión entre bloques:** los puntos de prueba pueden estar junto a los de entrenamiento al borde del bloque. Queda fuga residual.
2. **Bloques sin justificar:** se usa 4×4 (≈13 km) sin estimar el alcance de la autocorrelación (variograma). Además, el 54 % de los eventos está en dos distritos, así que algunos bloques tienen muy pocos.
3. **Solo AUC:** no hay PR-AUC, calibración, matriz de confusión con umbral ni FP/FN.
4. **Una sola muestra de pseudo-ausencias por ejecución.** Con las semillas 42 y 7 el AUC espacial varía entre 0,81 y 0,84. Hay que informar la distribución.
5. **Dominio de las ausencias sin restringir:** incluye glaciares, lagunas y cumbres de más de 5000 m, lo que facilita artificialmente la discriminación por altura.
6. **No hay prueba independiente:** todo está dentro de Huaraz.
7. **Resolución del DEM:** a ≈110 m se subestiman las pendientes.

### 4.2 Mezcla de procesos: hallazgo principal [V]

AUC de la pendiente por tipo, frente a las mismas pseudo-ausencias (pendiente mediana de las ausencias: 19,4°; tres semillas):

| `TIP_PELIGRO` | n | AUC pendiente | Pendiente mediana | AUC «elevación baja» |
|---|---|---|---|---|
| 1100 | 33 | **0,66** | 26,7° | 0,72 |
| 1300 | 68 | 0,53 | 19,5° | 0,88 |
| 1500 | 55 | **0,36** (relación inversa) | 12,6° | 0,80 |
| 1600 | 17 | 0,44 | 13,9° | 0,79 |
| 1700 | 8 | 0,39 | 15,8° | 0,83 |

**Interpretación [I]:** el patrón coincide con que 1100 sean caídas (laderas empinadas) y 1500 sean flujos o huaycos. En los flujos el punto marcaría el cauce o el depósito, que es plano. Mezclar los tipos **anula** la señal de la pendiente y explica el AUC global de 0,49.

**Consecuencia:** hay que modelar **por tipo de proceso**, no «movimientos en masa» en bloque. **Advertencia:** la correspondencia de los códigos con los procesos **no está confirmada oficialmente** y no debe publicarse como hecho.

### 4.3 Errores de descripción encontrados

- «Inventario de 2013» aparece en `inventory.py`, en el descriptor, en ROADMAP, en DATA_SOURCES y en CHECKLIST. Es incorrecto según §2.1 y debe corregirse.
- El aviso «181 movimientos en masa» es correcto en cantidad, pero con la mezcla de procesos sin aclarar.

### 4.4 NEURAL TRAINING

Ver §3: división aleatoria, coordenadas como variables y validación sin prueba independiente.

### 4.5 NEUROVOICE (Tarea 7)

| Requisito | Estado [V] |
|---|---|
| Recibe el contexto del mapa | **No.** `ChatIn` no lleva bbox, capas ni selección |
| Identifica el módulo | Sí, por palabras clave, con memoria del último módulo |
| Explica resultados reales | Parcial. Para `disasters` responde con el **escenario heurístico**, no con el informe de validación real |
| Distingue simulaciones | Sí en escenarios y predicciones. **Defecto:** en NEURODATA cuenta como «reales» todos los registros con `is_simulated=False`, **incluido el escenario heurístico** |
| Comunica incertidumbre | Sí, con textos fijos y limitaciones del descriptor |
| No inventa | Sí: plantillas y consultas, sin LLM |
| Respeta permisos | Sí: cualquier usuario autenticado, solo agregados de lectura |
| Idiomas | es-PE y es-ES en el navegador. **[D/I]** Web Speech no reconoce quechua ni aimara |

---

## 5. Propuesta de modelos y redes neuronales (Etapa 3)

| Modelo | Disponible sin instalar | Memoria (≤10 000 filas × ≤20 variables) | Interpretabilidad | Datos necesarios | Recomendación |
|---|---|---|---|---|---|
| Regresión logística | Sí (sklearn) | < 50 MB | Alta (coeficientes, odds ratio) | Decenas de eventos por variable | **Modelo de referencia obligatorio** |
| Random Forest | Sí | 50–200 MB | Media (importancias por permutación) | Cientos | Comparar |
| Gradient Boosting (`HistGradientBoostingClassifier`) | Sí | < 150 MB | Media (SHAP no instalado; permutación) | Cientos | Comparar; suele ser el mejor en datos tabulares |
| MLP (`sklearn.neural_network.MLPClassifier`) | Sí | < 100 MB | Baja | **Miles** | **No justificado aún** con 33–68 eventos por tipo; solo como ejercicio comparativo, sin expectativa de mejora |
| CNN (sobre parches de DEM o Sentinel-2) | **No**: requiere PyTorch o TensorFlow (≈200–700 MB de disco y ≥1 GB de RAM al entrenar) | Alta | Muy baja | **Miles de polígonos** de deslizamientos y GPU recomendable | **No justificado.** Revisar si hay un inventario poligonal amplio y autorización de instalación |

**Criterio:** con 181 eventos repartidos en 5 procesos, los modelos lineales y de árboles son los adecuados. Una red neuronal no puede demostrar ventaja con validación espacial honesta. Se propone añadirla al comparador solo como referencia y declarar el resultado sea cual sea.

---

## 6. Protocolo de validación para NEURODISASTER (Etapa 4)

### 6.1 Criterios registrados ANTES de mirar la prueba

Se guardan en un documento con hash en el Scientific Validation Engine (§7), antes de evaluar la región de prueba:
- **Unidad de modelado:** un modelo por proceso con n ≥ 30 (por ahora 1100, 1300 y 1500).
- **Variables candidatas y su justificación** (§6.3).
- **Métrica principal:** AUC-ROC espacial ≥ 0,70 y su intervalo del 95 % por bootstrap de bloques con límite inferior > 0,60.
- **Mejora exigida:** superar a la referencia «solo elevación» por ≥ 0,05 de AUC.
- **Umbral de clasificación:** fijado en validación, nunca en prueba.

### 6.2 Separación geográfica

1. **Entrenamiento y validación** con validación cruzada espacial por bloques. El tamaño del bloque ≥ el alcance del variograma de los residuos, y hay una **zona de exclusión** (por ejemplo 1 km) entre bloques de entrenamiento y de prueba.
2. **Prueba independiente:** una región sellada distinta de Huaraz, por ejemplo Recuay sur o Callejón de Conchucos. Requiere descargar otro recorte; ver §10. **Se evalúa una sola vez por versión del protocolo**, y el motor cuenta y registra los accesos.
3. **Duplicados y eventos relacionados:** los eventos a menos de *d* m (por ejemplo 150 m) o del mismo `NM_SECTOR` se agrupan y nunca se separan entre entrenamiento y prueba.
4. **Pseudo-ausencias:**
   - dominio restringido a terreno evaluable (sin hielo ni agua; máscara SCL o NDWI, o umbral de altura documentado);
   - ≥ d_min de cualquier evento;
   - 10 sorteos (semillas), informando la media y la dispersión.
   - Análisis de sensibilidad: aleatorias, en la misma franja de altura, y estratificadas por pendiente.

### 6.3 Variables candidatas y su justificación

| Variable | Justificación física | Fuente | Disponibilidad | Riesgo |
|---|---|---|---|---|
| Pendiente (30 m nativos) | Esfuerzo cortante; controla caídas y deslizamientos | GLO-30 | Ya integrada | Baja para flujos (depósito plano) |
| Curvatura y TPI | Convergencia del flujo y concavidad | Derivada del DEM | Sin datos nuevos | Bajo |
| Distancia a drenajes | Los flujos siguen cauces; erosión al pie de la ladera | Acumulación D8 del DEM (ya existe D8) | Sin datos nuevos | El umbral de cauce elegido define la red; documentarlo |
| Elevación | Proxy de clima, hielo y litología. **También del sesgo de muestreo** | GLO-30 | Integrada | Variable de confusión: usarla solo con la variante de franja de altura y declararlo |
| NDVI | Cobertura vegetal y estabilización por raíces | Sentinel-2 | Integrado como módulo | Ver la nota de temporalidad abajo |
| Litología | Resistencia del material | INGEMMET 1:50 000 (`SERV_GEOLOGIA_50K_INTEGRADA/7`, ago. 2025; 1104 polígonos en el recorte) | Consultable | Licencia (§6.5); no interpretar códigos sin el diccionario |
| Geomorfología | Unidades (piedemonte, abanico, vertiente) | INGEMMET `SERV_GEOMORFOLOGIA/0` (473 polígonos en el recorte; incluye Áncash) | Consultable | Licencia; **circularidad posible** si las unidades se cartografiaron usando los mismos eventos |
| Lluvia | Detonante | CHIRPS (≈5 km) o PISCO-SENAMHI (≈10 km) | Gratuitas | A 5–10 km, un recorte de 0,5° tiene ≈10×10 celdas: poca variación espacial. Más útil para susceptibilidad regional o detonante temporal |
| Mapa de susceptibilidad de INGEMMET | **No como variable** (circular: probablemente se construyó con este inventario) | `SERV_IMG_SUSCEP_MOV_MASA` | — | Solo como **comparador externo** |

**NDVI y la correspondencia temporal (Tarea 3):**
- Sentinel-2 L2A solo existe desde ≈2017 [I]. Los 158 eventos de «2007» no tienen NDVI anterior al evento.
- Un NDVI posterior puede mostrar la **cicatriz del propio evento**. Eso es fuga de información: el NDVI bajo «predice» porque el evento ya ocurrió.
- **Propuesta:**
  - un compuesto de mediana de época seca (mayo a septiembre, menos nubes) de un solo año;
  - porcentaje de píxeles válidos por evento, con umbral mínimo de 60 %;
  - NDVI en un anillo de 100–300 m alrededor del punto, no en el punto;
  - una prueba con y sin NDVI;
  - declarar que es «cobertura actual», no la condición previa.
- Para los eventos de 2018–2026 se puede usar la escena anterior al evento como **prueba de fuga**.
- Si la cobertura válida es insuficiente por nubes o nieve, se documenta y no se usa.

### 6.4 Métricas y qué permiten concluir

| Métrica | Qué dice | Qué NO dice |
|---|---|---|
| AUC-ROC | Si el modelo ordena eventos por encima de las ausencias | Nada sobre probabilidades reales. Con pseudo-ausencias no es la probabilidad de ocurrencia |
| PR-AUC | Rendimiento con desbalance; depende de la proporción eventos/ausencias | No es comparable entre ratios distintos |
| Precisión, recall, F1 | Con un umbral fijado en validación | No hay umbral «correcto» universal; dependen del coste de los FN (vidas) frente a los FP (alarmas) |
| Matriz de confusión, FP y FN | Dónde y cuánto se equivoca | Con pseudo-ausencias, un «FP» puede ser un evento no inventariado |
| Calibración (Brier, curva de fiabilidad) | Si las probabilidades son coherentes **en la muestra** | Con pseudo-ausencias la escala absoluta es arbitraria; solo vale la calibración relativa |
| Errores por región o bloque | Dónde generaliza y dónde no | — |
| Intervalos (bootstrap por bloques) | La incertidumbre de la métrica | — |
| Prueba fuera de Huaraz | **Única evidencia de generalización** | No garantiza que funcione en otra cordillera |

Lo que **no** se puede concluir con este inventario: probabilidades absolutas de ocurrencia, períodos de retorno ni fechas de eventos.

### 6.5 Datos geológicos (Tarea 4)

- **Litología 1:50 000:** el servicio dice `copyrightText: INGEMMET` y la capa no tiene texto de licencia [V]. **No hay licencia abierta declarada.** Mismo régimen que el inventario: uso interno con autorización explícita y sin redistribuir.
- Antes de usar la litología hay que agruparla en clases de resistencia **solo con la documentación oficial**: los campos `LITOLOGIA`, `UNIDAD` y `DESCRIP`, más los boletines de INGEMMET. No se inventan significados de los códigos.
- Recomendación: consultar a INGEMMET por los términos de uso y el diccionario de `TIP_PELIGRO`.

---

## 7. Arquitectura objetivo: Scientific Validation Engine (SVE)

Es un módulo nuevo `app/modules/validation/` con migración Alembic. Es ligero, todo en SQLite y sin dependencias nuevas.

```
dataset_versions   id, record_id → data_records, sha256, parent_version_id, transform (JSON),
                   filters, created_by, created_at          # inmutable
experiments        id, title, module_key, question, protocol_text, protocol_sha256,
                   criteria (JSON, fijado al crear), status, created_by
splits             id, experiment_id, dataset_version_id, method (bloques/región), params
                   (bloque_m, buffer_m, grupos), test_region (GeoJSON), sealed (bool),
                   test_access_count
model_versions     id, experiment_id, ai_model_id → ai_models, version, artifact_sha256,
                   algorithm, hyperparams, features, trained_on_split_id
metric_sets        id, model_version_id, split_id, partition (cv/val/test), fold, region,
                   metrics (JSON: auc, pr_auc, brier, cm, fp, fn, ci95), seed
evidence           id, experiment_id, kind (informe/figura/dataset), sha256, path, note
approvals          id, model_version_id, reviewer_id, decision, criteria_sha256,
                   comment, created_at                      # dos personas distintas
```

**Estados científicos** (en `model_versions.scientific_state`):

`borrador → experimental → evaluado_interno (CV espacial) → evaluado_independiente (prueba sellada) → validado_condicional (área, procesos y período declarados) → retirado | superado`

**Reglas:**
- `validado_condicional` solo se alcanza si `metric_sets` de la partición *test* cumplen `experiments.criteria`, con dos aprobaciones de personas distintas del entrenador.
- Si `protocol_sha256` cambia después de abrir la prueba, el experimento se invalida.

**Integración:**
- **NEURAL TRAINING:** `validate_model` delega en el SVE. El estado «validado» actual pasa a exigir una aprobación del SVE. Los modelos existentes no se tocan; ninguno está validado.
- **NEUROCORE:** el descriptor de cada módulo muestra su mejor estado científico, y la capacidad «amenaza con modelo validado» solo pasa a implementada con un `validado_condicional`.
- **NEURO PREDICTION y NEUROVOICE:** leen el estado científico para etiquetar y explicar cada resultado.
- **Auditoría:** cada transición se registra.

---

## 8. Plan de implementación por etapas

La memoria indicada es el pico estimado [I] durante la ejecución. El coste es 0 USD en todas.

| # | Tarea | Archivos | Dependencias | Memoria | Riesgos | Pruebas | Aceptación |
|---|---|---|---|---|---|---|---|
| **P0.1** ✅ | Corregir la descripción «2013» del inventario y el significado de `FECHA` | `disasters/inventory.py`, `descriptor.py`, ROADMAP, DATA_SOURCES, CHECKLIST | — | — | Ninguno | Texto del descriptor | Ninguna mención de «2013» como fecha del dato |
| **P0.2** ✅ | NEUROVOICE: contar los escenarios aparte de los «reales»; en `disasters`, explicar el último informe de validación | `neurovoice/service.py` | — | — | Bajo | 2 pruebas nuevas | El escenario no se cuenta como real; la respuesta cita el AUC real y sus advertencias |
| **P0.3** ✅ | NEURAL TRAINING: avisar o bloquear coordenadas como variables; marcar «corte aleatorio» como insuficiente para validar datos con coordenadas | `trainer.py`, `service.py` | — | — | Cambia el comportamiento de validación (no hay modelos validados) | Prueba de rechazo y aviso | Imposible validar con métricas de corte aleatorio si el dataset es geoespacial |
| P0.4 ✅ | Coma decimal en las conclusiones | `disasters/validation.py`, `DisasterPanel.tsx` | — | — | — | Ajustar pruebas | — |
| **P1.1** ✅ | Validación por tipo de proceso (n ≥ 30) | `disasters/validation.py`, API y panel | P0 | < 300 MB | Pocos eventos por tipo, con intervalos amplios | Pruebas sintéticas por tipo | Informe separado para 1100, 1300 y 1500 |
| **P1.2** ✅ (falta la máscara de hielo y agua) | Zona de exclusión entre bloques, variograma para el tamaño de bloque, 10 semillas de ausencias, máscara de dominio (hielo y agua) | `validation.py` | scipy (ya instalado) | < 300 MB | Máscara de hielo imperfecta | Prueba de que no hay puntos de prueba dentro de la zona de exclusión | Media ± desviación de las semillas en el informe |
| **P1.3** ✅ | Métricas completas: PR-AUC, Brier, curva de fiabilidad, matriz y FP/FN con umbral fijado en validación, bootstrap por bloques | `validation.py` | — | < 200 MB | — | Prueba de valores conocidos | Tabla completa en el informe |
| **P1.4** ✅ (≈35 m) | DEM a resolución nativa (≈30 m) | Uso de `fetch_dem` con res 0,000278° | — | ≈ 1800² × 4 B ≈ 13 MB por banda; < 400 MB en total | Descarga ≈10–20 MB **(autorización)** | — | Pendiente y curvatura a 30 m |
| **P2** ✅ (mínimo) | Scientific Validation Engine (tablas, servicio, API mínima, estados) | `modules/validation/*`, migración, `neurotraining/service.py` | P0.3 | < 100 MB | Migración de esquema (con copia previa de la base) | Pruebas de transiciones, prueba sellada y doble aprobación | No se puede validar sin criterios previos y prueba independiente |
| **P3.1** ✅ | Variables derivadas del DEM: curvatura, TPI, distancia a drenaje (D8) | `neuro3d/dem.py`, `validation.py` | P1.4 | < 400 MB | Umbral de cauce | Pruebas sobre un DEM sintético | Variables documentadas y justificadas |
| P3.2 | NDVI: compuesto de época seca, anillo, % válido y prueba con y sin | `environmental/*`, `validation.py` | P1 | < 500 MB | Fuga temporal (§6.3); descarga ≈20–50 MB **(autorización)** | Prueba del filtro de cobertura | La limitación temporal se declara en el informe |
| P3.3 ✅ | Litología y geomorfología (consulta por recorte, uso interno) | `disasters/geology.py` (nuevo) | **Autorización de licencia** | < 200 MB | Licencia; códigos sin diccionario | Prueba con fetcher falso | Clases solo según la documentación oficial |
| **P4** | Comparador de modelos: LR, RF, HistGB y MLP con el protocolo P1 | `validation.py` o SVE | P1, P2 | < 500 MB (n_jobs=1) | MLP sin ventaja esperable | Prueba de que todos usan las mismas divisiones | Tabla comparativa con tiempo, memoria y AUC ± IC |
| **P5** | Prueba independiente fuera de Huaraz | Recorte nuevo | P1–P4; **autorización** (DEM e inventario ≈20 MB) | < 500 MB | Pocos eventos en la región elegida | — | Se evalúa una sola vez y se registra en el SVE |
| P6 | Diseño InSAR para NEUROTERRAIN (solo documento) | `docs/DISENO_INSAR.md` | — | — | — | — | Ver §8.1 |
| P7 | Requisitos de los módulos pendientes (solo documento) | `docs/REQUISITOS_MODULOS.md` | — | — | — | — | Ver §8.2 |
| P8 | Contexto de mapa en NEUROVOICE | `api/neurovoice.py`, `service.py`, `MapPage.tsx` | P0.2 | — | Bajo | Pruebas con bbox | Responde sobre el área visible con los datos de esa área |

### Resultados de P1 (24 nov. 2026, datos reales de Huaraz)

Configuración del protocolo:
- validación cruzada espacial por bloques de ≈13,7 km con zona de exclusión de 500 m;
- 5 sorteos de pseudo-ausencias;
- umbral elegido con el entrenamiento de cada pliegue;
- IC 95 % por bootstrap de bloques.

En la tabla, «franja» significa ausencias tomadas en la misma franja de altura que los eventos (sesgo corregido).

| Grupo | n | AUC pendiente sola (franja) | AUC solo elevación (franja) | Regresión logística espacial (franja) | IC 95 % | Variación entre sorteos |
|---|---|---|---|---|---|---|
| Todos | 181 | 0,54 | 0,70 | 0,74 ± 0,09 | 0,52–0,79 | 0,74 ± 0,02 |
| 1100 (probables caídas) | 33 | **0,75** | 0,54 | 0,71 ± 0,08 | 0,53–0,80 | 0,70 ± 0,02 |
| 1300 (probables deslizamientos) | 68 | 0,62 | 0,70 | 0,72 ± 0,18 | 0,54–0,80 | 0,70 ± 0,02 |
| 1500 (probables flujos) | 55 | **0,40** (inversa) | 0,66 | 0,70 ± 0,11 | 0,43–0,77 | 0,70 ± 0,02 |

Lectura:
- **Caídas:** la pendiente sí es una variable útil, incluso sin entrenar.
- **Flujos:** la pendiente en el punto es engañosa. Para ellos hará falta la distancia a drenaje y la acumulación de flujo (P3.1).
- **Todos los grupos:** el límite inferior del IC queda en 0,43–0,54, así que la evidencia es débil. **Ningún modelo cumple los criterios de §6.1.** Los grupos 1600 (17) y 1700 (8) se omiten por pocos eventos.
- **Optimización:** el AUC del bootstrap se calcula por rangos (Mann-Whitney), con resultado idéntico a `roc_auc_score`. El bosque aleatorio se evalúa con el primer sorteo y la variación entre sorteos se mide con el modelo lineal. Así el protocolo completo tarda ≈40 s en el equipo de 4 GB.

**P1.4: DEM a ≈35 m (24 nov. 2026, autorización A2).**
- El modo «análisis» de `fetch_dem` admite hasta 1600 px por lado; el visor 3D sigue limitado a 512. Comando: `python -m app.cli descargar-dem --bbox=...`. Para 0,5° la resolución resultante es 0,0003125° (≈35 m), porque 1 segundo de arco exigiría 1800 px.
- Resultados con la franja de altura, al pasar de 110 m a 35 m:

| Grupo | AUC pendiente sola | Regresión logística |
|---|---|---|
| Todos | 0,54 → 0,56 | 0,74 → 0,76 |
| 1100 | 0,75 → 0,73 | 0,71 → 0,68 |
| 1300 | 0,62 → 0,58 | 0,72 → 0,70 |
| 1500 | 0,40 → 0,42 | 0,70 → 0,73 |

- **Las conclusiones no dependen de la resolución.** Las pendientes medianas de los eventos suben (en 1100, de 26,7° a 29,3°), pero la capacidad de discriminar no mejora.

**P3.1 y P1.2: variables del DEM y bloques por variograma (24 nov. 2026).**

Variables nuevas, todas derivadas del DEM de ≈35 m y sin datos adicionales:
- curvatura (laplaciano suavizado);
- TPI en un radio de 300 m;
- distancia a la red de cauces derivada del DEM: relleno priority-flood, D8 y área drenada ≥ 0,25 km², con la hidrología calculada a ≈70 m para caber en 4 GB.

Bloques automáticos:
- Se calcula el alcance práctico del semivariograma de cada variable sobre 1500 celdas.
- Alcances: pendiente 31 km, elevación 20 km, distancia a cauce 16 km, curvatura y TPI 2,9 km. La mediana es 16 km.
- Resultado: bloques de 3×3 de ≈18 km, que cubren el alcance mediano.

Modelo base = regresión logística solo con pendiente y elevación. Modelo completo = regresión logística con las cinco variables. Todo con la franja de altura:

| Grupo | Base → completo | Mejor variable sola |
|---|---|---|
| Todos | 0,73 → 0,74 | — |
| 1100 (probables caídas) | 0,70 → 0,74 | pendiente 0,73 (mayor en eventos) |
| 1300 (probables deslizamientos) | 0,68 → 0,67 | — |
| 1500 (probables flujos) | 0,67 → 0,70 | **distancia a cauce 0,72** (menor en eventos: mediana 69 m frente a 195 m) |

Lectura:
- Cada tipo de proceso responde a la variable que predice la física: las caídas a la pendiente y los flujos a la cercanía a los cauces.
- **Combinar las variables no mejora** con 33–68 eventos (variables correlacionadas o sobreajuste). Con estos datos, un índice de una sola variable por proceso es más honesto que un modelo multivariable.
- **Ningún modelo está validado.** Falta la prueba independiente fuera de Huaraz (P5).
- La red de cauces derivada no es la oficial de la ANA.

**P3.3: litología y geomorfología de INGEMMET (24 nov. 2026, autorización A4; uso interno, sin redistribuir).**

Capas importadas para el recorte de Huaraz (≈3,4 MB):
- **Litología** del Mapa Geológico Integrado 1:50 000, campo `TIPO_UNIDAD`: 1104 polígonos y 7 clases.
- **Geomorfología** regional, campo `SUBUNIDAD`: 473 polígonos y 17 clases.

Se usan los nombres oficiales tal como los publica el servicio, sin reinterpretar. Las clases con menos del 2 % del área se agrupan en «otras».

Regresión logística con validación espacial y franja de altura. «Topografía» son las 5 variables del DEM:

| Grupo | Topografía | + litología | + litología + geomorfología |
|---|---|---|---|
| Todos | 0,74 | 0,73 | 0,77 |
| 1100 (probables caídas) | 0,74 | 0,72 | 0,76 |
| 1300 (probables deslizamientos) | 0,67 | 0,67 | 0,69 |
| 1500 (probables flujos) | 0,70 | **0,78** (IC 0,67–0,84) | 0,74 |

Razón de frecuencia descriptiva (con todos los eventos): los flujos son 3,8 veces más frecuentes en la clase «Sedimento» (depósitos recientes).

**Advertencias:**
- **Circularidad:** «Sedimento» puede contener los depósitos de huaycos anteriores. La geomorfología incluye unidades como abanicos y vertientes coluviales que se cartografían a partir de esos mismos depósitos.
- **Por eso, la mejora en flujos no prueba capacidad predictiva independiente** y ningún modelo se valida.
- La geomorfología añade poco y es la más expuesta a la circularidad. **No se recomienda usarla como variable**, solo como comparación.

**P2: Scientific Validation Engine (24 nov. 2026, autorización A6).**
- **Base de datos:** migración `b3d8e2a41c07`, que solo añade tablas, aplicada tras copiar la base a `data/backups/`. Módulo `validation` registrado en NEUROCORE (16 módulos), API `/api/validation` y panel.
- **Implementado:**
  - criterios congelados por SHA-256;
  - métricas leídas de la ejecución, no escritas a mano;
  - control de fuga geográfica: una evaluación `cv` no puede usar un DEM que toque la región de prueba, y una `test` debe estar dentro de ella;
  - prueba sellada: una sola evaluación `test` por protocolo;
  - doble aprobación de administradores distintos de los autores; cualquier rechazo revoca el estado;
  - los datos simulados nunca cumplen los criterios.
- **NEURAL TRAINING** remite al motor cuando el dataset tiene coordenadas.
- **Pendiente:** versionado formal de datasets y divisiones; vínculo con los artefactos `.joblib`.
- **Estado real:** ningún experimento puede validarse todavía, porque no hay una región de prueba independiente evaluada (P5).

### 8.1 Diseño InSAR (Tarea 5)

**Procesar localmente no es viable:** SNAP o ISCE necesitan ≥ 8–16 GB de RAM y descargas de GB por escena. Las alternativas gratuitas son productos ya procesados:
- **ASF HyP3:** interferogramas Sentinel-1 bajo demanda, gratuitos. Requiere una **cuenta NASA Earthdata**, que necesita autorización. Cada producto pesa ≈100–500 MB, así que solo se descargan los recortes.
- **COMET-LiCSAR:** interferogramas por *frame* para algunas zonas andinas [I: verificar cobertura de Áncash y licencia].

Modelo de datos y reglas:
- **Separación obligatoria** en `terrain_series`: `observado_los` (desplazamiento en línea de visión, con su geometría ascendente o descendente), `estimado` (por ejemplo una proyección a la pendiente, siempre marcada como derivada), `ruido_estimado` (desviación por punto) y `coherencia`.
- **Regla:** un cambio de fase con coherencia < 0,3 [I: umbral a fijar], o explicable por la atmósfera o la desenvolvimiento de fase, **no se interpreta como movimiento**. Un movimiento solo se informa como «señal consistente» si se repite en ≥ 3 interferogramas independientes.
- **Validación:** contra los sensores de NEUROTERRAIN ya existentes (series CSV), comparando la tendencia del sensor con la del píxel. Sin sensores, el resultado queda como «no validado».
- **Limitaciones a mostrar:**
  - solo se mide la componente en la línea de visión;
  - en Huaraz, la vegetación y la nieve bajan la coherencia;
  - Sentinel-1B dejó de funcionar en 2021, lo que reduce la frecuencia de revisita [I].

### 8.2 Módulos pendientes (Tarea 6)

| Módulo | Requisitos mínimos | Fuentes gratuitas candidatas | Bloqueo actual |
|---|---|---|---|
| NEUROGEO | Litología, fallas, geoquímica por recorte; consulta y mapa | INGEMMET (`SERV_GEOLOGIA_50K_INTEGRADA`, `SERV_GEOLOGIA_FALLAS`, `DRME/SERV_DRME_GEOQUIMICA`) | Licencia no abierta: uso interno |
| NEUROMINING | Concesiones, pasivos ambientales y relaves; cambio de NDVI alrededor | GEOCATMIN (catastro minero) e inventario de pasivos del MINEM [I] | Verificar licencias; no inferir contaminación sin muestras |
| NEUROINDUSTRIAL | Ubicación de instalaciones y emisiones declaradas | OEFA o datos abiertos del Perú [I: verificar disponibilidad] | Sin fuente identificada y verificada |
| NEUROCONSTRUCTION | Ríos y compatibilidad territorial | Red hídrica de ANA; red derivada del DEM (D8, ya disponible); zonificación ZEE regional [I] | Para los ríos basta el DEM. La zonificación depende de la región |
| Biodiversidad (fotos) | Reconocimiento de especies | Modelo local pequeño (por ejemplo MobileNet ONNX, ≈15 MB), **no entrenado aquí**; o la sugerencia manual de iNaturalist (API con términos propios) | Requiere un modelo preentrenado y licencia; siempre como «sugerencia» a validar |

### 8.3 NEUROVOICE evolutivo (Tarea 7), sin costes

1. **Contexto:** `ChatIn` añade `{bbox, capas_activas, modulo_activo, registro_seleccionado}` y las respuestas filtran por el área.
2. **Herramientas de solo lectura:** el intérprete llama a funciones del servicio (último informe, NDVI del área, alertas del área), nunca SQL libre, y respetando el rol del usuario.
3. **Conversación natural (opcional):**
   - LLM local vía Ollama, ya presente en el equipo [V: carpeta `.ollama`], con un modelo de 0,5–1,5 B cuantizado (≈0,5–1,2 GB de RAM [I]).
   - El LLM **solo redacta** a partir de los hechos estructurados que le pasan las herramientas.
   - Un **verificador** rechaza la respuesta si contiene una cifra que no esté en los hechos y cae a la plantilla actual.
   - Requiere autorización por el uso de RAM.
4. **Varios idiomas:** Web Speech para el reconocimiento y la síntesis en es, en y pt. Las plantillas se traducen con archivos de textos. Quechua y aimara: sin reconocimiento disponible, solo texto si se traducen las plantillas con revisión humana.

---

## 9. Riesgos y limitaciones

1. **El inventario es la mayor limitación:**
   - eventos concentrados en zonas urbanas;
   - fecha del evento desconocida;
   - punto sin definición (escarpa, cuerpo o depósito);
   - códigos sin diccionario oficial.

   Ningún algoritmo corrige esto: solo se puede declarar.
2. **Con pseudo-ausencias no se estiman probabilidades absolutas**, solo un ordenamiento relativo.
3. **Con 33–68 eventos por proceso los intervalos serán amplios.** Es posible que ningún modelo alcance los criterios, y ese resultado es válido.
4. **Licencias:** litología, geomorfología e inventario tienen derechos de INGEMMET sin licencia abierta. Solo uso interno.
5. **4 GB de RAM:** limita el DEM nativo a recortes de ≈0,5–1° y excluye el InSAR local y las CNN.
6. **Sobreajuste al protocolo:** si se itera muchas veces mirando la prueba, deja de ser independiente. El SVE cuenta los accesos.
7. **Supuestos [I] de este informe** que deben verificarse antes de actuar:
   - el significado de los códigos;
   - las fechas de GLO-30;
   - la disponibilidad de Sentinel-2 L2A desde 2017;
   - la cobertura de LiCSAR;
   - los umbrales de coherencia.

---

## 10. Decisiones que requieren autorización

| # | Decisión | Coste | Impacto |
|---|---|---|---|
| A1 | Empezar la implementación (P0, luego P1…) | 0 USD | Modifica módulos funcionales (P0.3 cambia la compuerta de validación) |
| A2 | Descargar el DEM GLO-30 a 30 m del recorte de Huaraz | ≈10–20 MB | Necesario para P1.4 y P3.1 |
| A3 | Descargar escenas Sentinel-2 de época seca para el NDVI | ≈20–50 MB | P3.2 |
| A4 | Usar internamente la litología y la geomorfología de INGEMMET (sin licencia abierta) | 0 USD; ≈1–5 MB | P3.3 |
| A5 | Elegir y descargar una región de prueba independiente (DEM + inventario) | ≈20 MB | P5 |
| A6 | Migración de base de datos para el SVE (con copia de seguridad previa) | 0 USD | P2 |
| A7 | Crear una cuenta NASA Earthdata para InSAR (ASF HyP3) | 0 USD; cuenta personal | P6 en fase de implementación |
| A8 | Usar un LLM local vía Ollama para NEUROVOICE | 0 USD; ≈1 GB de RAM y descarga del modelo ≈0,4–1 GB | P8 opcional |
| A9 | Instalar PyTorch u ONNX Runtime (CNN o reconocimiento de especies) | 0 USD; 15 MB–700 MB | Por ahora **no recomendado** salvo ONNX Runtime para fotos |
| A10 | Consultar formalmente a INGEMMET (licencia y diccionario de códigos) | 0 USD | Lo hace el usuario; desbloquea la interpretación de los procesos |
