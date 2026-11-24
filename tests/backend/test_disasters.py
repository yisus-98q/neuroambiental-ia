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
                       json={"dem_id": dem_id, "inventory_id": inv_id, "blocks": 4, **kw})


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
    assert rep["dataset_record_id"] and rep["simulado"] is True            # el DEM de prueba es simulado
    ds = client.get(f"/api/neurodata/records/{rep['dataset_record_id']}", headers=analyst_h).json()
    assert ds["data_type"] == "csv" and "evento" in ds["extra"]["columns"]


def test_flat_valley_events_flag_the_heuristic_as_useless(client, analyst_h, monkeypatch):
    dem_id = _register_dem(_dem())
    rng = np.random.default_rng(2)
    flat = [(int(r), int(c)) for r, c in zip(rng.integers(5, 195, 60), rng.integers(96, 104, 60))]
    inv = _import(client, analyst_h, monkeypatch, _events(flat))
    rep = _validate(client, analyst_h, dem_id, inv["id"]).json()
    assert rep["ausencias_libres"]["auc_heuristico_pendiente"] < 0.5
    assert any("NO discrimina" in c for c in rep["conclusion_automatica"])


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
