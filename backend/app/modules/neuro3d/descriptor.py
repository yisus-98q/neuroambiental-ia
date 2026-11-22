from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neuro3d",
    codename="NEURO 3D SIMULATION ENGINE",
    group="simulacion",
    name="NEURO 3D LAB",
    version="0.0.1",
    description="Terreno 3D desde DEM, capas de riesgo y escenarios simplificados, conectados con el mapa 2D.",
    capabilities=[
        cap("terreno_dem", "Malla 3D del terreno desde un DEM real (Copernicus DEM GLO-30)"),
        cap("visor_threejs", "Visor 3D ligero con Three.js (requiere autorización de instalación)"),
        cap("capas_3d", "Capas de NDVI, cambios y riesgo sobre el terreno"),
        cap("escenarios_simplificados", "Escenarios demostrativos de deslizamiento e inundación"),
        cap("comparador_escenarios", "Comparar estado actual y escenarios"),
    ],
    dependencies=["neurodata", "terrain"],
    inputs=["DEM", "capas raster", "parámetros de escenario"],
    outputs=["terreno 3D", "escenarios rotulados como simulación"],
    possible_errors=["dem_no_disponible", "memoria_insuficiente"],
    limitations=["Las simulaciones son aproximaciones demostrativas: no son simulaciones geotécnicas ni hidráulicas."],
    keywords=["3d", "tridimensional", "simulacion", "simular", "escenario", "escenarios", "terreno", "relieve"],
)
