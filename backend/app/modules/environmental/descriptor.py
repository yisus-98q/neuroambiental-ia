from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="environmental",
    name="Predicción Ambiental Territorial",
    version="0.0.1",
    description="Cambios de vegetación, deforestación, ríos, lagunas, cobertura del suelo, erosión y degradación.",
    capabilities=[
        cap("comparacion_imagenes", "Comparar dos imágenes de una misma zona"),
        cap("analisis_temporal", "Series temporales de índices (p. ej. NDVI)"),
        cap("deteccion_cambios", "Identificar zonas con cambios"),
        cap("clasificacion_cobertura", "Clasificar cobertura cuando existan datos etiquetados"),
        cap("mapas_resultados", "Publicar resultados como capas del mapa"),
        cap("escenarios_futuros", "Proyectar escenarios con incertidumbre explícita"),
        cap("sentinel", "Integración con Sentinel-1 y Sentinel-2 (Copernicus, gratuito)"),
    ],
    dependencies=["neurodata"],
    inputs=["imagenes satelitales (GeoTIFF por bloques)", "GeoJSON de áreas de estudio"],
    outputs=["capas de cambio", "series temporales", "escenarios"],
    possible_errors=["imagen_sin_georreferencia", "nubosidad_excesiva", "memoria_insuficiente"],
    limitations=["Ninguna imagen se analiza todavía: el procesamiento raster no está implementado."],
    keywords=["vegetacion", "deforestacion", "bosque", "rio", "laguna", "cobertura", "erosion",
              "degradacion", "ndvi", "sentinel", "satelite", "ambiental", "glaciar"],
    api_prefix=None,
)
