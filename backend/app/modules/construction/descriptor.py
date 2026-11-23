from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="construction",
    codename="NEUROCONSTRUCTION",
    name="Construcción y Planificación Territorial",
    version="0.1.0",
    description="Carga de planos y documentos; análisis de ubicación, pendientes, ríos y riesgos territoriales.",
    capabilities=[
        cap("carga_documentos", "Cargar PDF, PNG, JPG, GeoJSON y CSV (vía NEURODATA)", implemented=True),
        cap("analisis_ubicacion", "Analizar el emplazamiento (punto o polígono) sobre un DEM: elevación, entorno, susceptibilidad heurística e inundación demostrativa opcional", implemented=True),
        cap("pendientes_relieve", "Calcular pendientes y relieve con un DEM (emplazamiento y entorno)", implemented=True),
        cap("compatibilidad_territorial", "Evaluar compatibilidad territorial"),
        cap("proximidad_rios", "Medir proximidad a ríos (requiere una capa de ríos, aún no disponible)"),
        cap("observaciones", "Generar observaciones automáticas basadas solo en los números del análisis (reglas fijas)", implemented=True),
        cap("cad_bim", "Adaptadores CAD/BIM (futuro)"),
    ],
    dependencies=["neurodata", "disasters", "terrain"],
    inputs=["PDF", "PNG", "JPG", "GeoJSON", "CSV", "DEM registrado + punto o polígono"],
    outputs=["observaciones técnicas preliminares"],
    possible_errors=["documento_sin_ubicacion", "formato_no_soportado"],
    limitations=["No reemplaza evaluaciones profesionales ni autorizaciones oficiales.",
                 "El análisis usa un DEM de ≈100 m: no representa taludes ni obras menores.",
                 "No hay capa de ríos ni de zonificación: no se evalúa proximidad a cauces ni compatibilidad territorial.",
                 "Susceptibilidad e inundación son escenarios simplificados, no calibrados ni validados."],
    keywords=["construccion", "obra", "plano", "planos", "edificio", "proyecto", "planificacion",
              "infraestructura", "pendiente", "relieve", "cad", "bim"],
    api_prefix="/api/construction",
)
