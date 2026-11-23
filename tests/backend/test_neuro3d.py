"""NEURO 3D LAB sin red: teselas GLO-30 sintéticas (plano inclinado y cuenca) servidas por un backend falso."""
from __future__ import annotations

import contextlib
import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.api import neuro3d
from app.main import app
from app.modules.neuro3d import dem, service

if not any(getattr(r, "path", "").startswith("/api/neuro3d") for r in app.routes):
    app.include_router(neuro3d.router)

SLOPE_DEG = 10.0
RES = 0.002  # resolución de las teselas sintéticas (1° = 500 px)
CROSS_BBOX = [-77.1, -9.1, -76.9, -8.9]    # cruza límites de lat (-9) y lon (-77): 4 teselas
BOWL_BBOX = [-77.3, -9.3, -77.1, -9.1]     # una sola tesela (S10 W078)
BOWL_CENTER = (-77.2, -9.2)


def plane(lon, lat):
    """Elevación que sube hacia el norte con pendiente SLOPE_DEG (continua entre teselas)."""
    return 3000 + math.tan(math.radians(SLOPE_DEG)) * dem.M_PER_DEG_LAT * (lat + 9)


def bowl(lon, lat):
    return 1500 + 30000 * ((lon - BOWL_CENTER[0]) ** 2 + (lat - BOWL_CENTER[1]) ** 2)


class FakeDemBackend:
    def __init__(self, tmp: Path, fn):
        self.tmp, self.fn, self.opened = tmp, fn, []

    def tile_href(self, tile):
        return str(self.tmp / f"{tile.name}.tif")

    @contextlib.contextmanager
    def open_band(self, href, opener):
        path = Path(href)
        if not path.exists():
            self._write(path)
        self.opened.append(path.name)
        with rasterio.open(path) as src:
            yield src

    def _write(self, path: Path):
        name = path.stem
        lat = int(name.split("_")[4][1:]) * (1 if name.split("_")[4][0] == "N" else -1)
        lon = int(name.split("_")[6][1:]) * (1 if name.split("_")[6][0] == "E" else -1)
        n = round(1 / RES)
        cols = lon + (np.arange(n) + 0.5) * RES
        rows = lat + 1 - (np.arange(n) + 0.5) * RES
        data = self.fn(cols[None, :], rows[:, None]) * np.ones((n, n))
        with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(lon, lat + 1, RES, RES)) as dst:
            dst.write(data.astype("float32"), 1)


@pytest.fixture()
def plane_backend(tmp_path, monkeypatch):
    b = FakeDemBackend(tmp_path / "p", plane)
    b.tmp.mkdir()
    monkeypatch.setattr(service, "backend", b)
    return b


@pytest.fixture()
def bowl_backend(tmp_path, monkeypatch):
    b = FakeDemBackend(tmp_path / "b", bowl)
    b.tmp.mkdir()
    monkeypatch.setattr(service, "backend", b)
    return b


def _terrain(client, h, bbox, res=0.002):
    return client.post("/api/neuro3d/terrain", headers=h, json={"bbox": bbox, "resolution_deg": res})


# ---------------------------------------------------------------- teselas y utilidades
def test_tiles_names_and_boundaries():
    t = dem.tiles_for_bbox([-77.60, -9.60, -77.30, -9.35])
    assert [x.name for x in t] == ["Copernicus_DSM_COG_10_S10_00_W078_00_DEM"]
    assert len(dem.tiles_for_bbox(CROSS_BBOX)) == 4
    assert len(dem.tiles_for_bbox([-78.0, -10.0, -77.0, -9.0])) == 1   # bordes enteros: sin tesela extra
    assert len(dem.tiles_for_bbox([-77.2, -9.4, -76.8, -9.1])) == 2    # cruza solo el meridiano -77
    assert dem.Tile(5, 10).name == "Copernicus_DSM_COG_10_N05_00_E010_00_DEM"


def test_slope_of_known_plane():
    bbox = (-77.2, -9.4, -77.0, -9.2)
    h = w = 100
    lats = bbox[3] - (np.arange(h) + 0.5) * (0.2 / h)
    z = np.repeat(plane(0, lats)[:, None], w, axis=1).astype("float32")
    s = dem.slope_deg(z, bbox)
    assert abs(float(np.nanmean(s)) - SLOPE_DEG) < 1.0
    classes = {c["label"]: c["pct"] for c in dem.slope_stats(s)["classes"]}
    assert classes["0-15°"] > 99 and classes[">35°"] == 0


def test_grid_too_large_for_viewer():
    with pytest.raises(dem.DemError):
        dem.make_dem_grid([-77.6, -9.6, -77.1, -9.1], 0.0003)


