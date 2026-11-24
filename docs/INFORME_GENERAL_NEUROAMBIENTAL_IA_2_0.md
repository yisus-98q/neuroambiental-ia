# Informe general — NEUROAMBIENTAL IA 2.0

- **Fecha:** 25 nov. 2026.
- **Repositorio:** https://github.com/yisus-98q/neuroambiental-ia (privado). Cada fase tiene su commit publicado.
- **Equipo de trabajo de esta sesión:** el **secundario de 4 GB** (i5-2410M, sin GPU utilizable). El equipo principal de 32 GB no estuvo disponible: lo pesado quedó **preparado** (perfiles, scripts, paquete portátil), no ejecutado allí.

## 1. Estado inicial (verificado)

- 171 pruebas pasaban y el frontend compilaba. El informe anterior decía 155.
- Git sin remoto.
- 0 modelos registrados o validados.
- NEURODISASTER con validación espacial por proceso, variables del DEM y litología.
- Interfaz funcional pero básica.

Detalle en `DIAGNOSTICO_EQUIPO_Y_PROYECTO.md`.

## 2. Estado final

- **186 pruebas de backend pasan**, el frontend compila y los BAT del paquete portátil se probaron en Windows.
- Repositorio privado en GitHub, sincronizado y verificado tras cada fase.

| Fase | Resultado | Commit |
|---|---|---|
| 0 Diagnóstico | `DIAGNOSTICO_EQUIPO_Y_PROYECTO.md` | f67dde0 |
| 8 Rendimiento y hardware | Perfiles ligero/estándar/potente, control de memoria antes de cada trabajo, cancelación, medición de recursos | ef42635 |
| 4 Validación científica | NDVI evaluado como candidato (no mejora), protocolo e informe de resultados | fdaf940 |
| 1 NEURODATA | Manifiestos con calidad, linaje, transformaciones y duplicados; catálogo; exportación a Git | 7a96ec6 |
| 2 Training Center | HistGradientBoosting y MLP condicionados al tamaño de los datos, división espacial, semilla e hiperparámetros, reproducción, exportación con ficha | b066240 |
| 5, 6 y 7 Voz, UI/UX y NEUROCORE | Rediseño completo, asistente flotante con contexto, centro de coordinación | 835805a |
| 3 Fichas técnicas | Generadas desde el registro (16 módulos) | c8d092c |
| 9 y 10 Portátil y BAT | Empaquetador, 8 BAT, integridad SHA-256 | bd50b0c |
| GitHub | Estrategia y `sincronizar_github.bat` | (este commit) |

## 3. Módulos implementados

Estado calculado a partir de sus capacidades; ver `FICHAS_TECNICAS_MODULOS.md`.

- **Operativos:** NEURODATA (7/7) y NEURO 3D LAB (6/6).
- **Parciales:**
  - NEURAL TRAINING 9/12
  - NEUROVOICE 6/9
  - Alertas 5/6
  - NEUROENVIRONMENT 5/9
  - SCIENTIFIC VALIDATION 5/7
  - NEUROTERRAIN 4/5
  - NEUROCONSTRUCTION 4/7
  - NEURODISASTER 3/7
  - NEUROVISION 3/6
  - NEURO PREDICTION 2/4
  - Biodiversidad 2/6

## 4. Módulos pendientes

- **NEUROGEO, NEUROMINING y NEUROINDUSTRIAL (0 capacidades):** hay fuentes identificadas, pero no datos con licencia abierta. Ver `CATALOGO_DATASETS.md`.
- **InSAR (NEUROTERRAIN):** diseñado; requiere una cuenta NASA Earthdata.
- **Reconocimiento fotográfico de especies:** requiere un modelo preentrenado (ONNX) y autorización.

## 5–7. Datasets descargados, procedencia, licencias y tamaño

