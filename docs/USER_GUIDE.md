# Guía de usuario

Para personas sin conocimientos técnicos. Si algo no queda claro, la interfaz siempre indica qué está «Operativo», «Parcial» o «En desarrollo».

> **Alertas experimentales.** Las alertas de NEUROAMBIENTAL IA **no son oficiales** y no sustituyen los avisos de las autoridades. Para emergencias, comuníquese con **INDECI / COEN** y las autoridades locales.

## Antes de empezar

1. Quien instala el sistema ejecuta `scripts\iniciar.bat` y se abre <http://127.0.0.1:8000>.
2. Ingrese con su **usuario y contraseña**. Si es la primera vez, el administrador debe haber creado la cuenta (`scripts\crear-admin.bat`).
3. Su **rol** aparece arriba a la derecha:
   - **lector**: solo consulta.
   - **analista**: además carga datos, registra alertas, eventos y modelos planificados.
   - **admin**: además crea usuarios.
4. Use **Salir** al terminar. La sesión dura 12 horas como máximo y se cierra si cierra el navegador.

El menú lateral tiene 15 secciones, numeradas. En el celular se abre con el botón ☰.

## 1. Inicio
Resumen con cifras tomadas de la base de datos: alertas (por nivel), alertas sin validar, registros de datos (reales y simulados), fuentes, un mapa pequeño, el estado de los módulos, actividad reciente y accesos directos. Si no hay datos, lo indica. **Funciona.**

## 2. Mapa territorial
Muestra sobre un mapa base local de países (Natural Earth, con Perú resaltado en verde) las **capas** que se cargaron en NEURODATA y las alertas con ubicación.
- Marque o desmarque capas; «Ir» acerca el mapa a una capa.
- Haga clic en un elemento para ver su información en el recuadro «Selección».
- Si se calcularon NDVI o cambios (Predicción ambiental), aparecen en «Rásters Sentinel-2» con casilla para mostrarlos y botón «Ir». La leyenda explica los colores (NDVI de marrón a verde oscuro; rojo = disminución, verde = aumento; el rojo **no confirma** daño).
- Los datos simulados se distinguen por contorno/borde especial y la etiqueta «simulado».
- «Modo marcador»: permite hacer clic en el mapa para marcar un punto.
- Casilla «Detalle OpenStreetMap» (desactivada por defecto): agrega el mapa detallado de OpenStreetMap. Requiere Internet y sus servidores pueden rechazar la carga según su política de uso; si no aparece, el mapa local sigue funcionando.
- El mapa base local funciona sin Internet. **Funciona.**

## 3 a 8. Módulos especializados
Predicción ambiental, Inteligencia minera, Fauna y flora, Movimientos territoriales, Catástrofes y Construcción. Cada página muestra una **ficha**: descripción, capacidades (Implementada / Pendiente), entradas, salidas, dependencias, errores posibles y limitaciones.

- **Predicción ambiental:** **parcial** (5 de 9 capacidades). Es el único módulo que analiza imágenes satelitales reales. Ver la sección «Predicción ambiental» más abajo.
- **Minería, fauna y flora, movimientos territoriales, catástrofes:** **en desarrollo**. No analizan nada ni muestran resultados; solo describen lo previsto. Catástrofes advierte que no se puede predecir la fecha exacta de sismos ni explosiones.
- **Construcción:** **parcial**. Permite cargar planos o documentos (PDF, PNG, JPG, GeoJSON, CSV) y ver la lista de documentos cargados. El análisis del proyecto (pendientes, ríos, riesgos) **aún no existe**; no reemplaza una evaluación profesional.

### Predicción ambiental: NDVI y cambios con Sentinel-2
Usa imágenes **reales** del satélite Sentinel-2 (programa Copernicus), gratis y sin cuenta. **Necesita Internet.** Solo se descarga el recorte del área (unos 17 MB por fecha en las pruebas); cada cálculo tarda unos 2 minutos (medido) y se procesa **uno a la vez**. Los lectores solo ven los resultados; los analistas pueden ejecutar los pasos:

1. **Buscar escenas.** El área por defecto es Huaraz / Cordillera Blanca; puede cambiar las coordenadas (máximo 0,5° por lado), las fechas y la nubosidad máxima. Se listan hasta 20 escenas.
2. **Calcular NDVI** de una escena (botón en su fila). El NDVI es un índice de vegetación (de -1 a 1; valores altos = más vegetación). El sistema excluye nubes, sombras y datos inválidos, y muestra el porcentaje de área válida, nubes/sombras y nieve. Si sale poco porcentaje válido, pruebe otra fecha.
3. **Elegir dos fechas** de la misma área (marque dos NDVI), indique el umbral (±0,2 por defecto) y pulse **Detectar cambios**. Verá los km² con disminución y aumento de NDVI.
4. **Ver en el mapa:** en «Mapa territorial», sección «Rásters Sentinel-2» (por defecto se muestra el más reciente).

