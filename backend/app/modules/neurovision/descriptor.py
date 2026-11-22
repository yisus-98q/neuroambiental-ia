from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="neurovision",
    codename="NEUROVISION",
    name="Visión artificial",
    version="0.1.0",
    api_prefix="/api/neurovision",
    description="Procesamiento de imágenes (OpenCV) y modelos de visión: clasificación, detección, segmentación y cambios.",
    capabilities=[
        cap("procesamiento_opencv", "Bordes Canny, CLAHE, segmentación Otsu, índice de verdor ExG y características con OpenCV (determinista)", implemented=True),
        cap("analisis_imagen", "Imagen original, procesada, regiones, características, confianza y limitaciones", implemented=True),
        cap("cambios_imagenes", "Comparación de dos fotos de la misma escena: alineación ORB/RANSAC y regiones de cambio (sin georreferenciación)", implemented=True),
        cap("clasificacion", "Clasificación de imágenes con un modelo entrenado"),
        cap("segmentacion", "Segmentación de terreno, vegetación y agua"),
        cap("deteccion", "Detección de infraestructura y grietas visibles"),
    ],
    dependencies=["neurodata", "neurotraining"],
    inputs=["fotografías", "imágenes de dron", "imágenes satelitales compatibles"],
    outputs=["imágenes procesadas", "regiones detectadas", "características", "limitaciones (sin confianza estadística)"],
    possible_errors=["imagen_corrupta", "resolucion_insuficiente", "sin_modelo_entrenado"],
    limitations=["Clasificación, segmentación con modelo y detección de grietas/infraestructura NO están implementadas: requieren un modelo entrenado.", "El procesamiento de imágenes no es entrenamiento de una red neuronal: ambos se registran por separado."],
    keywords=["imagen", "imagenes", "foto", "fotografia", "dron", "vision", "opencv", "grieta", "grietas"],
)
