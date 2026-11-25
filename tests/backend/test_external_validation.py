"""Misión 2.1: evaluación externa prerregistrada (sin fuga de etiquetas) e integración en NEUROCORE/NEURO
PREDICTION/NEUROVOICE."""
from __future__ import annotations

import numpy as np

from app.modules.disasters import external
from tests.backend.test_disasters import BBOX, _dem, _events, _register_dem


def _fc(seed: int, n: int = 45):
    rng = np.random.default_rng(seed)
    cells = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, n), rng.choice(
        np.r_[np.arange(3, 40), np.arange(160, 197)], n))]
    fc = _events(cells, code="1000|1100")
    fc["features"] += _events([(int(r), int(c)) for r, c in zip(rng.integers(5, 195, n), rng.integers(80, 120, n))],
                              code="1000|1500")["features"]
    return fc


def test_decision_rules_follow_the_preregistered_protocol():
    def g(auc, ic, sd=0.01, elev=0.55, m3s=0.75):
        f = {"auc_sorteos": {"media": auc, "sd": sd}, "auc_ic95_bloques": ic}
        return {"franja": {"X": f, "M3-topo+litologia": f, "R1-solo_elevacion": {"auc_sorteos": {"media": elev}},
                           "M3s-sin_Sedimento": {"auc_sorteos": {"media": m3s}}}}
    assert external.decide(g(0.8, [0.7, 0.85]), "X", 25)["estado"] == "VALIDACIÓN INSUFICIENTE"   # < 30 eventos
    assert external.decide(g(0.8, [0.45, 0.9]), "X", 40)["estado"] == "VALIDACIÓN INSUFICIENTE"   # IC > 0,30
    assert external.decide(g(0.55, [0.45, 0.62]), "X", 40)["estado"] == "NO VALIDADO"
    assert external.decide(g(0.76, [0.66, 0.84]), "X", 40)["estado"] == "VALIDACIÓN EXTERNA PROMETEDORA"
    assert external.decide(g(0.76, [0.66, 0.84], elev=0.74), "X", 40)["estado"] == "EXPERIMENTAL"  # ≈ solo elevación
    assert external.decide(g(0.76, [0.66, 0.84], sd=0.05), "X", 40)["estado"] == "EXPERIMENTAL"    # inestable
    # Litología: si sin «Sedimento» no se sostiene, se marca posible circularidad.
    r = external.decide(g(0.76, [0.66, 0.84], m3s=0.62), "M3-topo+litologia", 40)
    assert r["estado"] == "EXPERIMENTAL" and "circularidad" in r["motivo"]
    # Nunca «validado» desde aquí: requiere segunda zona y aprobaciones humanas.
    assert all(external.decide(g(0.95, [0.9, 0.97]), "X", 200)["estado"] != "VALIDADO BAJO ALCANCE DEFINIDO"
               for _ in range(1))


def test_external_labels_never_change_training():
    arr = _dem()
    a, b = _fc(1), _fc(2)
    r1 = external.run(arr, BBOX, a, None, arr, BBOX, b, None)
    b_shuffled = _fc(3)                                   # otras etiquetas externas
    r2 = external.run(arr, BBOX, a, None, arr, BBOX, b_shuffled, None)
    for g in ("1000|1100", "1000|1500"):
        t1, t2 = r1["grupos"][g]["entrenamiento"], r2["grupos"][g]["entrenamiento"]
        assert t1["auc_entrenamiento"] == t2["auc_entrenamiento"]          # el entrenamiento solo depende de A
        f = r1["grupos"][g]["franja"]["M2-topografico"]
        assert f["auc_sorteos"]["n"] == 10 and "confusion" in f and f["calibracion"]
        assert f["umbral_fijado_en_entrenamiento"] is not None
        assert r1["grupos"][g]["franja"]["V-pendiente_deg"]["brier"] is None   # una variable no es probabilidad
        assert set(r1["grupos"][g]["estados"]) >= {"M1-base", "M2-topografico", "R1-solo_elevacion"}


def test_external_results_are_integrated_and_labelled(client, analyst_h, reader_h, monkeypatch):
    from app.database.session import SessionLocal
    from app.modules.disasters import service as sd
    from tests.backend.test_disasters import _import
    arr = _dem()
    dem_a, dem_b = _register_dem(arr), _register_dem(arr)
    inv_a = _import(client, analyst_h, monkeypatch, _fc(5))["id"]
    inv_b = _import(client, analyst_h, monkeypatch, _fc(6))["id"]
    with SessionLocal() as db:
        out = sd.external_validation(db, None, dem_a=dem_a, inv_a=inv_a, lito_a=None, dem_b=dem_b, inv_b=inv_b,
                                     lito_b=None, zona_b="Zona de prueba")
    assert out["simulado"] is True                                           # DEM de prueba simulado
    ext = client.get("/api/disasters/external", headers=reader_h).json()
    assert ext and ext[0]["zona"] == "Zona de prueba" and ext[0]["estados"]
    ov = client.get("/api/neurocore/overview", headers=reader_h).json()["validacion_externa"]
    assert ov["zona"] == "Zona de prueba" and ov["grupos"] and ov["limitaciones"]
    cat = client.get("/api/neuroprediction/catalog?tipo=estimacion_modelo", headers=reader_h).json()
    item = next(i for i in cat["items"] if i["id"] == out["run_id"])
    assert item["estado_cientifico"].startswith("EVALUADO EXTERNAMENTE") and "no es una predicción" in item["resultado"]
    r = client.post("/api/neurovoice/chat", headers=analyst_h, json={"message": "riesgo de deslizamientos"}).json()
    assert "no es una predicción cierta" in r["reply"]


def test_register_external_result_from_another_machine(client, reader_h):
    from app.database.session import SessionLocal
    from app.modules.disasters import service as sd
    from app.modules.disasters import validation as v
    res = {"zona_externa": "Zona importada", "grupos": {"todos": {"n_eventos_externos": 40, "estados": {
        "M2-topografico": {"estado": "EXPERIMENTAL", "motivo": "prueba"}}}}, "parametros": {"dem_b": "x"}}
    with SessionLocal() as db:
        run = sd.register_external_result(db, res, "GitHub Actions run 1")
        assert run.parameters["origen"] == "GitHub Actions run 1" and run.parameters["importado"] is True
        import pytest
        with pytest.raises(v.ValidationError):
            sd.register_external_result(db, {"x": 1}, "otro")
    ext = client.get("/api/disasters/external", headers=reader_h).json()
    assert any(e["zona"] == "Zona importada" for e in ext)
