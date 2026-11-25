# Fichas técnicas de los módulos

Generado automáticamente desde el registro de NEUROCORE (`python -m app.cli exportar-fichas`).
Lo que aquí figura como implementado es exactamente lo que declara el código; nada se edita a mano.

| Módulo | Estado | Capacidades |
|---|---|---|
| NEURODATA ENGINE | operativo | 7/7 |
| NEUROALERTS | parcial | 5/6 |
| NEUROENVIRONMENT | parcial | 5/9 |
| NEUROTERRAIN | parcial | 4/5 |
| Fauna, Flora y Biodiversidad | parcial | 2/6 |
| NEUROGEO | en_desarrollo | 0/5 |
| NEUROMINING | en_desarrollo | 0/5 |
| NEURODISASTER | parcial | 3/7 |
| NEUROCONSTRUCTION | parcial | 4/7 |
| NEURAL TRAINING ENGINE | parcial | 9/12 |
| NEUROVISION | parcial | 3/6 |
| NEUROINDUSTRIAL | en_desarrollo | 0/3 |
| NEURO 3D SIMULATION ENGINE | operativo | 6/6 |
| NEURO PREDICTION ENGINE | parcial | 2/4 |
| NEUROVOICE IA | parcial | 6/9 |
| SCIENTIFIC VALIDATION ENGINE | parcial | 5/7 |

## NEURODATA ENGINE (NEURODATA ENGINE)

Recepción, validación, metadatos, procedencia y almacenamiento de datos.

- **Estado:** operativo · **versión** 0.1.0 · **API:** `/api/neurodata`
- **Datos que usa:** CSV · GeoJSON · PNG · JPG · PDF · registro manual
- **Resultados que produce:** registros de datos validados · capas GeoJSON
- **Depende de:** ninguno

**Implementado:**

- Carga y validación de CSV
- Carga y validación de GeoJSON
- Carga de imágenes PNG/JPG (validación por firma)
- Carga de documentos PDF
- Registro manual de mediciones
- Metadatos, fuente, fechas, calidad y procedencia
- Exponer datos georreferenciados como capas GeoJSON

**Pendiente:**

- Nada declarado.

**Limitaciones:**

- Imágenes satelitales GeoTIFF aún no soportadas.
- Tamaño máximo por archivo configurable (10 MB por defecto).

## NEUROALERTS (Alertas y Prevención)

Registro de eventos y alertas EXPERIMENTALES con evidencia, fuente, incertidumbre y validación.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/alerts`
- **Datos que usa:** datos de la alerta registrados por un analista
- **Resultados que produce:** alertas · seguimientos · informes
- **Depende de:** neurodata

**Implementado:**

- Registrar eventos
- Crear alertas experimentales
- Ubicación, evidencia, fuente, fecha e incertidumbre
- Estado de validación y seguimiento
- Generar informe de una alerta (Markdown)

**Pendiente:**

- Generar alertas automáticamente desde modelos

**Limitaciones:**

- Todas las alertas son experimentales. NO son emergencias oficiales.
- Para emergencias oficiales en Perú consulte INDECI / COEN.

## NEUROENVIRONMENT (Predicción Ambiental Territorial)

Cambios de vegetación, deforestación, ríos, lagunas, cobertura del suelo, erosión y degradación.

- **Estado:** parcial · **versión** 0.2.0 · **API:** `/api/environmental`
- **Datos que usa:** área de estudio (bbox, máx. 0,5° x 0,5°) · escenas Sentinel-2 L2A
- **Resultados que produce:** rasters NDVI (GeoTIFF) · rasters de cambio · vistas previas PNG para el mapa · estadísticas
- **Depende de:** neurodata

**Implementado:**

- Búsqueda y lectura por recorte de Sentinel-2 L2A (Copernicus, gratuito, sin cuenta)
- Cálculo de NDVI con máscara de nubes y sombras (SCL)
- Comparar dos fechas de una misma zona en una malla común
- Identificar zonas con disminución o aumento de NDVI
- Publicar resultados como capas del mapa

**Pendiente:**

- Series temporales de índices con muchas fechas
- Clasificar cobertura cuando existan datos etiquetados
- Proyectar escenarios con incertidumbre explícita
- Integración con Sentinel-1 (radar)

**Limitaciones:**

- Un cambio de NDVI no confirma deforestación ni daño: debe validarse (campo o imágenes de alta resolución).
- Resolución reducida (~33 m por defecto) para ahorrar memoria y descargas.
- Un solo procesamiento a la vez; cada NDVI tarda de segundos a pocos minutos según la conexión.
- Nieve, sombras de relieve y estacionalidad afectan el NDVI en zonas andinas.

## NEUROTERRAIN (Movimientos Territoriales)

Desplazamientos, deformaciones, laderas, taludes, suelos, infraestructura y depósitos mineros. Series de sensores importadas por CSV con indicadores experimentales por umbrales.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/terrain`
- **Datos que usa:** mediciones de sensores (CSV registrado en NEURODATA, formato largo o ancho) · productos InSAR (no implementado)
- **Resultados que produce:** series temporales · velocidad y aceleración · saltos/anomalías · clasificación experimental · alertas experimentales a petición
- **Depende de:** neurodata

