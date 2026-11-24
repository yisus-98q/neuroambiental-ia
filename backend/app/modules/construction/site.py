"""NEUROCONSTRUCTION: análisis preliminar de sitio sobre un DEM registrado.

Todo se deriva de números del DEM (elevación, pendiente) y de los escenarios simplificados de NEURO 3D LAB.
Las observaciones son reglas fijas sobre esos números; no sustituyen estudios ni autorizaciones.
"""
from __future__ import annotations

import json
import math

import numpy as np
from rasterio import features
from rasterio.transform import from_bounds
from scipy import ndimage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.models import DataRecord, Run, User
from app.models.common import new_id, utcnow
from app.modules.neuro3d import dem as demlib
from app.modules.neuro3d import scenarios, service
from app.modules.neuro3d.dem import DemError
from app.neurodata.service import absolute_path, get_or_create_source

NOTICE = "No reemplaza evaluaciones profesionales ni autorizaciones oficiales."
HEURISTIC_NOTE = ("La clase de susceptibilidad es un índice heurístico (solo pendiente, pesos por defecto) NO calibrado; "
                  "no predice deslizamientos. Evaluado con el inventario real de INGEMMET (181 movimientos en masa, Huaraz): la pendiente sola NO discrimina los eventos (AUC 0,49, igual al azar). No usar como indicador de susceptibilidad.")
MAX_VERTICES = 5000
MAX_BUFFER_M = 5000.0
RUN_TYPE = "analisis_sitio"
SOURCE_NAME = "NEUROCONSTRUCTION: análisis de sitio (derivado)"


# ---------------------------------------------------------------- geometría del emplazamiento
def _polygons(geojson: dict) -> list[list]:
    """Anillos exteriores [[lon, lat], ...] de un Polygon/MultiPolygon (o Feature/FeatureCollection)."""
    t = geojson.get("type")
    if t == "FeatureCollection":
        return [r for f in geojson.get("features", []) for r in _polygons(f)]
    if t == "Feature":
        return _polygons(geojson.get("geometry") or {})
    if t == "Polygon":
        return [geojson["coordinates"]]
    if t == "MultiPolygon":
        return list(geojson["coordinates"])
    raise DemError("El GeoJSON debe ser un Polygon, MultiPolygon o un Feature/FeatureCollection de polígonos.")


def validate_polygons(geojson: dict) -> list[dict]:
    try:
        polys = _polygons(geojson)
        out, n = [], 0
        for rings in polys:
            for ring in rings:
                for pt in ring:
                    n += 1
                    lon, lat = float(pt[0]), float(pt[1])
                    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
                        raise DemError("El GeoJSON tiene coordenadas fuera de rango (use lon, lat en EPSG:4326).")
            out.append({"type": "Polygon", "coordinates": rings})
        if n > MAX_VERTICES:
            raise DemError(f"El polígono tiene demasiados vértices (máx. {MAX_VERTICES}).")
    except DemError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise DemError("El GeoJSON no es válido.") from exc
    if not out:
        raise DemError("El GeoJSON no contiene polígonos.")
    return out


def site_mask(arr: np.ndarray, bbox, *, point: dict | None, geojson: dict | None) -> tuple[np.ndarray, dict]:
    """Máscara booleana de las celdas del emplazamiento y su descripción (centroide, geometría)."""
    h, w = arr.shape
    if point is not None:
        row, col = _cell(arr, bbox, point["lon"], point["lat"])
        m = np.zeros((h, w), bool)
        m[row, col] = True
        return m, {"type": "Point", "lon": point["lon"], "lat": point["lat"]}
    polys = validate_polygons(geojson or {})
    m = features.geometry_mask(polys, out_shape=(h, w), transform=from_bounds(*bbox, w, h), invert=True,
                               all_touched=True)
    if not m.any():
        raise DemError("El emplazamiento no se superpone al DEM.")
    ys, xs = np.nonzero(m)
    dlon, dlat = demlib.cell_size(bbox, arr)
    return m, {"type": "Polygon", "lon": round(bbox[0] + (xs.mean() + 0.5) * dlon, 6),
               "lat": round(bbox[3] - (ys.mean() + 0.5) * dlat, 6), "geometry": polys[0] if len(polys) == 1 else None}


def _cell(arr: np.ndarray, bbox, lon: float, lat: float) -> tuple[int, int]:
    dlon, dlat = demlib.cell_size(bbox, arr)
    col, row = int(math.floor((lon - bbox[0]) / dlon)), int(math.floor((bbox[3] - lat) / dlat))
    if not (0 <= col < arr.shape[1] and 0 <= row < arr.shape[0]):
        raise DemError("El punto está fuera del DEM cargado.")
    return row, col