**Cómo interpretarlo (importante):** los resultados quedan «sin validar». Una disminución de NDVI **no confirma deforestación ni daño ambiental**: también la producen la estacionalidad, los cultivos, la nieve, nubes no detectadas o diferencias de iluminación. Compare fechas de la misma época del año y valide con imágenes de alta resolución o trabajo de campo. La resolución se reduce a unos 33 m. Si ya hay un cálculo en curso, aparecerá un aviso para esperar. Cada NDVI incluye la atribución «Contiene datos modificados de Copernicus Sentinel».

## 9. Alertas
Lista de alertas con nivel (bajo, medio, alto), estado de validación (no validada, en revisión, validada, descartada) y marca de simulada.
- Haga clic en una alerta para ver ubicación, fuente, evidencia, **incertidumbre** y seguimientos.
- **Analistas:** «Nueva alerta experimental» (obligatorios: título, nivel, fuente, incertidumbre y si los datos son simulados). Pueden agregar notas de seguimiento, cambiar el estado y **Generar informe**.
- Las alertas las escribe una persona; el sistema **no genera alertas automáticas**.

## 10. NEUROCORE IA
Panel del coordinador central: lista de módulos con su estado y cuántas capacidades funcionan, un probador de interpretación («riesgo de huaycos en Huaraz» → módulo sugerido por palabras clave) y, para analistas, el registro de operaciones recientes. **Funciona**; no usa un modelo de lenguaje.

## 11. NEURODATA ENGINE
Aquí entran los datos.
- **Cargar archivo (analista):** elija un CSV, GeoJSON, PNG, JPG o PDF (máx. 10 MB), indique la **fuente**, la licencia si la conoce, y marque si los datos son **reales** o **simulados / de prueba**. El sistema valida el archivo y lo rechaza explicando el motivo si es inválido. Un CSV necesita columnas de latitud y longitud para verse en el mapa.
- **Registro manual (analista):** una medición con variable, valor, unidad, ubicación, fuente y marca real/simulado.
- **Datos recibidos:** tabla filtrable por tipo; clic en una fila para ver metadatos (procedencia, calidad, huella SHA-256, observaciones de validación).
- **Fuentes:** lista de fuentes registradas.
**Funciona (operativo).** No admite todavía imágenes satelitales GeoTIFF.

## 12. NEUROTRAINING
Muestra los modelos de IA registrados. **No hay ningún modelo entrenado.** Un analista puede «Registrar como planificado» un modelo previsto; siempre queda «planificado» y no puede marcarse como validado. No entrena ni evalúa. **Parcial.**

## 13. NEUROVOICE IA
Chat **escrito en español**. Pruebe: «estado de los módulos», «¿cuántas alertas hay?», «¿cuántos datos hay?», «riesgo de huaycos». Entiende palabras clave, no frases complejas, y responde con cifras reales y con lo que está o no implementado. Guarda su historial (solo usted lo ve). **Sin voz ni otros idiomas** (pendiente). **Parcial.**

## 14. Informes
Lista de informes generados (hoy, solo informes de alertas creados desde la sección Alertas). Haga clic para leerlos; están en formato Markdown (texto). No hay exportación a PDF.

## 15. Configuración
Muestra su cuenta, el estado del sistema (versión, base de datos), los límites de carga y formatos permitidos. Si es **admin**, también lista usuarios y permite crear nuevos (contraseña de mínimo 10 caracteres con letras y números/símbolos). No hay cambio de contraseña ni recuperación por ahora.

## Si algo falla
- **El mapa va muy lento o se traba:** en equipos antiguos el navegador puede estar dibujando por software (por ejemplo, Chrome con «Microsoft Basic Render Driver» cuando falta el driver de la tarjeta gráfica). Instale el driver de gráficos desde Windows Update o el sitio del fabricante (en Intel HD 3000, el de Intel) y cierre otras aplicaciones pesadas. Con poca RAM libre también se ralentiza.
- **El cálculo de NDVI tarda:** en las pruebas tomó unos 2 minutos por fecha (≈17 MB descargados). Espere; solo se procesa uno a la vez.- «No se pudo conectar con el backend»: el programa no está iniciado; ejecute `scripts\iniciar.bat`.
- «Demasiados intentos fallidos»: espere 5 minutos.
- «Sesión no válida o expirada»: vuelva a ingresar.
- Archivo rechazado: lea el motivo (formato, coordenadas fuera de rango, archivo vacío o demasiado grande).
