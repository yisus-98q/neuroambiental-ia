import json

CSV_OK = b"punto,latitud,longitud,valor\nA,-12.05,-77.04,1.5\nB,-13.53,-71.97,2.0\n"
GEOJSON_OK = json.dumps({"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"n": 1},
     "geometry": {"type": "Polygon", "coordinates": [[[-77, -9], [-76, -9], [-76, -10], [-77, -9]]]}}]}).encode()


def _upload(client, h, name, content, simulated="true", **extra):
    data = {"source_name": "Pruebas", "is_simulated": simulated, **extra}
    return client.post("/api/neurodata/upload", headers=h, data=data, files={"file": (name, content)})


def test_upload_csv_with_metadata(client, analyst_h):
    r = _upload(client, analyst_h, "estaciones.csv", CSV_OK)
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["data_type"] == "csv" and rec["validation_status"] == "valido"
    assert rec["is_simulated"] is True
    assert rec["extra"]["rows"] == 2 and rec["extra"]["lat_column"] == "latitud"
    assert rec["bbox"] == [-77.04, -13.53, -71.97, -12.05]
    assert len(rec["sha256"]) == 64 and rec["source_name"] == "Pruebas"
    gj = client.get(f"/api/neurodata/records/{rec['id']}/geojson", headers=analyst_h).json()
    assert len(gj["features"]) == 2
    assert gj["features"][0]["properties"]["is_simulated"] is True


def test_upload_geojson_and_layers(client, analyst_h):
    r = _upload(client, analyst_h, "zona.geojson", GEOJSON_OK, simulated="false")
    assert r.status_code == 201, r.text
    layers = client.get("/api/neurodata/layers", headers=analyst_h).json()
    assert any(layer["record_id"] == r.json()["id"] for layer in layers)
    real_only = client.get("/api/neurodata/layers?include_simulated=false", headers=analyst_h).json()
    assert all(not layer["is_simulated"] for layer in real_only)


def test_rejects_invalid_files(client, analyst_h):
    assert _upload(client, analyst_h, "malo.exe", b"MZ").status_code == 415
    assert _upload(client, analyst_h, "vacio.csv", b"").status_code == 422
    assert _upload(client, analyst_h, "falso.png", b"esto no es png").status_code == 422
    bad_geo = json.dumps({"type": "Feature", "geometry": {"type": "Point", "coordinates": [500, 10]}}).encode()
    r = _upload(client, analyst_h, "fuera.geojson", bad_geo)
    assert r.status_code == 422 and "fuera de rango" in str(r.json())
    assert _upload(client, analyst_h, "roto.geojson", b"{no json").status_code == 422


def test_rejects_oversize(client, analyst_h):
    big = b"a,b\n" + b"1,2\n" * 300_000  # > 1 MB (límite de pruebas)
    assert _upload(client, analyst_h, "grande.csv", big).status_code == 413


def test_simulated_flag_is_mandatory(client, analyst_h):
    r = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "x"},
                    files={"file": ("a.csv", CSV_OK)})
    assert r.status_code == 422


def test_path_traversal_filename_is_neutralized(client, analyst_h):
    r = _upload(client, analyst_h, "../../../evil.csv", CSV_OK)
    assert r.status_code == 201
    rec = client.get(f"/api/neurodata/records/{r.json()['id']}", headers=analyst_h).json()
    assert rec["extra"]["original_name"] == "evil.csv"


def test_manual_record(client, analyst_h, reader_h):
    body = {"title": "Caudal río Santa", "variable": "caudal", "value": 12.5, "unit": "m3/s",
            "latitude": -9.1, "longitude": -77.7, "source_name": "Aforo manual", "is_simulated": False}
    r = client.post("/api/neurodata/records/manual", json=body, headers=analyst_h)
    assert r.status_code == 201 and r.json()["is_simulated"] is False
    only_lat = {**body, "longitude": None}
    assert client.post("/api/neurodata/records/manual", json=only_lat, headers=analyst_h).status_code == 422
    future = {**body, "observed_at": "2999-01-01T00:00:00Z"}
    assert client.post("/api/neurodata/records/manual", json=future, headers=analyst_h).status_code == 422
    assert client.post("/api/neurodata/records/manual", json=body, headers=reader_h).status_code == 403


def test_download_file(client, analyst_h):
    rec = _upload(client, analyst_h, "descarga.csv", CSV_OK).json()
    r = client.get(f"/api/neurodata/records/{rec['id']}/file", headers=analyst_h)
    assert r.status_code == 200 and r.content == CSV_OK
