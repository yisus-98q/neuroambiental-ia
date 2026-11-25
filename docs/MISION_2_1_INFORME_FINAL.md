# Misión 2.1 — Informe final: validación científica independiente

## Hechos observados

- La misión se ejecutó en el **equipo de 4 GB**, no en el de 32 GB.
- El repositorio estaba en `56424de`, quedó congelado con la etiqueta `mision-2.0-congelada` y pasaba **186 pruebas**.
- El protocolo se **prerregistró** (commit `610f756`) antes de consultar ningún dato externo.
- La regla eligió la zona **E, Callejón de Conchucos**: 148 eventos de los procesos evaluados, uno más que N.
- Se descargaron **27,9 MB** con autorización: inventario, litología y DEM. En disco ocupan ≈10 MB.
- **Independencia geográfica verificada:** 0 registros compartidos, 14,1 km entre eventos. **No hay independencia metodológica:** mismos estudios y autores.

## Resultados medidos

Ejecución `ea1cbb80`: pico de **413 MB**, ≈3 min.

| Modelo / hipótesis | AUC en Huaraz | AUC externo (IC 95 %) | Estado |
|---|---|---|---|
| Caídas: pendiente (H1) | 0,66–0,73 | **0,57** (0,43–0,65) | **NO VALIDADO** |
| Flujos: distancia a cauce (H2) | 0,72–0,76 | **0,76** (0,61–0,82) | **VALIDACIÓN INSUFICIENTE** (27 eventos) |
| Flujos con litología (H3) | 0,78–0,89 | **0,70** (sin «Sedimento»: 0,68) | **VALIDACIÓN INSUFICIENTE**; no mejora a M2 (0,76) |
| Pendiente + elevación (H4) | 0,74–0,81 | **0,64**, frente a 0,66 de la elevación sola | Se confirma que no aporta: **EXPERIMENTAL** |
| Mejor modelo general (M2, todos) | 0,83 | **0,65** (0,53–0,72) | **EXPERIMENTAL** |
| Pendiente sola, todos | 0,49–0,50 | **0,41** (0,36–0,47) | **NO VALIDADO** |

Otras mediciones:
- **Umbral de Huaraz en la zona externa:** el de elevación da sensibilidad 1,0 y especificidad 0,0.
- **Calibración:** se predice 0,85 donde se observa 0,39.
- **Bosque aleatorio:** 0,94 en entrenamiento y 0,62 fuera.

## Interpretación

1. **Ningún modelo generaliza lo bastante.** No hay ningún resultado «prometedor» y ninguno está «validado bajo alcance definido».
2. **La pendiente como predictor de caídas no se sostiene** fuera de Huaraz.
3. **Lo que se transfiere mejor es la elevación,** coherente con el sesgo de muestreo del inventario, más que con el peligro físico.
4. **La mejora de la litología en Huaraz era local o circular:** desaparece fuera.
5. **Los flujos son la única señal física coherente** en ambas zonas: TPI y distancia a cauce, con relación inversa a la pendiente. Pero el tamaño de muestra no permite concluir.

## Estado científico final de cada modelo

| Modelo | Estado |
|---|---|
| Índice heurístico de pendiente | NO VALIDADO |
| Pendiente para caídas | NO VALIDADO |
| Pendiente + elevación (base) | EXPERIMENTAL |
| Topográfico (5 variables) | EXPERIMENTAL |
| Topográfico + litología | EXPERIMENTAL (flujos: VALIDACIÓN INSUFICIENTE; circularidad no descartada) |
| Bosque aleatorio | EXPERIMENTAL / NO VALIDADO según el grupo (sobreajusta) |
| Distancia a cauce y TPI para flujos | VALIDACIÓN INSUFICIENTE (hipótesis prioritaria) |

## Limitaciones

Ver `MISION_2_1_LIMITACIONES_Y_RIESGOS.md`:
- una sola zona externa;
- 27 flujos externos;
- dependencia metodológica del inventario;
- pseudo-ausencias;
- cambio de dominio;
- IC amplios.

## Hipótesis pendientes

1. **H2 y H3 (flujos)** con una zona que tenga ≥ 30 flujos. La zona **N (Carhuaz–Yungay)** tiene 50.
2. **Si la señal de flujos (TPI y distancia a cauce) se mantiene** en una segunda zona.
3. **Si recalibrar el umbral por zona** resuelve el cambio de dominio sin introducir fuga.

## Recomendaciones

1. **Evaluar N como segunda zona externa**, aplicando sin cambios el mismo protocolo congelado. Son ≈28 MB y necesitan autorización.
2. **Conseguir inventarios de otras fuentes o autores** (SINPAD/INDECI, estudios recientes) para romper la dependencia metodológica.
3. **No usar operativamente ningún modelo,** ni sus umbrales ni sus probabilidades.
4. **Mantener MLP y CNN descartados** hasta tener miles de eventos independientes.

## Integración realizada

- **NEUROCORE:** `/api/neurocore/overview` → `validacion_externa`, con la fecha, la zona, los datasets, el estado, el AUC y el IC de cada modelo, las limitaciones y el historial.
- **NEURO PREDICTION:** cada elemento tiene `estado_cientifico`.
  - Las evaluaciones externas aparecen como «EVALUADO EXTERNAMENTE · mejor estado: …».
  - Las estimaciones sin evaluación externa figuran como «EXPERIMENTAL».
  - Solo los modelos aprobados figuran como «VALIDADO».
- **NEUROVOICE:** resume la evaluación externa y **siempre** añade que una estimación no es una predicción cierta de un desastre ni una alerta oficial.
- **API `/api/disasters/external`** y **CLI `validacion-externa`**.

## Pruebas

**189 pasan**: las 186 previas más 3 nuevas, sin eliminar ninguna. El frontend compila.


---

## Actualización: segunda zona (Carhuaz–Yungay, GitHub Actions)

- **Ejecutada en la nube** por falta de memoria local; **reproducibilidad verificada** frente a este equipo (44/48 AUC de entrenamiento idénticos; los datos tienen la misma huella salvo la codificación de los DEM).
- **H2 (distancia a cauce, flujos): VALIDACIÓN EXTERNA PROMETEDORA en N** (0,76; IC 0,71–0,79), con el mismo AUC en E. El estado combinado sigue siendo **VALIDACIÓN INSUFICIENTE**, porque E tiene solo 27 flujos y la regla prerregistrada no se relaja.
- **H1 refutada en dos zonas.** H3 no aporta. **H4 confirmada en dos zonas.**
- **Siguiente paso para H2:** una tercera zona con ≥ 30 flujos. La zona S (Recuay–Cátac) tiene 37. Si confirma, H2 podría pasar a revisión humana en el SCIENTIFIC VALIDATION ENGINE.
- Detalle en `MISION_2_1_RESULTADOS_CIENTIFICOS.md`, §5.
