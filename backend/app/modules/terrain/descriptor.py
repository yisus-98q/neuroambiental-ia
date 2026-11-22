from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="terrain",
    codename="NEUROTERRAIN",
    name="Movimientos Territoriales",
    version="0.0.1",
    description="Desplazamientos, deformaciones, laderas, taludes, suelos, infraestructura y depósitos mineros.",
    capabilities=[
        cap("series_desplazamiento", "Series de desplazamiento de sensores"),
        cap("gps", "Integración con GPS"),
        cap("insar", "Integración con InSAR (Sentinel-1)"),
        cap("inclinometros", "Integración con inclinómetros"),
        cap("deteccion_aceleraciones", "Detectar aceleraciones anómalas de movimiento"),
    ],
    dependencies=["neurodata"],
    inputs=["mediciones de sensores (CSV)", "productos InSAR"],
    outputs=["series temporales", "zonas en movimiento"],
    possible_errors=["serie_incompleta", "sensor_sin_calibracion"],
    limitations=["Las tablas de sensores y mediciones existen, pero aún no hay análisis."],
    keywords=["desplazamiento", "deformacion", "ladera", "talud", "taludes", "movimiento",
              "inclinometro", "insar", "gps", "suelo", "asentamiento"],
)
