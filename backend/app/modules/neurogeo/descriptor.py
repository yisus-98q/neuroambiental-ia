from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurogeo",
    codename="NEUROGEO",
    name="Geología",
    version="0.0.1",
    description="Unidades y estructuras geológicas, fallas, geofísica, geoquímica, perforaciones y prospectividad.",
    capabilities=[
        cap("unidades_geologicas", "Consultar unidades y estructuras geológicas cargadas"),
        cap("geoquimica", "Analizar datos geoquímicos tabulares"),
        cap("geofisica", "Incorporar datos geofísicos"),
        cap("perforaciones", "Registrar información de perforaciones"),
        cap("prospectividad", "Mapas de prospectividad (indicios, nunca reservas)"),
    ],
    dependencies=["neurodata"],
    inputs=["mapas geológicos (GeoJSON)", "CSV geoquímico", "datos de perforación"],
    outputs=["capas temáticas", "zonas de interés con incertidumbre"],
    possible_errors=["unidades_incompatibles", "sistema_de_referencia_desconocido"],
    limitations=["Un indicio no equivale a un yacimiento; la IA no certifica reservas minerales."],
    keywords=["geologia", "geologico", "falla", "fallas", "mineral", "mineralizacion", "geoquimica", "geofisica",
              "perforacion", "yacimiento", "prospectividad"],
)
