"""Fase 3: entrenamiento real con scikit-learn. Los CSV se generan aquí y se cargan como SIMULADOS,
salvo uno marcado como real solo para probar el flujo de validación humana."""
from __future__ import annotations

import numpy as np

from app.core import jobs


def _csv(n=200, seed=0, noise=0.1) -> bytes:
    rng = np.random.default_rng(seed)
    x1, x2 = rng.random(n), rng.random(n)
    y = np.where(x1 + x2 + rng.normal(0, noise, n) > 1.0, "alto", "bajo")
    caudal = 3 * x1 + 2 * x2 + rng.normal(0, 0.05, n)
    lines = ["pendiente,lluvia,clase,caudal"] + [f"{a:.4f},{b:.4f},{c},{q:.4f}" for a, b, c, q in zip(x1, x2, y, caudal)]
    return ("\n".join(lines) + "\n").encode()


def _upload(client, h, name, raw, simulated):
    r = client.post("/api/neurodata/upload", headers=h, data={"source_name": "Pruebas", "is_simulated": simulated},
                    files={"file": (name, raw)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _model(client, h, name="Clasificador prueba"):
    r = client.post("/api/neurotraining/models", headers=h, json={"name": name, "module_key": "disasters"})
    assert r.status_code == 201
    return r.json()["id"]


def _train(client, h, model_id, ds, **kw):
    body = {"dataset_record_id": ds, "task": "clasificacion", "target": "clase",
            "features": ["pendiente", "lluvia"], "algorithm": "random_forest", **kw}
    return client.post(f"/api/neurotraining/models/{model_id}/train", headers=h, json=body)


def test_train_evaluate_predict_with_simulated_data(client, analyst_h, admin_h):
    ds = _upload(client, analyst_h, "sim.csv", _csv(), "true")
    mid = _model(client, analyst_h)
    r = _train(client, analyst_h, mid, ds)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["status"] == "entrenado" and m["trained_with_simulated"] is True and m["version"] == "1.0.0"
    met = m["metrics"]
    for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "confusion_matrix", "per_class",
                "roc_auc", "brier_score", "baseline_majority"):
        assert key in met
    assert met["n_test"] == 50 and met["accuracy"] > 0.8          # la regla es aprendible
    assert len(m["artifact_sha256"]) == 64
    # Nunca se valida con datos simulados.
    v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h, json=_reviewed(m, "x" * 60))
    assert v.status_code == 422 and "simulados" in v.text
    # Predicción: marcada como experimental y simulada.
    new = _upload(client, analyst_h, "nuevos.csv", _csv(n=40, seed=7), "true")
    p = client.post(f"/api/neurotraining/models/{mid}/predict", headers=analyst_h, json={"dataset_record_id": new})
    assert p.status_code == 200, p.text
    out = p.json()
    assert out["n"] == 40 and out["is_validated"] is False
    assert "NO validado" in out["uncertainty"] and "SIMULADOS" in out["uncertainty"]
    assert 0 <= out["rows"][0]["model_probability"] <= 1 and "NO está calibrada" in out["uncertainty"]
    assert out["input_simulated"] is True and "ENTRADA son SIMULADOS" in out["uncertainty"]
    # Reentrenar incrementa la versión.
    assert _train(client, analyst_h, mid, ds).json()["version"] == "1.1.0"


def test_regression_metrics(client, analyst_h):
    ds = _upload(client, analyst_h, "reg.csv", _csv(seed=3), "true")
    mid = _model(client, analyst_h, "Regresión caudal")
    r = _train(client, analyst_h, mid, ds, task="regresion", target="caudal", algorithm="ridge")
    assert r.status_code == 200, r.text
    met = r.json()["metrics"]
    assert met["r2"] > 0.9 and met["rmse"] >= met["mae"] > 0 and met["mae"] < met["baseline_mae_mean"]


def _reviewed(model: dict, evidence: str) -> dict:
    """Cuerpo de validación: la evidencia más la versión y la huella exactas que se revisaron."""
    return {"evidence": evidence, "version": model["version"], "artifact_sha256": model["artifact_sha256"]}


