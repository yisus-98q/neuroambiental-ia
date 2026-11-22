ALERT = {"title": "Posible huayco en quebrada", "level": "alto", "source_name": "Observación de campo",
         "uncertainty": "Alta: un solo reporte visual", "is_simulated": True, "latitude": -9.5, "longitude": -77.5,
         "evidence": "Foto del cauce"}


def test_alert_lifecycle_and_report(client, analyst_h):
    r = client.post("/api/alerts", json={**ALERT, "alert_kind": "oficial"}, headers=analyst_h)
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["alert_kind"] == "experimental"  # nunca se acepta "oficial"
    assert alert["validation_status"] == "no_validada"
    r = client.post(f"/api/alerts/{alert['id']}/followups", headers=analyst_h,
                    json={"note": "Revisión en curso por el equipo", "new_status": "en_revision"})
    assert r.status_code == 201 and r.json()["validation_status"] == "en_revision"
    assert len(r.json()["followups"]) == 1
    rep = client.post(f"/api/alerts/{alert['id']}/report", headers=analyst_h).json()
    assert "No es una emergencia oficial" in rep["content_md"]
    assert "Datos simulados:** SÍ" in rep["content_md"]
    gj = client.get("/api/alerts/geojson", headers=analyst_h).json()
    assert any(f["properties"]["alert_id"] == alert["id"] for f in gj["features"])


def test_alert_requires_uncertainty_and_valid_level(client, analyst_h):
    assert client.post("/api/alerts", json={**ALERT, "uncertainty": ""}, headers=analyst_h).status_code == 422
    assert client.post("/api/alerts", json={**ALERT, "level": "critico"}, headers=analyst_h).status_code == 422
    assert client.post("/api/alerts", json={**ALERT, "latitude": 95}, headers=analyst_h).status_code == 422


def test_events(client, analyst_h):
    ev = {"event_type": "deslizamiento", "title": "Deslizamiento en vía", "source_name": "Prensa local",
          "is_simulated": False}
    assert client.post("/api/alerts/events", json=ev, headers=analyst_h).status_code == 201
    assert len(client.get("/api/alerts/events", headers=analyst_h).json()) >= 1


def test_model_registration_is_always_planned(client, analyst_h):
    body = {"name": "Clasificador cobertura", "module_key": "environmental", "algorithm": "RandomForest",
            "status": "validado"}
    r = client.post("/api/neurotraining/models", json=body, headers=analyst_h)
    assert r.status_code == 201 and r.json()["status"] == "planificado"
    bad = {**body, "module_key": "inventado"}
    assert client.post("/api/neurotraining/models", json=bad, headers=analyst_h).status_code == 422


def test_neurovoice_uses_real_counts(client, analyst_h):
    alerts_total = len(client.get("/api/alerts", headers=analyst_h).json())
    r = client.post("/api/neurovoice/chat", json={"message": "¿Cuántas alertas hay?"}, headers=analyst_h)
    body = r.json()
    assert r.status_code == 200 and body["module_key"] == "alerts"
    assert f"Hay {alerts_total} alerta" in body["reply"]
    r2 = client.post("/api/neurovoice/chat", headers=analyst_h,
                     json={"message": "estado de los módulos", "conversation_id": body["conversation_id"]})
    assert "en_desarrollo" in r2.json()["reply"]
    conv = client.get(f"/api/neurovoice/conversations/{body['conversation_id']}", headers=analyst_h).json()
    assert len(conv["messages"]) == 4


def test_conversations_are_private(client, analyst_h, admin_h):
    conv_id = client.post("/api/neurovoice/chat", json={"message": "hola"}, headers=analyst_h).json()["conversation_id"]
    assert client.get(f"/api/neurovoice/conversations/{conv_id}", headers=admin_h).status_code == 404


def test_dashboard_counts_come_from_db(client, admin_h):
    d = client.get("/api/dashboard", headers=admin_h).json()
    assert d["records"]["total"] == d["records"]["real"] + d["records"]["simulated"]
    assert len(d["modules"]) == 15


def test_territory_geometry_validated(client, analyst_h):
    ok = {"name": "Cuenca prueba", "geometry": {"type": "Point", "coordinates": [-77, -9]}}
    assert client.post("/api/territories", json=ok, headers=analyst_h).status_code == 201
    bad = {"name": "Mala", "geometry": {"type": "Point", "coordinates": [-777, -9]}}
    assert client.post("/api/territories", json=bad, headers=analyst_h).status_code == 422
