from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neuroindustrial",
    codename="NEUROINDUSTRIAL",
    name="Instalaciones industriales",
    version="0.0.1",
    description="Inspección visual, anomalías en variables operativas, corrosión y grietas visibles, escenarios de falla.",
    capabilities=[
        cap("inspeccion_visual", "Inspección visual de corrosión, grietas y deterioro"),
        cap("anomalias_sensores", "Detección de anomalías en vibración, temperatura y presión"),
        cap("escenarios_falla", "Escenarios hipotéticos de fugas e incendios"),
    ],
    dependencies=["neurodata", "neurovision"],
    inputs=["imágenes industriales", "series de sensores"],
    outputs=["anomalías con incertidumbre", "escenarios hipotéticos"],
    possible_errors=["serie_incompleta", "sensor_sin_calibracion"],
    limitations=[
        "No controla maquinaria ni activa paradas: no hay integración con sistemas de control.",
        "No sustituye inspecciones industriales certificadas.",
    ],
    keywords=["industrial", "industria", "planta", "corrosion", "vibracion", "presion", "temperatura", "fuga",
              "tanque", "tuberia"],
)