def test_validation_requires_admin_evidence_and_real_data(client, analyst_h, admin_h):
    ds = _upload(client, analyst_h, "real.csv", _csv(seed=5), "false")
    mid = _model(client, analyst_h, "Modelo con datos declarados reales")
    trained = _train(client, analyst_h, mid, ds).json()
    url = f"/api/neurotraining/models/{mid}/validate"
    long_ev = "Evaluado con 120 eventos independientes de 2024, F1 0.81, revisado por geólogo."
    assert client.post(url, headers=analyst_h, json=_reviewed(trained, long_ev)).status_code == 403
    assert client.post(url, headers=admin_h, json=_reviewed(trained, "corta")).status_code == 422
    stale = {**_reviewed(trained, long_ev), "version": "0.9.0"}          # revisó otra versión
    assert client.post(url, headers=admin_h, json=stale).status_code == 422
    ok = client.post(url, headers=admin_h, json=_reviewed(trained, long_ev))
    assert ok.status_code == 200 and ok.json()["status"] == "validado"
    assert _train(client, analyst_h, mid, ds).status_code == 422     # un modelo validado no se reentrena sin retirar


def test_model_worse_than_baseline_cannot_be_validated(client, analyst_h, admin_h):
    rng = np.random.default_rng(21)
    rows = ["a,b,clase"] + [f"{x:.4f},{y:.4f},{'alto' if rng.random() < 0.9 else 'bajo'}"
                            for x, y in rng.random((200, 2))]   # etiqueta al azar: no hay nada que aprender
    ds = _upload(client, analyst_h, "ruido.csv", ("\n".join(rows) + "\n").encode(), "false")
    mid = _model(client, analyst_h, "Ruido")
    r = _train(client, analyst_h, mid, ds, features=["a", "b"])
    assert r.status_code == 200
    if r.json()["metrics"]["accuracy"] <= r.json()["metrics"]["baseline_majority"]:
        v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h, json=_reviewed(r.json(), "x" * 60))
        assert v.status_code == 422 and "línea base" in v.text
    retire = client.post(f"/api/neurotraining/models/{mid}/retire", headers=admin_h)
    assert retire.status_code == 200
    assert client.post(f"/api/neurotraining/models/{mid}/retire", headers=admin_h).status_code == 422


def test_rejects_leakage_bad_columns_and_small_data(client, analyst_h):
    ds = _upload(client, analyst_h, "leak.csv", _csv(seed=9), "true")
    mid = _model(client, analyst_h, "Fugas")
    leak = _train(client, analyst_h, mid, ds, features=["pendiente", "clase"], target="clase")
    assert leak.status_code == 422 and "fuga" in leak.text
    assert _train(client, analyst_h, mid, ds, features=["no_existe"]).status_code == 422
    small = _upload(client, analyst_h, "small.csv", _csv(n=10), "true")
    assert _train(client, analyst_h, mid, small).status_code == 422


def test_tampered_artifact_is_not_loaded(client, analyst_h):
    from app.core.config import settings
    from app.database.session import SessionLocal
    from app.models import AIModel

    ds = _upload(client, analyst_h, "t.csv", _csv(seed=11), "true")
    mid = _model(client, analyst_h, "Alterado")
    assert _train(client, analyst_h, mid, ds).status_code == 200
    with SessionLocal() as db:
        path = settings.uploads_dir / db.get(AIModel, mid).artifact_path
    path.write_bytes(path.read_bytes() + b"x")
    p = client.post(f"/api/neurotraining/models/{mid}/predict", headers=analyst_h, json={"dataset_record_id": ds})
    assert p.status_code == 422 and "modificado" in p.text


def test_training_respects_busy_lock(client, analyst_h):
    ds = _upload(client, analyst_h, "b.csv", _csv(seed=13), "true")
    mid = _model(client, analyst_h, "Ocupado")
    jobs.LOCK.acquire()
    try:
        assert _train(client, analyst_h, mid, ds).status_code == 409
    finally:
        jobs.LOCK.release()
    runs = client.get("/api/neurotraining/runs", headers=analyst_h).json()
    assert any(r["run_type"] == "entrenamiento" and r["status"] == "ok" for r in runs)


def test_trainer_cannot_validate_own_model(client, admin_h):
    ds = _upload(client, admin_h, "propio.csv", _csv(seed=17), "false")
    mid = _model(client, admin_h, "Entrenado por admin")
    trained = _train(client, admin_h, mid, ds).json()
    v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h,
                    json=_reviewed(trained, "Evaluado con datos externos independientes por un tercero, F1 0.8."))
    assert v.status_code == 422 and "otro administrador" in v.text


def test_rare_class_is_a_clear_error_not_500(client, analyst_h):
    rows = ["a,b,clase"] + [f"{i/100:.2f},{i/50:.2f},{'x' if i else 'unica'}" for i in range(80)]
    ds = _upload(client, analyst_h, "rara.csv", ("\n".join(rows) + "\n").encode(), "true")
    mid = _model(client, analyst_h, "Clase rara")
    r = _train(client, analyst_h, mid, ds, features=["a", "b"])
    assert r.status_code == 422 and "al menos 2 filas" in r.text