**Implementado:**

- Series de desplazamiento de sensores (CSV de NEURODATA): acumulado, velocidad por regresión, saltos
- GPS solo por CSV: series de una variable ya expresada como desplazamiento (sin conexión a receptores ni conversión de coordenadas)
- Inclinómetros solo por CSV: lecturas ya convertidas a desplazamiento (sin conexión a equipos ni cálculo de perfiles)
- Detectar aceleraciones por comparación de velocidades entre ventanas (indicador experimental)

**Pendiente:**

- Integración con InSAR (Sentinel-1)

**Limitaciones:**

- Indicador experimental por umbrales de EJEMPLO configurables; no es una predicción de falla ni sustituye el criterio geotécnico.
- No hay conexión en vivo con GPS, inclinómetros ni otros equipos: solo CSV subidos a NEURODATA.
- No hay InSAR ni procesamiento de Sentinel-1; no se calculan desplazamientos desde coordenadas crudas.
- Sin compensación de temperatura, calibración ni modelos físicos; los saltos solo se marcan, no se explican.

## Fauna, Flora y Biodiversidad (Fauna, Flora y Biodiversidad)

Registro de especies y observaciones georreferenciadas, con validación manual y capa de mapa.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `sin API propia`
- **Datos que usa:** formulario de especies y observaciones · fotografías ya cargadas en NEURODATA
- **Resultados que produce:** registros de especies · observaciones · capa GeoJSON de observaciones · resumen por especie, mes y estado
- **Depende de:** neurodata, environmental

**Implementado:**

- Registrar especies (catálogo propio, sin especies precargadas)
- Registrar observaciones georreferenciadas y validarlas

**Pendiente:**

- Analizar fotografías (sin modelo: la foto solo se enlaza como evidencia)
- Reconocer especies con un modelo validado (no existe tal modelo)
- Analizar cambios de hábitat (sin análisis implementado)
- Analizar fragmentación de ecosistemas (sin análisis implementado)

**Limitaciones:**

- No hay modelo de reconocimiento de especies: la identificación la declara el observador y no se verifica.
- Las fotografías no se analizan; solo se enlazan como evidencia.
- No se analiza cambio de hábitat ni fragmentación.
- La categoría de conservación (tipo UICN) se muestra según la fuente indicada; el sistema no la evalúa.
- La riqueza de especies (nº de especies distintas) depende del esfuerzo de muestreo: no es un índice de biodiversidad.
- El catálogo de especies empieza vacío: no hay especies precargadas.

## NEUROGEO (Geología)

Unidades y estructuras geológicas, fallas, geofísica, geoquímica, perforaciones y prospectividad.

- **Estado:** en_desarrollo · **versión** 0.0.1 · **API:** `sin API propia`
- **Datos que usa:** mapas geológicos (GeoJSON) · CSV geoquímico · datos de perforación
- **Resultados que produce:** capas temáticas · zonas de interés con incertidumbre
- **Depende de:** neurodata

**Implementado:**

- Nada todavía (solo contrato).

**Pendiente:**

