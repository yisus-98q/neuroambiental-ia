"""SCIENTIFIC VALIDATION ENGINE: criterios congelados, separación geográfica, prueba sellada, doble aprobación."""
from __future__ import annotations

import pytest

from app.database.session import SessionLocal
from app.models import DataRecord, Run
from app.neurodata.service import get_or_create_source
from tests.backend.conftest import _ensure_user, _token

TRAIN_BBOX = [-77.75, -9.78, -77.25, -9.28]
TEST_REGION = [-77.5, -10.3, -77.0, -9.9]
CRITERIA = {"auc_min": 0.70, "ic95_inf_min": 0.60, "mejora_min": 0.05, "referencia": "auc_solo_elevacion_baja"}


def _summary(auc: float, ic_low: float, elev: float, simulado: bool = False) -> dict:
    variant = {"n_presencias": 55, "auc_solo_elevacion_baja": elev, "auc_heuristico_pendiente": 0.4,
               "regresion_logistica_geo": {"espacial": {"auc_mean": auc, "auc_sd": 0.05,
                                                        "auc_ic95_bloques": [ic_low, 0.9], "pr_auc": 0.5}},
               "regresion_logistica": {"espacial": {"auc_mean": auc - 0.08, "auc_ic95_bloques": [0.5, 0.8]}}}
    return {"simulado": simulado, "ausencias_libres": variant, "ausencias_mismo_rango_elevacion": variant,
            "por_proceso": {"1000|1500": {"ausencias_libres": variant, "ausencias_mismo_rango_elevacion": variant}}}


def _run(bbox: list[float], summary: dict) -> str:
    with SessionLocal() as db:
        src = get_or_create_source(db, "DEM de prueba SVE", "archivo")
        dem = DataRecord(source_id=src.id, data_type="raster_dem", title="DEM SVE", bbox=bbox, is_simulated=False,
                         validation_status="valido")
        db.add(dem)
        db.flush()
        run = Run(run_type="validacion_susceptibilidad", module_key="disasters", status="ok",
                  parameters={"dem_id": dem.id}, result_summary=summary)
        db.add(run)
        db.commit()
        return run.id


