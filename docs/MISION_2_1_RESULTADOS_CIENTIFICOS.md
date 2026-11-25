# Misión 2.1 — Resultados científicos (evaluación externa en el Callejón de Conchucos)

- **Ejecución:** `ea1cbb80cd07435bb8af53da15ec28d4`.
- **Resultado completo:** `datasets/resultados/mision_2_1_validacion_externa_E.json`, con todas las métricas, ambas variantes y los 12 modelos de cada grupo.
- **Entrenamiento:** solo Huaraz, semilla 42.
- **Evaluación:** zona E, 10 sorteos de pseudo-ausencias (semillas 100–109), IC 95 % por bootstrap de bloques 3×3. **Umbral fijado en Huaraz.**

## 1. Hipótesis prerregistradas

AUC en la zona externa, variante franja, media de 10 sorteos.

| Hipótesis | Modelo | AUC en Huaraz (entrenamiento) | **AUC externo** (IC 95 %) | Estado |
|---|---|---|---|---|
| **H1** La pendiente discrimina las caídas (1100) | V-pendiente | 0,66 | **0,57** (0,43–0,65) | **NO VALIDADO** |
| **H2** La distancia a cauce discrimina los flujos (1500) | V-dist_cauce | 0,76 | **0,76** (0,61–0,82) | **VALIDACIÓN INSUFICIENTE** (27 eventos < 30) |
| **H3** La litología mejora los flujos sin «Sedimento» | M3 / M3s / M2 | 0,89 / 0,89 / 0,85 | **0,70 / 0,68 / 0,76** | **INSUFICIENTE**; además la litología **no** mejora fuera de Huaraz |
| **H4** Pendiente + elevación no supera a la elevación sola | M1 frente a R1 | 0,81 frente a 0,80 | **0,64 frente a 0,66** (todos) | **Se sostiene**: la pendiente no aporta sobre la elevación |

## 2. Resumen por grupo (AUC externo en franja ± desviación entre sorteos)

| Modelo | Todos (181) | 1100 caídas (39) | 1300 deslizamientos (82) | 1500 flujos (27)* |
|---|---|---|---|---|
| R1 solo elevación | 0,66 ± 0,01 | 0,57 ± 0,03 | 0,67 ± 0,02 | 0,73 |
| R2 heurístico pendiente | 0,41 | 0,57 | 0,43 | 0,27 (inversa) |
| V-pendiente | 0,41 | 0,57 | 0,43 | 0,73† |
| V-TPI | 0,60 | 0,62 | 0,52 | 0,78 |
| V-dist_cauce | 0,58 | 0,49 | 0,56 | 0,76 |
| M1 base | 0,64 | 0,59 | 0,66 | 0,72 |
| M2 topográfico | 0,65 (0,53–0,72) | 0,65 (0,49–0,75) | 0,66 (0,53–0,75) | 0,76 (0,57–0,90) |
| M3 topo + litología | 0,65 | 0,63 | 0,66 | 0,70 |
| M3s sin «Sedimento» | 0,63 | 0,64 | 0,66 | 0,68 |
| M4 bosque aleatorio | 0,62 | 0,67 (0,56–0,80) | 0,65 | 0,75 |

\* Por debajo del mínimo de 30 eventos: **validación insuficiente** para todo el grupo.
† Con el signo aprendido en Huaraz (menor pendiente indica más flujos): la relación inversa **se reproduce** fuera de Huaraz.

**Estados finales:** ningún modelo llega a «VALIDACIÓN EXTERNA PROMETEDORA».
- **Todos y 1300:** «EXPERIMENTAL» (AUC 0,60–0,67, por debajo de 0,70) o «NO VALIDADO» (pendiente, curvatura, distancia a cauce y bosque).
- **1100:** casi todo «NO VALIDADO»; el bosque aleatorio y la litología, «EXPERIMENTAL».
- **1500:** «VALIDACIÓN INSUFICIENTE».

## 3. Más allá del AUC

### Cambio de dominio
- Los mismos modelos pierden entre 0,10 y 0,30 de AUC al salir de Huaraz. Por ejemplo, M2 en todos los procesos pasa de 0,83 a 0,65.
- El bosque aleatorio cae de 0,94–0,97 a 0,62–0,67: **sobreajuste**.

### Umbral de Huaraz aplicado en Conchucos
La zona externa es ≈400 m más baja, así que el umbral transfiere mal:

| Modelo y grupo | Sensibilidad | Especificidad |
|---|---|---|
| Solo elevación, en 1100 y 1500 | 1,00 | 0,00 (todo se clasifica como evento) |
| M2 en todos | 0,90 | 0,23 |

### Calibración (M2, todos)
Las probabilidades no son transferibles, ni siquiera de forma relativa.

| Probabilidad media predicha | 0,14 | 0,28 | 0,44 | 0,61 | 0,85 |
|---|---|---|---|---|---|
| Tasa observada | 0,13 | 0,16 | 0,26 | 0,31 | 0,39 |

### Pseudo-ausencias y sesgo de muestreo
- Con ausencias libres, los AUC externos suben unos 0,10–0,15 (todos: M2 0,77 libre frente a 0,65 franja). La elevación sigue explicando gran parte de la señal también fuera de Huaraz.
- Variación entre sorteos: desviación de 0,01 a 0,04. **La incertidumbre la dominan los bloques espaciales**, no los sorteos de ausencias.

### Litología y circularidad
- En todos los procesos, M3 (0,65) es igual a M2 (0,65).
- En flujos, M3 (0,70) es peor que M2 (0,76).
- La mejora de 0,70 a 0,78 observada en Huaraz **no se reproduce** fuera: es coherente con un efecto local o circular de «Sedimento».

