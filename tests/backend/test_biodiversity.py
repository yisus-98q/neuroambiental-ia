"""Biodiversidad: especies, observaciones, validación, capa GeoJSON y resumen."""
import struct
import zlib
from datetime import UTC, datetime, timedelta

import pytest

from app.database.session import SessionLocal
from app.models import AuditLog

B = "/api/biodiversity"
PAST = "2025-06-15T10:00:00Z"


# El router se registra en app.main (integración oficial).


def _png() -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00\x00"))
            + chunk(b"IEND", b""))


def _species(client, h, name, **extra):
    body = {"nombre_cientifico": name, "nombre_comun": "Prueba", "fuente_taxonomica": "Fuente de prueba", **extra}
    return client.post(f"{B}/species", json=body, headers=h)


def _obs(client, h, species_id=None, **extra):
    body = {"species_id": species_id, "latitude": -9.5, "longitude": -77.5, "fecha_observacion": PAST,
            "observador": "Ana Prueba", "cantidad": 2, "metodo": "avistamiento",
            "confianza_identificacion": "media", "is_simulated": True, **extra}
    return client.post(f"{B}/observations", json=body, headers=h)


def test_species_crud_and_search(client, analyst_h, reader_h):
    assert client.get(f"{B}/species", headers=reader_h).status_code == 200
    r = _species(client, analyst_h, "Puma concolor", nombre_comun="Puma", categoria_conservacion="lc",
                 reino="Animalia")
    assert r.status_code == 201, r.text
    sp = r.json()
    assert sp["categoria_conservacion"] == "LC" and "según la fuente" in sp["aviso_categoria"]
    found = client.get(f"{B}/species?q=pum", headers=reader_h).json()
    assert [s["id"] for s in found] == [sp["id"]]
    assert client.get(f"{B}/species?q=%25", headers=reader_h).json() == []  # el comodín no se interpreta


def test_species_validation(client, analyst_h):
    assert _species(client, analyst_h, "Tremarctos ornatus").status_code == 201
    dup = _species(client, analyst_h, "  tremarctos   ORNATUS ")
    assert dup.status_code == 409
    assert _species(client, analyst_h, "Zz categoria", categoria_conservacion="XX").status_code == 422
    r = client.post(f"{B}/species", json={"nombre_cientifico": "Sin fuente"}, headers=analyst_h)
    assert r.status_code == 422


def test_species_permissions(client, reader_h):
    assert client.get(f"{B}/species").status_code == 401
    assert _species(client, reader_h, "Lector no puede").status_code == 403
    assert client.post(f"{B}/species", json={}).status_code == 401


def test_observation_create_and_get(client, analyst_h, reader_h):
    sp = _species(client, analyst_h, "Vicugna vicugna").json()
    r = _obs(client, analyst_h, sp["id"])
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["estado_validacion"] == "no_validada" and o["is_simulated"] is True
    assert o["nombre_cientifico"] == "Vicugna vicugna" and o["cantidad"] == 2
    assert client.get(f"{B}/observations/{o['id']}", headers=reader_h).json()["id"] == o["id"]
    assert client.get(f"{B}/observations/noexiste", headers=reader_h).status_code == 404
    unid = _obs(client, analyst_h, None)
    assert unid.status_code == 201 and unid.json()["species_id"] is None


def test_observation_validation_errors(client, analyst_h):
    assert _obs(client, analyst_h, latitude=95).status_code == 422
    assert _obs(client, analyst_h, longitude=-181).status_code == 422
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    assert _obs(client, analyst_h, fecha_observacion=future).status_code == 422
    assert _obs(client, analyst_h, cantidad=0).status_code == 422
    assert _obs(client, analyst_h, metodo="adivinanza").status_code == 422
    assert _obs(client, analyst_h, confianza_identificacion="total").status_code == 422
    assert _obs(client, analyst_h, species_id="inexistente").status_code == 422
    r = client.post(f"{B}/observations", headers=analyst_h, json={
        "latitude": 1, "longitude": 1, "fecha_observacion": PAST, "observador": "X Y", "metodo": "huella",
        "confianza_identificacion": "baja"})
    assert r.status_code == 422  # is_simulated es obligatorio


