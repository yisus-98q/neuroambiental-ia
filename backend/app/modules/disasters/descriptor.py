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
        "Resultado real en Huaraz (181 movimientos en masa): la pendiente sola no discrimina (AUC 0,49); "
        "pendiente + elevación da AUC espacial ~0,74 tras corregir el sesgo de elevación, explicado casi solo "
        "por la elevación. Ningún modelo de susceptibilidad está validado para uso operativo.",
        "Faltan variables clave (litología, geomorfología, lluvia, cobertura) para un modelo útil.",
    ],
    keywords=["huayco", "huaico", "inundacion", "deslizamiento", "derrumbe", "incendio", "sequia",
              "sismo", "terremoto", "catastrofe", "desastre", "riesgo", "amenaza", "contaminacion", "fuga",
              "inventario", "ingemmet", "susceptibilidad"],
    api_prefix="/api/disasters",
)
