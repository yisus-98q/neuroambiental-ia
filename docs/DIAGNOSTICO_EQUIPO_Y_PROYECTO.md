# Diagnóstico del equipo y del proyecto — NEUROAMBIENTAL IA 2.0

- **Fecha:** 25 nov. 2026.
- **Método:** todo lo de este documento se **midió en este equipo**, salvo lo marcado como [I] (inferencia).

## 1. Equipo en el que se ejecutó el diagnóstico

| Elemento | Valor medido |
|---|---|
| Procesador | Intel Core i5-2410M a 2,30 GHz (2 núcleos, 4 hilos; generación de 2011) |
| RAM | **3,94 GB** en total; ≈0,37–0,63 GB libres durante el diagnóstico |
| GPU | Intel HD Graphics 3000 (≈1,8 GB compartidos). **No admite CUDA ni aceleración útil para aprendizaje automático** |
| Almacenamiento | C: 4,4 GB libres de 195 GB (crítico). D: 185,5 GB libres de 252 GB |
| Unidades extraíbles | Ninguna. E: es una unidad óptica sin disco; **no hay USB conectado** |
| Sistema operativo | Windows 10 Pro 10.0.19045, 64 bits |
| Python | 3.14.7 (`C:\Python314`); dependencias en `backend/.deps` (≈462 MB) |
| Node.js / npm | v24.20.0 / 12.2.0; `frontend/node_modules` ≈155 MB |
| Git / GitHub CLI | git 2.55.0; gh 2.103.1 con sesión iniciada en github.com |
| Antivirus | Avast elimina los `.exe` nuevos (entornos virtuales) y algunos `.bat`; por eso se usa `.deps` con PYTHONPATH |

**Conclusión: este es el EQUIPO SECUNDARIO (4 GB), no el de 32 GB.** La misión describe un equipo principal de 32 GB que no está disponible en esta sesión. En consecuencia:
- No se ejecuta ningún entrenamiento pesado aquí.
- Todo lo pesado se deja preparado (perfiles, scripts y paquete portátil) para ejecutarlo en el equipo principal.
- Los perfiles de hardware (Fase 8) detectan la memoria y eligen los límites automáticamente.
- Con 4,4 GB libres en C:, todo lo nuevo se escribe en D:.

## 2. Estado del proyecto (verificado, no supuesto)

| Comprobación | Resultado |
|---|---|
| Pruebas de backend | **171 pasan** en 86 s. El informe anterior decía 155; desde entonces se añadieron pruebas en las fases de validación |
| Compilación del frontend | Correcta (Vite, 1,2 s) |
| Git | Rama `master`, 25 commits, árbol limpio, **sin remoto configurado**. El archivo versionado más grande pesa 192 KB (`paises.geojson`); `.git` ocupa 876 KB |
| Datos | `data/` excluido de git; 13 MB en `data/uploads`. La copia de seguridad previa a la migración está en `data/backups/` |
| Servidor | FastAPI + SQLite en 127.0.0.1:8000; la comprobación de salud responde «ok» |

### Dependencias principales (versiones instaladas)

fastapi 0.165.0 · sqlalchemy 2.1.9 · alembic 1.20.1 · pydantic 2.14.4 · uvicorn 0.54.0 · numpy 2.5.5 · scipy 1.18.1 · scikit-learn 1.9.1 · rasterio 1.5.2 · opencv-python-headless 4.14.0.94 · joblib 1.6.0. Frontend: React 19, TypeScript 7, Vite 8, MapLibre 6, Three.js 0.187.

### Módulos: estado calculado a partir de las capacidades implementadas

| Módulo | Estado | Capacidades |
|---|---|---|
| NEURODATA | operativo | 7/7 |
| NEURO 3D LAB | operativo | 6/6 |
| Alertas | parcial | 5/6 |
| Ambiental (Sentinel-2, NDVI) | parcial | 5/9 |
| NEUROTERRAIN | parcial | 4/5 |
| NEUROCONSTRUCTION | parcial | 4/7 |
| NEURAL TRAINING | parcial | 7/10 |
| NEUROVOICE | parcial | 5/8 |
| Validación científica (SVE) | parcial | 5/7 |
| NEURODISASTER | parcial | 3/7 |
| NEUROVISION (OpenCV) | parcial | 3/6 |
| NEURO PREDICTION | parcial | 2/4 |
| Biodiversidad | parcial | 2/6 |
| NEUROGEO | en desarrollo | 0/5 |
| NEUROMINING | en desarrollo | 0/5 |
| NEUROINDUSTRIAL | en desarrollo | 0/3 |

### Datos y modelos en la base real

**Registros:** 9 CSV, 3 GeoJSON, 2 DEM y 1 escenario heurístico; ninguno simulado.
- **GeoJSON:** el inventario INGEMMET y las capas de litología y geomorfología.
- **DEM:** el de 110 m y el de 35 m.

**Modelos:** 0 registrados y **0 validados**.

**Ejecuciones:** 15, entre ellas las validaciones de Huaraz.

**Usuarios:** 1 (administrador).

### Estado científico (de los informes anteriores, verificable en el historial de ejecuciones)

- **Mezclando procesos**, la pendiente no discrimina (AUC 0,49).
- **Pendiente + elevación** da 0,74 tras corregir el sesgo de altura, explicado casi solo por la elevación.
- **Por proceso:**
  - probables caídas (1100): la pendiente sola da AUC 0,73;
  - probables flujos (1500): la distancia a cauce da 0,72 y, con litología, el modelo llega a 0,78, con posible circularidad.
- **Ningún modelo está validado**, porque no hay prueba independiente fuera de Huaraz.

## 3. Riesgos detectados

1. **Equipo de 4 GB:** procesos de más de ≈300 MB pueden agotar la memoria. Claude Code ya detuvo una vez el servidor por falta de memoria.
2. **C: casi lleno (4,4 GB):** las cachés de pip, npm o uv pueden llenarlo. Hay que dirigir las cachés a D:.
3. **Avast:** borra los `.exe` de los entornos virtuales y ha borrado `.bat` con finales LF. Los `.bat` nuevos deben usar CRLF y tener una alternativa en Python.
4. **Sin remoto Git:** todo el trabajo existe en un solo disco; GitHub es urgente como respaldo.
5. **Sin USB conectado:** el paquete portátil se puede preparar en D:, pero no copiar ni verificar en el USB.

## 4. Decisiones que requieren al usuario

- Publicar el repositorio en GitHub (nombre, público o privado). Es una acción externa.
- Descargar voces de Piper (≈60 MB por voz) u otros modelos de voz.
- Conectar el USB para copiar y verificar el paquete portátil.
- Ejecutar el entrenamiento y la validación pesados en el equipo de 32 GB.
