"""Fase 2: NDVI y detección de cambios. Sin red: se usan rasters sintéticos (UTM 18S) que imitan
las bandas de Sentinel-2 L2A, y un _request falso que sirve rangos de bytes desde disco."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.modules.environmental import raster, remote, service

BBOX = [-77.60, -9.60, -77.50, -9.50]  # área pequeña para pruebas rápidas
SCALE = {"raster:bands": [{"scale": 0.0001, "offset": -0.1, "nodata": 0}]}


def _band(path: Path, data: np.ndarray, res: float, dtype: str) -> str:
    # Origen UTM 18S que cubre holgadamente BBOX (≈ lon -77.6, lat -9.5 → x≈214000, y≈8948000).
    transform = from_origin(195000, 8960000, res, res)
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
                       dtype=dtype, crs="EPSG:32718", transform=transform, nodata=0, tiled=True,
                       blockxsize=256, blockysize=256) as dst:
        dst.write(data.astype(dtype), 1)
    return str(path)


def _scene(tmp: Path, name: str, nir_dn_right: int, cloud: bool) -> remote.Scene:
    n = 3000  # 3000 px x 10 m = 30 km
    red = np.full((n, n), 2000)            # reflectancia 0.1
    nir = np.full((n, n), 6000)            # reflectancia 0.5 → NDVI 0.6667
    nir[:, n // 2:] = nir_dn_right
    scl = np.full((n // 2, n // 2), 4)     # vegetación (20 m)
    if cloud:
        scl[:200, :200] = 9                # una nube
    d = tmp / name
    d.mkdir()
    assets = {
        "red": {"href": _band(d / "B04.tif", red, 10, "uint16"), **SCALE},
        "nir": {"href": _band(d / "B08.tif", nir, 10, "uint16"), **SCALE},
        "scl": {"href": _band(d / "SCL.tif", scl, 20, "uint8")},
    }
    return remote.Scene(id=name, datetime=f"{name[-10:]}T15:00:00Z", cloud_cover=5.0, mgrs_tile="18LTQ",
                        platform="sentinel-2c", bbox=BBOX, assets=assets)


class FakeBackend:
    def __init__(self, scenes: dict[str, remote.Scene]):
        self.scenes = scenes

    def get_scene(self, item_id: str) -> remote.Scene:
        return self.scenes[item_id]

    @contextlib.contextmanager
    def open_band(self, href, opener):
        with rasterio.open(href) as src:
            yield src


@pytest.fixture(scope="module")
def scenes(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("s2")
    before = _scene(tmp, "S2C_18LTQ_20250601_0_L2A_2025-06-01", 6000, cloud=True)
    after = _scene(tmp, "S2C_18LTQ_20250901_0_L2A_2025-09-01", 2500, cloud=False)  # NDVI baja a la derecha
    return {s.id: s for s in (before, after)}


@pytest.fixture()
def fake_backend(scenes, monkeypatch):
    monkeypatch.setattr(service, "backend", FakeBackend(scenes))


def _ndvi(client, h, item_id):
    return client.post("/api/environmental/ndvi", headers=h,
                       json={"item_id": item_id, "bbox": BBOX, "resolution_deg": 0.0005})


def test_ndvi_and_change_end_to_end(client, analyst_h, scenes, fake_backend):
    ids = list(scenes)
    r1 = _ndvi(client, analyst_h, ids[0])
    assert r1.status_code == 201, r1.text
    before = r1.json()
    st = before["extra"]["stats"]
    assert before["data_type"] == "raster_ndvi" and before["is_simulated"] is False
    assert 0.0 < st["cloud_shadow_masked_pct"] < 20            # la nube quedó enmascarada
    assert st["ndvi_p10"] == pytest.approx(0.6667, abs=0.01)   # (0.5-0.1)/(0.5+0.1)
    assert "Copernicus Sentinel" in before["provenance"]
    png = client.get(f"/api/neurodata/records/{before['id']}/preview", headers=analyst_h)
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"

    after = _ndvi(client, analyst_h, ids[1]).json()
    r = client.post("/api/environmental/change", headers=analyst_h,
                    json={"before_id": after["id"], "after_id": before["id"], "threshold": 0.2})
    assert r.status_code == 201, r.text
    ch = r.json()
    s = ch["extra"]["stats"]
    assert ch["extra"]["before"] == before["id"]               # se ordena por fecha automáticamente
    assert s["ndvi_increase_km2"] == 0
    assert s["ndvi_decrease_km2"] > 0
    assert s["ndvi_mean_after"] < s["ndvi_mean_before"]
    assert ch["extra"]["validated"] is False and "NO confirma" in ch["extra"]["uncertainty"]
    assert "Copernicus Sentinel 2025" in ch["provenance"]
    full = client.get(f"/api/neurodata/records/{ch['id']}", headers=analyst_h).json()
    assert len(full["sha256"]) == 64
    runs = client.get("/api/environmental/analyses", headers=analyst_h).json()
    assert {"ndvi", "deteccion_cambios"} <= {x["run_type"] for x in runs}
    assert all(x["status"] == "ok" for x in runs)


def test_change_requires_same_grid_and_distinct(client, analyst_h, scenes, fake_backend):
    ids = list(scenes)
    a = _ndvi(client, analyst_h, ids[0]).json()
    b = client.post("/api/environmental/ndvi", headers=analyst_h,
                    json={"item_id": ids[1], "bbox": BBOX, "resolution_deg": 0.0004}).json()
    bad = client.post("/api/environmental/change", headers=analyst_h, json={"before_id": a["id"], "after_id": b["id"]})
    assert bad.status_code == 422 and "misma área" in bad.text
    same = client.post("/api/environmental/change", headers=analyst_h, json={"before_id": a["id"], "after_id": a["id"]})
    assert same.status_code == 422


def test_validation_and_permissions(client, analyst_h, reader_h):
    assert client.post("/api/environmental/ndvi", headers=reader_h, json={"item_id": "S2C_18LTQ_20250601_0_L2A"}).status_code == 403
    big = {"item_id": "S2C_18LTQ_20250601_0_L2A", "bbox": [-78, -10, -77, -9]}
    assert client.post("/api/environmental/ndvi", headers=analyst_h, json=big).status_code == 422
    future = {"date_from": "2025-01-01", "date_to": "2999-01-01"}
    assert client.post("/api/environmental/scenes/search", headers=analyst_h, json=future).status_code == 422


def test_busy_lock_returns_409(client, analyst_h, scenes, fake_backend):
    service._LOCK.acquire()
    try:
        r = _ndvi(client, analyst_h, list(scenes)[0])
        assert r.status_code == 409
    finally:
        service._LOCK.release()


def test_choose_offset_detects_already_corrected_data():
    scl = np.full((10, 10), 4.0)
    # Datos crudos con +1000 incluido (reflectancia escalada 0.15): el desplazamiento SÍ corresponde.
    off, info = raster.choose_offset(np.full((10, 10), 0.15, "float32"), scl, -0.1)
    assert off == -0.1 and info["applied_offset"] == -0.1
    # Datos ya corregidos (vegetación con rojo 0.04): aplicar -0.1 daría reflectancias negativas.
    off, info = raster.choose_offset(np.full((10, 10), 0.04, "float32"), scl, -0.1)
    assert off == 0.0 and "ya vienen corregidos" in info["reason"]


def test_ndvi_excludes_nonpositive_reflectance():
    red = np.array([[0.05, -0.01, 0.0]], "float32")
    nir = np.array([[0.30, 0.20, 0.20]], "float32")
    ndvi, st = raster.compute_ndvi(red, nir, None)
    assert np.isfinite(ndvi[0, 0]) and np.isnan(ndvi[0, 1]) and np.isnan(ndvi[0, 2])
    assert st["nonpositive_reflectance_pct"] == pytest.approx(66.67, abs=0.01)
    assert st["ndvi_p90"] < 1.0


def test_make_grid_limits():
    with pytest.raises(raster.GridError):
        raster.make_grid([-78, -10, -77, -9], 0.0001)
    g = raster.make_grid(BBOX, 0.001)
    assert (g.width, g.height) == (100, 100)


def test_remote_rejects_foreign_hosts_and_bad_ids():
    with pytest.raises(remote.RemoteError):
        remote._check_url("https://evil.example.com/x.tif")
    with pytest.raises(remote.RemoteError):
        remote._check_url("http://sentinel-cogs.s3.us-west-2.amazonaws.com/x.tif")
    with pytest.raises(remote.RemoteError):
        remote.get_scene("../../etc/passwd")


class _FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, headers: dict):
        super().__init__(data)
        self.headers = headers


def test_https_opener_reads_cog_by_ranges(tmp_path, monkeypatch):
    """El opener de Python entrega a GDAL solo los rangos pedidos (verificación TLS intacta)."""
    data = np.arange(512 * 512, dtype="uint16").reshape(512, 512)
    path = Path(_band(tmp_path / "b.tif", data + 1, 10, "uint16"))
    blob = path.read_bytes()

    def fake_request(url, *, data=None, headers=None):
        remote._check_url(url)
        start, end = (int(x) for x in headers["Range"].split("=")[1].split("-"))
        return _FakeResponse(blob[start:end + 1], {"Content-Range": f"bytes {start}-{end}/{len(blob)}"})

    monkeypatch.setattr(remote, "_request", fake_request)
    opener = remote.HttpsOpener()
    url = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/prueba/b.tif"
    with rasterio.open(url, opener=opener) as src:
        window = src.read(1, window=rasterio.windows.Window(0, 0, 10, 10))
    assert window[0, 0] == 1 and window[9, 9] == data[9, 9] + 1
    assert 0 < opener.stats["bytes"] <= len(blob)