- Consultar unidades y estructuras geológicas cargadas
- Analizar datos geoquímicos tabulares
- Incorporar datos geofísicos
- Registrar información de perforaciones
- Mapas de prospectividad (indicios, nunca reservas)

**Limitaciones:**

- Un indicio no equivale a un yacimiento; la IA no certifica reservas minerales.

## NEUROMINING (Inteligencia Minera)

Actividad minera: tajos, botaderos, relaves, drenaje, taludes e impactos en cuerpos de agua.

- **Estado:** en_desarrollo · **versión** 0.0.2 · **API:** `sin API propia`
- **Datos que usa:** imágenes multitemporales · GeoJSON de concesiones o depósitos · datos de sensores
- **Resultados que produce:** capas de cambio · fichas de actividad · indicadores con incertidumbre
- **Depende de:** neurodata, environmental, terrain

**Implementado:**

- Nada todavía (solo contrato).

**Pendiente:**

- Registrar actividades e infraestructura minera
- Comparar imágenes históricas de tajos y botaderos
- Monitorear depósitos de relaves
- Posibles impactos en cuerpos de agua y drenaje minero
- Análisis de estabilidad de taludes (requiere datos geotécnicos)

**Limitaciones:**

- No sustituye estudios geotécnicos ni inspecciones mineras.

## NEURODISASTER (Predicción de Catástrofes)

Huaycos, inundaciones, deslizamientos, incendios, sequías, sismos, relaves y accidentes industriales.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/disasters`
- **Datos que usa:** inventario INGEMMET (GEOJSON) · DEM Copernicus GLO-30
- **Resultados que produce:** informe de validación (AUC espacial, sesgos, conclusiones) · dataset para NEURAL TRAINING
- **Depende de:** neurodata, environmental, terrain, alerts

**Implementado:**

- Importar el inventario REAL de peligros geológicos de INGEMMET (GEOCATMIN) por recorte
- Validar índices y modelos de susceptibilidad con eventos reales mediante validación cruzada espacial por bloques y corrección del sesgo de elevación
- Importar litología y geomorfología de INGEMMET por recorte (uso interno) y usarlas en la validación

**Pendiente:**

- Evaluar amenaza con un modelo validado
- Evaluar exposición
- Evaluar vulnerabilidad
- Combinar amenaza, exposición y vulnerabilidad en riesgo

**Limitaciones:**

- No puede predecir la fecha exacta de terremotos, explosiones ni otros eventos.
- Inventario INGEMMET incompleto y concentrado donde hay población y vías (sesgo de muestreo); la fecha del evento es desconocida (FECHA parece la del estudio: 2007 en la mayoría); licencia no declarada por el servicio: uso interno de investigación autorizado por el usuario.
- Resultado real en Huaraz (181 eventos): mezclando procesos, la pendiente no discrimina (AUC 0,49). Por proceso (códigos sin diccionario oficial): 1100 (probables caídas) AUC 0,75 con la pendiente sola tras corregir el sesgo de altura; 1500 (probables flujos) relación inversa (0,38). Los intervalos de confianza por bloques llegan a 0,43–0,54 y no hay prueba independiente: ningún modelo está validado.
- Variables del DEM (≈35 m): pendiente, elevación, curvatura, TPI y distancia a cauces derivados. En flujos (1500) la distancia a cauce sola discrimina (AUC 0,72); combinar variables no mejora con tan pocos eventos.
- Litología y geomorfología de INGEMMET (uso interno): en flujos la litología sube el AUC de 0,70 a 0,78, pero la clase «Sedimento» puede contener los depósitos de los propios eventos (circularidad).
- Evaluación externa prerregistrada (misión 2.1, Callejón de Conchucos): ningún modelo generaliza lo suficiente (mejor AUC externo 0,65 en general; la pendiente para caídas cae a 0,57). Flujos: señal coherente (distancia a cauce 0,76) pero solo 27 eventos externos: validación insuficiente.
- Segunda zona externa (Carhuaz–Yungay): la distancia a cauce para flujos repite AUC 0,76 (IC 0,71–0,79): VALIDACIÓN EXTERNA PROMETEDORA allí, pero el estado combinado sigue INSUFICIENTE (27 flujos en Conchucos). La pendiente para caídas queda refutada en dos zonas.
- Faltan lluvia y cobertura vegetal; ningún modelo validado bajo alcance definido.

## NEUROCONSTRUCTION (Construcción y Planificación Territorial)

Carga de planos y documentos; análisis de ubicación, pendientes, ríos y riesgos territoriales.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/construction`
- **Datos que usa:** PDF · PNG · JPG · GeoJSON · CSV · DEM registrado + punto o polígono
- **Resultados que produce:** observaciones técnicas preliminares
- **Depende de:** neurodata, disasters, terrain

