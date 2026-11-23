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
        cap("capas_3d", "Capa «Escenario» sobre el terreno 3D: clases de susceptibilidad heurística (con NDVI opcional) y profundidad de inundación demostrativa", True),
        cap("escenarios_simplificados", "Escenario demostrativo de trayectoria de máxima pendiente (D8), rotulado como simulación", True),
        cap("comparador_escenarios", "Comparar 2-4 configuraciones de escenario lado a lado frente al estado actual observado (cálculo en memoria, sin guardar)", True),
    ],
    dependencies=["neurodata", "terrain"],
    inputs=["DEM Copernicus GLO-30", "NDVI opcional", "punto de inicio (lon, lat)", "pesos, umbrales y subida de nivel"],
    outputs=["terreno 3D", "estadísticas de pendiente", "trayectoria, susceptibilidad e inundación rotuladas como simulación", "tabla comparativa de escenarios"],
    possible_errors=["dem_no_disponible", "punto_fuera_del_dem", "memoria_insuficiente"],
    limitations=[
        "Las simulaciones son aproximaciones demostrativas: no son simulaciones geotécnicas ni hidráulicas.",
        "El DEM tiene ~100 m de resolución por defecto y errores verticales de varios metros; no sustituye un levantamiento.",
        "La susceptibilidad es un índice heurístico (pendiente/45° y 1−NDVI) NO calibrado ni validado con inventarios de eventos; no predice deslizamientos ni fechas.",
        "La inundación es un modelo de bañera: ignora caudal, cauce, rugosidad, tiempo y drenaje; no es una simulación hidráulica y se trunca en el borde del DEM.",
        "Los escenarios son hipotéticos y se rotulan SIMULACIÓN; el comparador no guarda resultados. No se dibujan capas de cambios de NDVI.",
        "La trayectoria D8 no rellena depresiones: un pozo de ruido del DEM puede detenerla; si se detiene junto "
        "a celdas sin dato se informa «sin_dato».",
    ],
    keywords=["3d", "tridimensional", "simulacion", "simular", "escenario", "escenarios", "terreno", "relieve"],
)
