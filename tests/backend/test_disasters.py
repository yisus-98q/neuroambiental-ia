"""NEURODISASTER: importación del inventario (sin red: fetcher falso) y validación espacial con DEM sintético."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.core import jobs
from app.core.config import settings
from app.database.session import SessionLocal
from app.models import DataRecord
from app.modules.disasters import inventory
from app.neurodata.service import get_or_create_source

BBOX = [-77.5, -9.5, -77.3, -9.3]
N = 200                       # DEM 200x200 → 0,001° por celda
RES = (BBOX[2] - BBOX[0]) / N


def _dem() -> np.ndarray:
    """Valle en U: fondo casi plano en el centro; la pendiente crece hacia los bordes (≈36° en el borde)."""
    x = np.linspace(-1, 1, N)
    z = 3000 + 4000 * (x ** 2)[None, :] + 200 * np.sin(np.linspace(0, 6, N))[:, None]
    return z.astype("float32")


def _register_dem(arr: np.ndarray) -> str:
    rel = Path("terrain") / "test" / f"dem_{np.random.default_rng().integers(1e9)}.tif"
    path = settings.uploads_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", width=N, height=N, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(BBOX[0], BBOX[3], RES, RES), nodata=-9999) as dst:
        dst.write(arr, 1)
    with SessionLocal() as db:
        src = get_or_create_source(db, "DEM sintético de prueba", "archivo")
        rec = DataRecord(source_id=src.id, data_type="raster_dem", title="DEM prueba", bbox=BBOX,
                         is_simulated=True, file_path=rel.as_posix(), validation_status="valido")
        db.add(rec)
        db.commit()
        return rec.id


def _events(cells, code="1000|1300") -> dict:
    feats = []
    for r, c in cells:
        lon, lat = BBOX[0] + (c + 0.5) * RES, BBOX[3] - (r + 0.5) * RES
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": {"TIP_PELIGRO": code, "NOM_PELIGRO": code + "|1302", "COD_INV": f"T{r}-{c}"}})
    return {"type": "FeatureCollection", "features": feats}


def _import(client, h, monkeypatch, fc):
    monkeypatch.setattr(inventory, "fetch_events", lambda bbox: fc)
    r = client.post("/api/disasters/inventory/import", headers=h, json={"bbox": BBOX})
    assert r.status_code == 201, r.text
    return r.json()


def _validate(client, h, dem_id, inv_id, **kw):
    return client.post("/api/disasters/susceptibility/validate", headers=h,
                       json={"dem_id": dem_id, "inventory_id": inv_id, "blocks": 4, "n_seeds": 2, **kw})


def test_import_registers_source_license_and_types(client, analyst_h, monkeypatch):
    fc = _events([(10, 20), (30, 40), (50, 60)])
    fc["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [-77.4, -9.4]},
                           "properties": {"TIP_PELIGRO": "2000|2100"}})
    out = _import(client, analyst_h, monkeypatch, fc)
    assert out["eventos"] == 4 and out["is_simulated"] is False
    assert "INGEMMET" in out["source"] and "no redistribuir" in out["license"]
    assert out["tipos_peligro"] == {"1000|1300": 3, "2000|2100": 1}
    listed = client.get("/api/disasters/inventories", headers=analyst_h).json()
    assert any(i["id"] == out["id"] and i["eventos"] == 4 for i in listed)


def test_heuristic_discriminates_when_events_are_on_steep_slopes(client, analyst_h, monkeypatch):
    dem_id = _register_dem(_dem())
    rng = np.random.default_rng(1)
    steep = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, 60), rng.choice(
        np.r_[np.arange(3, 30), np.arange(170, 197)], 60))]
    inv = _import(client, analyst_h, monkeypatch, _events(steep))
    r = _validate(client, analyst_h, dem_id, inv["id"])
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["ausencias_libres"]["n_presencias"] >= 50
    assert rep["ausencias_libres"]["auc_heuristico_pendiente"] > 0.75      # eventos en flancos empinados
    assert rep["ausencias_libres"]["regresion_logistica"]["espacial"]["folds"] >= 3
    assert "rango_elevacion_m" in rep["ausencias_mismo_rango_elevacion"]
    esp = rep["ausencias_libres"]["regresion_logistica"]["espacial"]
    for key in ("auc_agrupado", "auc_ic95_bloques", "pr_auc", "pr_auc_azar", "brier", "confusion", "precision",
                "recall", "f1", "por_pliegue", "auc_semillas", "excluidos_por_zona_de_exclusion"):
        assert key in esp, key
    c = esp["confusion"]
    assert c["vp"] + c["fn"] == rep["ausencias_libres"]["n_presencias"]
    assert esp["auc_semillas"]["n"] == 2 and rep["protocolo"]["zona_exclusion_m"] == 500
    assert rep["dataset_record_id"] and rep["simulado"] is True            # el DEM de prueba es simulado
    ds = client.get(f"/api/neurodata/records/{rep['dataset_record_id']}", headers=analyst_h).json()
    assert ds["data_type"] == "csv" and "evento" in ds["extra"]["columns"]


def test_flat_valley_events_flag_the_heuristic_as_useless(client, analyst_h, monkeypatch):
    dem_id = _register_dem(_dem())
    rng = np.random.default_rng(2)
    flat = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, 60), rng.integers(96, 104, 60))]
    inv = _import(client, analyst_h, monkeypatch, _events(flat))
    rep = _validate(client, analyst_h, dem_id, inv["id"]).json()
    assert rep["ausencias_libres"]["auc_heuristico_pendiente"] < 0.4
    assert any("INVERSA" in c for c in rep["conclusion_automatica"])


def test_validation_errors_permissions_and_lock(client, analyst_h, reader_h, monkeypatch):
    dem_id = _register_dem(_dem())
    few = _import(client, analyst_h, monkeypatch, _events([(10, 30), (20, 40)]))
    assert _validate(client, analyst_h, dem_id, few["id"]).status_code == 422          # < 20 eventos
    assert _validate(client, analyst_h, "0" * 32, few["id"]).status_code == 404
    assert _validate(client, reader_h, dem_id, few["id"]).status_code == 403
    big = {"bbox": [-80.0, -12.0, -76.0, -8.0]}
    assert client.post("/api/disasters/inventory/import", headers=analyst_h, json=big).status_code == 422
    jobs.LOCK.acquire()
    try:
        assert _validate(client, analyst_h, dem_id, few["id"]).status_code == 409
    finally:
        jobs.LOCK.release()


def test_inventory_refuses_foreign_hosts(monkeypatch):
    monkeypatch.setattr(inventory, "SERVICE", "https://evil.example.com/x")
    with pytest.raises(inventory.InventoryError):
        inventory._get({"f": "json"})


def test_cli_imports_as_system_without_user(monkeypatch, client):
    from app import cli
    monkeypatch.setattr(inventory, "fetch_events", lambda bbox: _events([(10, 20), (40, 50)]))
    assert cli.main(["importar-ingemmet", "--bbox=-77.5,-9.5,-77.3,-9.3"]) == 0
    assert cli.main(["importar-ingemmet", "--bbox=-80,-12,-76,-8"]) == 2
    with SessionLocal() as db:
        rec = db.query(DataRecord).filter(DataRecord.title.like("Inventario INGEMMET%")).order_by(
            DataRecord.received_at.desc()).first()
        assert rec.created_by is None and rec.is_simulated is False


def test_validation_by_process_type_separates_falls_and_flows(client, analyst_h, monkeypatch):
    dem_id = _register_dem(_dem())
    rng = np.random.default_rng(5)
    steep = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, 40), rng.choice(
        np.r_[np.arange(3, 30), np.arange(170, 197)], 40))]
    flat = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, 40), rng.integers(96, 104, 40))]
    fc = _events(steep, code="1000|1100")
    fc["features"] += _events(flat, code="1000|1500")["features"]
    fc["features"] += _events([(10, 10), (20, 20)], code="1000|1700")["features"]   # muy pocos: se omite
    inv = _import(client, analyst_h, monkeypatch, fc)
    rep = _validate(client, analyst_h, dem_id, inv["id"]).json()
    pp = rep["por_proceso"]
    assert set(pp) == {"1000|1100", "1000|1500"} and "1000|1700" in rep["procesos_omitidos_por_pocos_eventos"]
    assert pp["1000|1100"]["ausencias_libres"]["auc_heuristico_pendiente"] > 0.7
    assert pp["1000|1500"]["ausencias_libres"]["auc_heuristico_pendiente"] < 0.4
    assert any("INVERSA" in c for c in pp["1000|1500"]["conclusion_automatica"])
    assert "NO confirmada" in rep["nota_codigos"]


def test_exclusion_zone_removes_training_points_near_test_points():
    from sklearn.model_selection import GroupKFold

    from app.modules.disasters import protocol

    class Spy:
        seen: list = []

        def fit(self, X, y):
            Spy.seen.append(X[:, 0].copy())
            return self

        def predict_proba(self, X):
            return np.c_[1 - X[:, 1], X[:, 1]]

    rng = np.random.default_rng(0)
    n = 200
    xy = rng.random((n, 2)) * 10_000
    y = (rng.random(n) < 0.3).astype(int)
    X = np.c_[np.arange(n), rng.random(n)]
    groups = (xy[:, 0] // 2500).astype(int)
    splitter = GroupKFold(n_splits=4)
    res = protocol.spatial_oof(lambda: Spy(), X, y, groups, xy, splitter, buffer_m=800)
    assert res["removed_by_buffer"] > 0
    for (tr, te), used in zip(splitter.split(X, y, groups), Spy.seen):
        used = used.astype(int)
        d = np.sqrt(((xy[used][:, None, :] - xy[te][None, :, :]) ** 2).sum(-1)).min()
        assert d >= 800


def test_conclusions_rules():
    from app.modules.disasters.validation import _conclusion

    def v(h, e, m, ic=None):
        return {"auc_heuristico_pendiente": h, "auc_solo_elevacion_baja": e,
                "regresion_logistica": {"espacial": {"auc_mean": m, "auc_ic95_bloques": ic}}}
    falls = _conclusion(v(0.69, 0.73, 0.81), v(0.75, 0.54, 0.71, [0.53, 0.80]))
    assert any("SÍ discrimina" in c and "0,75" in c for c in falls)
    assert any("llega a 0,53" in c for c in falls)
    flows = _conclusion(v(0.38, 0.79, 0.79), v(0.40, 0.66, 0.70))
    assert any("INVERSA" in c for c in flows) and not any("SÍ discrimina" in c for c in flows)
    mixed = _conclusion(v(0.49, 0.81, 0.83), v(0.54, 0.70, 0.74))
    assert any("NO discrimina" in c for c in mixed) and any("elevación" in c for c in mixed)


def _geology_fc():
    """Dos polígonos: mitad oeste «Sedimento», mitad este «Volcánica» (nombres oficiales como texto)."""
    mid = (BBOX[0] + BBOX[2]) / 2
    def poly(x0, x1, cls):
        return {"type": "Feature", "properties": {"TIPO_UNIDAD": cls},
                "geometry": {"type": "Polygon", "coordinates": [[[x0, BBOX[1]], [x1, BBOX[1]], [x1, BBOX[3]],
                                                                 [x0, BBOX[3]], [x0, BBOX[1]]]]}}
    return {"type": "FeatureCollection", "features": [poly(BBOX[0], mid, "Sedimento"), poly(mid, BBOX[2], "Volcánica")]}


def test_geology_import_rasterize_and_frequency_ratio(client, analyst_h, monkeypatch):
    from app.modules.disasters import geology
    monkeypatch.setattr(geology, "fetch_layer", lambda kind, bbox: _geology_fc())
    r = client.post("/api/disasters/geology/import", headers=analyst_h, json={"capa": "litologia", "bbox": BBOX})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["clases"] == {"Sedimento": 1, "Volcánica": 1} and "no redistribuir" in out["license"]
    assert any(g["id"] == out["id"] for g in client.get("/api/disasters/geology", headers=analyst_h).json())
    # Rasterización a la malla del DEM y razón de frecuencia (todos los eventos al oeste → Sedimento ≈ 2).
    arr = _dem()
    idx, names = geology.rasterize(_geology_fc(), "TIPO_UNIDAD", arr, BBOX)
    assert names == ["(sin dato)", "Sedimento", "Volcánica"]
    assert idx[:, :95].min() == 1 and idx[:, 105:].max() == 2
    west = np.array([[r_, c_] for r_, c_ in zip(range(10, 190, 6), range(5, 95, 3))])
    fr = {x["clase"]: x["razon_frecuencia"] for x in geology.frequency_ratio(idx, names, west)}
    assert fr["Sedimento"] == 2.0 and fr["Volcánica"] == 0.0
    # Validación con la capa geológica: aparece el modelo topografía + geología y la advertencia de circularidad.
    dem_id = _register_dem(arr)
    rng = np.random.default_rng(9)
    ev = [(int(a), int(b)) for a, b in zip(rng.integers(5, 195, 50), rng.integers(3, 60, 50))]
    inv = _import(client, analyst_h, monkeypatch, _events(ev))
    rep = _validate(client, analyst_h, dem_id, inv["id"], geology_ids=[out["id"]]).json()
    assert rep["geologia_clases_usadas"] == {"litologia": ["Sedimento", "Volcánica"]}
    assert "regresion_logistica_geo" in rep["ausencias_mismo_rango_elevacion"]
    assert any("circular" in w for w in rep["advertencias"])
    assert any("clases geológicas" in c for c in rep["conclusion_automatica"])
    # Un inventario no sirve como capa geológica.
    assert _validate(client, analyst_h, dem_id, inv["id"], geology_ids=[inv["id"]]).status_code == 422


def test_geology_refuses_foreign_hosts(monkeypatch):
    from app.modules.disasters import geology
    with pytest.raises(geology.GeologyError):
        geology._get("https://evil.example.com/q", {"f": "json"})


def test_ndvi_candidate_is_compared_on_the_same_points(client, analyst_h, monkeypatch):
    from app.modules.environmental import raster as envraster
    arr = _dem()
    dem_id = _register_dem(arr)
    # NDVI en la MISMA malla, con una franja sin dato (nubes) para comprobar que se descartan los mismos puntos.
    nd = (0.2 + 0.4 * np.random.default_rng(3).random(arr.shape)).astype("float32")
    nd[:, 150:] = np.nan
    rel = Path("terrain") / "test" / f"ndvi_{np.random.default_rng().integers(1e9)}.tif"
    grid = envraster.Grid(tuple(BBOX), RES, N, N)
    envraster.write_ndvi(settings.uploads_dir / rel, nd, grid)
    with SessionLocal() as db:
        src = get_or_create_source(db, "NDVI de prueba", "satelite")
        rec = DataRecord(source_id=src.id, data_type="raster_ndvi", title="NDVI prueba", bbox=BBOX, is_simulated=True,
                         file_path=rel.as_posix(), validation_status="valido",
                         extra={"grid": {"bbox": BBOX, "res": RES, "width": N, "height": N}})
        db.add(rec)
        db.commit()
        ndvi_id = rec.id
    rng = np.random.default_rng(4)
    ev = [(int(a), int(b)) for a, b in zip(rng.integers(5, 195, 60), rng.integers(3, 197, 60))]
    inv = _import(client, analyst_h, monkeypatch, _events(ev))
    rep = _validate(client, analyst_h, dem_id, inv["id"], ndvi_id=ndvi_id).json()
    v = rep["ausencias_mismo_rango_elevacion"]
    assert "ndvi_anillo" in rep["variables"] and "ndvi_anillo" in v["por_variable"]
    assert "regresion_logistica_ndvi" in v and v["puntos_sin_dato_descartados"]["eventos"] > 0
    assert any("NDVI" in c for c in rep["conclusion_automatica"])
    assert any("posterior a los eventos" in w for w in rep["advertencias"])
    # Un NDVI de otra malla se rechaza: no se remuestrea en silencio.
    with SessionLocal() as db:
        bad = db.get(DataRecord, ndvi_id)
        bad.extra = {"grid": {"bbox": [0, 0, 1, 1], "res": RES, "width": N, "height": N}}
        db.commit()
    assert _validate(client, analyst_h, dem_id, inv["id"], ndvi_id=ndvi_id).status_code == 422