def _experiment(client, h, region=TEST_REGION):
    body = {"title": "Flujos 1500 con litología", "module_key": "disasters",
            "question": "¿La litología mejora la susceptibilidad a flujos fuera de Huaraz?",
            "protocol_text": "Validación espacial por bloques, franja de altura, 5 sorteos, zona de exclusión 500 m.",
            "criteria": CRITERIA, "test_region": region}
    r = client.post("/api/validation/experiments", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def second_admin_h(client):
    _ensure_user("admin2", "admin")
    return _token(client, "admin2")


@pytest.fixture()
def third_admin_h(client):
    _ensure_user("admin3", "admin")
    return _token(client, "admin3")


def test_full_lifecycle_requires_independent_test_and_two_approvals(client, analyst_h, admin_h, second_admin_h,
                                                                    third_admin_h):
    exp = _experiment(client, analyst_h)
    assert exp["estado_cientifico"] == "borrador" and len(exp["protocol_sha256"]) == 64
    url = f"/api/validation/experiments/{exp['id']}"
    cv = client.post(url + "/evaluations", headers=analyst_h, json={
        "run_id": _run(TRAIN_BBOX, _summary(0.78, 0.67, 0.66)), "model_ref": "1000|1500/regresion_logistica_geo",
        "partition": "cv"})
    assert cv.status_code == 201, cv.text
    assert cv.json()["estado_cientifico"] == "evaluado_interno"
    cv_eval = cv.json()["evaluations"][0]
    assert cv_eval["criteria_met"] is True and cv_eval["metrics"]["auc"] == 0.78
    # Una evaluación interna no se puede aprobar: solo la prueba independiente.
    d = {"evaluation_id": cv_eval["id"], "decision": "aprobar", "comment": "Revisado: métricas internas coherentes."}
    assert client.post(url + "/decisions", headers=admin_h, json=d).status_code == 422

    test_run = _run([-77.45, -10.25, -77.05, -9.95], _summary(0.76, 0.64, 0.68))
    t = client.post(url + "/evaluations", headers=analyst_h,
                    json={"run_id": test_run, "model_ref": "1000|1500/regresion_logistica_geo", "partition": "test"})
    assert t.status_code == 201, t.text
    out = t.json()
    assert out["estado_cientifico"] == "evaluado_independiente"
    test_eval = [e for e in out["evaluations"] if e["partition"] == "test"][0]
    assert test_eval["criteria_met"] is True
    # Prueba sellada: no se puede repetir la prueba con el mismo protocolo.
    again = client.post(url + "/evaluations", headers=analyst_h,
                        json={"run_id": test_run, "model_ref": "1000|1500/regresion_logistica_geo", "partition": "test"})
    assert again.status_code == 422 and "sellada" in again.text
    # Doble aprobación de administradores distintos; quien creó el experimento no puede aprobar.
    dec = {"evaluation_id": test_eval["id"], "decision": "aprobar",
           "comment": "Revisé la región de prueba independiente y las métricas por bloque."}
    assert client.post(url + "/decisions", headers=analyst_h, json=dec).status_code == 403
    r1 = client.post(url + "/decisions", headers=admin_h, json=dec)
    assert r1.status_code == 201 and r1.json()["estado_cientifico"] == "evaluado_independiente"
    assert client.post(url + "/decisions", headers=admin_h, json=dec).status_code == 422      # una vez por persona
    r2 = client.post(url + "/decisions", headers=second_admin_h, json=dec)
    assert r2.status_code == 201 and r2.json()["estado_cientifico"] == "validado_condicional"
    # Un rechazo posterior revoca el estado.
    rej = {**dec, "decision": "rechazar", "comment": "El área de prueba comparte el mismo estudio de 2007."}
    r3 = client.post(url + "/decisions", headers=third_admin_h, json=rej)
    assert r3.status_code == 201 and r3.json()["estado_cientifico"] == "evaluado_independiente"


def test_geographic_leakage_criteria_and_simulated_data(client, analyst_h, admin_h):
    exp = _experiment(client, analyst_h)
    url = f"/api/validation/experiments/{exp['id']}/evaluations"
    ref = "1000|1500/regresion_logistica_geo"
    # cv con un DEM que toca la región de prueba → fuga geográfica.
    leak = client.post(url, headers=analyst_h, json={"run_id": _run([-77.3, -10.0, -76.9, -9.6], _summary(0.8, 0.7, 0.6)),
                                                     "model_ref": ref, "partition": "cv"})
    assert leak.status_code == 422 and "Fuga" in leak.text
    # test fuera de la región de prueba → rechazado.
    out = client.post(url, headers=analyst_h, json={"run_id": _run(TRAIN_BBOX, _summary(0.8, 0.7, 0.6)),
                                                    "model_ref": ref, "partition": "test"})
    assert out.status_code == 422 and "dentro de la región" in out.text
    # Criterios: IC inferior bajo → no cumple; datos simulados → nunca cumplen.
    weak = client.post(url, headers=analyst_h, json={"run_id": _run(TRAIN_BBOX, _summary(0.78, 0.43, 0.66)),
                                                     "model_ref": ref, "partition": "cv"}).json()
    assert weak["evaluations"][-1]["criteria_met"] is False
    assert weak["evaluations"][-1]["criteria_detail"]["ic95_inferior"]["cumple"] is False
    sim = client.post(url, headers=analyst_h, json={"run_id": _run(TRAIN_BBOX, _summary(0.9, 0.8, 0.6, simulado=True)),
                                                    "model_ref": ref, "partition": "cv"}).json()
    assert sim["evaluations"][-1]["criteria_met"] is False
    # Referencias y modelos inexistentes.
    bad = client.post(url, headers=analyst_h, json={"run_id": _run(TRAIN_BBOX, _summary(0.8, 0.7, 0.6)),
                                                    "model_ref": "9999/regresion_logistica_geo", "partition": "cv"})
    assert bad.status_code == 422


def test_criteria_are_validated_and_frozen(client, analyst_h, reader_h):
    base = {"title": "Experimento inválido", "module_key": "disasters", "question": "¿Pregunta suficientemente larga?",
            "protocol_text": "Protocolo de prueba con más de cuarenta caracteres en total.", "test_region": None}
    assert client.post("/api/validation/experiments", headers=analyst_h,
                       json={**base, "criteria": {"auc_min": 0.4, "ic95_inf_min": 0.6, "mejora_min": 0.05,
                                                  "referencia": "auc_solo_elevacion_baja"}}).status_code == 422
    assert client.post("/api/validation/experiments", headers=analyst_h,
                       json={**base, "criteria": {"auc_min": 0.7}}).status_code == 422
    assert client.post("/api/validation/experiments", headers=reader_h,
                       json={**base, "criteria": CRITERIA}).status_code == 403
    exp = _experiment(client, analyst_h, region=None)
    # Sin región de prueba no hay evaluación independiente posible.
    t = client.post(f"/api/validation/experiments/{exp['id']}/evaluations", headers=analyst_h,
                    json={"run_id": _run(TRAIN_BBOX, _summary(0.8, 0.7, 0.6)),
                          "model_ref": "todos/regresion_logistica_geo", "partition": "test"})
    assert t.status_code == 422 and "región de prueba" in t.text
    # No hay endpoint de edición: los criterios quedan congelados.
    assert client.patch(f"/api/validation/experiments/{exp['id']}", headers=analyst_h, json={}).status_code == 405
    mod = client.get("/api/neurocore/modules/validation", headers=reader_h).json()
    assert mod["codename"] == "SCIENTIFIC VALIDATION ENGINE"
