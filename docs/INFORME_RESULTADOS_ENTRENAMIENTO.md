# Informe de resultados de entrenamiento y validación

- **Actualizado:** 25 nov. 2026.
- **Fuente de cada cifra:** ejecuciones registradas en la tabla `runs` de la base real. El ID se indica para poder verificarla en el panel NEURODISASTER → Ejecuciones.

## 1. Resumen

- **Modelos registrados en NEURAL TRAINING:** 0. **Modelos validados:** 0.
- **Experimentos de validación (SVE):** 0. No hay región de prueba independiente evaluada.
- **Qué se entrenó:** en las validaciones se entrenaron regresiones logísticas y bosques aleatorios **dentro de la validación cruzada espacial**, para medir qué capacidad predictiva tienen las variables. Ninguno se guardó como modelo operativo, porque **ninguno cumple los criterios** del protocolo: el límite inferior del IC 95 % queda siempre en 0,43–0,66 y no hay prueba independiente.
- **Estado:** **experimental**.

## 2. Datos usados (todos reales, recorte de Huaraz −77,75/−9,78/−77,25/−9,28)

| Dataset | Origen | Detalle | Licencia |
|---|---|---|---|
| Inventario de peligros geológicos | INGEMMET GEOCATMIN | 181 eventos: 1300: 68, 1500: 55, 1100: 33, 1600: 17, 1700: 8 | No declarada; uso interno |
| DEM | Copernicus GLO-30 | 1600×1600 a 0,0003125° (≈35 m); también uno de 500×500 a ≈110 m | Copernicus DEM, atribución |
| NDVI | Sentinel-2 L2A S2A_18LTQ_20240716 (0 % nubes) | 1600×1600 misma malla; 94,1 % válido; 39,8 MB descargados | Copernicus Sentinel, libre |
| Litología | INGEMMET 1:50 000, `TIPO_UNIDAD` | 1104 polígonos, 7 clases | Sin licencia abierta; uso interno |
| Geomorfología | INGEMMET regional, `SUBUNIDAD` | 473 polígonos, 17 clases | Sin licencia abierta; uso interno |

## 3. Configuración común

- **Pseudo-ausencias:** 3:1, a ≥ 300 m de cualquier evento; 5 sorteos con semillas 42–46.
- **Bloques espaciales:** automáticos por variograma, 3×3 de ≈18 km, con zona de exclusión de 500 m.
- **Umbral:** de Youden, elegido en entrenamiento.
- **IC 95 %:** 200 réplicas de bootstrap por bloques.
- **Regresión logística:** `StandardScaler` y `LogisticRegression(max_iter=1000)`.
- **Bosque aleatorio:** 100 árboles con profundidad máxima 6 y `min_samples_leaf` 5, según el perfil «ligero».
- **Perfil de hardware:** «ligero» (equipo de 4 GB). Pico ≈160–250 MB; ≈60–90 s por ejecución.

## 4. Resultados

Todos los valores son de la variante «franja de altura»: AUC espacial de la regresión logística, media ± desviación entre pliegues.

### 4.1 Evolución por etapa

| Etapa (ejecución) | Todos | 1100 caídas | 1300 deslizamientos | 1500 flujos |
|---|---|---|---|---|
| Pendiente sola, sin entrenar (110 m; `332ea8ed`) | 0,54 | 0,75 | 0,62 | 0,40 (inversa) |
| Pendiente + elevación (110 m; `332ea8ed`) | 0,74 ± 0,09 | 0,71 | 0,72 | 0,70 |
| Pendiente + elevación (35 m; `5c5e36cc`) | 0,76 | 0,68 | 0,70 | 0,73 |
| 5 variables del DEM (35 m; `12a39ce0`) | 0,74 ± 0,05 | 0,74 | 0,67 | 0,70 |
| + litología (`601e9c4a`) | 0,73 | 0,72 | 0,67 | **0,78** (IC 0,67–0,84)* |
| + litología + geomorfología (`c229d09b`) | 0,77 | 0,76 | 0,69 | 0,74* |
| **+ NDVI** (`235994a9`; mismos puntos) | 0,74 → **0,73** | 0,77 → 0,78 | 0,67 → **0,64** | 0,71 → **0,70** |

\* Posible circularidad: «Sedimento» y unidades geomorfológicas pueden contener los depósitos de los propios eventos.

### 4.2 Variables solas, sin entrenar (35 m, franja de altura)

- **Pendiente:**
  - 1100: AUC 0,73, mayor en eventos;
  - 1500: 0,40, relación inversa.
- **Distancia a cauce:** 1500: 0,72, menor en eventos (mediana 69 m frente a 195 m).
- **NDVI en anillo:** 0,53–0,61 según el grupo. Es *mayor* en eventos (0,37 frente a 0,31–0,34), lo que encaja con el sesgo hacia valles habitados y cultivados.

## 5. Conclusiones científicas

1. **El índice heurístico de pendiente no sirve** para todos los procesos mezclados (AUC 0,49–0,54). Solo es útil para las probables caídas (1100).
2. **El AUC 0,74 de pendiente + elevación no prueba validez.** Se explica casi solo por la elevación y por el sesgo de muestreo del inventario.
3. **Cada proceso responde a la variable que predice la física:** las caídas a la pendiente y los flujos a la cercanía a cauces.
4. **El NDVI NO mejora el modelo** en ningún grupo (−0,03 a +0,01), y además es posterior a los eventos. Se mantiene solo como variable descriptiva.
5. **La litología mejora los flujos (0,78),** pero con circularidad posible. Hay que comprobarlo con una prueba independiente antes de aceptarla.
6. **Con 33–68 eventos por proceso, combinar variables apenas aporta.** Una variable física por proceso es más defendible que un modelo multivariable.

## 6. Modelos más complejos: decisión razonada

| Modelo | Decisión | Motivo |
|---|---|---|
| Gradient Boosting / HistGradientBoosting | No entrenado | Con 33–68 eventos el bosque aleatorio ya iguala o empeora a la regresión logística. Más capacidad solo aumentaría el sobreajuste |
| MLP | No entrenado | Requiere miles de ejemplos; no puede demostrar ventaja con validación espacial |
| CNN / segmentación | No entrenado | No hay polígonos de deslizamientos ni imágenes etiquetadas. Requeriría PyTorch (no instalado) y una GPU compatible (la HD 3000 no lo es) |
| Series temporales | No entrenado | No hay series de eventos fechados; los sensores de NEUROTERRAIN no tienen datos reales cargados |

Estos modelos se reconsiderarán cuando haya más eventos: todo Áncash, otras regiones o un inventario poligonal.

## 7. Próximos pasos

1. **Prueba independiente:** un experimento del SVE con criterios congelados y una región fuera de Huaraz, como el Callejón de Conchucos o Recuay sur. Requiere DEM, inventario y litología de esa región (≈20 MB).
2. **Máscara de hielo y agua para las ausencias**, a partir de la clase SCL de Sentinel-2.
3. **Consultar a INGEMMET** el diccionario de `TIP_PELIGRO` y la fecha real de los eventos.
