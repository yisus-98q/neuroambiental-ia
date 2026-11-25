from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="disasters",
    codename="NEURODISASTER",
    name="Predicción de Catástrofes",
    version="0.1.0",
    description="Huaycos, inundaciones, deslizamientos, incendios, sequías, sismos, relaves y accidentes industriales.",
    capabilities=[
        cap("registro_eventos_historicos", "Importar el inventario REAL de peligros geológicos de INGEMMET (GEOCATMIN) "
            "por recorte", implemented=True),
        cap("validacion_espacial", "Validar índices y modelos de susceptibilidad con eventos reales mediante "
            "validación cruzada espacial por bloques y corrección del sesgo de elevación", implemented=True),
        cap("capas_geologicas", "Importar litología y geomorfología de INGEMMET por recorte (uso interno) y usarlas "
            "en la validación", implemented=True),
        cap("amenaza", "Evaluar amenaza con un modelo validado"),
        cap("exposicion", "Evaluar exposición"),
        cap("vulnerabilidad", "Evaluar vulnerabilidad"),
        cap("riesgo", "Combinar amenaza, exposición y vulnerabilidad en riesgo"),
    ],
    dependencies=["neurodata", "environmental", "terrain", "alerts"],
    inputs=["inventario INGEMMET (GEOJSON)", "DEM Copernicus GLO-30"],
    outputs=["informe de validación (AUC espacial, sesgos, conclusiones)", "dataset para NEURAL TRAINING"],
    possible_errors=["datos_historicos_insuficientes", "servicio_ingemmet_no_disponible", "area_demasiado_pequena"],
    limitations=[
        "No puede predecir la fecha exacta de terremotos, explosiones ni otros eventos.",
        "Inventario INGEMMET incompleto y concentrado donde hay población y vías (sesgo de muestreo); la fecha del "
        "evento es desconocida (FECHA parece la del estudio: 2007 en la mayoría); "
        "licencia no declarada por el servicio: uso interno de investigación autorizado por el usuario.",
        "Resultado real en Huaraz (181 eventos): mezclando procesos, la pendiente no discrimina (AUC 0,49). Por "
        "proceso (códigos sin diccionario oficial): 1100 (probables caídas) AUC 0,75 con la pendiente sola tras "
        "corregir el sesgo de altura; 1500 (probables flujos) relación inversa (0,38). Los intervalos de "
        "confianza por bloques llegan a 0,43–0,54 y no hay prueba independiente: ningún modelo está validado.",
        "Variables del DEM (≈35 m): pendiente, elevación, curvatura, TPI y distancia a cauces derivados. En flujos "
        "(1500) la distancia a cauce sola discrimina (AUC 0,72); combinar variables no mejora con tan pocos eventos.",
        "Litología y geomorfología de INGEMMET (uso interno): en flujos la litología sube el AUC de 0,70 a 0,78, "
        "pero la clase «Sedimento» puede contener los depósitos de los propios eventos (circularidad).",
        "Evaluación externa prerregistrada (misión 2.1, Callejón de Conchucos): ningún modelo generaliza lo "
        "suficiente (mejor AUC externo 0,65 en general; la pendiente para caídas cae a 0,57). Flujos: señal "
        "coherente (distancia a cauce 0,76) pero solo 27 eventos externos: validación insuficiente.",
        "Segunda zona externa (Carhuaz–Yungay): la distancia a cauce para flujos repite AUC 0,76 (IC 0,71–0,79): "
        "VALIDACIÓN EXTERNA PROMETEDORA allí, pero el estado combinado sigue INSUFICIENTE (27 flujos en Conchucos). "
        "La pendiente para caídas queda refutada en dos zonas.",
        "Faltan lluvia y cobertura vegetal; ningún modelo validado bajo alcance definido.",
    ],
    keywords=["huayco", "huaico", "inundacion", "deslizamiento", "derrumbe", "incendio", "sequia",
              "sismo", "terremoto", "catastrofe", "desastre", "riesgo", "amenaza", "contaminacion", "fuga",
              "inventario", "ingemmet", "susceptibilidad"],
    api_prefix="/api/disasters",
)