### Los flujos, a pesar de ser insuficientes
TPI (0,78; IC 0,71–0,87), distancia a cauce (0,76) y pendiente inversa (0,73) mantienen la dirección física esperada en la zona externa. **Es la señal más consistente de las dos misiones**, pero con 27 eventos no permite concluir.

## 4. Entrenamiento adicional (Fase H)

- **No se justifica.** El bosque aleatorio no supera al modelo lineal M2 de forma consistente: −0,03 en todos, +0,02 en caídas y −0,01 en deslizamientos, dentro del ruido. Por el criterio prerregistrado no se entrenan HistGradientBoosting ni Gradient Boosting.
- **MLP y CNN quedan excluidos:** hay < 1000 eventos independientes por proceso, no hay imágenes etiquetadas y la independencia metodológica es incompleta.
- **Lo que haría falta:** más eventos independientes, especialmente flujos, y una segunda zona externa.


---

## 5. Segunda zona externa: Carhuaz–Yungay (N), ejecutada en GitHub Actions

- **Plan:** anexo prerregistrado `MISION_2_1_ANEXO_SEGUNDA_ZONA.md` (commit `cd21595`), confirmado antes de descargar o evaluar.
- **Ejecución:** GitHub Actions, run `45527139022`, commit `b76d79f`, perfil «estándar». Este equipo no tenía memoria suficiente: la evaluación necesitaba ≈560 MB con el margen, y el pico en la nube fue de 517 MB.
- **Resultado completo:** `datasets/resultados/mision_2_1_validacion_externa_N.json`. Registrado en la base local como la ejecución `9a434627…`, con su origen.

### Reproducibilidad entre equipos (Windows local frente a Linux en la nube)

- **SHA-256 idéntico** en los inventarios y en la litología de Huaraz y de N: la nube descargó los mismos datos.
- **SHA-256 distinto en los DEM.** Las elevaciones, sin embargo, son las mismas: los **44 de 48 AUC de entrenamiento** de Huaraz son idénticos en ambos equipos. Solo cambia el bosque aleatorio, por la diferencia de árboles indicada abajo. La diferencia está en la codificación del GeoTIFF (GDAL de Windows frente al de Linux), no en los valores.
- **Desviación declarada:** el perfil «estándar» usa 200 árboles en M4 (bosque aleatorio), frente a 100 en el equipo local. Solo afecta a M4.

### Independencia

0 registros compartidos con Huaraz y con E. Distancia mínima de 6,9 km a Huaraz (es la misma cuenca del Callejón de Huaylas, menos independiente que E) y de 34,9 km a E. Inventario dominado por Valderrama y Luque, 2007.

### Resultados en N (franja de altura, 10 sorteos)

| Hipótesis | Modelo | AUC N (IC 95 %) | Estado N | AUC E | Estado E | **Estado combinado** (regla del anexo) |
|---|---|---|---|---|---|---|
| **H1** Caídas: pendiente | V-pendiente | 0,59 (0,44–0,68) | NO VALIDADO | 0,57 | NO VALIDADO | **NO VALIDADO**, refutada en 2 zonas |
| **H2** Flujos: distancia a cauce | V-dist_cauce | **0,76 ± 0,02 (0,71–0,79)**; +0,16 sobre la elevación | **VALIDACIÓN EXTERNA PROMETEDORA** | 0,76 | INSUFICIENTE (27 ev.) | **VALIDACIÓN INSUFICIENTE** |
| **H3** Flujos: litología | M3 / M3s / M2 | 0,70 / 0,69 / 0,67 | EXPERIMENTAL | 0,70 / 0,68 / 0,76 | INSUFICIENTE | **EXPERIMENTAL**: mejora < 0,05; no aporta de forma consistente |
| **H4** Pendiente + elevación | M1 frente a R1 | 0,72 frente a 0,73 | — | 0,64 frente a 0,66 | — | **Confirmado en 2 zonas**: la pendiente no aporta sobre la elevación |
| Caídas: bosque aleatorio | M4 | 0,71 (0,63–0,78) | PROMETEDORA | 0,67 | EXPERIMENTAL | **EXPERIMENTAL** |
| General (todos) | M2 | 0,74 (0,67–0,82) | EXPERIMENTAL | 0,65 | EXPERIMENTAL | **EXPERIMENTAL** |

Además:
- **Deslizamientos (1300) en N:** la mayoría de los modelos quedan en «insuficiente» por IC anchos. Con ausencias libres el AUC llega a 0,86, frente a 0,63 en la franja, y la especificidad baja a 0,01–0,04 con el umbral de Huaraz. Es el sesgo de elevación en su forma más fuerte.
- **Umbral:** el de Huaraz sigue sin transferirse; con la elevación, en flujos, la especificidad es 0,00.

### Interpretación

1. **H2 es la evidencia más sólida de todo el proyecto.**
   - La distancia a cauce discrimina los flujos con el **mismo AUC (0,76) en dos zonas externas** y en Huaraz (0,72–0,76).
   - En N cumple todos los criterios de «prometedora».
   - **No llega a validarse** porque, por la regla fijada de antemano, E tiene solo 27 flujos. No se rebajó ningún criterio para que pasara.
2. **La pendiente como indicador de caídas queda refutada** en dos zonas.
3. **La litología no aporta de forma consistente** fuera de Huaraz: la mejora original era local o circular.
4. **El bosque aleatorio para caídas fue prometedor en N pero no en E:** resultado inestable entre zonas.
5. **Ningún modelo está «VALIDADO BAJO ALCANCE DEFINIDO».**
