from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="validation",
    codename="SCIENTIFIC VALIDATION ENGINE",
    name="Validación científica",
    version="0.1.0",
    description="Experimentos con criterios fijados de antemano, evaluaciones con separación geográfica, prueba "
                "independiente sellada y doble aprobación.",
    capabilities=[
        cap("experimentos", "Registrar experimentos con protocolo, criterios y región de prueba congelados (SHA-256)",
            implemented=True),
        cap("evaluaciones", "Registrar evaluaciones internas (cv) e independientes (test) leyendo las métricas de "
            "ejecuciones reales, con control de fuga geográfica", implemented=True),
        cap("prueba_sellada", "Permitir una sola evaluación de prueba por protocolo", implemented=True),
        cap("aprobaciones", "Doble aprobación de administradores distintos de los autores", implemented=True),
        cap("estados_cientificos", "Estado científico derivado: borrador → evaluado interno → evaluado independiente "
            "→ validado condicional (o retirado)", implemented=True),
        cap("versiones_dataset", "Versionado formal de datasets y divisiones"),
        cap("integracion_artefactos", "Vincular la validación a artefactos de NEURAL TRAINING"),
    ],
    dependencies=["neurodata", "neurotraining", "disasters"],
    inputs=["ejecuciones de validación de NEURODISASTER"],
    outputs=["estado científico por experimento", "historial de evaluaciones y decisiones"],
    possible_errors=["criterios_incompletos", "fuga_geografica", "prueba_ya_usada", "autoaprobacion"],
    limitations=[
        "«Validado condicional» vale solo para la configuración evaluada (grupo, variables, modelo), el área de "
        "prueba y el inventario usados; no autoriza decisiones sin revisión experta.",
        "Hoy no existe ninguna región de prueba independiente evaluada: ningún experimento puede estar validado.",
        "No versiona aún los datasets ni se vincula a los artefactos .joblib de NEURAL TRAINING.",
    ],
    keywords=["validacion", "experimento", "criterios", "aprobacion", "prueba", "independiente", "cientifica"],
    api_prefix="/api/validation",
)