**Implementado:**

- Cargar PDF, PNG, JPG, GeoJSON y CSV (vía NEURODATA)
- Analizar el emplazamiento (punto o polígono) sobre un DEM: elevación, entorno, susceptibilidad heurística e inundación demostrativa opcional
- Calcular pendientes y relieve con un DEM (emplazamiento y entorno)
- Generar observaciones automáticas basadas solo en los números del análisis (reglas fijas)

**Pendiente:**

- Evaluar compatibilidad territorial
- Medir proximidad a ríos (requiere una capa de ríos, aún no disponible)
- Adaptadores CAD/BIM (futuro)

**Limitaciones:**

- No reemplaza evaluaciones profesionales ni autorizaciones oficiales.
- El análisis usa un DEM de ≈100 m: no representa taludes ni obras menores.
- No hay capa de ríos ni de zonificación: no se evalúa proximidad a cauces ni compatibilidad territorial.
- Susceptibilidad e inundación son escenarios simplificados, no calibrados ni validados.

## NEURAL TRAINING ENGINE (NEURAL TRAINING ENGINE (NEUROTRAINING))

Datasets, entrenamiento, evaluación con filas de prueba reservadas y registro de versiones de modelos.

- **Estado:** parcial · **versión** 0.3.0 · **API:** `/api/neurotraining`
- **Datos que usa:** CSV registrados en NEURODATA (columnas numéricas + columna objetivo)
- **Resultados que produce:** modelos versionados · métricas de prueba · predicciones experimentales
- **Depende de:** neurodata

**Implementado:**

- Registro de modelos con estado honesto (planificado/entrenado/validado/retirado)
- Historial de ejecuciones con parámetros y resultados
- Entrenamiento con scikit-learn sobre CSV de NEURODATA (n_jobs=1)
- Métricas sobre datos de prueba separados: precisión, recall, F1, matriz de confusión, ROC-AUC, Brier, MAE, RMSE, R²
- Versionado de artefactos con SHA-256 verificado antes de cargar
- Validación solo por administrador con evidencia; nunca con datos simulados
- Predicción sobre nuevos CSV, marcada como experimental si el modelo no está validado
- Semilla, hiperparámetros, versiones y SHA-256 del dataset registrados; reproducción verificable y exportación del modelo con su ficha (model_card.json)
- División de prueba por bloques geográficos y algoritmos condicionados al tamaño de los datos (HistGradientBoosting ≥ 200 filas, MLP ≥ 1000 filas)

**Pendiente:**

- Redes neuronales (PyTorch) para imágenes y series: requiere autorización y hardware
- Datasets de imágenes con anotaciones (Dataset Manager)
- Reanudar entrenamientos largos por épocas

**Limitaciones:**

- Solo modelos ligeros (bosques aleatorios, regresión logística, ridge). Sin redes neuronales todavía.
- Un modelo entrenado con datos simulados nunca puede validarse.
- La validación la decide un administrador con evidencia; terminar un entrenamiento no aprueba un modelo.

## NEUROVISION (Visión artificial)