def test_geospatial_dataset_cannot_be_validated_with_random_split(client, analyst_h, admin_h):
    rng = np.random.default_rng(11)
    n = 200
    lat, lon, pend = -9.5 + rng.random(n) * 0.5, -77.7 + rng.random(n) * 0.5, rng.random(n) * 40
    ev = (pend + rng.normal(0, 5, n) > 20).astype(int)
    raw = ("latitud,longitud,pendiente_deg,evento\n" + "\n".join(
        f"{a:.5f},{b:.5f},{c:.2f},{d}" for a, b, c, d in zip(lat, lon, pend, ev)) + "\n").encode()
    ds = _upload(client, analyst_h, "geo.csv", raw, "false")
    mid = _model(client, analyst_h, "Modelo geoespacial")
    r = _train(client, analyst_h, mid, ds, target="evento", features=["latitud", "longitud", "pendiente_deg"])
    assert r.status_code == 200, r.text
    m = r.json()
    met = m["metrics"]
    assert met["geoespacial"] and met["random_split_insufficient"]
    assert met["coordinate_features"] == ["latitud", "longitud"]
    assert any("memorizar la ubicación" in w for w in met["warnings"])
    v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h,
                    json=_reviewed(m, "Evaluado con 120 eventos independientes de 2024, revisado por geólogo."))
    assert v.status_code == 422 and "geoespacial" in v.text


def _geo_csv(n=300, seed=21) -> bytes:
    rng = np.random.default_rng(seed)
    lat, lon, pend = -9.5 + rng.random(n) * 0.5, -77.7 + rng.random(n) * 0.5, rng.random(n) * 40
    ev = np.where(pend + rng.normal(0, 6, n) > 20, "si", "no")
    return ("latitud,longitud,pendiente_deg,evento\n" + "\n".join(
        f"{a:.5f},{b:.5f},{c:.2f},{d}" for a, b, c, d in zip(lat, lon, pend, ev)) + "\n").encode()


def test_new_algorithms_spatial_split_seed_and_hyperparameters(client, analyst_h):
    ds = _upload(client, analyst_h, "geo300.csv", _geo_csv(), "true")
    mid = _model(client, analyst_h, "HGB espacial")
    r = _train(client, analyst_h, mid, ds, target="evento", features=["pendiente_deg"],
               algorithm="hist_gradient_boosting", split="espacial", blocks=4, seed=7)
    assert r.status_code == 200, r.text
    met = r.json()["metrics"]
    assert met["division"] == "espacial" and met["semilla"] == 7 and "bloques" in met["evaluated_on"]
    assert met["hiperparametros"]["random_state"] == 7 and "scikit_learn" in met["versiones"]
    assert met["dataset_sha256"]
    # MLP con 300 filas: no se justifica (mínimo 1000).
    r = _train(client, analyst_h, _model(client, analyst_h, "MLP"), ds, target="evento",
               features=["pendiente_deg"], algorithm="mlp")
    assert r.status_code == 422 and "1000" in r.text
    # División espacial sin coordenadas: rechazada.
    plain = _upload(client, analyst_h, "plain.csv", _csv(), "true")
    r = _train(client, analyst_h, _model(client, analyst_h, "Sin coords"), plain, split="espacial")
    assert r.status_code == 422 and "latitud" in r.text


def test_reproduce_and_export_model(client, analyst_h, reader_h):
    import io
    import json
    import zipfile
    ds = _upload(client, analyst_h, "rep.csv", _csv(seed=11), "true")
    mid = _model(client, analyst_h, "Reproducible")
    assert _train(client, analyst_h, mid, ds, seed=5).status_code == 200
    rep = client.post(f"/api/neurotraining/models/{mid}/reproduce", headers=analyst_h).json()
    assert rep["reproducible"] is True and rep["semilla"] == 5 and rep["metricas"]["accuracy"]["original"] is not None
    assert client.get(f"/api/neurotraining/models/{mid}/export", headers=reader_h).status_code == 403
    z = client.get(f"/api/neurotraining/models/{mid}/export", headers=analyst_h)
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(z.content)) as f:
        names = f.namelist()
        card = json.loads(f.read("model_card.json"))
    assert any(n.endswith(".joblib") for n in names)
    assert card["semilla"] == 5 and card["entrenado_con_simulados"] is True and len(card["artefacto_sha256"]) == 64
