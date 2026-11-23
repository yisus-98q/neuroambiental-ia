"""NEUROTERRAIN: sensores, importación desde CSV de NEURODATA y análisis de series (sin red, series sintéticas)."""
import random
from datetime import UTC, datetime, timedelta

import pytest


START = datetime(2025, 1, 1, tzinfo=UTC)
AVISO = "Indicador experimental por umbrales; no es una predicción de falla ni sustituye el criterio geotécnico"


# El router se registra en app.main (integración oficial).


def _csv(values, variable="desplazamiento", unit="mm", days=None):
    rows = ["fecha,variable,valor,unidad"]
    for i, v in enumerate(values):
        d = START + timedelta(days=i if days is None else days[i])
        rows.append(f"{d.isoformat()},{variable},{v:.6f},{unit}")
    return "\n".join(rows).encode()


def _noisy(fn, n=120, sd=0.05, seed=1):
    rnd = random.Random(seed)
    return [fn(i) + rnd.gauss(0, sd) for i in range(n)]


def _upload(client, h, content, name="serie.csv", simulated="true"):
    r = client.post("/api/neurodata/upload", headers=h, data={"source_name": "Pruebas terrain", "is_simulated": simulated},
                    files={"file": (name, content)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _sensor(client, h, kind="gps", **extra):
    r = client.post("/api/terrain/sensors", headers=h, json={"name": "S-" + kind, "kind": kind, **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _import(client, h, sensor_id, record_id, **body):
    return client.post(f"/api/terrain/sensors/{sensor_id}/import", headers=h, json={"data_record_id": record_id, **body})


def _setup(client, h, content, simulated="true"):
    sid = _sensor(client, h)
    r = _import(client, h, sid, _upload(client, h, content, simulated=simulated))
    assert r.status_code == 201, r.text
    return sid


def _series(client, h, sid, **params):
    return client.get(f"/api/terrain/sensors/{sid}/series", headers=h, params=params)


def _piecewise(i):
    return 0.2 * i if i <= 90 else 18 + 0.8 * (i - 90)


def test_linear_velocity_known(client, analyst_h, reader_h):
    sid = _setup(client, analyst_h, _csv(_noisy(lambda i: 0.5 * i)))
    r = _series(client, reader_h, sid)  # un lector puede consultar
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["variable"] == "desplazamiento" and s["unit"] == "mm" and s["is_simulated"] is True
    assert s["velocidad_total"]["velocidad"] == pytest.approx(0.5, rel=0.05)
    assert s["velocidad_reciente"]["velocidad"] == pytest.approx(0.5, rel=0.05)
    assert s["desplazamiento_acumulado"] == pytest.approx(0.5 * 119, rel=0.05)
    assert s["anomalias"] == [] and s["aceleracion"]["significativa"] is False
    assert s["clasificacion"]["estado"] == "en_movimiento" and s["clasificacion"]["experimental"] is True
    assert AVISO in s["aviso"] and AVISO in s["clasificacion"]["aviso"]
    assert "EJEMPLO" in s["umbrales"]["rotulo"]
    assert s["submuestreada"] is False and len(s["puntos"]) == 120


def test_stable_series(client, analyst_h):
    sid = _setup(client, analyst_h, _csv(_noisy(lambda i: 0.0, seed=2)))
    s = _series(client, analyst_h, sid).json()
    assert s["clasificacion"]["estado"] == "estable"


def test_acceleration_only_in_accelerated_series(client, analyst_h):
    sid_acc = _setup(client, analyst_h, _csv(_noisy(_piecewise, seed=3)))
    acc = _series(client, analyst_h, sid_acc).json()
    assert acc["velocidad_previa"]["velocidad"] == pytest.approx(0.2, rel=0.05)
    assert acc["velocidad_reciente"]["velocidad"] == pytest.approx(0.8, rel=0.05)
    assert acc["aceleracion"]["significativa"] is True and acc["aceleracion"]["valor"] > 0
    assert acc["aceleracion_cuadratica"] > 0
    assert acc["clasificacion"]["estado"] == "acelerando"
    sid_lin = _setup(client, analyst_h, _csv(_noisy(lambda i: 0.5 * i, seed=4)))
    assert _series(client, analyst_h, sid_lin).json()["clasificacion"]["estado"] != "acelerando"
    # Los umbrales son configurables: con un cociente exigido muy alto ya no se declara aceleración.
    strict = _series(client, analyst_h, sid_acc, acc_ratio=10).json()
    assert strict["clasificacion"]["estado"] == "en_movimiento"
    assert strict["umbrales"]["acc_ratio"] == 10


def test_jump_detected_and_neutralized(client, analyst_h):
    sid = _setup(client, analyst_h, _csv(_noisy(lambda i: 0.3 * i + (5.0 if i >= 60 else 0.0), seed=5)))
    s = _series(client, analyst_h, sid).json()
    assert [a["index"] for a in s["anomalias"]] == [60]
    assert s["anomalias"][0]["increment"] == pytest.approx(5.3, abs=0.5)
    assert any(p["a"] for p in s["puntos"])
    assert s["velocidad_total"]["velocidad"] == pytest.approx(0.3, rel=0.05)
    assert s["velocidad_total_con_saltos"]["velocidad"] > 0.33  # el salto sesga la regresión cruda
    assert s["clasificacion"]["estado"] == "en_movimiento"  # el salto no se confunde con aceleración
    assert any("salto" in n for n in s["notas"])
    # Un pico aislado (sube y baja) también se marca.
    spike = _noisy(lambda i: 0.3 * i, seed=6)
    spike[40] += 8
    sid2 = _setup(client, analyst_h, _csv(spike))
    assert 40 in [a["index"] for a in _series(client, analyst_h, sid2).json()["anomalias"]]


def test_subsampling_to_2000_points(client, analyst_h):
    n = 3000
    sid = _sensor(client, analyst_h)
    rec = _upload(client, analyst_h, b"fecha,desplazamiento\n" + "\n".join(
        f"{(START + timedelta(hours=i)).isoformat()},{0.01 * i:.4f}" for i in range(n)).encode())
    r = _import(client, analyst_h, sid, rec, format="ancho", value_columns=["desplazamiento"], default_unit="mm")
    assert r.status_code == 201 and r.json()["importadas"] == n
    s = _series(client, analyst_h, sid).json()
    assert s["n_mediciones"] == n and s["submuestreada"] is True and len(s["puntos"]) <= 2000
    assert s["puntos"][0]["t"] < s["puntos"][-1]["t"]
    assert s["velocidad_total"]["velocidad"] == pytest.approx(0.24, rel=0.05)  # 0.01/h = 0.24 por día


def test_disordered_and_duplicate_dates(client, analyst_h):
    vals = [0.5 * i for i in range(30)]
    days = list(range(30))
    shuffled = days[:10][::-1] + days[10:]
    bad_order = _upload(client, analyst_h, _csv(vals, days=shuffled))
    sid = _sensor(client, analyst_h)
    r = _import(client, analyst_h, sid, bad_order)
    assert r.status_code == 422 and "fuera de orden" in str(r.json())
    # Con normalize se ordena (los valores van pareados a su fecha, no se alteran).
    ok = _import(client, analyst_h, sid, bad_order, normalize=True)
    assert ok.status_code == 201 and ok.json()["importadas"] == 30
    # Duplicados idénticos: error por defecto, descartados con normalize.
    dup_days = days + [5]
    dup_vals = vals + [vals[5]]
    dup = _upload(client, analyst_h, _csv(dup_vals, days=dup_days))
    sid2 = _sensor(client, analyst_h)
    assert "duplicada" in str(_import(client, analyst_h, sid2, dup).json())
    r2 = _import(client, analyst_h, sid2, dup, normalize=True)
    assert r2.status_code == 201 and r2.json()["importadas"] == 30 and r2.json()["descartadas_duplicadas"] == 1
    # Duplicado con valor distinto: siempre se rechaza.
    conflict = _upload(client, analyst_h, _csv(vals + [99.0], days=days + [5]))
    r3 = _import(client, analyst_h, _sensor(client, analyst_h), conflict, normalize=True)
    assert r3.status_code == 422 and "valores distintos" in str(r3.json())


def test_import_validation_errors(client, analyst_h, monkeypatch):
    sid = _sensor(client, analyst_h)
    bad_date = _upload(client, analyst_h, b"fecha,variable,valor,unidad\nayer,d,1,mm\n2025-01-02,d,2,mm\n")
    r = _import(client, analyst_h, sid, bad_date)
    assert r.status_code == 422 and "fecha no interpretable" in str(r.json())
    bad_val = _upload(client, analyst_h, b"fecha,variable,valor,unidad\n2025-01-01,d,abc,mm\n2025-01-02,d,nan,mm\n")
    r = _import(client, analyst_h, sid, bad_val)
    assert r.status_code == 422 and "no numérico" in str(r.json()) and "no finito" in str(r.json())
    good = _upload(client, analyst_h, _csv([1, 2, 3, 4, 5, 6]))
    r = _import(client, analyst_h, sid, good, date_column="timestamp")
    assert r.status_code == 422 and "Columnas no encontradas" in str(r.json())
    assert _import(client, analyst_h, sid, "0" * 32).status_code == 404
    assert _import(client, analyst_h, "no-existe", good).status_code == 404
    assert _import(client, analyst_h, sid, good, format="ancho").status_code == 422  # falta value_columns
    # Solo CSV registrados en NEURODATA.
    geo = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "x", "is_simulated": "true"},
                      files={"file": ("a.geojson", b'{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[-77,-12]}}')})
    assert _import(client, analyst_h, sid, geo.json()["id"]).status_code == 422
    # Tope de filas (se baja el límite para no subir 50 000 filas en la prueba).
    from app.modules.terrain import service
    monkeypatch.setattr(service, "MAX_ROWS", 5)
    r = _import(client, analyst_h, sid, good)
    assert r.status_code == 422 and "máximo" in str(r.json())
    monkeypatch.undo()
    # Reimportar el mismo CSV al mismo sensor duplicaría mediciones: 409.
    assert _import(client, analyst_h, sid, good).status_code == 201
    assert _import(client, analyst_h, sid, good).status_code == 409


def test_wide_format_and_simulated_inheritance(client, analyst_h):
    rows = ["fecha,norte,este"] + [f"{(START + timedelta(days=i)).isoformat()},{0.1 * i:.3f},{0.2 * i if i % 7 else ''}"
                                   for i in range(40)]
    rec = _upload(client, analyst_h, "\n".join(rows).encode(), simulated="false")
    sid = _sensor(client, analyst_h, "extensometro")
    r = _import(client, analyst_h, sid, rec, format="ancho", value_columns=["norte", "este"], units={"norte": "mm"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["variables"]["norte"] == 40 and body["variables"]["este"] == 40 - 6 and body["is_simulated"] is False
    from app.database.session import SessionLocal
    from app.models import Measurement
    with SessionLocal() as db:
        ms = db.query(Measurement).filter_by(sensor_id=sid).all()
        assert len(ms) == 74 and all(m.is_simulated is False and m.data_record_id == rec for m in ms)
    s = client.get(f"/api/terrain/sensors/{sid}", headers=analyst_h).json()
    assert {v["variable"] for v in s["variables"]} == {"norte", "este"}
    assert _series(client, analyst_h, sid).status_code == 422  # varias variables: debe indicarse cuál
    ok = _series(client, analyst_h, sid, variable="norte").json()
    assert ok["is_simulated"] is False and ok["velocidad_total"]["velocidad"] == pytest.approx(0.1, rel=0.05)
    assert _series(client, analyst_h, sid, variable="otra").status_code == 404


def test_series_edge_cases(client, analyst_h):
    assert _series(client, analyst_h, "no-existe").status_code == 404
    sid = _sensor(client, analyst_h)
    assert _series(client, analyst_h, sid).status_code == 404  # sin mediciones
    short = _setup(client, analyst_h, _csv([1, 2, 3]))
    assert "insuficiente" in str(_series(client, analyst_h, short).json())
    ok = _setup(client, analyst_h, _csv(_noisy(lambda i: 0.5 * i, n=40)))
    assert _series(client, analyst_h, ok, window_days=0).status_code == 422
    assert _series(client, analyst_h, ok, acc_ratio=1).status_code == 422
    assert _series(client, analyst_h, ok, max_points=5000).status_code == 422
    # Serie de 40 días con ventana de 30: se reduce la ventana y se avisa.
    s = _series(client, analyst_h, ok).json()
    assert s["ventana_dias"] <= 20 and any("ventana efectiva" in n for n in s["notas"])


def test_sensor_crud_and_permissions(client, analyst_h, reader_h):
    assert client.get("/api/terrain/sensors").status_code == 401
    assert client.post("/api/terrain/sensors", json={"name": "x1", "kind": "gps"}).status_code == 401
    assert client.post("/api/terrain/sensors", headers=reader_h, json={"name": "Lector", "kind": "gps"}).status_code == 403
    for bad in ({"kind": "gps", "name": "ok", "latitude": 95, "longitude": 0},
                {"kind": "gps", "name": "ok", "latitude": 10},
                {"kind": "radar", "name": "ok"},
                {"kind": "gps", "name": "o"},
                {"kind": "gps", "name": "ok", "territory_id": "x" * 32}):
        assert client.post("/api/terrain/sensors", headers=analyst_h, json=bad).status_code == 422, bad
    r = client.post("/api/terrain/sensors", headers=analyst_h,
                    json={"name": "Talud norte", "kind": "inclinometro", "latitude": -12.05, "longitude": -77.04})
    assert r.status_code == 201 and r.json()["variables"] == []
    lst = client.get("/api/terrain/sensors", headers=reader_h)
    assert lst.status_code == 200 and any(s["name"] == "Talud norte" for s in lst.json())
    rec = _upload(client, analyst_h, _csv([1, 2, 3, 4, 5, 6]))
    sid = r.json()["id"]
    assert _import(client, reader_h, sid, rec).status_code == 403
    assert client.post(f"/api/terrain/sensors/{sid}/import", json={"data_record_id": rec}).status_code == 401
    assert client.post(f"/api/terrain/sensors/{sid}/alert", headers=reader_h, json={}).status_code == 403
    assert client.post(f"/api/terrain/sensors/{sid}/alert", json={}).status_code == 401
    assert client.get(f"/api/terrain/sensors/{sid}/series").status_code == 401


def test_alert_only_on_request_and_experimental(client, analyst_h, reader_h):
    sid = _setup(client, analyst_h, _csv(_noisy(_piecewise, seed=7)))
    # Importar y analizar no crea alertas.
    _series(client, analyst_h, sid)
    before = client.get("/api/alerts?limit=500", headers=analyst_h).json()
    assert not any(a["module_key"] == "terrain" for a in before)
    r = client.post(f"/api/terrain/sensors/{sid}/alert", headers=analyst_h, json={"notes": "Revisión solicitada"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["alert_kind"] == "experimental" and body["validation_status"] == "no_validada"
    assert body["level"] == "alto" and body["is_simulated"] is True and AVISO in body["aviso"]
    alert = client.get(f"/api/alerts/{body['alert_id']}", headers=reader_h).json()
    assert alert["module_key"] == "terrain" and alert["alert_kind"] == "experimental"
    assert alert["validation_status"] == "no_validada" and len(alert["uncertainty"]) > 20
    assert "Métricas" in alert["evidence"] and "EJEMPLO" in alert["evidence"]
    over = client.post(f"/api/terrain/sensors/{sid}/alert", headers=analyst_h, json={"level": "bajo"}).json()
    assert over["level"] == "bajo"
    after = client.get("/api/alerts?limit=500", headers=analyst_h).json()
    assert sum(a["module_key"] == "terrain" for a in after) == 2
    # Sin mediciones suficientes no hay alerta.
    empty = _sensor(client, analyst_h)
    assert client.post(f"/api/terrain/sensors/{empty}/alert", headers=analyst_h, json={}).status_code == 404


def test_descriptor_is_honest(client, reader_h):
    mod = client.get("/api/neurocore/modules/terrain", headers=reader_h).json()
    caps = {c["key"]: c["implemented"] for c in mod["capabilities"]}
    assert caps["series_desplazamiento"] and caps["deteccion_aceleraciones"] and not caps["insar"]
    assert mod["status"] == "parcial"
    assert any("CSV" in c["description"] for c in mod["capabilities"] if c["key"] in ("gps", "inclinometros"))
    assert any("InSAR" in lim for lim in mod["limitations"])
