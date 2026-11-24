"""Manifiesto de cada dataset (Fase 1 de NEUROAMBIENTAL IA 2.0).

Reúne en un documento verificable: identidad y huella (SHA-256), procedencia, licencia, fechas (adquisición y
dato), sistema de coordenadas, cobertura, resolución, variables, etiquetas, calidad (faltantes, duplicados,
atípicos), linaje (registros de los que deriva) y transformaciones (ejecuciones que lo produjeron o usaron).
Nada se rellena con suposiciones: lo desconocido se marca «desconocido».
Los manifiestos se pueden exportar a JSON (solo metadatos, sin los datos) para versionarlos en Git.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataRecord, Run
from app.neurodata.service import absolute_path
from app.neurodata.validators import read_csv_rows

ID_RE = re.compile(r"\b[0-9a-f]{32}\b")
M_PER_DEG = 111_320.0
MAX_ROWS_QUALITY = 50_000


def _num(v) -> float | None:
    try:
        f = float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def csv_quality(raw: bytes) -> dict:
    headers, rows = read_csv_rows(raw)
    rows = rows[:MAX_ROWS_QUALITY]
    n = len(rows)
    missing = {h: sum(1 for r in rows if (r.get(h) is None or str(r.get(h)).strip() == "")) for h in headers}
    dup = n - len({tuple((r.get(h) or "").strip() for h in headers) for r in rows})
    numeric, outliers = {}, {}
    for h in headers:
        vals = [x for x in (_num(r.get(h)) for r in rows) if x is not None]
        if len(vals) >= max(5, int(0.8 * (n - missing[h]))) and vals:
            vals.sort()
            q1, q3 = vals[len(vals) // 4], vals[(3 * len(vals)) // 4]
            iqr = q3 - q1
            lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
            numeric[h] = {"min": vals[0], "max": vals[-1], "mediana": vals[len(vals) // 2]}
            outliers[h] = sum(1 for v in vals if v < lo or v > hi) if iqr > 0 else 0
    return {"filas": n, "columnas": headers, "faltantes_por_columna": {k: v for k, v in missing.items() if v},
            "filas_duplicadas": dup, "columnas_numericas": numeric,
            "atipicos_por_columna_iqr3": {k: v for k, v in outliers.items() if v},
            "metodo_atipicos": "fuera de [Q1 − 3·IQR, Q3 + 3·IQR]; señal para revisar, no para borrar"}


def geojson_quality(raw: bytes) -> dict:
    fc = json.loads(raw.decode("utf-8-sig"))
    feats = fc.get("features", [])
    geoms = Counter(json.dumps(f.get("geometry"), sort_keys=True) for f in feats)
    props = Counter()
    nulls = Counter()
    for f in feats:
        for k, v in (f.get("properties") or {}).items():
            props[k] += 1
            if v in (None, "", " "):
                nulls[k] += 1
    return {"elementos": len(feats), "tipos_geometria": dict(Counter((f.get("geometry") or {}).get("type") for f in feats)),
            "propiedades": sorted(props), "nulos_por_propiedad": dict(nulls),
            "geometrias_duplicadas": sum(c - 1 for c in geoms.values() if c > 1)}


def _resolution(rec: DataRecord) -> dict:
    g = (rec.extra or {}).get("grid") or {}
    if not g:
        return {"espacial": "desconocida (vectorial o tabular)" if rec.data_type in ("geojson", "csv") else "desconocida"}
    lat = ((rec.bbox[1] + rec.bbox[3]) / 2) if rec.bbox else 0.0
    res = g.get("res")
    return {"espacial_grados": res, "espacial_m_aprox": round(res * M_PER_DEG * math.cos(math.radians(lat)), 1)
            if res else None, "malla": f"{g.get('width')}x{g.get('height')}"}


def build(db: Session, rec: DataRecord, with_quality: bool = True) -> dict:
    ex = rec.extra or {}
    src = rec.source
    linked = sorted(set(ID_RE.findall(rec.provenance or "")) - {rec.id})
    lineage = [{"id": r.id, "titulo": r.title, "tipo": r.data_type}
               for r in db.scalars(select(DataRecord).where(DataRecord.id.in_(linked)))] if linked else []
    runs = db.scalars(select(Run).order_by(Run.started_at).limit(5000)).all()
    transforms = []
    for r in runs:
        blob = json.dumps(r.parameters or {}) + json.dumps(r.result_summary or {}, default=str)
        if rec.id in blob:
            role = "produjo" if any((r.result_summary or {}).get(k) == rec.id
                                    for k in ("record_id", "dataset_record_id")) else "usó"
            transforms.append({"ejecucion": r.id, "tipo": r.run_type, "estado": r.status, "rol": role,
                               "fecha": r.started_at.isoformat() if r.started_at else None})
    m = {
        "manifiesto_version": 1,
        "id": rec.id, "titulo": rec.title, "tipo": rec.data_type, "formato": rec.file_format or "desconocido",
        "sha256": rec.sha256, "tamano_bytes": rec.file_size,
        "simulado": rec.is_simulated, "estado_validacion": rec.validation_status, "calidad_declarada": rec.quality,
        "fuente": {"nombre": src.name if src else "desconocida", "tipo": src.kind if src else None,
                   "url": (src.url or None) if src else None, "licencia": src.license if src else "desconocida",
                   "terminos_revisados": bool(src.terms_reviewed) if src else False},
        "procedencia": rec.provenance or "desconocida",
        "fechas": {"adquisicion": rec.received_at.isoformat() if rec.received_at else None,
                   "dato": rec.observed_at.isoformat() if rec.observed_at else "desconocida"},
        "sistema_coordenadas": "EPSG:4326 (WGS84 lon/lat)" if (rec.bbox or rec.data_type == "geojson") else "no aplica",
        "cobertura_bbox": rec.bbox, "resolucion": _resolution(rec),
        "variables": ex.get("columns") or ex.get("properties") or ([rec.unit] if rec.unit else []),
        "etiquetas": ex.get("tipos_peligro") or ex.get("classes") or None,
        "linaje": lineage, "transformaciones": transforms,
        "estadisticas_registradas": ex.get("stats") or ex.get("elevation") or None,
        # Mismo contenido exacto (SHA-256) registrado más de una vez: candidato a no conservar por duplicado.
        "duplicado_exacto_de": [r for r in db.scalars(select(DataRecord.id).where(
            DataRecord.sha256 == rec.sha256, DataRecord.id != rec.id))] if rec.sha256 else [],
    }
    if with_quality and rec.file_path:
        path: Path = absolute_path(rec)
        try:
            if rec.data_type == "csv" and path.is_file():
                m["calidad"] = csv_quality(path.read_bytes())
            elif rec.data_type == "geojson" and path.is_file():
                m["calidad"] = geojson_quality(path.read_bytes())
            elif rec.data_type.startswith("raster"):
                st = ex.get("stats") or ex.get("elevation") or {}
                m["calidad"] = {"validos_pct": st.get("valid_pct"), "nota": "estadísticas calculadas al registrar"}
        except (OSError, ValueError) as exc:
            m["calidad"] = {"error": f"No se pudo evaluar: {exc}"[:200]}
    return m


def export_all(db: Session, out_dir: Path) -> list[Path]:
    """Escribe un JSON por dataset (solo metadatos). No incluye rutas locales ni datos."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for rec in db.scalars(select(DataRecord).order_by(DataRecord.received_at)):
        m = build(db, rec)
        p = out_dir / f"{rec.data_type}_{rec.id}.json"
        p.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        paths.append(p)
    return paths
