# Misión 2.1 — Reproducibilidad

## Versiones

- **Referencia:** etiqueta `mision-2.0-congelada` (`56424de`). Protocolo prerregistrado en el commit `610f756`.
- **Python** 3.14.7 · **scikit-learn** 1.9.1 · **numpy** 2.5.5 · **scipy** 1.18.1 · **rasterio** 1.5.2.
- **Lista fijada:** `requirements-lock.txt` del paquete portátil.

## Pasos (desde `backend/`, con `PYTHONPATH=.deps`)

```
# 1. Datos de la zona externa (≈28 MB transferidos)
python -m app.cli importar-ingemmet --bbox=-77.205,-9.60,-76.705,-9.10
python -m app.cli importar-geologia --bbox=-77.205,-9.60,-76.705,-9.10 --capas litologia
python -m app.cli descargar-dem     --bbox=-77.205,-9.60,-76.705,-9.10

# 2. Evaluación externa (los IDs salen de los pasos anteriores y de la misión 2.0)
python -m app.cli validacion-externa --dem-a 32108f1b… --inv-a d47196d8… --lito-a 8575041e…
       --dem-b c556e14e… --inv-b 0e8516c4… --lito-b 733b8830… --zona "E · Callejón de Conchucos"
       --salida ../datasets/resultados/mision_2_1_validacion_externa_E.json
```

## Semillas y parámetros fijos

- **Entrenamiento:** semilla 42, pseudo-ausencias 3:1 a ≥ 300 m, ausencias libres.
- **Evaluación externa:** semillas 100–109; variantes libre y franja (P5–P95 de la altura de los eventos externos); 3×3 bloques; 200 réplicas de bootstrap.
- **Litología:** clases con ≥ 2 % del área **en Huaraz**; «Sedimento» excluido en M3s.
- **Hiperparámetros:**
  - regresión logística: `StandardScaler` y `max_iter=2000`;
  - bosque aleatorio: 100 árboles (perfil ligero), profundidad máxima 6, `min_samples_leaf` 5.
- **Verificación de datos:** comparar el SHA-256 de cada dataset con su manifiesto (`datasets/manifiestos/`).

## Pruebas que protegen el método (`tests/backend/test_external_validation.py`)

- Reglas de estado exactamente iguales al protocolo prerregistrado.
- **Sin fuga de etiquetas:** cambiar las etiquetas externas no altera nada del entrenamiento.
- Integración en NEUROCORE, NEURO PREDICTION y NEUROVOICE, con las advertencias obligatorias.

## Variación esperada

Con los mismos datos y semillas, los resultados deben ser **idénticos**. Un número distinto de árboles del bosque (perfil «potente»: 300) solo cambia M4.