def test_observation_photo_must_be_image(client, analyst_h):
    csv = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "Pruebas", "is_simulated": "true"},
                      files={"file": ("a.csv", b"punto,latitud,longitud\nA,-12,-77\n")}).json()
    bad = _obs(client, analyst_h, photo_record_id=csv["id"])
    assert bad.status_code == 422 and "imagen" in bad.text
    assert _obs(client, analyst_h, photo_record_id="noexiste").status_code == 422
    png = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "Pruebas", "is_simulated": "true"},
                      files={"file": ("f.png", _png())}).json()
    ok = _obs(client, analyst_h, photo_record_id=png["id"])
    assert ok.status_code == 201 and ok.json()["photo_record_id"] == png["id"]


def test_observation_permissions_and_filters(client, analyst_h, reader_h):
    assert _obs(client, reader_h).status_code == 403
    assert client.get(f"{B}/observations").status_code == 401
    sp = _species(client, analyst_h, "Filtro filtrus").json()
    _obs(client, analyst_h, sp["id"], latitude=-3, longitude=-70, is_simulated=False,
         fecha_observacion="2024-01-10T00:00:00Z")
    _obs(client, analyst_h, sp["id"], latitude=-3.1, longitude=-70.1, is_simulated=True,
         fecha_observacion="2024-03-10T00:00:00Z")
    q = lambda s: client.get(f"{B}/observations?{s}", headers=reader_h).json()  # noqa: E731
    assert len(q(f"species_id={sp['id']}")) == 2
    assert len(q(f"species_id={sp['id']}&is_simulated=false")) == 1
    assert len(q(f"species_id={sp['id']}&desde=2024-02-01T00:00:00Z")) == 1
    assert len(q(f"species_id={sp['id']}&hasta=2024-02-01T00:00:00Z")) == 1
    assert len(q(f"species_id={sp['id']}&bbox=-71,-4,-69,-2")) == 2
    assert q(f"species_id={sp['id']}&bbox=-10,-10,-9,-9") == []
    assert client.get(f"{B}/observations?bbox=1,2,3", headers=reader_h).status_code == 422
    assert client.get(f"{B}/observations?bbox=5,0,1,1", headers=reader_h).status_code == 422


def test_validate_admin_only_and_audited(client, admin_h, analyst_h, reader_h):
    o = _obs(client, analyst_h, None).json()
    url = f"{B}/observations/{o['id']}/validate"
    body = {"estado": "validada", "nota": "Revisada con la foto"}
    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers=analyst_h).status_code == 403
    assert client.post(url, json=body, headers=reader_h).status_code == 403
    assert client.post(url, json={"estado": "validada", "nota": ""}, headers=admin_h).status_code == 422
    assert client.post(url, json={"estado": "no_validada", "nota": "volver"}, headers=admin_h).status_code == 422
    r = client.post(url, json=body, headers=admin_h)
    assert r.status_code == 200 and r.json()["estado_validacion"] == "validada"
    assert r.json()["validation_note"] == "Revisada con la foto" and r.json()["is_simulated"] is True
    assert client.post(f"{B}/observations/zzz/validate", json=body, headers=admin_h).status_code == 404
    with SessionLocal() as db:
        log = db.query(AuditLog).filter_by(action="observacion_validada", target_id=o["id"]).one()
        assert log.details["nuevo"] == "validada" and log.details["nota"] == "Revisada con la foto"