def environment_mask(site: np.ndarray, bbox, arr: np.ndarray, buffer_m: float) -> np.ndarray:
    """Celdas a <= buffer_m del emplazamiento (incluye el emplazamiento). Distancia euclídea en metros."""
    if buffer_m <= 0:
        return site.copy()
    dx, dy = demlib._spacing(bbox, arr)  # noqa: SLF001
    dist = ndimage.distance_transform_edt(~site, sampling=(dy, float(dx.mean())))
    return dist <= buffer_m


# ---------------------------------------------------------------- métricas
def _slope_block(slope: np.ndarray, mask: np.ndarray) -> dict:
    v = slope[mask & np.isfinite(slope)]
    if v.size == 0:
        return {"cells": 0, "mean_deg": None, "max_deg": None, "classes": []}
    full = np.full(slope.shape, np.nan, dtype="float32")
    full[mask] = slope[mask]
    st = demlib.slope_stats(full)
    return {"cells": int(v.size), "mean_deg": st["mean_deg"], "max_deg": st["max_deg"], "classes": st["classes"]}


def analyze(arr: np.ndarray, bbox, *, point: dict | None, geojson: dict | None, buffer_m: float,
            flood: dict | None, res_deg: float | None) -> dict:
    if not 0 <= buffer_m <= MAX_BUFFER_M:
        raise DemError(f"El entorno debe estar entre 0 y {MAX_BUFFER_M:.0f} m.")
    if (point is None) == (geojson is None):
        raise DemError("Indique un punto o un polígono GeoJSON (solo uno).")
    site, desc = site_mask(arr, bbox, point=point, geojson=geojson)
    if not np.isfinite(arr[site]).any():
        raise DemError("El emplazamiento cae en celdas sin dato de elevación.")
    env = environment_mask(site, bbox, arr, buffer_m)
    slope = demlib.slope_deg(arr, bbox)
    z = arr[site & np.isfinite(arr)]
    _, cls = scenarios.susceptibility_classes(slope, None, 1.0, 0.0, 0.33, 0.66)
    cs = cls[site]
    cs = cs[cs > 0]
    susc = {"classes": [{"class": k, "label": scenarios.CLASS_LABELS[k],
                         "pct": round(100 * float((cs == k).mean()), 1) if cs.size else 0.0} for k in (1, 2, 3)],
            "dominant": scenarios.CLASS_LABELS[int(np.bincount(cs).argmax())] if cs.size else "sin dato",
            "heuristic": True, "note": HEURISTIC_NOTE}
    out = {"site": desc, "site_cells": int(site.sum()), "buffer_m": buffer_m,
           "cell_size_m": round(demlib.cell_size(bbox, arr)[1] * demlib.M_PER_DEG_LAT) if res_deg is None else
           round(res_deg * demlib.M_PER_DEG_LAT),
           "elevation": {"min": round(float(z.min()), 1), "mean": round(float(z.mean()), 1), "max": round(float(z.max()), 1)},
           "slope_site": _slope_block(slope, site), "slope_environment": _slope_block(slope, env),
           "susceptibility": susc, "flood": None}
    if flood:
        depth, m = scenarios.bathtub(arr, bbox, flood["lon"], flood["lat"], flood["rise_m"])
        wet = site & np.isfinite(depth) & (depth > 0)
        out["flood"] = {"rise_m": flood["rise_m"], "origin": {"lon": flood["lon"], "lat": flood["lat"]},
                        "site_flooded_pct": round(100 * float(wet.sum()) / max(1, int(site.sum())), 1),
                        "site_max_depth_m": round(float(depth[wet].max()), 2) if wet.any() else 0.0,
                        "flooded_km2": m["flooded_km2"], "touches_dem_border": m["touches_dem_border"],
                        "disclaimer": scenarios.FLOOD_DISCLAIMER}
    out["observations"] = observations(out)
    out["notice"] = NOTICE
    return out


