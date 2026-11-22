from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="environmental",
    name="Predicción Ambiental Territorial",
    version="0.2.0",
    description="Cambios de vegetación, deforestación, ríos, lagunas, cobertura del suelo, erosión y degradación.",
    capabilities=[
        cap("sentinel2", "Búsqueda y lectura por recorte de Sentinel-2 L2A (Copernicus, gratuito, sin cuenta)",
            implemented=True),
        cap("ndvi", "Cálculo de NDVI con máscara de nubes y sombras (SCL)", implemented=True),
        cap("comparacion_imagenes", "Comparar dos fechas de una misma zona en una malla común", implemented=True),
        cap("deteccion_cambios", "Identificar zonas con disminución o aumento de NDVI", implemented=True),
        cap("mapas_resultados", "Publicar resultados como capas del mapa", implemented=True),
        cap("analisis_temporal", "Series temporales de índices con muchas fechas"),
        cap("clasificacion_cobertura", "Clasificar cobertura cuando existan datos etiquetados"),
        cap("escenarios_futuros", "Proyectar escenarios con incertidumbre explícita"),
        cap("sentinel1", "Integración con Sentinel-1 (radar)"),
    ],
    dependencies=["neurodata"],
    inputs=["área de estudio (bbox, máx. 0,5° x 0,5°)", "escenas Sentinel-2 L2A"],
    outputs=["rasters NDVI (GeoTIFF)", "rasters de cambio", "vistas previas PNG para el mapa", "estadísticas"],
    possible_errors=["escena_no_cubre_area", "sin_pixeles_validos", "servicio_remoto_no_disponible",
                     "procesamiento_en_curso", "area_demasiado_grande"],
    limitations=[
        "Un cambio de NDVI no confirma deforestación ni daño: debe validarse (campo o imágenes de alta resolución).",
        "Resolución reducida (~33 m por defecto) para ahorrar memoria y descargas.",
        "Un solo procesamiento a la vez; cada NDVI tarda de segundos a pocos minutos según la conexión.",
        "Nieve, sombras de relieve y estacionalidad afectan el NDVI en zonas andinas.",
    ],
    keywords=["vegetacion", "deforestacion", "bosque", "rio", "laguna", "cobertura", "erosion",
              "degradacion", "ndvi", "sentinel", "satelite", "ambiental", "glaciar", "cambio", "cambios"],
    api_prefix="/api/environmental",
)