def test_geojson_layer(client, analyst_h, admin_h, reader_h):
    sp = _species(client, analyst_h, "Geo jsonus").json()
    real = _obs(client, analyst_h, sp["id"], latitude=-8.0, longitude=-78.0, is_simulated=False).json()
    sim = _obs(client, analyst_h, sp["id"], latitude=-8.1, longitude=-78.1, is_simulated=True).json()
    gone = _obs(client, analyst_h, sp["id"], is_simulated=True).json()
    client.post(f"{B}/observations/{gone['id']}/validate", json={"estado": "descartada", "nota": "Error"}, headers=admin_h)
    assert client.get(f"{B}/observations/geojson").status_code == 401
    gj = client.get(f"{B}/observations/geojson?species_id={sp['id']}", headers=reader_h).json()
    assert gj["type"] == "FeatureCollection"
    by_id = {f["properties"]["observation_id"]: f for f in gj["features"]}
    assert set(by_id) == {real["id"], sim["id"]}  # la descartada no aparece
    f = by_id[real["id"]]
    assert f["geometry"] == {"type": "Point", "coordinates": [-78.0, -8.0]}
    p = f["properties"]
    assert p["is_simulated"] is False and by_id[sim["id"]]["properties"]["is_simulated"] is True
    assert p["nombre_cientifico"] == "Geo jsonus" and p["estado_validacion"] == "no_validada"
    assert p["identificada"] is True and p["metodo"] == "avistamiento"
    only_real = client.get(f"{B}/observations/geojson?species_id={sp['id']}&is_simulated=false", headers=reader_h).json()
    assert [x["properties"]["observation_id"] for x in only_real["features"]] == [real["id"]]


def test_summary_is_coherent(client, analyst_h, admin_h, reader_h):
    s = client.get(f"{B}/summary", headers=reader_h)
    assert s.status_code == 200 and client.get(f"{B}/summary").status_code == 401
    data = s.json()
    total = data["total_observaciones"]
    assert total == sum(x["observaciones"] for x in data["por_especie"]) == sum(x["observaciones"] for x in data["por_mes"])
    assert total == sum(data["por_estado"].values())
    assert set(data["por_estado"]) == {"no_validada", "validada", "descartada"}
    assert "esfuerzo de muestreo" in data["aviso"]
    ident = {x["species_id"] for x in data["por_especie"] if x["species_id"]}
    assert data["riqueza_especies"] <= len(ident)
    assert data["riqueza_especies_solo_reales"] <= data["riqueza_especies"]
    real = client.get(f"{B}/summary?is_simulated=false", headers=reader_h).json()
    assert real["total_observaciones"] <= total
    sp = _species(client, analyst_h, "Riqueza unicus").json()
    before = client.get(f"{B}/summary", headers=reader_h).json()["riqueza_especies"]
    _obs(client, analyst_h, sp["id"], is_simulated=False)
    after = client.get(f"{B}/summary", headers=reader_h).json()
    assert after["riqueza_especies"] == before + 1
    assert any(m["mes"] == "2025-06" for m in after["por_mes"])


def test_descriptor_flags():
    from app.modules.biodiversity.descriptor import DESCRIPTOR
    caps = {c.key: c.implemented for c in DESCRIPTOR.capabilities}
    assert caps == {"registro_especies": True, "registro_observaciones": True, "analisis_fotografias": False,
                    "reconocimiento_especies": False, "cambio_habitat": False, "fragmentacion": False}
    assert any("no se verifica" in x for x in DESCRIPTOR.limitations)


def test_admin_cannot_validate_own_observation(client, admin_h):
    """Separación de funciones: quien registra una observación no puede validarla."""
    obs = _obs(client, admin_h).json()
    r = client.post(f"{B}/observations/{obs['id']}/validate", json={"estado": "validada", "nota": "Revisada"},
                    headers=admin_h)
    assert r.status_code == 422 and "otro administrador" in r.text


def test_observations_appear_in_prediction_catalog(client, analyst_h, admin_h):
    """Catálogo de NEURO PREDICTION: real → observación real; simulada → simulación; descartada → excluida."""
    real = _obs(client, analyst_h, is_simulated=False).json()
    sim = _obs(client, analyst_h, is_simulated=True).json()
    gone = _obs(client, analyst_h, is_simulated=False).json()
    client.post(f"{B}/observations/{gone['id']}/validate", json={"estado": "descartada", "nota": "Error de registro"},
                headers=admin_h)

    def ids(tipo):
        r = client.get(f"/api/neuroprediction/catalog?tipo={tipo}&limit=200", headers=analyst_h).json()
        return {i["id"] for i in r["items"]}

    assert real["id"] in ids("observacion_real") and real["id"] not in ids("simulacion")
    assert sim["id"] in ids("simulacion") and sim["id"] not in ids("observacion_real")
    assert gone["id"] not in ids("observacion_real") | ids("simulacion")
