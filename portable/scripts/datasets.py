"""DESCARGAR_DATASETS / ENTRENAR_MODELOS: menús que piden confirmación por cada descarga o trabajo.

Descargas (todas por RECORTE, nunca territorios completos; tamaños medidos en Huaraz 0,5°):
  1. Inventario INGEMMET de peligros geológicos  ≈0,2 MB  (licencia no declarada: uso interno)
  2. DEM Copernicus GLO-30 a ≈35 m (1600 px)       ≈10 MB, 4–5 min
  3. Litología + geomorfología INGEMMET           ≈3,4 MB (sin licencia abierta: uso interno)
  4. NDVI Sentinel-2 de época seca                 ≈40 MB, 4–5 min
Entrenamiento/validación: validación espacial de NEURODISASTER con los datos ya descargados.
"""
from __future__ import annotations

import subprocess
import sys

from comun import BACKEND, entorno_backend, python_backend, titulo

HUARAZ = "-77.75,-9.78,-77.25,-9.28"


def si(pregunta: str) -> bool:
    return input(f"{pregunta} [s/N]: ").strip().lower() in ("s", "si", "sí", "y")


def cli(*args: str) -> int:
    return subprocess.run([python_backend(), "-m", "app.cli", *args], cwd=BACKEND, env=entorno_backend()).returncode


NDVI = """
import sys
from app.database.session import SessionLocal
from app.modules.environmental import remote, service
bbox = [float(v) for v in sys.argv[1].split(',')]
sc = []
for y in (2024, 2023):
    sc += remote.search_scenes(bbox, f'{y}-06-01', f'{y}-08-31', 5, limit=10)
sc = [s for s in sc if s.bbox and s.bbox[0] <= bbox[0] + 0.05 and s.bbox[2] >= bbox[2] - 0.05]
if not sc: sys.exit('No hay escenas de época seca con <5 % de nubes que cubran el recorte.')
best = min(sc, key=lambda s: s.cloud_cover)
print('Escena elegida:', best.id, best.datetime[:10], f'nubes {best.cloud_cover:.1f} %')
with SessionLocal() as db:
    r = service.compute_ndvi(db, None, item_id=best.id, bbox=bbox, res=float(sys.argv[2]))
    print('NDVI registrado:', r.id, r.extra.get('download'))
"""


def descargar() -> int:
    titulo("NEUROAMBIENTAL IA · descarga de datasets (por recorte)")
    bbox = input(f"Recorte minLon,minLat,maxLon,maxLat [{HUARAZ}]: ").strip() or HUARAZ
    lado = max(float(bbox.split(",")[2]) - float(bbox.split(",")[0]), float(bbox.split(",")[3]) - float(bbox.split(",")[1]))
    res = round(lado / 1600, 7)
    if si("1) Inventario INGEMMET (≈0,2 MB; uso interno, no redistribuir)"):
        cli("importar-ingemmet", f"--bbox={bbox}")
    if si(f"2) DEM GLO-30 a {res}° (≈{res * 111000:.0f} m; ≈10 MB por 0,5°)"):
        cli("descargar-dem", f"--bbox={bbox}", f"--res={res}")
    if si("3) Litología y geomorfología INGEMMET (≈3–4 MB; uso interno)"):
        cli("importar-geologia", f"--bbox={bbox}")
    if si("4) NDVI Sentinel-2 de época seca (≈40 MB por 0,5°)"):
        subprocess.run([python_backend(), "-c", NDVI, bbox, str(res)], cwd=BACKEND, env=entorno_backend())
    cli("exportar-manifiestos")
    print("\nListo. Los manifiestos de los datasets están en codigo/datasets/manifiestos/.")
    return 0


VALIDAR = """
import json, sys
from sqlalchemy import select
from app.database.session import SessionLocal
from app.models import DataRecord
from app.modules.disasters import service as sd
with SessionLocal() as db:
    q = lambda t: db.scalars(select(DataRecord).where(DataRecord.data_type == t).order_by(DataRecord.received_at.desc())).all()
    inv = next((r for r in q('geojson') if (r.extra or {}).get('inventory')), None)
    dem = next((r for r in q('raster_dem') if (r.extra or {}).get('analysis')), None) or next(iter(q('raster_dem')), None)
    if not inv or not dem: sys.exit('Faltan datos: descargue primero el inventario y el DEM (DESCARGAR_DATASETS.bat).')
    geo = [r.id for r in q('geojson') if (r.extra or {}).get('geology') == 'litologia'][:1] if sys.argv[1] == 's' else []
    ndvi = next((r.id for r in q('raster_ndvi') if r.bbox == dem.bbox), None) if sys.argv[2] == 's' else None
    r = sd.validate(db, None, dem_id=dem.id, inventory_id=inv.id, ratio=3, min_dist_m=300.0, blocks=0, seed=42,
                    n_seeds=10, buffer_m=500.0, geology_ids=geo, ndvi_id=ndvi)
    print('Ejecución', r['run_id'], 'recursos', r.get('recursos'))
    for k, a in [('todos', r)] + list(r['por_proceso'].items()):
        v = a['ausencias_mismo_rango_elevacion']['regresion_logistica']['espacial']
        print(f"{k:10s} AUC espacial {v['auc_mean']} IC95 {v['auc_ic95_bloques']}")
        for c in a['conclusion_automatica']: print('   -', c)
"""


def entrenar() -> int:
    titulo("NEUROAMBIENTAL IA · entrenamiento y validación")
    print("Modelos preparados:\n  1. Validación espacial de susceptibilidad (NEURODISASTER) con los datos descargados")
    print("  2. Regenerar fichas técnicas y manifiestos\n  0. Salir")
    op = input("Opción: ").strip()
    if op == "1":
        geo = "s" if si("¿Incluir litología (si fue descargada)?") else "n"
        ndvi = "s" if si("¿Incluir NDVI como candidata (si fue descargado)?") else "n"
        return subprocess.run([python_backend(), "-c", VALIDAR, geo, ndvi], cwd=BACKEND, env=entorno_backend()).returncode
    if op == "2":
        return cli("exportar-fichas") or cli("exportar-manifiestos")
    return 0


if __name__ == "__main__":
    raise SystemExit(descargar() if (sys.argv[1:] or ["descargar"])[0] == "descargar" else entrenar())
