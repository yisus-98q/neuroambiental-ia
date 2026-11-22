from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="construction",
    codename="NEUROCONSTRUCTION",
    name="Construcción y Planificación Territorial",
    version="0.0.1",
    description="Carga de planos y documentos; análisis de ubicación, pendientes, ríos y riesgos territoriales.",
    capabilities=[
        cap("carga_documentos", "Cargar PDF, PNG, JPG, GeoJSON y CSV (vía NEURODATA)", implemented=True),
        cap("analisis_ubicacion", "Analizar ubicación y proximidad a ríos"),
        cap("pendientes_relieve", "Calcular pendientes y relieve con un DEM"),
        cap("compatibilidad_territorial", "Evaluar compatibilidad territorial"),
        cap("observaciones", "Generar observaciones sobre el proyecto"),
        cap("cad_bim", "Adaptadores CAD/BIM (futuro)"),
    ],
    dependencies=["neurodata", "disasters", "terrain"],
    inputs=["PDF", "PNG", "JPG", "GeoJSON", "CSV"],
    outputs=["observaciones técnicas preliminares"],
    possible_errors=["documento_sin_ubicacion", "formato_no_soportado"],
    limitations=["No reemplaza evaluaciones profesionales ni autorizaciones oficiales."],
    keywords=["construccion", "obra", "plano", "planos", "edificio", "proyecto", "planificacion",
              "infraestructura", "pendiente", "relieve", "cad", "bim"],
    api_prefix="/api/neurodata",
)
