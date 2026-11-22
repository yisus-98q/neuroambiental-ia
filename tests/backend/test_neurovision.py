"""NEUROVISION: imágenes sintéticas generadas con cv2/numpy, subidas a NEURODATA como simuladas."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.api import neurovision
from app.core import jobs
from app.main import app

if not any(getattr(r, "path", "").startswith("/api/neurovision") for r in app.routes):
    _n = len(app.router.routes)
    app.include_router(neurovision.router)
    # Las rutas nuevas deben quedar antes del comodín de la SPA (/{full_path}) para ser alcanzables.
    _new = app.router.routes[_n:]
    del app.router.routes[_n:]
    _spa = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", "") == "/{full_path:path}"),
                len(app.router.routes))
    app.router.routes[_spa:_spa] = _new


def _png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _upload(client, h, content, name="img.png", simulated="true"):
    r = client.post("/api/neurodata/upload", headers=h, data={"source_name": "Prueba", "is_simulated": simulated},
                    files={"file": (name, content)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _texture(seed=1, size=(400, 500)):
    """Escena con muchas figuras aleatorias (esquinas nítidas para ORB), reproducible."""
    rng = np.random.default_rng(seed)
    img = np.full(size + (3,), 110, np.uint8)
    for _ in range(120):
        col = tuple(int(c) for c in rng.integers(0, 255, 3))
        x, y = int(rng.integers(0, size[1] - 40)), int(rng.integers(0, size[0] - 40))
        w, h = int(rng.integers(8, 40)), int(rng.integers(8, 40))
        if rng.random() < 0.5:
            cv2.rectangle(img, (x, y), (x + w, y + h), col, -1)
        else:
            cv2.circle(img, (x + w // 2, y + h // 2), w // 2, col, -1)
    return cv2.GaussianBlur(img, (3, 3), 0)


def _shapes():
    img = np.full((300, 400, 3), 30, np.uint8)
    cv2.rectangle(img, (40, 40), (140, 120), (255, 255, 255), -1)
    cv2.circle(img, (280, 200), 50, (220, 220, 220), -1)
    return img


@pytest.fixture(scope="module")
def ids(client, analyst_h):
    green = np.full((200, 300, 3), (40, 40, 40), np.uint8)  # BGR
    cv2.rectangle(green, (50, 50), (150, 150), (30, 200, 30), -1)  # verde
    base = _texture()
    moved = base.copy()
    cv2.rectangle(moved, (200, 150), (320, 260), (0, 0, 255), -1)  # cambio
    # versión levemente girada de la base (sin cambios)
    rot = cv2.warpAffine(base, cv2.getRotationMatrix2D((250, 200), 3, 1.0), (500, 400))
    return {
        "shapes": _upload(client, analyst_h, _png(_shapes())),
        "green": _upload(client, analyst_h, _png(green)),
        "gray": _upload(client, analyst_h, _png(cv2.cvtColor(_shapes(), cv2.COLOR_BGR2GRAY))),
        "base": _upload(client, analyst_h, _png(base)),
        "changed": _upload(client, analyst_h, _png(moved)),
        "rot": _upload(client, analyst_h, _png(rot)),
        "flat": _upload(client, analyst_h, _png(np.full((400, 500, 3), 128, np.uint8))),
    }


def _analyze(client, h, rid, op, params=None):
    return client.post("/api/neurovision/analyze", headers=h, json={"record_id": rid, "operation": op, "params": params})


def test_operations_public(client):
    r = client.get("/api/neurovision/operations")
    assert r.status_code == 200
    keys = {o["key"] for o in r.json()["operations"]}
    assert keys == {"canny", "clahe", "segmentacion", "verdor_exg", "caracteristicas"}
    assert "no aplica" in r.json()["confidence_note"]


def test_segmentation_regions_and_provenance(client, analyst_h, ids):
    r = _analyze(client, analyst_h, ids["shapes"], "segmentacion", {"min_area": 200})
    assert r.status_code == 201, r.text
    d = r.json()
    ex = d["extra"]
    assert d["data_type"] == "imagen_procesada" and d["is_simulated"] is True
    assert ex["confidence"] is None and "no aplica" in ex["confidence_note"]
    assert ex["limitations"] and ex["opencv_version"] and ex["source_record"] == ids["shapes"]
    assert ex["regions_total"] == 2 and len(ex["regions"]) == 2
    big, small = ex["regions"]  # ordenadas por área: el círculo (≈7850) y el rectángulo (≈8000)
    areas = sorted(r_["area_px"] for r_ in ex["regions"])
    assert 7000 < areas[0] < 8500 and 7000 < areas[1] < 8500
    rect = next(r_ for r_ in ex["regions"] if r_["bbox"][0] < 100)
    assert abs(rect["centroid"][0] - 90) < 3 and abs(rect["centroid"][1] - 80) < 3
    assert d["overlay_url"]
    # La imagen procesada y la superposición se sirven con los endpoints existentes.
    f = client.get(d["image_url"], headers=analyst_h)
    assert f.status_code == 200 and f.content[:4] == b"\x89PNG"
    o = client.get(d["overlay_url"], headers=analyst_h)
    assert o.status_code == 200 and o.content[:4] == b"\x89PNG"
    listed = client.get("/api/neurovision/results", headers=analyst_h).json()
    assert any(x["id"] == d["id"] for x in listed)


def test_canny_clahe_features(client, analyst_h, ids):
    canny = _analyze(client, analyst_h, ids["shapes"], "canny").json()["extra"]
    assert canny["features"]["densidad_bordes_pct"] > 0 and canny["regions"] == []
    clahe = _analyze(client, analyst_h, ids["shapes"], "clahe", {"clip_limit": 3.0, "tile": 4})
    assert clahe.status_code == 201 and clahe.json()["extra"]["params"] == {"clip_limit": 3.0, "tile": 4}
    ft = _analyze(client, analyst_h, ids["shapes"], "caracteristicas").json()["extra"]["features"]
    assert ft["ancho_px"] == 400 and ft["alto_px"] == 300 and len(ft["media_rgb"]) == 3
    assert ft["nitidez_laplaciano"] > 0 and ft["regiones_total"] == 2


def test_exg_vegetation(client, analyst_h, ids):
    ex = _analyze(client, analyst_h, ids["green"], "verdor_exg").json()["extra"]
    assert ex["regions_total"] == 1
    # 100x100 px verdes sobre 200x300 → ≈16.7 %
    assert 15 < ex["features"]["verdor_aparente_pct"] < 18
    assert any("no equivale a vegetación confirmada" in lim for lim in ex["limitations"])
    assert _analyze(client, analyst_h, ids["gray"], "verdor_exg").status_code == 422


def test_invalid_params_and_record(client, analyst_h, ids):
    assert _analyze(client, analyst_h, ids["shapes"], "canny", {"low": 200, "high": 100}).status_code == 422
    assert _analyze(client, analyst_h, ids["shapes"], "canny", {"blur_ksize": 4}).status_code == 422
    assert _analyze(client, analyst_h, ids["shapes"], "canny", {"xx": 1}).status_code == 422
    assert _analyze(client, analyst_h, ids["shapes"], "magia").status_code == 422
    assert _analyze(client, analyst_h, "0" * 32, "canny").status_code == 404


def test_corrupt_and_huge_images(client, analyst_h):
    corrupt = b"\x89PNG\r\n\x1a\n" + b"basura" * 20  # pasa la validación de NEURODATA, no la decodificación
    cid = _upload(client, analyst_h, corrupt, "rota.png")
    assert _analyze(client, analyst_h, cid, "canny").status_code == 422
    huge = _upload(client, analyst_h, _png(np.zeros((5200, 5200, 3), np.uint8)), "enorme.png")  # 27 MP
    r = _analyze(client, analyst_h, huge, "canny")
    assert r.status_code == 422 and "MP" in r.json()["detail"]


def test_large_image_is_resized(client, analyst_h):
    rid = _upload(client, analyst_h, _png(np.full((2400, 3000, 3), 90, np.uint8)), "grande.png")
    ex = _analyze(client, analyst_h, rid, "caracteristicas").json()["extra"]
    assert ex["work_size"]["resized"] and max(ex["work_size"]["work_width"], ex["work_size"]["work_height"]) == 2048


def test_permissions(client, reader_h, ids):
    assert _analyze(client, reader_h, ids["shapes"], "canny").status_code == 403
    r = client.post("/api/neurovision/compare", headers=reader_h, json={"record_a": ids["base"], "record_b": ids["rot"]})
    assert r.status_code == 403
    assert client.get("/api/neurovision/results", headers=reader_h).status_code == 200


def test_compare_detects_changes(client, analyst_h, ids):
    r = client.post("/api/neurovision/compare", headers=analyst_h,
                    json={"record_a": ids["base"], "record_b": ids["changed"]})
    assert r.status_code == 201, r.text
    ex = r.json()["extra"]
    assert ex["kind"] == "comparacion" and ex["confidence"] is None
    assert ex["features"]["cambio_pct"] > 1 and ex["regions_total"] >= 1
    reg = ex["regions"][0]["bbox"]  # el parche rojo está en x 200-320, y 150-260
    assert 150 < reg[0] < 260 and 100 < reg[1] < 200
    assert any("georreferenciación" in lim for lim in ex["limitations"])


def test_compare_no_changes_with_rotation(client, analyst_h, ids):
    r = client.post("/api/neurovision/compare", headers=analyst_h,
                    json={"record_a": ids["base"], "record_b": ids["rot"]})
    assert r.status_code == 201, r.text
    assert r.json()["extra"]["features"]["cambio_pct"] < 2
    same = client.post("/api/neurovision/compare", headers=analyst_h,
                       json={"record_a": ids["base"], "record_b": ids["base"]})
    assert same.status_code == 422  # misma imagen: se pide dos distintas


def test_compare_cannot_align(client, analyst_h, ids):
    r = client.post("/api/neurovision/compare", headers=analyst_h,
                    json={"record_a": ids["base"], "record_b": ids["flat"]})
    assert r.status_code == 422 and "alinear" in r.json()["detail"]


def test_lock_returns_409(client, analyst_h, ids):
    assert jobs.LOCK.acquire(blocking=False)
    try:
        assert _analyze(client, analyst_h, ids["shapes"], "canny").status_code == 409
    finally:
        jobs.LOCK.release()
    assert _analyze(client, analyst_h, ids["shapes"], "canny").status_code == 201
