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
    v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h, json={"evidence": "x" * 60})
    assert v.status_code == 422 and "simulados" in v.text
    # Predicción: marcada como experimental y simulada.
    new = _upload(client, analyst_h, "nuevos.csv", _csv(n=40, seed=7), "true")
    p = client.post(f"/api/neurotraining/models/{mid}/predict", headers=analyst_h, json={"dataset_record_id": new})
    assert p.status_code == 200, p.text
    out = p.json()
    assert out["n"] == 40 and out["is_validated"] is False
    assert "NO validado" in out["uncertainty"] and "SIMULADOS" in out["uncertainty"]
    assert 0 <= out["rows"][0]["confidence"] <= 1
    # Reentrenar incrementa la versión.
    assert _train(client, analyst_h, mid, ds).json()["version"] == "1.1.0"


def test_regression_metrics(client, analyst_h):
    ds = _upload(client, analyst_h, "reg.csv", _csv(seed=3), "true")
    mid = _model(client, analyst_h, "Regresión caudal")
    r = _train(client, analyst_h, mid, ds, task="regresion", target="caudal", algorithm="ridge")
    assert r.status_code == 200, r.text
    met = r.json()["metrics"]
    assert met["r2"] > 0.9 and met["rmse"] >= met["mae"] > 0 and met["mae"] < met["baseline_mae_mean"]


def test_validation_requires_admin_evidence_and_real_data(client, analyst_h, admin_h):
    ds = _upload(client, analyst_h, "real.csv", _csv(seed=5), "false")
    mid = _model(client, analyst_h, "Modelo con datos declarados reales")
    assert _train(client, analyst_h, mid, ds).status_code == 200
    url = f"/api/neurotraining/models/{mid}/validate"
    assert client.post(url, headers=analyst_h, json={"evidence": "x" * 60}).status_code == 403
    assert client.post(url, headers=admin_h, json={"evidence": "corta"}).status_code == 422
    ok = client.post(url, headers=admin_h, json={"evidence": "Evaluado con 120 eventos independientes de 2024, "
                                                             "F1 0.81, revisado por geólogo."})
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
        v = client.post(f"/api/neurotraining/models/{mid}/validate", headers=admin_h, json={"evidence": "x" * 60})
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
