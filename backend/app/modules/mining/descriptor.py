from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="mining",
    name="Inteligencia Minera y Geológica",
    version="0.0.1",
    description="Información geológica, mineralógica, geoquímica y geofísica; actividad minera y relaves.",
    capabilities=[
        cap("consulta_geologica", "Consultar capas geológicas cargadas"),
        cap("mapas_mineralogicos", "Incorporar mapas mineralógicos"),
        cap("geoquimica", "Analizar datos geoquímicos tabulares"),
        cap("geofisica", "Incorporar datos geofísicos"),
        cap("indicios_mineralizacion", "Señalar indicios (nunca confirmar reservas)"),
        cap("registro_actividad", "Registrar actividades mineras"),
        cap("monitoreo_relaves", "Monitorear relaves"),
        cap("impacto_ambiental", "Evaluar posibles impactos ambientales"),
    ],
    dependencies=["neurodata", "environmental", "terrain"],
    inputs=["CSV geoquímico", "GeoJSON de concesiones o depósitos", "mapas"],
    outputs=["capas temáticas", "indicios con incertidumbre", "fichas de actividad"],
    possible_errors=["datos_sin_coordenadas", "unidades_incompatibles"],
    limitations=["No confirma reservas minerales: eso requiere estudios técnicos y exploración de campo."],
    keywords=["mina", "minera", "mineria", "geologia", "geologico", "mineral", "geoquimica",
              "geofisica", "relave", "relaves", "yacimiento"],
)