| Dataset | Licencia | Tamaño |
|---|---|---|
| Inventario INGEMMET (181 eventos) | No declarada; uso interno | ≈0,2 MB |
| Litología y geomorfología INGEMMET | Sin licencia abierta; uso interno | 3,4 MB |
| DEM GLO-30 a ≈35 m y a ≈110 m | Copernicus, con atribución | ≈10 MB + 1 MB |
| NDVI Sentinel-2 (16 jul. 2024) | Copernicus, libre | 39,8 MB descargados |

- Manifiestos (solo metadatos, en Git): `datasets/manifiestos/`.
- 7 de 17 registros son duplicados exactos (CSV de validaciones repetidas): están identificados y **no se borraron**.

## 8–11. Modelos, configuración, métricas y validación

- **No hay modelos entrenados como operativos ni validados.** Ninguno cumple los criterios: el límite inferior del IC 95 % queda en 0,43–0,66 y no hay prueba independiente.
- **Resultados principales** (validación espacial, franja de altura):
  - Mezclando procesos, la pendiente no discrimina (0,49–0,54).
  - El AUC 0,74 de pendiente + elevación se explica por la elevación y el sesgo de muestreo; **no es validez científica**.
  - Probables caídas (1100): la pendiente sola da 0,73–0,75.
  - Probables flujos (1500): la distancia a cauce da 0,72 y la litología eleva el modelo a 0,78, con posible circularidad.
  - **El NDVI no mejora** en ningún grupo (−0,03 a +0,01) y es posterior a los eventos.
- **Configuración:** pseudo-ausencias 3:1 a ≥ 300 m; 5 sorteos; bloques por variograma (3×3 de ≈18 km); zona de exclusión de 500 m; umbral de Youden en entrenamiento; IC por bootstrap de bloques.
- Detalle: `INFORME_RESULTADOS_ENTRENAMIENTO.md` y `PROTOCOLO_VALIDACION_CIENTIFICA.md`.
- **GBM, MLP y CNN no se entrenaron**, porque los datos no los justifican: 33–68 eventos por proceso y sin imágenes etiquetadas. Están disponibles en NEURAL TRAINING con requisitos mínimos de datos.

## 12. Limitaciones

1. Inventario incompleto y sesgado hacia zonas pobladas.
2. Fecha del evento desconocida.
3. Códigos de tipo de evento sin diccionario oficial.
4. Ubicación del punto sin definir (escarpa, cuerpo o depósito).
5. Sin prueba independiente fuera de Huaraz.
6. Circularidad posible con litología y geomorfología.
7. Voz: el reconocimiento envía el audio a Google, solo hay respuestas en español, inglés y portugués no están probados, y quechua y aimara no tienen voz.
8. El equipo de esta sesión es de 4 GB.

## 13. UI/UX

- **Sistema de diseño:** tema claro, oscuro o del sistema; tarjetas translúcidas; ancho máximo de 1320 px centrado; diseño adaptable a móvil.
- **Barra lateral:** iconos propios, grupos desplegables, modo contraído e indicador de estado por módulo.
- **Componentes:** interruptores, estados vacíos explicativos, tooltips, cargadores, ondas de voz y aparición progresiva.
- **Ficha «Cómo funciona»** en cada módulo, con las seis preguntas pedidas.
- **Rendimiento:** modo rendimiento activado solo en equipos de ≤ 4 núcleos y ≤ 4 GB (sin desenfoque ni animaciones); se respeta `prefers-reduced-motion`.
- **Verificado en el navegador:** 21 iconos, 16 indicadores de estado, los indicadores principales con datos reales y el asistente funcionando.

## 14. NEUROVOICE

- **Asistente flotante en todas las pantallas:**
  - usa el contexto de la pantalla para resolver «explícame esto»;
  - estados escuchando, procesando y respondiendo;
  - consentimiento de micrófono por sesión, voz activable, volumen, texto alternativo y enlace al historial completo.
- **Respuestas:** se basan en datos reales. En NEURODISASTER cita la última validación real con su AUC y sus conclusiones.
- **Piper:** no se descargó (decisión del usuario). Queda como adaptador opcional para el equipo de 32 GB, igual que Vosk o Whisper locales.
- **Idiomas:** ninguno se declara soportado sin pruebas.

