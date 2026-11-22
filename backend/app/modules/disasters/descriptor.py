from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="disasters",
    name="Predicción de Catástrofes",
    version="0.0.1",
    description="Huaycos, inundaciones, deslizamientos, incendios, sequías, sismos, relaves y accidentes industriales.",
    capabilities=[
        cap("amenaza", "Evaluar amenaza"),
        cap("exposicion", "Evaluar exposición"),
        cap("vulnerabilidad", "Evaluar vulnerabilidad"),
        cap("riesgo", "Combinar amenaza, exposición y vulnerabilidad en riesgo"),
        cap("registro_eventos_historicos", "Usar eventos históricos registrados"),
    ],
    dependencies=["neurodata", "environmental", "terrain", "alerts"],
    inputs=["eventos históricos", "pendientes", "lluvia", "capas de exposición"],
    outputs=["mapas de susceptibilidad y riesgo con incertidumbre"],
    possible_errors=["datos_historicos_insuficientes"],
    limitations=[
        "No puede predecir la fecha exacta de terremotos, explosiones ni otros eventos.",
        "Ningún modelo de riesgo está implementado ni validado todavía.",
    ],
    keywords=["huayco", "huaico", "inundacion", "deslizamiento", "derrumbe", "incendio", "sequia",
              "sismo", "terremoto", "catastrofe", "desastre", "riesgo", "amenaza", "contaminacion", "fuga"],
)