Procesamiento de imágenes (OpenCV) y modelos de visión: clasificación, detección, segmentación y cambios.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/neurovision`
- **Datos que usa:** fotografías · imágenes de dron · imágenes satelitales compatibles
- **Resultados que produce:** imágenes procesadas · regiones detectadas · características · limitaciones (sin confianza estadística)
- **Depende de:** neurodata, neurotraining

**Implementado:**

- Bordes Canny, CLAHE, segmentación Otsu, índice de verdor ExG y características con OpenCV (determinista)
- Imagen original, procesada, regiones, características, confianza y limitaciones
- Comparación de dos fotos de la misma escena: alineación ORB/RANSAC y regiones de cambio (sin georreferenciación)

**Pendiente:**

- Clasificación de imágenes con un modelo entrenado
- Segmentación de terreno, vegetación y agua
- Detección de infraestructura y grietas visibles

**Limitaciones:**

- Clasificación, segmentación con modelo y detección de grietas/infraestructura NO están implementadas: requieren un modelo entrenado.
- El procesamiento de imágenes no es entrenamiento de una red neuronal: ambos se registran por separado.

## NEUROINDUSTRIAL (Instalaciones industriales)

Inspección visual, anomalías en variables operativas, corrosión y grietas visibles, escenarios de falla.

- **Estado:** en_desarrollo · **versión** 0.0.1 · **API:** `sin API propia`
- **Datos que usa:** imágenes industriales · series de sensores
- **Resultados que produce:** anomalías con incertidumbre · escenarios hipotéticos
- **Depende de:** neurodata, neurovision

**Implementado:**

- Nada todavía (solo contrato).

**Pendiente:**

- Inspección visual de corrosión, grietas y deterioro
- Detección de anomalías en vibración, temperatura y presión
- Escenarios hipotéticos de fugas e incendios

**Limitaciones:**

- No controla maquinaria ni activa paradas: no hay integración con sistemas de control.
- No sustituye inspecciones industriales certificadas.

## NEURO 3D SIMULATION ENGINE (NEURO 3D LAB)

Terreno 3D desde DEM real (Copernicus GLO-30), pendiente y escenario demostrativo de trayectoria, conectados con el mapa 2D.

- **Estado:** operativo · **versión** 0.1.0 · **API:** `/api/neuro3d`
- **Datos que usa:** DEM Copernicus GLO-30 · NDVI opcional · punto de inicio (lon, lat) · pesos, umbrales y subida de nivel
- **Resultados que produce:** terreno 3D · estadísticas de pendiente · trayectoria, susceptibilidad e inundación rotuladas como simulación · tabla comparativa de escenarios
- **Depende de:** neurodata, terrain

**Implementado:**

- Malla 3D del terreno desde un DEM real (Copernicus DEM GLO-30) con pendiente y estadísticas
- Visor 3D ligero con Three.js (render bajo demanda, exageración vertical, capas de elevación y pendiente)
- Capa «Escenario» sobre el terreno 3D: clases de susceptibilidad heurística (con NDVI opcional) y profundidad de inundación demostrativa
- Capas NDVI y de cambio de NDVI (Fase 2) reproyectadas a la malla del DEM y dibujadas sobre el terreno 3D
- Escenario demostrativo de trayectoria de máxima pendiente (D8), rotulado como simulación
- Comparar 2-4 configuraciones de escenario lado a lado frente al estado actual observado (cálculo en memoria, sin guardar)

**Pendiente:**

- Nada declarado.

**Limitaciones:**

- Las simulaciones son aproximaciones demostrativas: no son simulaciones geotécnicas ni hidráulicas.
- El DEM tiene ~100 m de resolución por defecto y errores verticales de varios metros; no sustituye un levantamiento.
- La susceptibilidad es un índice heurístico (pendiente/45° y 1−NDVI) NO calibrado; no predice deslizamientos ni fechas. Evaluado con el inventario real de INGEMMET (181 movimientos en masa, Huaraz): la pendiente sola NO discrimina los eventos (AUC 0,49, igual al azar). No usar como indicador de susceptibilidad.
- La inundación es un modelo de bañera: ignora caudal, cauce, rugosidad, tiempo y drenaje; no es una simulación hidráulica y se trunca en el borde del DEM.
- Los escenarios son hipotéticos y se rotulan SIMULACIÓN; el comparador no guarda resultados. Las capas de NDVI/cambio se remuestrean a la malla del DEM (≈100 m) y no confirman deforestación ni daño.
- La trayectoria D8 no rellena depresiones: un pozo de ruido del DEM puede detenerla; si se detiene junto a celdas sin dato se informa «sin_dato».

## NEURO PREDICTION ENGINE (Motor de predicción)

Estimaciones de los modelos con ubicación, modelo, versión, incertidumbre, evidencias y limitaciones.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/neuroprediction`
- **Datos que usa:** resultados de modelos entrenados · datos de NEURODATA
- **Resultados que produce:** predicciones con incertidumbre y nivel de evidencia
- **Depende de:** neurodata, neurotraining

