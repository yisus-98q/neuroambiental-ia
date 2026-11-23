"""NEURO PREDICTION ENGINE: el catálogo separa observación, histórico, procesamiento, estimación,
simulación, predicción y alerta. La base de pruebas se comparte: se buscan elementos por id."""
from __future__ import annotations

import numpy as np
import pytest


# El router se registra en app.main (integración oficial): no hace falta incluirlo aquí.

BASE = "/api/neuroprediction"


def _csv(n=200, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    x1, x2 = rng.random(n), rng.random(n)
    y = np.where(x1 + x2 + rng.normal(0, 0.1, n) > 1.0, "alto", "bajo")
    lines = ["pendiente,lluvia,clase"] + [f"{a:.4f},{b:.4f},{c}" for a, b, c in zip(x1, x2, y)]
    return ("\n".join(lines) + "\n").encode()


def _upload(client, h, name, raw, simulated):
    r = client.post("/api/neurodata/upload", headers=h, data={"source_name": "Pruebas", "is_simulated": simulated},
                    files={"file": (name, raw)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _find(client, h, tipo, id_):
    r = client.get(f"{BASE}/catalog/{tipo}/{id_}", headers=h)
    assert r.status_code in (200, 404), r.text
    return r.json() if r.status_code == 200 else None


def _all(client, h, tipo=None):
    out, off = [], 0
    while True:
        q = f"?limit=200&offset={off}" + (f"&tipo={tipo}" if tipo else "")
        d = client.get(f"{BASE}/catalog{q}", headers=h).json()
        out += d["items"]
        off += 200
        if off >= d["total"]:
            return out, d


def _train_predict(client, analyst_h, ds_train, ds_pred):
    mid = client.post("/api/neurotraining/models", headers=analyst_h,
                      json={"name": "Modelo catálogo", "module_key": "disasters"}).json()["id"]
    body = {"dataset_record_id": ds_train, "task": "clasificacion", "target": "clase",
            "features": ["pendiente", "lluvia"], "algorithm": "random_forest"}
    m = client.post(f"/api/neurotraining/models/{mid}/train", headers=analyst_h, json=body)
    assert m.status_code == 200, m.text
    p = client.post(f"/api/neurotraining/models/{mid}/predict", headers=analyst_h, json={"dataset_record_id": ds_pred})
    assert p.status_code == 200, p.text
    return mid, m.json(), p.json()["prediction_id"]


@pytest.fixture(scope="module")
def seeded(client, analyst_h, admin_h):
    from app.database.session import SessionLocal
    from app.models import DataRecord, Run, Source
    ids: dict[str, str] = {}
    ids["csv_real"] = _upload(client, analyst_h, "real.csv", _csv(seed=1), "false")
    ids["csv_sim"] = _upload(client, analyst_h, "sim.csv", _csv(seed=2), "true")
    ev = {"event_type": "huayco", "title": "Huayco pasado", "occurred_at": "2020-02-01T10:00:00Z",
          "source_name": "Reporte municipal", "is_simulated": False, "latitude": -9.5, "longitude": -77.5}
    ids["evento_real"] = client.post("/api/alerts/events", headers=analyst_h, json=ev).json()["id"]
    ids["evento_sim"] = client.post("/api/alerts/events", headers=analyst_h,
                                    json={**ev, "title": "Huayco simulado", "is_simulated": True}).json()["id"]
    al = {"title": "Alerta de prueba", "level": "medio", "source_name": "Pruebas", "uncertainty": "Alta incertidumbre",
          "is_simulated": False}
    ids["alerta_no_val"] = client.post("/api/alerts", headers=analyst_h, json=al).json()["id"]
    ids["alerta_val"] = client.post("/api/alerts", headers=analyst_h, json={**al, "title": "Alerta validada"}).json()["id"]
    r = client.post(f"/api/alerts/{ids['alerta_val']}/followups", headers=analyst_h,
                    json={"note": "Verificada en campo", "new_status": "validada"})
    assert r.status_code == 201, r.text
    ids["alerta_sim_val"] = client.post("/api/alerts", headers=analyst_h,
                                        json={**al, "title": "Alerta simulada", "is_simulated": True}).json()["id"]
    client.post(f"/api/alerts/{ids['alerta_sim_val']}/followups", headers=analyst_h,
                json={"note": "Marcada validada por error", "new_status": "validada"})
    # Modelos: uno sin validar (datos simulados) y uno validado con datos reales.
    _, _, ids["pred_exp"] = _train_predict(client, analyst_h, ids["csv_sim"], ids["csv_sim"])
    mid, trained, _ = _train_predict(client, analyst_h, ids["csv_real"], ids["csv_real"])
    ev_txt = "Evaluado con 120 eventos independientes de 2024, F1 0.81, revisado por geólogo."
    v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h,
                    json={"evidence": ev_txt, "version": trained["version"], "artifact_sha256": trained["artifact_sha256"]})
    assert v.status_code == 200, v.text
    ids["pred_val"] = client.post(f"/api/neurotraining/models/{mid}/predict", headers=admin_h,
                                  json={"dataset_record_id": ids["csv_real"]}).json()["prediction_id"]
    ids["pred_val_sim_input"] = client.post(f"/api/neurotraining/models/{mid}/predict", headers=admin_h,
                                            json={"dataset_record_id": ids["csv_sim"]}).json()["prediction_id"]
    with SessionLocal() as db:
        src = db.query(Source).first()
        for key, dtype, sim in (("ndvi", "raster_ndvi", False), ("ndvi_sim", "raster_ndvi", True),
                                ("escenario", "raster_escenario", False), ("dem", "raster_dem", False)):
            rec = DataRecord(source_id=src.id, data_type=dtype, title=f"Prueba {dtype}", is_simulated=sim,
                             bbox=[-77.1, -9.1, -77.0, -9.0])
            db.add(rec)
            db.flush()
            ids[key] = rec.id
        run = Run(run_type="escenario_trayectoria", module_key="neuro3d", status="ok",
                  parameters={"record_id": ids["dem"], "lon": -77.0, "lat": -9.0, "metodo": "D8"})
        entrenamiento = Run(run_type="entrenamiento", module_key="neurotraining", status="ok")
        db.add_all([run, entrenamiento])
        db.flush()
        ids["run_escenario"], ids["run_entrenamiento"] = run.id, entrenamiento.id
        db.commit()
    return ids


@pytest.mark.parametrize("key,tipo,simulated", [
    ("csv_real", "observacion_real", False), ("dem", "observacion_real", False),
    ("csv_sim", "simulacion", True), ("evento_real", "dato_historico", False), ("evento_sim", "simulacion", True),
    ("ndvi", "resultado_procesamiento", False), ("ndvi_sim", "resultado_procesamiento", True),
    ("escenario", "simulacion", False), ("run_escenario", "simulacion", False),
    ("pred_exp", "estimacion_modelo", True), ("pred_val", "prediccion", False),
    ("pred_val_sim_input", "estimacion_modelo", True),
    ("alerta_no_val", "alerta_experimental", False), ("alerta_val", "alerta_verificada", False),
    ("alerta_sim_val", "alerta_experimental", True),
])
def test_each_source_lands_in_the_right_kind(client, reader_h, seeded, key, tipo, simulated):
    it = _find(client, reader_h, tipo, seeded[key])
    assert it is not None, f"{key} no aparece como {tipo}: " + client.get(f"{BASE}/catalog/{tipo}/{seeded[key]}", headers=reader_h).text
    assert it["tipo"] == tipo and it["simulated"] is simulated
    assert it["horizonte_temporal"] is None
    assert it["limitaciones"] and it["recomendaciones_de_verificacion"] and it["incertidumbre"]
    # No aparece en ningún otro tipo.
    for otro in ("observacion_real", "dato_historico", "resultado_procesamiento", "estimacion_modelo",
                 "simulacion", "prediccion", "alerta_verificada", "alerta_experimental"):
        if otro != tipo:
            assert _find(client, reader_h, otro, seeded[key]) is None, f"{key} también en {otro}"


def test_non_catalog_runs_are_excluded(client, reader_h, seeded):
    items, _ = _all(client, reader_h)
    assert seeded["run_entrenamiento"] not in {i["id"] for i in items}


def test_simulated_never_observation_or_prediction(client, reader_h, seeded):
    items, _ = _all(client, reader_h)
    assert items
    for i in items:
        if i["simulated"]:
            assert i["tipo"] not in ("observacion_real", "dato_historico", "prediccion", "alerta_verificada"), i
            assert i["verificado"] is False
        if i["tipo"] != "prediccion":
            assert i["probabilidad"] is None


def test_probability_null_for_unvalidated_model(client, reader_h, seeded):
    exp = _find(client, reader_h, "estimacion_modelo", seeded["pred_exp"])
    assert exp["probabilidad"] is None and "no validada" in exp["probabilidad_nota"].lower()
    assert exp["modelo"] and exp["version"] == "1.0.0" and "NO validado" in exp["incertidumbre"]
    val = _find(client, reader_h, "prediccion", seeded["pred_val"])
    assert val["verificado"] is True and 0 <= val["probabilidad"] <= 1 and "NO calibrado" in val["probabilidad_nota"]


def test_totals_are_coherent(client, reader_h, seeded):
    items, d = _all(client, reader_h)
    totales = d["totales_por_tipo"]
    assert set(totales) == {"observacion_real", "dato_historico", "resultado_procesamiento", "estimacion_modelo",
                            "simulacion", "prediccion", "alerta_verificada", "alerta_experimental"}
    assert d["total"] == sum(totales.values()) == len(items)
    for tipo, n in totales.items():
        por_tipo, _ = _all(client, reader_h, tipo)
        assert len(por_tipo) == n and all(i["tipo"] == tipo for i in por_tipo)
    assert len({(i["tipo"], i["id"]) for i in items}) == len(items)


def test_pagination_and_limits(client, reader_h, seeded):
    full, d = _all(client, reader_h)
    p1 = client.get(f"{BASE}/catalog?limit=5&offset=0", headers=reader_h).json()
    p2 = client.get(f"{BASE}/catalog?limit=5&offset=5", headers=reader_h).json()
    assert [i["id"] for i in p1["items"] + p2["items"]] == [i["id"] for i in full[:10]]
    assert p1["total"] == d["total"] and len(p1["items"]) == 5
    assert client.get(f"{BASE}/catalog?limit=201", headers=reader_h).status_code == 422
    assert client.get(f"{BASE}/catalog?limit=0", headers=reader_h).status_code == 422
    assert client.get(f"{BASE}/catalog?offset=-1", headers=reader_h).status_code == 422
    assert client.get(f"{BASE}/catalog?tipo=inventado", headers=reader_h).status_code == 422
    assert client.get(f"{BASE}/catalog/inventado/x", headers=reader_h).status_code == 422
    assert client.get(f"{BASE}/catalog/simulacion/no-existe", headers=reader_h).status_code == 404


def test_kinds_and_permissions(client, reader_h, seeded):
    kinds = client.get(f"{BASE}/kinds", headers=reader_h).json()
    assert len(kinds) == 8 and all(k["regla"] and k["definicion"] and k["limitaciones"] for k in kinds)
    assert next(k for k in kinds if k["tipo"] == "alerta_experimental")["verificado"] is False
    for path in ("/kinds", "/catalog", f"/catalog/simulacion/{seeded['escenario']}"):
        assert client.get(BASE + path).status_code == 401


def test_descriptor_declares_separation_but_not_calibration():
    from app.modules.neuroprediction.descriptor import DESCRIPTOR
    caps = {c.key: c.implemented for c in DESCRIPTOR.capabilities}
    assert caps["separacion_tipos"] is True
    assert caps["probabilidad_calibrada"] is False and caps["horizonte_temporal"] is False
    assert DESCRIPTOR.api_prefix == "/api/neuroprediction"
