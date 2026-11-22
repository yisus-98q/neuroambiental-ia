from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurovision",
    codename="NEUROVISION",
    name="Visión artificial",
    version="0.0.1",
    description="Procesamiento de imágenes (OpenCV) y modelos de visión: clasificación, detección, segmentación y cambios.",
    capabilities=[
        cap("procesamiento_opencv", "Procesamiento de imágenes con OpenCV (requiere autorización de instalación)"),
        cap("analisis_imagen", "Imagen original, procesada, regiones, características, confianza y limitaciones"),
        cap("cambios_imagenes", "Comparación temporal de imágenes georreferenciadas"),
        cap("clasificacion", "Clasificación de imágenes con un modelo entrenado"),
        cap("segmentacion", "Segmentación de terreno, vegetación y agua"),
        cap("deteccion", "Detección de infraestructura y grietas visibles"),
    ],
    dependencies=["neurodata", "neurotraining"],
    inputs=["fotografías", "imágenes de dron", "imágenes satelitales compatibles"],
    outputs=["imágenes procesadas", "regiones detectadas", "resultados con confianza"],
    possible_errors=["imagen_corrupta", "resolucion_insuficiente", "sin_modelo_entrenado"],
    limitations=["El procesamiento de imágenes no es entrenamiento de una red neuronal: ambos se registran por separado."],
    keywords=["imagen", "imagenes", "foto", "fotografia", "dron", "vision", "opencv", "grieta", "grietas"],
)
