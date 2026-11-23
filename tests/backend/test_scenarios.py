"""Fase 6 sin red: escenarios simplificados sobre DEM sintético registrado directamente en la base de pruebas."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from app.api import simulation
from app.core import jobs
from app.core.config import settings
from app.database.session import SessionLocal
from app.main import app
from app.models import DataRecord
from app.models.common import new_id
from app.modules.environmental import raster
from app.modules.neuro3d import dem as demlib
from app.modules.neuro3d import scenarios
from app.neurodata.service import get_or_create_source

if not any(getattr(r, "path", "").startswith("/api/simulation") for r in app.routes):
    _n = len(app.router.routes)
    app.include_router(simulation.router)
    # Si main.py monta el frontend en "/", las rutas añadidas después quedarían tapadas: se anteponen.
    _new = app.router.routes[_n:]
    del app.router.routes[_n:]
    app.router.routes[0:0] = _new

BBOX = [-77.30, -9.30, -77.10, -9.10]
RES = 0.001
LAT_MID = -9.20
T5, T40 = math.tan(math.radians(5)), math.tan(math.radians(40))


def two_slopes(lon, lat):
    """5° al sur de LAT_MID y 40° al norte (continuo)."""
    y = (lat - LAT_MID) * demlib.M_PER_DEG_LAT
    return 3000 + np.where(y < 0, T5 * y, T40 * y) + 0 * lon


def valley(lon, lat):
    """Valle parabólico: z = 2000 + k·x² con x en metros desde el eje (lon -77.2); plano a lo largo de lat."""
    x = (lon - (-77.2)) * demlib.M_PER_DEG_LON * math.cos(math.radians(-9.2))
    return 2000 + 1e-5 * x ** 2 + 0 * lat


def make_dem(fn, bbox=BBOX, res=RES) -> str:
    grid = raster.make_grid(bbox, res)
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


def make_ndvi(value: float, bbox, res=0.002) -> str:
    grid = raster.make_grid(bbox, res)
    rid = new_id()
    rel = Path("rasters") / "test" / f"{rid}_ndvi.tif"
    raster.write_ndvi(settings.uploads_dir / rel, np.full((grid.height, grid.width), value, "float32"), grid)
    with SessionLocal() as db:
        src = get_or_create_source(db, "NDVI sintético de prueba", "simulacion", "prueba", "")
        db.add(DataRecord(id=rid, source_id=src.id, data_type="raster_ndvi", title="NDVI sintético",
                          bbox=list(grid.bbox), is_simulated=False, file_path=rel.as_posix(), extra={}))
        db.commit()
    return rid


@pytest.fixture(scope="module")
def slopes_dem():
    return make_dem(two_slopes)


@pytest.fixture(scope="module")
def valley_dem():
    return make_dem(valley)


def _susc(client, h, dem_id, **kw):
    return client.post("/api/simulation/susceptibility", headers=h, json={"dem_id": dem_id, **kw})


# ---------------------------------------------------------------- susceptibilidad
def test_susceptibility_classes_follow_slope(client, analyst_h, slopes_dem):
    r = _susc(client, analyst_h, slopes_dem, w_pendiente=1.0, w_vegetacion=0.0)
    assert r.status_code == 201, r.text
    rec = r.json()
    ex = rec["extra"]
    assert rec["data_type"] == "raster_escenario" and ex["kind"] == "susceptibilidad"
    assert "NO calibrado ni validado" in ex["disclaimer"] and "SIMULACIÓN" in rec["banner"]
    by = {c["class"]: c for c in ex["stats"]["classes"]}
    # 5° → 0.11 (bajo); 40° → 0.89 (alto); mitad y mitad aproximadamente; ninguna celda media salvo la transición.
    assert by[1]["pct"] == pytest.approx(50, abs=3) and by[3]["pct"] == pytest.approx(50, abs=3)
    assert by[2]["pct"] < 3
    b = rec["bbox"]   # make_grid puede añadir un píxel por redondeo: se usa el bbox real de la malla
    total = ((b[2] - b[0]) * demlib.M_PER_DEG_LON * math.cos(math.radians(-9.2))) * ((b[3] - b[1]) * demlib.M_PER_DEG_LAT) / 1e6
    assert ex["stats"]["valid_km2"] == pytest.approx(total, rel=0.01)
    assert sum(c["km2"] for c in ex["stats"]["classes"]) == pytest.approx(ex["stats"]["valid_km2"], rel=0.001)
    assert client.get(f"/api/simulation/scenarios/{rec['id']}/preview", headers=analyst_h).status_code == 200


def test_susceptibility_with_ndvi_changes_classes(client, analyst_h, slopes_dem):
    ndvi_bare = make_ndvi(0.0, [-77.4, -9.4, -77.0, -9.0])     # otra malla (0.002°) y más grande: se reproyecta
    ndvi_green = make_ndvi(0.9, [-77.4, -9.4, -77.0, -9.0])
    kw = {"w_pendiente": 0.5, "w_vegetacion": 0.5}
    bare = _susc(client, analyst_h, slopes_dem, ndvi_id=ndvi_bare, **kw).json()["extra"]
    green = _susc(client, analyst_h, slopes_dem, ndvi_id=ndvi_green, **kw).json()["extra"]
    b = {c["class"]: c["pct"] for c in bare["stats"]["classes"]}
    g = {c["class"]: c["pct"] for c in green["stats"]["classes"]}
    assert b[3] > 90 or (b[2] > 40 and b[3] > 40)   # suelo desnudo: sur medio (0.56), norte alto (0.94)
    assert g[1] > 40 and g[2] > 40 and g[3] == pytest.approx(0, abs=3)   # vegetación densa: sur 0.16, norte 0.54
    assert bare["ndvi_id"] == ndvi_bare and bare["stats"]["ndvi_used"] is True


def test_susceptibility_validation(client, analyst_h, reader_h, slopes_dem):
    assert _susc(client, analyst_h, slopes_dem, w_pendiente=0.7, w_vegetacion=0.7).status_code == 422   # no suma 1
    assert _susc(client, analyst_h, slopes_dem, umbral_medio=0.8, umbral_alto=0.5).status_code == 422
    far = make_ndvi(0.5, [-70.0, -5.0, -69.0, -4.0])
    r = _susc(client, analyst_h, slopes_dem, ndvi_id=far)
    assert r.status_code == 422 and "no se superpone" in r.json()["detail"]
    assert _susc(client, analyst_h, "0" * 32).status_code == 404
    assert _susc(client, reader_h, slopes_dem).status_code == 403


# ---------------------------------------------------------------- inundación
def test_bathtub_volume_matches_analytic_valley(client, analyst_h, reader_h, valley_dem):
    rise = 10.0
    r = client.post("/api/simulation/flood", headers=analyst_h,
                    json={"dem_id": valley_dem, "lon": -77.2, "lat": -9.2, "rise_m": rise})
    assert r.status_code == 201, r.text
    rec = r.json()
    st = rec["extra"]["stats"]
    assert rec["extra"]["kind"] == "inundacion_demostrativa" and "bañera" in rec["extra"]["disclaimer"]
    half_w = math.sqrt(rise / 1e-5)                                    # ≈ 1000 m a cada lado
    length = (rec["bbox"][3] - rec["bbox"][1]) * demlib.M_PER_DEG_LAT
    assert st["flooded_km2"] * 1e6 == pytest.approx(2 * half_w * length, rel=0.08)
    assert st["volume_m3"] == pytest.approx(4 / 3 * rise * half_w * length, rel=0.08)
    assert st["max_depth_m"] == pytest.approx(rise, abs=0.5)
    assert st["touches_dem_border"] is True

    g = client.get(f"/api/simulation/scenarios/{rec['id']}/grid?max_size=64", headers=reader_h).json()
    assert g["width"] <= 64 and g["height"] <= 64 and len(g["values"]) == g["width"] * g["height"]
    assert max(g["values"]) == pytest.approx(rise, abs=1.0) and g["banner"].startswith("SIMULACIÓN")
    mesh_dem = client.get(f"/api/neuro3d/terrains/{valley_dem}/mesh?max_size=64", headers=reader_h).json()
    assert (g["width"], g["height"]) == (mesh_dem["width"], mesh_dem["height"])   # alineado con la malla 3D
    lst = client.get(f"/api/simulation/scenarios?dem_id={valley_dem}", headers=reader_h).json()
    assert any(x["id"] == rec["id"] for x in lst)


def test_flood_validation_and_permissions(client, analyst_h, reader_h, valley_dem):
    body = {"dem_id": valley_dem, "lon": -77.2, "lat": -9.2}
    assert client.post("/api/simulation/flood", headers=analyst_h, json={**body, "rise_m": 0.1}).status_code == 422
    assert client.post("/api/simulation/flood", headers=analyst_h, json={**body, "rise_m": 80}).status_code == 422
    out = client.post("/api/simulation/flood", headers=analyst_h, json={**body, "lon": -70.0, "rise_m": 5})
    assert out.status_code == 422 and "fuera del DEM" in out.json()["detail"]
    assert client.post("/api/simulation/flood", headers=reader_h, json={**body, "rise_m": 5}).status_code == 403
    assert client.get("/api/simulation/scenarios").status_code in (401, 403)


def test_bathtub_only_connected_cells():
    z = np.full((20, 20), 100.0, dtype="float32")
    z[:, 10] = 200.0                         # muro que separa dos cuencas
    z[5:8, 12:15] = 90.0                     # depresión aislada (no conectada al punto)
    depth, m = scenarios.bathtub(z, (0, 0, 0.02, 0.02), 0.0015, 0.0185, 5.0)   # punto en la mitad izquierda
    assert depth[5:8, 12:15].max() == 0 and depth[:, :10].min() == pytest.approx(5.0)
    assert m["flooded_cells"] == 200


# ---------------------------------------------------------------- comparador
def test_compare_monotonic_and_observed(client, analyst_h, reader_h, valley_dem, slopes_dem):
    cfgs = [{"kind": "inundacion_demostrativa", "lon": -77.2, "lat": -9.2, "rise_m": r, "label": f"+{r} m"}
            for r in (2, 5, 10)]
    before = len(client.get("/api/simulation/scenarios", headers=reader_h).json())
    r = client.post("/api/simulation/compare", headers=analyst_h, json={"dem_id": valley_dem, "configs": cfgs})
    assert r.status_code == 200, r.text
    out = r.json()
    areas = [s["metrics"]["flooded_km2"] for s in out["scenarios"]]
    vols = [s["metrics"]["volume_m3"] for s in out["scenarios"]]
    assert areas == sorted(areas) and areas[0] < areas[2] and vols == sorted(vols)
    assert out["saved"] is False and out["observed"]["is_simulated"] is False
    assert out["observed"]["elevation"]["min"] < out["observed"]["elevation"]["max"]
    assert len(client.get("/api/simulation/scenarios", headers=reader_h).json()) == before   # nada guardado

    susc = [{"kind": "susceptibilidad", "w_pendiente": 1.0, "w_vegetacion": 0.0, "umbral_medio": a, "umbral_alto": b}
            for a, b in ((0.1, 0.3), (0.3, 0.6))]
    s = client.post("/api/simulation/compare", headers=analyst_h, json={"dem_id": slopes_dem, "configs": susc}).json()
    hi = [next(c for c in x["metrics"]["classes"] if c["class"] == 3)["pct"] for x in s["scenarios"]]
    assert hi[0] >= hi[1]                    # umbral más bajo → más área «alta»
    assert client.post("/api/simulation/compare", headers=analyst_h,
                       json={"dem_id": valley_dem, "configs": cfgs[:1]}).status_code == 422
    assert client.post("/api/simulation/compare", headers=reader_h,
                       json={"dem_id": valley_dem, "configs": cfgs}).status_code == 403


def test_lock_returns_409_and_no_orphans(client, analyst_h, valley_dem):
    files_before = {p for p in (settings.uploads_dir / "scenarios").rglob("*") if p.is_file()}
    assert jobs.LOCK.acquire(blocking=False)
    try:
        body = {"dem_id": valley_dem, "lon": -77.2, "lat": -9.2, "rise_m": 5}
        assert client.post("/api/simulation/flood", headers=analyst_h, json=body).status_code == 409
        assert _susc(client, analyst_h, valley_dem).status_code == 409
        cfg = [{"kind": "inundacion_demostrativa", "lon": -77.2, "lat": -9.2, "rise_m": r} for r in (2, 5)]
        assert client.post("/api/simulation/compare", headers=analyst_h,
                           json={"dem_id": valley_dem, "configs": cfg}).status_code == 409
    finally:
        jobs.LOCK.release()
    assert {p for p in (settings.uploads_dir / "scenarios").rglob("*") if p.is_file()} == files_before


def test_failed_scenario_leaves_no_files(client, analyst_h, slopes_dem):
    before = {p for p in (settings.uploads_dir / "scenarios").rglob("*") if p.is_file()}
    far = make_ndvi(0.5, [-70.0, -5.0, -69.0, -4.0])
    assert _susc(client, analyst_h, slopes_dem, ndvi_id=far).status_code == 422
    assert {p for p in (settings.uploads_dir / "scenarios").rglob("*") if p.is_file()} == before


def test_descriptor_capabilities():
    from app.modules.neuro3d.descriptor import DESCRIPTOR
    caps = {c.key: c.implemented for c in DESCRIPTOR.capabilities}
    assert caps["capas_3d"] and caps["comparador_escenarios"] and caps["escenarios_simplificados"]
