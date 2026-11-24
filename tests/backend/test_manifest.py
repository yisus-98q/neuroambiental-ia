"""Fase 1 (2.0): manifiestos de datasets con calidad, linaje y transformaciones."""
from __future__ import annotations

from app.neurodata.manifest import csv_quality, geojson_quality


def test_csv_quality_reports_missing_duplicates_and_outliers():
    rows = ["a,b,c"] + [f"{i},{i % 5},x" for i in range(40)] + ["1,1,x", "1,1,x", "5,,x", "100000,2,x"]
    q = csv_quality(("\n".join(rows) + "\n").encode())
    assert q["filas"] == 44 and q["filas_duplicadas"] >= 1
    assert q["faltantes_por_columna"] == {"b": 1}
    assert q["atipicos_por_columna_iqr3"].get("a") == 1 and "c" not in q["columnas_numericas"]


def test_geojson_quality_counts_nulls_and_duplicate_geometries():
    pt = {"type": "Point", "coordinates": [-77.5, -9.5]}
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": pt, "properties": {"TIPO": "A", "NOTA": None}},
        {"type": "Feature", "geometry": pt, "properties": {"TIPO": "B", "NOTA": "x"}}]}
    import json
    q = geojson_quality(json.dumps(fc).encode())
    assert q["elementos"] == 2 and q["geometrias_duplicadas"] == 1 and q["nulos_por_propiedad"] == {"NOTA": 1}


def test_manifest_endpoint_and_catalog(client, analyst_h, reader_h):
    raw = b"x,y,clase\n" + b"".join(f"{i},{i * 2},a\n".encode() for i in range(10))
    r = client.post("/api/neurodata/upload", headers=analyst_h, data={"source_name": "Prueba manifiesto",
                                                                        "is_simulated": "true"},
                    files={"file": ("m.csv", raw)})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    m = client.get(f"/api/neurodata/records/{rid}/manifest", headers=reader_h).json()
    assert m["sha256"] and m["simulado"] is True and m["fuente"]["nombre"] == "Prueba manifiesto"
    assert m["calidad"]["filas"] == 10 and m["fechas"]["dato"] == "desconocida"
    assert "ruta" not in str(m).lower() or "uploads" not in str(m)          # no expone rutas locales
    cat = client.get("/api/neurodata/catalog", headers=reader_h).json()
    assert any(x["id"] == rid and "calidad" not in x for x in cat)


def test_source_licenses_fit_the_column():
    from app.modules.disasters import geology, inventory
    for lic in (geology.LICENSE, inventory.SOURCE_LICENSE):
        assert len(lic) <= 128
