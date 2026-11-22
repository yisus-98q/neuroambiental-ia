# Modelos de IA: estado honesto

**No existe ningún modelo de IA entrenado en este proyecto.** Las carpetas `ai/datasets`, `ai/evaluation` y `ai/models` están vacías y reservadas.

## Qué hay hoy

| Componente | Cómo funciona realmente |
|---|---|
| NEUROCORE (intérprete) | Reglas: normaliza el texto y cuenta palabras clave por módulo. No aprende ni entiende contexto. |
| NEUROVOICE | Usa ese intérprete y responde con conteos reales de la base y el contrato del módulo. Solo texto en español. Sin voz, sin modelo de lenguaje, sin otros idiomas. Puede no entender frases complejas. |
| NEUROTRAINING | Solo **registra** modelos con nombre, módulo, algoritmo previsto y descripción de datos. Todo modelo nace `planificado` y la API no permite cambiar su estado ni entrenar. No hay ejecuciones. |
| Predicción ambiental, catástrofes, minería, biodiversidad, terreno | Sin análisis ni modelos: solo el contrato del módulo. |
| Alertas | Las crea una persona. No hay alertas automáticas. |

## Estados de un modelo

`planificado` → `en_entrenamiento` → `entrenado` → `validado` → `retirado` (definidos en el esquema; hoy solo se usa `planificado`).

## Criterios propuestos para marcar un modelo como «validado»

Aún no hay mecanismo que lo haga; esto es lo que debería cumplirse cuando exista:

1. Conjunto de datos descrito, con fuente, licencia y fecha, sin datos simulados mezclados con reales.
2. Separación de entrenamiento y prueba (y, si hay tiempo o espacio, validación cruzada por zonas/fechas) para evitar fuga de datos.
3. Métricas apropiadas guardadas en `ai_models.metrics`, comparadas con una línea base simple.
4. Incertidumbre explícita en cada predicción (`predictions.uncertainty`, obligatoria).
5. Revisión por una persona experta del dominio; evidencia guardada (`validation_evidence`).
6. Versión y artefacto reproducibles.

Mientras no se cumpla, cualquier salida debe presentarse como experimental. Ningún modelo puede predecir la fecha exacta de terremotos, explosiones u otros eventos.

## Restricciones por 4 GB de RAM

- Sin modelos de lenguaje grandes ni redes profundas en el equipo.
- Preferir scikit-learn (árboles, regresión) con conjuntos tabulares pequeños.
- Imágenes satelitales por bloques, nunca completas en memoria.
- Entrenar un modelo a la vez y con el navegador y otras aplicaciones cerradas.
- Si se necesita GPU o más memoria, ver costos y alternativas en [COSTS.md](../COSTS.md).
