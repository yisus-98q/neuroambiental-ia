"""Evaluación externa prerregistrada (misión 2.1) en una máquina limpia (GitHub Actions o cualquier equipo).

Uso:  python scripts/ci_validacion_externa.py --zona N --salida salida/
- Descarga desde las FUENTES OFICIALES (INGEMMET, Copernicus) los recortes de Huaraz (entrenamiento) y de la zona
  externa, en una base de datos temporal. Nada se redistribuye: los datos crudos no salen de la máquina.
- Ejecuta exactamente el protocolo congelado (docs/MISION_2_1_PROTOCOLO_VALIDACION_EXTERNA.md y su anexo).
- Compara el SHA-256 de cada dataset con los manifiestos versionados (datasets/manifiestos/): si una fuente cambió
  (p. ej. INGEMMET actualizó su inventario), se informa, porque los resultados ya no serían comparables.
- Escribe en --salida SOLO métricas y metadatos: resultados JSON, comparación de huellas y un resumen Markdown.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HUARAZ = [-77.75, -9.78, -77.25, -9.28]
ZONAS = {
    "N": ("N · Carhuaz–Yungay (−78,00/−9,235/−77,50/−8,735)", [-78.00, -9.235, -77.50, -8.735]),
    "E": ("E · Callejón de Conchucos (−77,205/−9,60/−76,705/−9,10)", [-77.205, -9.60, -76.705, -9.10]),
}
RES = 0.0003125


def manifiesto_local(tipo: str, bbox: list[float], titulo_prefijo: str) -> dict | None:
    """Manifiesto versionado del mismo dataset: mismo tipo, mismo recorte (en la cobertura o en la procedencia,
    porque los polígonos pueden salirse del recorte) y, en los DEM, la misma malla de análisis (1600x1600)."""
    for p in sorted((REPO / "datasets" / "manifiestos").glob(f"{tipo}_*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        if not m.get("titulo", "").startswith(titulo_prefijo):
            continue
        b = m.get("cobertura_bbox") or []
        same = (b and all(abs(x - y) < 1e-6 for x, y in zip(b, bbox))) or str(bbox) in (m.get("procedencia") or "")
        if tipo == "raster_dem":
            same = same and (m.get("resolucion") or {}).get("malla") == "1600x1600"
        if same:
            return m
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zona", choices=sorted(ZONAS), required=True)
    ap.add_argument("--salida", default="salida")
    a = ap.parse_args()
    out = Path(a.salida).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="neuro_ci_"))
    os.environ["NEURO_DATABASE_URL"] = f"sqlite:///{(tmp / 'ci.db').as_posix()}"
    os.environ["NEURO_UPLOADS_DIR"] = str(tmp / "uploads")
    sys.path.insert(0, str(REPO / "backend"))

    from app.cli import migrate
    from app.database.session import SessionLocal
    from app.modules.disasters import service as dis
    from app.modules.neuro3d import service as n3d

    migrate(os.environ["NEURO_DATABASE_URL"])
    nombre, zb = ZONAS[a.zona]
    huellas = []
    with SessionLocal() as db:
        recs = {}
        for clave, bbox in (("a", HUARAZ), ("b", zb)):
            print(f"Descargando {('Huaraz' if clave == 'a' else nombre)}…", flush=True)
            recs[f"inv_{clave}"] = dis.import_inventory(db, None, bbox)
            recs[f"lito_{clave}"] = dis.import_geology(db, None, "litologia", bbox)
            recs[f"dem_{clave}"] = n3d.fetch_dem(db, None, bbox=bbox, res=RES, analysis=True)
        for k, r in recs.items():
            bbox = HUARAZ if k.endswith("_a") else zb
            pref = {"inv": "Inventario", "lito": "Litologia", "dem": "DEM"}[k.split("_")[0]]
            loc = manifiesto_local(r.data_type, bbox, pref)
            huellas.append({"dataset": k, "titulo": r.title, "sha256_ci": r.sha256,
                            "sha256_manifiesto_local": loc.get("sha256") if loc else None,
                            "coincide": bool(loc and loc.get("sha256") == r.sha256),
                            "descarga": (r.extra or {}).get("download")})
        res = dis.external_validation(db, None, dem_a=recs["dem_a"].id, inv_a=recs["inv_a"].id,
                                      lito_a=recs["lito_a"].id, dem_b=recs["dem_b"].id, inv_b=recs["inv_b"].id,
                                      lito_b=recs["lito_b"].id, zona_b=nombre)
    (out / f"mision_2_1_validacion_externa_{a.zona}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "huellas_sha256.json").write_text(json.dumps(huellas, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# Evaluación externa · {nombre}", "",
             "Entrenamiento solo en Huaraz; protocolo prerregistrado (commits 610f756 y cd21595).", "",
             "## Huellas de los datos frente a los manifiestos versionados", "",
             "| Dataset | Coincide | SHA-256 (CI) |", "|---|---|---|"]
    lines += [f"| {h['dataset']} | {'sí' if h['coincide'] else ('no (fuente cambiada)' if h['sha256_manifiesto_local'] else 'sin manifiesto previo')} "
              f"| `{h['sha256_ci'][:16]}…` |" for h in huellas]
    for g, v in res["grupos"].items():
        lines += ["", f"## {g}: {v['n_eventos_externos']} eventos externos", "",
                  "| Modelo | Estado | AUC externo (franja) | IC 95 % |", "|---|---|---|---|"]
        for name, st in v["estados"].items():
            f = (v.get("franja") or {}).get(name) or {}
            lines.append(f"| {name} | {st['estado']} | {f.get('auc_sorteos', {}).get('media')} | "
                         f"{f.get('auc_ic95_bloques')} |")
    lines += ["", f"Recursos: {res.get('recursos')}"]
    md = "\n".join(lines) + "\n"
    (out / "resumen.md").write_text(md, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
