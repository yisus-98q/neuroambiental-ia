"""Fase 7: NEUROVOICE consulta NEUROCORE y explica con datos reales; memoria de sesión; capacidades de voz honestas."""


def _chat(client, h, message, conv=None):
    r = client.post("/api/neurovoice/chat", headers=h, json={"message": message, "conversation_id": conv})
    assert r.status_code == 200, r.text
    return r.json()


def test_explains_predictions_and_models_with_real_counts(client, analyst_h):
    pred = _chat(client, analyst_h, "¿Qué predicciones hay?")
    assert pred["module_key"] == "neuroprediction"
    assert "Catálogo de resultados" in pred["reply"]
    models = _chat(client, analyst_h, "estado de los modelos entrenados")
    assert models["module_key"] == "neurotraining"


def test_simulation_answer_is_labelled_as_simulation(client, analyst_h):
    r = _chat(client, analyst_h, "explícame la simulación 3D")
    assert r["module_key"] == "neuro3d"
    # Sin terreno en esta base de pruebas: lo dice en lugar de inventar.
    assert "terreno" in r["reply"].lower()
    assert "SIMULACIÓN" in r["reply"] or "No hay" in r["reply"] or "Aún no hay" in r["reply"]


def test_session_memory_follow_up(client, analyst_h):
    first = _chat(client, analyst_h, "¿cuántas alertas hay?")
    assert first["module_key"] == "alerts"
    follow = _chat(client, analyst_h, "explícame más", first["conversation_id"])
    assert follow["intent"] == "seguimiento" and follow["module_key"] == "alerts"
    # Sin conversación previa, «explícame más» no tiene contexto: no se inventa el tema.
    alone = _chat(client, analyst_h, "explícame más")
    assert alone["intent"] == "desconocida"


def test_voice_capabilities_are_honest(client, reader_h):
    cap = client.get("/api/neurovoice/capabilities").json()
    assert cap["asr"]["where"] == "navegador" and "Google" in cap["asr"]["privacy"]
    assert cap["tts"]["where"].startswith("navegador")
    assert cap["languages"]["qu"]["voice"] is False and cap["languages"]["ay"]["voice"] is False
    mod = client.get("/api/neurocore/modules/neurovoice", headers=reader_h).json()
    caps = {c["key"]: c["implemented"] for c in mod["capabilities"]}
    assert caps["reconocimiento_voz"] and caps["sintesis_voz"]
    assert not caps["modelo_lenguaje"] and not caps["otros_idiomas"] and not caps["acciones_sensibles"]


def test_scenarios_are_not_counted_as_real_data(client, analyst_h):
    from app.database.session import SessionLocal
    from app.models import DataRecord
    from app.neurodata.service import get_or_create_source
    with SessionLocal() as db:
        src = get_or_create_source(db, "Escenario de prueba (voz)", "archivo")
        db.add(DataRecord(source_id=src.id, data_type="raster_escenario", title="SIMULACIÓN · prueba voz",
                          is_simulated=False, validation_status="valido"))
        db.commit()
    r = _chat(client, analyst_h, "¿cuántos datos hay en neurodata?")
    assert r["module_key"] == "neurodata"
    assert "escenario(s) hipotético(s)" in r["reply"] and "no son observaciones" in r["reply"]


def test_disasters_answer_explains_the_real_validation(client, analyst_h):
    from app.database.session import SessionLocal
    from app.models import Run
    summary = {"ausencias_libres": {"n_presencias": 181, "n_ausencias": 543, "auc_heuristico_pendiente": 0.486},
               "ausencias_mismo_rango_elevacion": {"regresion_logistica": {"espacial": {"auc_mean": 0.7415,
                                                                                         "auc_sd": 0.0875}}},
               "conclusion_automatica": ["El índice heurístico por pendiente NO discrimina."]}
    with SessionLocal() as db:
        db.add(Run(run_type="validacion_susceptibilidad", module_key="disasters", status="ok",
                   parameters={}, result_summary=summary))
        db.commit()
    r = _chat(client, analyst_h, "¿qué riesgo de deslizamiento hay?")
    assert r["module_key"] == "disasters"
    assert "AUC 0,49" in r["reply"] and "AUC 0,74" in r["reply"] and "NO discrimina" in r["reply"]
    assert "Ningún modelo de susceptibilidad está validado" in r["reply"]
