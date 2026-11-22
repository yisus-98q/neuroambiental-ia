from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurodata",
    codename="NEURODATA ENGINE",
    group="nucleo",
    name="NEURODATA ENGINE",
    version="0.1.0",
    description="Recepción, validación, metadatos, procedencia y almacenamiento de datos.",
    capabilities=[
        cap("carga_csv", "Carga y validación de CSV", implemented=True),
        cap("carga_geojson", "Carga y validación de GeoJSON", implemented=True),
        cap("carga_imagenes", "Carga de imágenes PNG/JPG (validación por firma)", implemented=True),
        cap("carga_documentos", "Carga de documentos PDF", implemented=True),
        cap("registro_manual", "Registro manual de mediciones", implemented=True),
        cap("metadatos_procedencia", "Metadatos, fuente, fechas, calidad y procedencia", implemented=True),
        cap("capas_mapa", "Exponer datos georreferenciados como capas GeoJSON", implemented=True),
    ],
    dependencies=[],
    inputs=["CSV", "GeoJSON", "PNG", "JPG", "PDF", "registro manual"],
    outputs=["registros de datos validados", "capas GeoJSON"],
    possible_errors=["formato_no_soportado", "archivo_demasiado_grande", "coordenadas_fuera_de_rango",
                     "csv_sin_encabezados", "geojson_invalido"],
    limitations=["Imágenes satelitales GeoTIFF aún no soportadas.", "Tamaño máximo por archivo configurable (10 MB por defecto)."],
    keywords=["dato", "datos", "archivo", "cargar", "subir", "csv", "geojson", "imagen", "medicion",
              "mediciones", "fuente", "fuentes"],
    api_prefix="/api/neurodata",
)
