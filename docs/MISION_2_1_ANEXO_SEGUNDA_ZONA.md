# Misión 2.1 — Anexo: segunda zona externa (decidido ANTES de ver sus datos)

- **Fecha:** 24 nov. 2026, según el reloj del equipo. Autorizado por el usuario: «Autoriza la evaluación en Carhuaz–Yungay».
- **Motivo:** la zona E (Callejón de Conchucos) tenía solo 27 flujos, de modo que H2 y H3 quedaron en «validación insuficiente». El protocolo (§7) exige una **segunda zona externa independiente** para pasar de «prometedor».
- **Zona:** **N, Carhuaz–Yungay–Caraz (Callejón de Huaylas norte)**, −78,00 / −9,235 / −77,50 / −8,735. Es la segunda en número de eventos según la misma regla de selección; sus conteos ya figuran en `MISION_2_1_DATASETS_Y_PROCEDENCIA.md`.
- **Protocolo:** **idéntico** a `MISION_2_1_PROTOCOLO_VALIDACION_EXTERNA.md` (commit `610f756`): mismos modelos entrenados solo en Huaraz, semilla 42, umbral fijado en Huaraz, ausencias externas con semillas 100–109, variantes libre y franja, IC por bootstrap de bloques 3×3, y mismos criterios de estado. **No se cambia ningún criterio ni se añaden modelos.**
- **Regla de combinación de las dos zonas (fijada ahora):**
  - Un modelo es candidato a «VALIDADO BAJO ALCANCE DEFINIDO» solo si alcanza «VALIDACIÓN EXTERNA PROMETEDORA» **en ambas zonas** con evaluación suficiente (≥ 30 eventos), **y** después obtiene dos aprobaciones humanas en el SCIENTIFIC VALIDATION ENGINE.
  - Si una zona es insuficiente, el modelo conserva el estado más bajo que tenga.
  - Un resultado favorable en N **no** compensa uno desfavorable en E.
- **Riesgo conocido:** N es contigua al valle de Huaraz (mismo Callejón de Huaylas, ≥ 5 km de separación). Es más parecida a Huaraz que E, así que su independencia ambiental es menor: un buen resultado en N es evidencia más débil que en E.
