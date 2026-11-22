from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neuro3d",
    codename="NEURO 3D SIMULATION ENGINE",
    group="simulacion",
    name="NEURO 3D LAB",
    version="0.1.0",
    api_prefix="/api/neuro3d",
    description="Terreno 3D desde DEM real (Copernicus GLO-30), pendiente y escenario demostrativo de trayectoria, "
                "conectados con el mapa 2D.",
    capabilities=[
        cap("terreno_dem", "Malla 3D del terreno desde un DEM real (Copernicus DEM GLO-30) con pendiente y estadísticas", True),
        cap("visor_threejs", "Visor 3D ligero con Three.js (render bajo demanda, exageración vertical, capas de elevación y pendiente)", True),
        cap("capas_3d", "Capas de NDVI, cambios y riesgo drapeadas sobre el terreno"),
        cap("escenarios_simplificados", "Escenario demostrativo de trayectoria de máxima pendiente (D8), rotulado como simulación", True),
        cap("comparador_escenarios", "Comparar estado actual y escenarios"),
    ],
    dependencies=["neurodata", "terrain"],
    inputs=["DEM Copernicus GLO-30", "punto de inicio (lon, lat)"],
    outputs=["terreno 3D", "estadísticas de pendiente", "trayectoria demostrativa rotulada como simulación"],
    possible_errors=["dem_no_disponible", "punto_fuera_del_dem", "memoria_insuficiente"],
    limitations=[
        "Las simulaciones son aproximaciones demostrativas: no son simulaciones geotécnicas ni hidráulicas.",
        "El DEM tiene ~100 m de resolución por defecto y errores verticales de varios metros; no sustituye un levantamiento.",
        "Aún no se dibujan capas de NDVI/cambios sobre el terreno ni se comparan escenarios.",
    ],
    keywords=["3d", "tridimensional", "simulacion", "simular", "escenario", "escenarios", "terreno", "relieve"],
)
