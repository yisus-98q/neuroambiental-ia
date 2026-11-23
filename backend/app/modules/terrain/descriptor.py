from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="terrain",
    codename="NEUROTERRAIN",
    name="Movimientos Territoriales",
    version="0.1.0",
    description="Desplazamientos, deformaciones, laderas, taludes, suelos, infraestructura y depósitos mineros. "
                "Series de sensores importadas por CSV con indicadores experimentales por umbrales.",
    capabilities=[
        cap("series_desplazamiento",
            "Series de desplazamiento de sensores (CSV de NEURODATA): acumulado, velocidad por regresión, saltos", True),
        cap("gps", "GPS solo por CSV: series de una variable ya expresada como desplazamiento "
                   "(sin conexión a receptores ni conversión de coordenadas)", True),
        cap("insar", "Integración con InSAR (Sentinel-1)"),
        cap("inclinometros", "Inclinómetros solo por CSV: lecturas ya convertidas a desplazamiento "
                             "(sin conexión a equipos ni cálculo de perfiles)", True),
        cap("deteccion_aceleraciones",
            "Detectar aceleraciones por comparación de velocidades entre ventanas (indicador experimental)", True),
    ],
    dependencies=["neurodata"],
    inputs=["mediciones de sensores (CSV registrado en NEURODATA, formato largo o ancho)", "productos InSAR (no implementado)"],
    outputs=["series temporales", "velocidad y aceleración", "saltos/anomalías", "clasificación experimental",
             "alertas experimentales a petición"],
    possible_errors=["serie_incompleta", "sensor_sin_calibracion", "fechas_desordenadas", "fechas_duplicadas"],
    limitations=[
        "Indicador experimental por umbrales de EJEMPLO configurables; no es una predicción de falla ni sustituye el criterio geotécnico.",
        "No hay conexión en vivo con GPS, inclinómetros ni otros equipos: solo CSV subidos a NEURODATA.",
        "No hay InSAR ni procesamiento de Sentinel-1; no se calculan desplazamientos desde coordenadas crudas.",
        "Sin compensación de temperatura, calibración ni modelos físicos; los saltos solo se marcan, no se explican.",
    ],
    keywords=["desplazamiento", "deformacion", "ladera", "talud", "taludes", "movimiento",
              "inclinometro", "insar", "gps", "suelo", "asentamiento"],
    api_prefix="/api/terrain",
)
