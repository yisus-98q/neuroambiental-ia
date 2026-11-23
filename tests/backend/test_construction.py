"""NEUROCONSTRUCTION: análisis de sitio sobre un DEM sintético registrado (sin red)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from app.core import jobs
from app.core.config import settings
from app.database.session import SessionLocal
from app.models import DataRecord
from app.models.common import new_id
from app.modules.construction import site
from app.modules.environmental import raster
from app.modules.neuro3d import dem as demlib
from app.neurodata.service import get_or_create_source

BBOX = [-77.30, -9.30, -77.10, -9.10]
LAT_MID = -9.20
T5, T40 = math.tan(math.radians(5)), math.tan(math.radians(40))
URL = "/api/construction/site-analysis"


def two_slopes(lon, lat):
    y = (lat - LAT_MID) * demlib.M_PER_DEG_LAT
    return 3000 + np.where(y < 0, T5 * y, T40 * y) + 0 * lon


def valley(lon, lat):
    x = (lon - (-77.2)) * demlib.M_PER_DEG_LON * math.cos(math.radians(-9.2))
    return 2000 + 1e-5 * x ** 2 + 0 * lat


def make_dem(fn, res=0.001) -> str:
    grid = raster.make_grid(BBOX, res)
    lon = grid.bbox[0] + (np.arange(grid.width) + 0.5) * res
    lat = grid.bbox[3] - (np.arange(grid.height) + 0.5) * res
    arr = np.asarray(fn(lon[None, :], lat[:, None]), dtype="float32") * np.ones((grid.height, grid.width), "float32")
    rid = new_id()
    rel = Path("terrain") / "test" / f"{rid}_dem.tif"
    demlib.write_dem(settings.uploads_dir / rel, arr, grid)
    with SessionLocal() as db:
        src = get_or_create_source(db, "DEM sintético de prueba", "simulacion", "prueba", "")
        db.add(DataRecord(id=rid, source_id=src.id, data_type="raster_dem", title="DEM sintético", bbox=list(grid.bbox),
                          is_simulated=False, file_path=rel.as_posix(), extra={"kind": "dem", "grid": {
                              "bbox": list(grid.bbox), "res": res, "width": grid.width, "height": grid.height}}))
        db.commit()
    return rid


@pytest.fixture(scope="module")
def slopes_dem():
    return make_dem(two_slopes)


@pytest.fixture(scope="module")
def valley_dem():
    return make_dem(valley)


def _post(client, h, dem_id, **kw):
    return client.post(URL, headers=h, json={"dem_id": dem_id, **kw})


def _square(lon, lat, half=0.01):
    return {"type": "Polygon", "coordinates": [[[lon - half, lat - half], [lon + half, lat - half],
                                                [lon + half, lat + half], [lon - half, lat + half], [lon - half, lat - half]]]}


def test_flat_south_site(client, analyst_h, slopes_dem):
    r = _post(client, analyst_h, slopes_dem, point={"lon": -77.2, "lat": -9.25}, buffer_m=500, name="Sitio sur")
    assert r.status_code == 201, r.text
    rec = r.json()
    res = rec["extra"]["result"]
    assert rec["extra"]["kind"] == "analisis_sitio" and rec["is_simulated"] is False
    assert abs(res["slope_site"]["mean_deg"] - 5) < 1.0
    assert res["susceptibility"]["dominant"] == "bajo" and res["susceptibility"]["heuristic"] is True
    assert res["slope_environment"]["cells"] > res["slope_site"]["cells"] == 1
    assert res["elevation"]["min"] <= res["elevation"]["mean"] <= res["elevation"]["max"]
    assert any("≤ 15°" in o for o in res["observations"]) and not any("geotécnico" in o for o in res["observations"])
    assert any("1 celda" in o for o in res["observations"])           # sitio de una celda: poco representativo
    assert res["notice"] == "No reemplaza evaluaciones profesionales ni autorizaciones oficiales."
    assert rec["notice"] == res["notice"] and "heurístico" in res["susceptibility"]["note"]


def test_steep_north_polygon(client, analyst_h, reader_h, slopes_dem):
    r = _post(client, analyst_h, slopes_dem, geojson={"type": "Feature", "properties": {}, "geometry": _square(-77.2, -9.15)},
              buffer_m=300)
    assert r.status_code == 201, r.text
    res = r.json()["extra"]["result"]
    assert abs(res["slope_site"]["mean_deg"] - 40) < 1.5 and res["site_cells"] > 100
    assert next(c for c in res["slope_site"]["classes"] if c["label"] == ">35°")["pct"] > 95
    assert res["susceptibility"]["dominant"] == "alto"
    obs = " ".join(res["observations"])
    assert "requiere estudio geotécnico" in obs and "> 35°" in obs
    lst = client.get("/api/construction/analyses", headers=reader_h)
    assert lst.status_code == 200 and any(x["id"] == r.json()["id"] for x in lst.json())
    with SessionLocal() as db:
        assert db.get(DataRecord, r.json()["id"]).data_type == "analisis_sitio"


def test_flood_inside_and_outside(client, analyst_h, valley_dem):
    inside = _post(client, analyst_h, valley_dem, geojson=_square(-77.2, -9.2, 0.003),
                   flood={"lon": -77.2, "lat": -9.2, "rise_m": 10}).json()["extra"]["result"]
    assert inside["flood"]["site_flooded_pct"] == 100 and inside["flood"]["site_max_depth_m"] > 9
    assert any("queda bajo el agua" in o for o in inside["observations"])
    out = _post(client, analyst_h, valley_dem, point={"lon": -77.15, "lat": -9.2},
                flood={"lon": -77.2, "lat": -9.2, "rise_m": 10}).json()["extra"]["result"]
    assert out["flood"]["site_flooded_pct"] == 0
    assert any("no queda cubierto" in o for o in out["observations"])


def test_validation_permissions_lock(client, analyst_h, reader_h, slopes_dem):
    pt = {"lon": -77.2, "lat": -9.25}
    assert _post(client, analyst_h, slopes_dem).status_code == 422                                       # ni punto ni polígono
    assert _post(client, analyst_h, slopes_dem, point=pt, geojson=_square(-77.2, -9.25)).status_code == 422
    assert _post(client, analyst_h, slopes_dem, geojson={"type": "LineString", "coordinates": [[0, 0], [1, 1]]}).status_code == 422
    assert _post(client, analyst_h, slopes_dem, geojson={"type": "Polygon", "coordinates": "x"}).status_code == 422
    assert _post(client, analyst_h, slopes_dem, geojson=_square(-70.0, -5.0)).status_code == 422          # fuera del DEM
    out = _post(client, analyst_h, slopes_dem, point={"lon": -70.0, "lat": -5.0})
    assert out.status_code == 422 and "fuera del DEM" in out.json()["detail"]
    assert _post(client, analyst_h, slopes_dem, point=pt, buffer_m=9000).status_code == 422
    assert _post(client, analyst_h, slopes_dem, point=pt, flood={**pt, "rise_m": 80}).status_code == 422
    assert _post(client, analyst_h, "0" * 32, point=pt).status_code == 404
    assert _post(client, reader_h, slopes_dem, point=pt).status_code == 403
    assert client.get("/api/construction/analyses").status_code in (401, 403)
    assert jobs.LOCK.acquire(blocking=False)
    try:
        assert _post(client, analyst_h, slopes_dem, point=pt).status_code == 409
    finally:
        jobs.LOCK.release()


def test_observation_rules_only_use_numbers():
    base = {"slope_site": {"mean_deg": 20.0}, "slope_environment": {"classes": [{"label": ">35°", "pct": 0}]},
            "susceptibility": {"dominant": "medio"}, "elevation": {"mean": 4000.0}, "site_cells": 50, "cell_size_m": 100,
            "buffer_m": 500, "flood": None}
    obs = site.observations(base)
    assert any("15-25°" in o for o in obs) and any("3500" in o for o in obs)
    assert not any("geotécnico" in o for o in obs)


def test_descriptor_honest():
    from app.modules.construction.descriptor import DESCRIPTOR
    caps = {c.key: c.implemented for c in DESCRIPTOR.capabilities}
    assert caps["analisis_ubicacion"] and caps["pendientes_relieve"] and caps["observaciones"]
    assert not caps["compatibilidad_territorial"] and not caps["proximidad_rios"]