**Implementado:**

- Registrar predicciones con modelo, versión e incertidumbre
- Catálogo que separa observación real, dato histórico, procesamiento, estimación, simulación, predicción validada y alerta verificada (sin tablas nuevas; ver /api/neuroprediction/kinds)

**Pendiente:**

- Probabilidades solo cuando el modelo está calibrado y validado
- Estimaciones con horizonte temporal explícito

**Limitaciones:**

- Si el modelo no está validado, la predicción se presenta como experimental.
- Sin probabilidades calibradas ni horizonte temporal: probabilidad y horizonte_temporal quedan en null.
- El catálogo es de solo lectura y clasifica por reglas; no valida nada por sí mismo.

## NEUROVOICE IA (NEUROVOICE IA)

Asistente conversacional: texto y voz en español que consulta NEUROCORE y explica resultados reales.

- **Estado:** parcial · **versión** 0.2.0 · **API:** `/api/neurovoice`
- **Datos que usa:** texto en español · voz en español (Chrome)
- **Resultados que produce:** respuesta en texto · respuesta hablada · módulo consultado
- **Depende de:** neurocore

**Implementado:**

- Conversación escrita en español
- Consultar datos reales: alertas, datos, terreno y escenarios, NDVI, modelos y catálogo de predicciones
- Guardar conversaciones y memoria de sesión (preguntas de seguimiento)
- Reconocimiento de voz en Chrome (Web Speech API; el audio se procesa en servidores de Google, con consentimiento previo)
- Respuestas habladas con las voces del navegador (local), interrumpibles
- Asistente flotante en toda la plataforma con el contexto de la pantalla, estados de escucha/proceso/respuesta, volumen y voz activable

**Pendiente:**

- Comprensión con modelo de lenguaje
- Inglés, quechua, aimara, portugués
- Ejecutar análisis o simulaciones por voz con confirmación

**Limitaciones:**

- No usa un modelo de lenguaje: interpreta palabras clave. Puede no entender frases complejas.
- El reconocimiento de voz solo funciona en Chrome/Edge y envía el audio a Google; sin internet no funciona.
- Solo español. Quechua y aimara no están soportados (requieren hablantes competentes y datos propios).
- Solo consulta y explica: no ejecuta análisis ni simulaciones por voz.

## SCIENTIFIC VALIDATION ENGINE (Validación científica)

Experimentos con criterios fijados de antemano, evaluaciones con separación geográfica, prueba independiente sellada y doble aprobación.

- **Estado:** parcial · **versión** 0.1.0 · **API:** `/api/validation`
- **Datos que usa:** ejecuciones de validación de NEURODISASTER
- **Resultados que produce:** estado científico por experimento · historial de evaluaciones y decisiones
- **Depende de:** neurodata, neurotraining, disasters

**Implementado:**

- Registrar experimentos con protocolo, criterios y región de prueba congelados (SHA-256)
- Registrar evaluaciones internas (cv) e independientes (test) leyendo las métricas de ejecuciones reales, con control de fuga geográfica
- Permitir una sola evaluación de prueba por protocolo
- Doble aprobación de administradores distintos de los autores
- Estado científico derivado: borrador → evaluado interno → evaluado independiente → validado condicional (o retirado)

**Pendiente:**

- Versionado formal de datasets y divisiones
- Vincular la validación a artefactos de NEURAL TRAINING

**Limitaciones:**

- «Validado condicional» vale solo para la configuración evaluada (grupo, variables, modelo), el área de prueba y el inventario usados; no autoriza decisiones sin revisión experta.
- Hoy no existe ninguna región de prueba independiente evaluada: ningún experimento puede estar validado.
- No versiona aún los datasets ni se vincula a los artefactos .joblib de NEURAL TRAINING.
