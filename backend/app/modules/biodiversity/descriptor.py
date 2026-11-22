from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="biodiversity",
    name="Fauna, Flora y Biodiversidad",
    version="0.0.1",
    description="Registro de especies y observaciones, hábitat y fragmentación de ecosistemas.",
    capabilities=[
        cap("registro_especies", "Registrar especies"),
        cap("registro_observaciones", "Registrar observaciones georreferenciadas"),
        cap("analisis_fotografias", "Analizar fotografías"),
        cap("reconocimiento_especies", "Reconocer especies con un modelo validado"),
        cap("cambio_habitat", "Analizar cambios de hábitat"),
        cap("fragmentacion", "Analizar fragmentación de ecosistemas"),
    ],
    dependencies=["neurodata", "environmental"],
    inputs=["fotografías", "CSV de observaciones", "GeoJSON de hábitats"],
    outputs=["registros de especies", "capas de hábitat"],
    possible_errors=["especie_no_reconocida", "foto_sin_ubicacion"],
    limitations=["No hay modelo de reconocimiento de especies entrenado ni validado."],
    keywords=["fauna", "flora", "especie", "especies", "biodiversidad", "habitat", "animal",
              "planta", "ecosistema", "fragmentacion"],
)