## 15–16. Requisitos de instalación y consumo de RAM

- **Software:** Python 3.14 (python.org), 40 paquetes fijados en `requirements-lock.txt`. Node solo hace falta para recompilar el frontend; el paquete lo trae compilado.
- **Servidor en reposo:** ≈73–91 MB.
- **Validación NEURODISASTER completa** (1600×1600, con geología o NDVI): estimación ≈250–330 MB; pico medido de las variables del terreno ≈164 MB; 60–90 s en el equipo de 4 GB.
- **Descarga del DEM o el NDVI:** ≈70–250 MB.
- En el equipo de 32 GB, el perfil «potente» permite hasta 20 GB por trabajo (objetivo 16 GB).

## 17. Tamaño final del USB

- **Paquete principal:** 325 archivos, **4,6 MB** (código, frontend compilado, documentación, scripts, configuración y manifiestos).
- **Con `--con-datos`:** se añaden ≈60 MB de datos locales, de uso interno.
- **Con `--wheelhouse`:** se añaden aproximadamente 200–250 MB de paquetes para instalar sin internet (estimación, no medido).
- **Todo cabe holgadamente en 20 GB.** No había USB conectado: el paquete se creó y verificó en `D:\NEUROAMBIENTAL_IA_PORTABLE`; falta copiarlo al USB y ejecutar allí `VERIFICAR_INTEGRIDAD.bat`.

## 18. Instrucciones de ejecución

- **Desarrollo:** `scripts\iniciar.bat` o uvicorn con `--workers 1` → http://127.0.0.1:8000.
- **Portátil:** ver `portable/README_USB.md`. El orden es:
  1. `VERIFICAR_INTEGRIDAD`
  2. `VERIFICAR_EQUIPO`
  3. `INSTALAR_DEPENDENCIAS`
  4. `INICIAR_NEUROAMBIENTAL`
  5. `DETENER_SISTEMA` (al terminar)
- **Regenerar el paquete:** `python scripts\empaquetar_portable.py [--con-datos] [--wheelhouse]`.
- **Sincronizar:** `scripts\sincronizar_github.bat`.

## 19. Pruebas realizadas

| Tipo | Resultado |
|---|---|
| Backend (pytest) | **186 pasan**: integración, permisos, entrenamiento, validación, voz, memoria y cancelación |
| Compilación del frontend | Correcta |
| Navegación UI | Verificada en Chrome: tema, iconos, estados, indicadores principales y asistente |
| BAT del paquete | VERIFICAR_INTEGRIDAD (325/325), VERIFICAR_EQUIPO, DETENER (sin cerrar procesos ajenos), INICIAR (rechazo correcto con el puerto ocupado; la ventana no se cierra) |
| Sincronización GitHub | Detección de secretos, pruebas y cancelación verificadas |
| **No realizadas** | INSTALAR_DEPENDENCIAS en limpio (requiere unos 200 MB de PyPI y C: tiene 4,4 GB libres), pruebas de carga con usuarios concurrentes, ejecución en el equipo de 32 GB y en un USB real |

## 20. Problemas pendientes

1. **Prueba independiente fuera de Huaraz** (DEM, inventario y litología de otra región, ≈20 MB): es el paso que puede validar un modelo.
2. Máscara de hielo y agua para las pseudo-ausencias.
3. Consultar a INGEMMET la licencia, el diccionario de códigos y la fecha de los eventos.
4. Ejecutar `INSTALAR_DEPENDENCIAS` y las pruebas en el equipo de 32 GB, y copiar y verificar el paquete en el USB.
5. Voz local (Piper/Vosk) en el equipo principal, con pruebas de pronunciación por idioma.
6. InSAR con cuenta Earthdata; NEUROGEO, NEUROMINING y NEUROINDUSTRIAL con datos con licencia.
7. El nombre de la fuente geológica antigua en la base local conserva una licencia larga (más de 128 caracteres); SQLite lo admite, pero hay que corregirlo antes de migrar a PostgreSQL.