# ---------------------------------------------------------------- API
def test_terrain_end_to_end(client, analyst_h, reader_h, plane_backend):
    r = _terrain(client, analyst_h, CROSS_BBOX)
    assert r.status_code == 201, r.text
    rec = r.json()
    ex = rec["extra"]
    assert rec["data_type"] == "raster_dem" and rec["is_simulated"] is False and rec["sha256"]
    assert len(ex["tiles"]) == 4 and len(plane_backend.opened) == 4
    assert "Airbus Defence and Space" in rec["provenance"] and ex["attribution"]
    assert ex["elevation"]["min"] == pytest.approx(plane(0, -9.1), abs=40)
    assert ex["elevation"]["max"] == pytest.approx(plane(0, -8.9), abs=40)
    assert ex["elevation"]["min"] < ex["elevation"]["max"]
    assert abs(ex["slope_stats"]["mean_deg"] - SLOPE_DEG) < 1.0
    assert ex["elevation"]["valid_pct"] > 99

    lst = client.get("/api/neuro3d/terrains", headers=reader_h)
    assert lst.status_code == 200 and any(x["id"] == rec["id"] for x in lst.json())

    m = client.get(f"/api/neuro3d/terrains/{rec['id']}/mesh?max_size=64", headers=reader_h)
    assert m.status_code == 200, m.text
    mesh = m.json()
    assert mesh["width"] <= 64 and mesh["height"] <= 64
    assert len(mesh["heights"]) == mesh["width"] * mesh["height"] == len(mesh["slopes"])
    assert mesh["min"] <= min(mesh["heights"]) and max(mesh["heights"]) <= mesh["max"]
    assert mesh["attribution"] and mesh["extent_m"][0] > 0 and mesh["slope_stats"]["classes"]
    assert len(mesh["valid"]) == len(mesh["heights"]) and mesh["valid_pct"] > 99   # máscara de validez
    full = client.get(f"/api/neuro3d/terrains/{rec['id']}/mesh", headers=reader_h).json()
    assert max(full["width"], full["height"]) <= 256
    assert client.get("/api/neuro3d/terrains/inexistente/mesh", headers=reader_h).status_code == 404


def test_flow_path_stopped_by_missing_data_is_not_a_minimum():
    """Si el camino se detiene junto a celdas sin dato, el motivo es «sin_dato», no «minimo_local»."""
    z = np.tile(np.linspace(100, 10, 20, dtype="float32"), (20, 1))  # desciende hacia el este
    z[:, 10:] = np.nan                                                # hueco de datos a mitad de camino
    out = dem.flow_path(z, (-77.0, -9.02, -76.98, -9.0), lon=-76.9975, lat=-9.0105)  # columna 2, fila 10
    assert out["end_reason"] == "sin_dato" and out["steps"] > 0


def test_flow_path_descends_to_minimum(client, analyst_h, reader_h, bowl_backend):
    rec = _terrain(client, analyst_h, BOWL_BBOX).json()
    start = {"lon": -77.15, "lat": -9.15}
    r = client.post(f"/api/neuro3d/terrains/{rec['id']}/flow-path", headers=analyst_h, json=start)
    assert r.status_code == 201, r.text
    res = r.json()
    z = [p[2] for p in res["path"]]
    assert len(z) > 5 and all(a > b for a, b in zip(z, z[1:]))        # desciende estrictamente
    assert res["end_reason"] == "minimo_local"
    end = res["path"][-1]
    assert abs(end[0] - BOWL_CENTER[0]) < 0.01 and abs(end[1] - BOWL_CENTER[1]) < 0.01
    assert res["drop_m"] == pytest.approx(z[0] - z[-1], abs=0.2) and res["length_km"] > 1
    assert "No es una simulación geotécnica" in res["disclaimer"] and res["is_simulated"] is True
    sc = client.get("/api/neuro3d/scenarios", headers=reader_h).json()
    assert any(s["id"] == res["id"] and "path" not in s for s in sc)
    full = client.get(f"/api/neuro3d/scenarios/{res['id']}", headers=reader_h).json()
    assert len(full["path"]) == len(res["path"])


def test_flow_path_outside_dem_is_422(client, analyst_h, bowl_backend):
    rec = _terrain(client, analyst_h, BOWL_BBOX).json()
    r = client.post(f"/api/neuro3d/terrains/{rec['id']}/flow-path", headers=analyst_h, json={"lon": -70.0, "lat": -5.0})
    assert r.status_code == 422 and "fuera del DEM" in r.json()["detail"]


def test_validation_permissions_and_lock(client, analyst_h, reader_h, plane_backend):
    big = _terrain(client, analyst_h, [-78.0, -10.0, -77.0, -9.0])
    assert big.status_code == 422
    too_fine = _terrain(client, analyst_h, [-77.6, -9.6, -77.1, -9.1], res=0.0003)  # 1667 px
    assert too_fine.status_code == 422
    assert _terrain(client, reader_h, BOWL_BBOX).status_code == 403
    assert client.post("/api/neuro3d/terrains/x/flow-path", headers=reader_h,
                       json={"lon": -77.2, "lat": -9.2}).status_code == 403
    assert client.get("/api/neuro3d/terrains").status_code in (401, 403)
    from app.core import jobs
    assert jobs.LOCK.acquire(blocking=False)
    try:
        assert _terrain(client, analyst_h, BOWL_BBOX).status_code == 409
    finally:
        jobs.LOCK.release()


def test_descriptor_honest():
    from app.modules.neuro3d.descriptor import DESCRIPTOR
    caps = {c.key: c.implemented for c in DESCRIPTOR.capabilities}
    assert caps == {"terreno_dem": True, "visor_threejs": True, "capas_3d": False,
                    "escenarios_simplificados": True, "comparador_escenarios": False}
    assert DESCRIPTOR.version == "0.1.0" and DESCRIPTOR.api_prefix == "/api/neuro3d"
