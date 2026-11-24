# Misión 2.1 — Protocolo de validación externa (PRERREGISTRADO)

- **Fijado** el 25 nov. 2026, **antes** de consultar el inventario de cualquier zona candidata y antes de evaluar ningún modelo fuera de Huaraz. El commit Git de este documento es la prueba de su fecha.
- **Referencia científica congelada:** etiqueta `mision-2.0-congelada` (commit `56424de`).
- **Regla de cambio:** cualquier desviación posterior se documenta como desviación. No se modifica este texto.

## 1. Zona de entrenamiento (fija)

**Huaraz:** −77,75 / −9,78 / −77,25 / −9,28 (0,5° × 0,5°). Datos: inventario INGEMMET, DEM GLO-30 a 0,0003125° (≈35 m) y litología INGEMMET 1:50 000.

## 2. Regla de selección de la zona externa (decidida sin mirar resultados)

**Candidatas:** recortes de 0,5° × 0,5° en los Andes de Áncash, separados ≥ 5 km (0,045°) del recorte de entrenamiento.

| Código | Nombre | minLon, minLat, maxLon, maxLat |
|---|---|---|
| N | Carhuaz–Yungay–Caraz (Callejón de Huaylas, norte) | −78,00, −9,235, −77,50, −8,735 |
| S | Recuay–Cátac (Callejón de Huaylas, sur) | −77,60, −10,325, −77,10, −9,825 |
| E | Callejón de Conchucos (Chavín–Huari) | −77,205, −9,60, −76,705, −9,10 |
| O | Cordillera Negra (vertiente occidental) | −78,295, −9,78, −77,795, −9,28 |

**Regla:**
1. Para cada candidata se cuentan **solo** los eventos por código `TIP_PELIGRO` (1100, 1300 y 1500), con una consulta de conteo al servicio. No se miran sus variables ni ningún resultado.
2. Es elegible si tiene **≥ 30 eventos en al menos 2** de esos 3 procesos.
3. Entre las elegibles se elige la de **mayor número total** de eventos de esos 3 procesos. No hay otro criterio de desempate.
4. Si ninguna es elegible, **no se fuerza la validación**: se declara que los datos no permiten concluir.

## 3. Independencia y fuga de información (se comprueba antes de evaluar)

- **Sin solapamiento:** separación ≥ 5 km entre recortes.
- **Sin registros compartidos:** ningún `COD_INV` y ninguna coordenada idéntica (al metro) en ambos inventarios.
- **Ninguna etiqueta externa** interviene en el entrenamiento, ni en la elección de variables, ni en el umbral.
- **Variables temporalmente compatibles:** solo variables del terreno y de la geología, que son estables a escala de décadas. **El NDVI se excluye**: Sentinel-2 es posterior a los eventos y en Huaraz no mejoró.
- **Limitación aceptada:** gran parte del inventario procede del mismo estudio de 2007 y de los mismos autores. La evaluación es **geográficamente** independiente, pero no **metodológicamente** independiente.

## 4. Modelos y referencias (por proceso: 1100, 1300, 1500, y todos juntos)

Todo se entrena **solo con Huaraz**: semilla 42, ausencias 3:1 a ≥ 300 m.

| Id | Modelo | Entrenamiento |
|---|---|---|
| R0 | Azar | AUC 0,5 (referencia teórica) |
| R1 | Solo elevación | Dirección elegida en Huaraz |
| R2 | Índice heurístico pendiente/45° | Sin entrenamiento |
| V* | Cada variable sola (pendiente, elevación, curvatura, TPI, distancia a cauce) | Dirección elegida en Huaraz |
| M1 | Regresión logística base (pendiente + elevación) | Huaraz |
| M2 | Regresión logística topográfica (5 variables) | Huaraz |
| M3 | M2 + litología (clases con ≥ 2 % del área en **Huaraz**) | Huaraz |
| M3s | M3 **sin la clase «Sedimento»** (prueba de circularidad) | Huaraz |
| M4 | Bosque aleatorio topográfico | Huaraz |

- **Umbral de clasificación:** Youden sobre las predicciones de Huaraz. **Fijado antes** de ver la zona externa.
- **Ausencias externas:** las mismas reglas (3:1, ≥ 300 m de cualquier evento externo). Dos variantes:
  - libres;
  - en la franja de altura de los eventos externos (P5–P95).

  **10 sorteos** (semillas 100–109). Los criterios se aplican a la **variante franja**; la libre se informa.

## 5. Hipótesis prerregistradas

| Id | Hipótesis | Modelo |
|---|---|---|
| H1 | La pendiente discrimina las probables caídas (1100) fuera de Huaraz | V-pendiente en 1100 |
| H2 | La distancia a cauce discrimina los probables flujos (1500) fuera de Huaraz | V-dist_cauce en 1500 |
| H3 | La litología mejora los flujos fuera de Huaraz **sin depender de «Sedimento»** | M3 frente a M3s frente a M2, en 1500 |
| H4 | Pendiente + elevación no generaliza mejor que la elevación sola (sesgo de muestreo) | M1 frente a R1 |

## 6. Métricas (en la zona externa)

- ROC-AUC con **IC 95 % por bootstrap de bloques** (3×3 bloques en la zona externa).
- PR-AUC y su valor de azar.
- Brier y una curva de calibración en 5 tramos, relativa a las pseudo-ausencias.
- Con el umbral fijado en Huaraz: matriz de confusión (VP, FP, VN, FN), precisión, sensibilidad, especificidad y F1.
- Media y desviación del AUC entre los 10 sorteos.

## 7. Criterios de estado (por modelo y proceso)

| Estado | Condición |
|---|---|
| VALIDACIÓN INSUFICIENTE | < 30 eventos externos del proceso, o IC 95 % no calculable o de anchura > 0,30 |
| NO VALIDADO | AUC externo < 0,60, o límite inferior del IC 95 % < 0,50 |
| EXPERIMENTAL | Ninguna de las otras condiciones (resultado intermedio, sin evidencia suficiente) |
| VALIDACIÓN EXTERNA PROMETEDORA | AUC externo ≥ 0,70, **e** IC 95 % inferior ≥ 0,60, **y** mejora ≥ 0,05 sobre R1 (solo elevación) en la variante franja, **y** desviación entre sorteos ≤ 0,03, **y** sin sospecha de circularidad. Para M3, solo si M3s también cumple |
| VALIDADO BAJO ALCANCE DEFINIDO | Todo lo anterior **más**: una segunda zona externa independiente, reproducibilidad verificada y **dos aprobaciones humanas** en el SCIENTIFIC VALIDATION ENGINE. **No alcanzable en esta misión** con una sola zona y sin revisores |

**Un resultado prometedor no se convierte automáticamente en aprobación.**

## 8. Entrenamiento adicional (solo después de la evaluación)

- MLP y CNN quedan **excluidos de antemano** mientras haya < 1000 eventos independientes por proceso y no existan imágenes etiquetadas.
- HistGradientBoosting o Gradient Boosting solo si M4 (bosque aleatorio) supera a M2 en la zona externa, que sería una señal de no linealidad aprovechable.
