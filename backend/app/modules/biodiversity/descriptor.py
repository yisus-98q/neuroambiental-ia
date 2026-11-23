from app.neurocore.base import ModuleDescriptor, cap

DESCRIPTOR = ModuleDescriptor(
    key="biodiversity",
    name="Fauna, Flora y Biodiversidad",
    version="0.1.0",
    description="Registro de especies y observaciones georreferenciadas, con validación manual y capa de mapa.",
    capabilities=[
        cap("registro_especies", "Registrar especies (catálogo propio, sin especies precargadas)", True),
        cap("registro_observaciones", "Registrar observaciones georreferenciadas y validarlas", True),
        cap("analisis_fotografias", "Analizar fotografías (sin modelo: la foto solo se enlaza como evidencia)"),
        cap("reconocimiento_especies", "Reconocer especies con un modelo validado (no existe tal modelo)"),
        cap("cambio_habitat", "Analizar cambios de hábitat (sin análisis implementado)"),
        cap("fragmentacion", "Analizar fragmentación de ecosistemas (sin análisis implementado)"),
    ],
    dependencies=["neurodata", "environmental"],
    inputs=["formulario de especies y observaciones", "fotografías ya cargadas en NEURODATA"],
    outputs=["registros de especies", "observaciones", "capa GeoJSON de observaciones", "resumen por especie, mes y estado"],
    possible_errors=["coordenadas_fuera_de_rango", "fecha_futura", "especie_duplicada", "foto_no_es_imagen"],
    limitations=[
        "No hay modelo de reconocimiento de especies: la identificación la declara el observador y no se verifica.",
        "Las fotografías no se analizan; solo se enlazan como evidencia.",
        "No se analiza cambio de hábitat ni fragmentación.",
        "La categoría de conservación (tipo UICN) se muestra según la fuente indicada; el sistema no la evalúa.",
        "La riqueza de especies (nº de especies distintas) depende del esfuerzo de muestreo: no es un índice de biodiversidad.",
        "El catálogo de especies empieza vacío: no hay especies precargadas.",
    ],
    keywords=["fauna", "flora", "especie", "especies", "biodiversidad", "habitat", "animal",
              "planta", "ecosistema", "fragmentacion", "observacion", "avistamiento"],
)
