# Protocolo de validación científica — NEUROAMBIENTAL IA

- **Versión:** 1.0 (25 nov. 2026).
- **Dónde se aplica:** NEURODISASTER (`app/modules/disasters/validation.py` y `protocol.py`) y el SCIENTIFIC VALIDATION ENGINE (`app/modules/validation/engine.py`).
- **Ámbito:** cualquier modelo geoespacial de la plataforma. Los modelos de NEURAL TRAINING con datos que tienen coordenadas **no** pueden validarse con un corte aleatorio.

## 1. Principios

1. **Criterios antes que resultados.** Los umbrales se registran en un experimento del SVE, se congelan con SHA-256 y no se editan. Cambiar algo exige un experimento nuevo.
2. **La prueba es independiente y sellada.** La región de prueba no toca ningún dato de entrenamiento ni de validación interna, y solo se evalúa una vez por protocolo.
3. **Nada se valida solo.** Hacen falta la prueba independiente, cumplir los criterios y dos aprobaciones humanas de personas distintas de los autores. Un rechazo revoca la validación.
4. **Los datos simulados nunca validan.**
5. **Un AUC aceptable no es validez científica.** Hay que revisar sesgos, circularidad, intervalos y generalización.

## 2. Separación de los datos

| Partición | Cómo se construye | Para qué |
|---|---|---|
| Entrenamiento / validación interna (cv) | Validación cruzada espacial por bloques: los bloques miden lo mismo que el alcance mediano del semivariograma, con un mínimo de 3×3. Hay una **zona de exclusión** de 500 m: se quitan del entrenamiento los puntos a menos de 500 m de cualquier punto de prueba del pliegue | Elegir variables y modelo; estimar el rendimiento |
| Prueba independiente (test) | Una región geográfica distinta, declarada en el experimento. Su DEM debe quedar dentro de ella, y ningún DEM de cv puede tocarla | La única evidencia de generalización |
| Referencia aleatoria | Validación cruzada estratificada aleatoria | Solo para mostrar cuánto infla la autocorrelación; **nunca** como evidencia |

**Temporal:** la mayoría de los eventos no tiene fecha de evento: `FECHA` parece ser la del estudio (2007). Por eso no se aplica una separación temporal. Las variables posteriores a los eventos, como el NDVI de 2024, se declaran como posible fuga temporal.

## 3. Etiquetas y pseudo-ausencias

- **Presencias:** un evento del inventario por celda. Varios eventos en la misma celda cuentan una vez.
- **Unidad de modelado:** el **tipo de proceso** (código `TIP_PELIGRO` con ≥ 30 eventos). Mezclar caídas y flujos anula señales opuestas. El significado de los códigos **no** está confirmado por INGEMMET.
- **Pseudo-ausencias:** celdas al azar a ≥ 300 m de cualquier evento, en proporción 3:1, con varios sorteos. «Sin evento inventariado» no significa «sin peligro».
- **Dos variantes, obligatorias:**
  - ausencias libres;
  - ausencias en la **misma franja de altura** (percentiles 5–95) que los eventos. Corrige el sesgo de muestreo del inventario, concentrado en valles habitados. **Los criterios se evalúan en esta variante.**
- **Datos faltantes:** las celdas sin dato (nubes, nieve o agua en el NDVI) se quitan **para todos los modelos del mismo sorteo**. Así las comparaciones usan los mismos puntos.

## 4. Modelos y referencias

| Modelo | Uso |
|---|---|
| Índice heurístico (pendiente/45°) y cada variable sola (sin entrenar) | Referencias directas |
| Solo elevación | Referencia del sesgo de muestreo |
| Regresión logística base (pendiente + elevación) | Referencia entrenada |
| Regresión logística topográfica (5 variables del DEM) | Modelo principal interpretable |
| + NDVI, + litología, + geomorfología | Candidatos. Solo se aceptan si mejoran ≥ 0,05 de AUC sobre los mismos puntos |
| Bosque aleatorio | Comparador no lineal. Árboles e hilos según el perfil de hardware |

Gradient Boosting, MLP o CNN solo se justifican con muchos más eventos que los actuales (33 a 68 por proceso). Ver `INFORME_RESULTADOS_ENTRENAMIENTO.md`.

## 5. Métricas y su interpretación

| Métrica | Qué permite concluir | Qué NO permite concluir |
|---|---|---|
| AUC por pliegue (media ± desviación) y AUC agrupado | Si el modelo ordena los eventos por encima de las ausencias en zonas no vistas | Una probabilidad real de ocurrencia |
| IC 95 % por bootstrap de **bloques** | La estabilidad. El límite inferior es el criterio | Generalización fuera del recorte |
| Variación entre sorteos de ausencias | Sensibilidad a la muestra de ausencias | — |
| PR-AUC (con su valor de azar) | Rendimiento con clases desbalanceadas | Comparaciones entre proporciones distintas |
| Precisión, recall, F1 y matriz de confusión (umbral de Youden elegido en entrenamiento) | Volumen de aciertos y errores | Que un falso positivo sea un error: puede ser un evento no inventariado |
| Brier | Comparación relativa de la calibración | La calibración absoluta (las pseudo-ausencias fijan la escala) |
| Razón de frecuencia geológica | Descripción | Capacidad predictiva (usa todos los eventos) |

## 6. Criterios mínimos recomendados para un experimento

| Criterio | Umbral |
|---|---|
| `auc_min` (prueba independiente, franja de altura) | 0,70 |
| `ic95_inf_min` | 0,60 |
| `mejora_min` sobre la referencia (solo elevación o la base) | 0,05 |
| Datos | Reales |

## 7. Sesgos y amenazas que se revisan siempre

1. **Sesgo de muestreo** del inventario (zonas pobladas y vías). Se controla con la variante de franja de altura.
2. **Circularidad.** La litología «Sedimento» y unidades geomorfológicas como abanicos o vertientes coluviales pueden contener los propios depósitos. El mapa de susceptibilidad de INGEMMET **no** se usa como variable.
3. **Fuga temporal.** Variables posteriores a los eventos (NDVI 2024).
4. **Ubicación del punto.** No se sabe si marca la escarpa, el cuerpo o el depósito del evento.
5. **Autocorrelación.** Se controla con bloques, zona de exclusión y bootstrap por bloques.
6. **Pocos eventos.** Hay que mirar los intervalos, no los puntos.

## 8. Reproducibilidad

- Cada ejecución guarda en `runs`: parámetros (DEM, inventario, capas, semilla, sorteos, bloques y zona de exclusión), el informe completo, los recursos (perfil, pico de memoria, estimación), el dataset exportado (SHA-256 en NEURODATA) y la auditoría.
- **Repetir:** `POST /api/disasters/susceptibility/validate` con los mismos IDs y la misma semilla. También se puede usar el CLI: `python -m app.cli importar-ingemmet`, `descargar-dem` e `importar-geologia`.
