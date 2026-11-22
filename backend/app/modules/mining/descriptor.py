from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="mining",
    codename="NEUROMINING",
    name="Inteligencia Minera",
    version="0.0.2",
    description="Actividad minera: tajos, botaderos, relaves, drenaje, taludes e impactos en cuerpos de agua.",
    capabilities=[
        cap("registro_actividad", "Registrar actividades e infraestructura minera"),
        cap("cambios_tajos_botaderos", "Comparar imágenes históricas de tajos y botaderos"),
        cap("monitoreo_relaves", "Monitorear depósitos de relaves"),
        cap("drenaje_agua", "Posibles impactos en cuerpos de agua y drenaje minero"),
        cap("estabilidad_taludes", "Análisis de estabilidad de taludes (requiere datos geotécnicos)"),
    ],
    dependencies=["neurodata", "environmental", "terrain"],
    inputs=["imágenes multitemporales", "GeoJSON de concesiones o depósitos", "datos de sensores"],
    outputs=["capas de cambio", "fichas de actividad", "indicadores con incertidumbre"],
    possible_errors=["datos_sin_coordenadas", "imagenes_no_comparables"],
    limitations=["No sustituye estudios geotécnicos ni inspecciones mineras."],
    keywords=["mina", "minera", "mineria", "relave", "relaves", "tajo", "botadero", "talud"],
)