def observations(r: dict) -> list[str]:
    """Reglas fijas sobre los números calculados; nada de lo que no se midió."""
    obs, s, e = [], r["slope_site"], r["slope_environment"]
    if s["mean_deg"] is not None:
        if s["mean_deg"] > 25:
            obs.append(f"Pendiente media del emplazamiento {s['mean_deg']}° (> 25°): requiere estudio geotécnico.")
        elif s["mean_deg"] > 15:
            obs.append(f"Pendiente media del emplazamiento {s['mean_deg']}° (15-25°): considerar movimiento de tierras, "
                       "estabilidad de taludes y drenaje.")
        else:
            obs.append(f"Pendiente media del emplazamiento {s['mean_deg']}° (≤ 15°) según el DEM.")
    steep = next((c["pct"] for c in e["classes"] if c["label"] == ">35°"), 0)
    if steep >= 10:
        obs.append(f"El {steep} % del entorno ({r['buffer_m']:.0f} m) tiene pendiente > 35°: revisar laderas aledañas.")
    if r["susceptibility"]["dominant"] == "alto":
        obs.append("El índice heurístico de pendiente es «alto» en la mayor parte del emplazamiento (no calibrado).")
    if r["elevation"]["mean"] > 3500:
        obs.append(f"Elevación media {r['elevation']['mean']} m (> 3500 m): considerar condiciones de alta montaña.")
    if r["site_cells"] < 4:
        obs.append(f"El emplazamiento ocupa {r['site_cells']} celda(s) del DEM (≈{r['cell_size_m']} m): "
                   "los valores son poco representativos del terreno real.")
    f = r["flood"]
    if f:
        if f["site_flooded_pct"] > 0:
            obs.append(f"El {f['site_flooded_pct']} % del emplazamiento queda bajo el agua en el escenario hipotético de "
                       f"+{f['rise_m']} m (profundidad máx. {f['site_max_depth_m']} m); modelo de bañera, no es un estudio hidráulico.")
        else:
            obs.append(f"El emplazamiento no queda cubierto en el escenario hipotético de +{f['rise_m']} m "
                       "(modelo de bañera; no descarta inundación real).")
    obs.append("Sin capa de ríos ni de zonificación: no se evaluó proximidad a cauces ni compatibilidad territorial.")
    return obs


# ---------------------------------------------------------------- registro
def run_site_analysis(db: Session, user: User, *, dem_id: str, point: dict | None, geojson: dict | None,
                      buffer_m: float, flood: dict | None, name: str = "") -> DataRecord:
    with service._exclusive():  # noqa: SLF001
        for stale in db.scalars(select(Run).where(Run.module_key == "construction", Run.status == "en_proceso")):
            stale.status, stale.finished_at = "error", utcnow()
        params = {"dem_id": dem_id, "point": point, "geojson": bool(geojson), "buffer_m": buffer_m, "flood": flood}
        run = Run(run_type=RUN_TYPE, module_key="construction", status="en_proceso", parameters=params)
        db.add(run)
        db.commit()
        try:
            dem_rec = service._dem_record(db, dem_id)  # noqa: SLF001
            arr, bbox = demlib.read_dem(absolute_path(dem_rec))
            res = analyze(arr, bbox, point=point, geojson=geojson, buffer_m=buffer_m, flood=flood,
                          res_deg=dem_rec.extra.get("grid", {}).get("res"))
            source = get_or_create_source(db, SOURCE_NAME, "simulacion", "Derivado de datos abiertos con atribución", "")
            lon, lat = res["site"]["lon"], res["site"]["lat"]
            rec = DataRecord(
                id=new_id(), source_id=source.id, data_type="analisis_sitio",
                title=f"Análisis de sitio{(' · ' + name) if name else ''} ({lat:.4f}, {lon:.4f})",
                latitude=lat, longitude=lon, bbox=list(dem_rec.bbox), file_format="application/json",
                validation_status="valido", quality="sin_evaluar", unit="",
                provenance=(f"Análisis preliminar sobre el DEM {dem_rec.id}: elevación y pendiente del emplazamiento y de un "
                            f"entorno de {buffer_m:.0f} m; susceptibilidad heurística"
                            f"{' y escenario de inundación demostrativo' if flood else ''}. {NOTICE}"),
                is_simulated=bool(dem_rec.is_simulated),
                extra={"kind": "analisis_sitio", "dem_id": dem_rec.id, "name": name, "params": params,
                       "result": res, "notice": NOTICE, "validated": False},
                created_by=user.id)
            db.add(rec)
            db.flush()
            audit(db, "analisis_sitio", user_id=user.id, target_type="data_record", target_id=rec.id,
                  details={"dem": dem_rec.id, "buffer_m": buffer_m, "inundacion": bool(flood)}, commit=False)
            run.status, run.finished_at = "ok", utcnow()
            run.result_summary = {"record_id": rec.id, "slope_site_mean_deg": res["slope_site"]["mean_deg"],
                                  "susceptibility": res["susceptibility"]["dominant"]}
            db.commit()
            return rec
        except Exception as exc:
            db.rollback()
            run.status, run.finished_at, run.result_summary = "error", utcnow(), {"error": str(exc)[:500]}
            db.commit()
            raise


def list_analyses(db: Session) -> list[DataRecord]:
    q = select(DataRecord).where(DataRecord.data_type == "analisis_sitio").order_by(
        DataRecord.received_at.desc()).limit(50)
    return list(db.scalars(q))


def geojson_size_ok(geojson: dict) -> bool:
    return len(json.dumps(geojson)) <= 200_000
