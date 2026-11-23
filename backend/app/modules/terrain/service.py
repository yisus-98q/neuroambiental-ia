"""NEUROTERRAIN: sensores, importación de mediciones desde CSV de NEURODATA y análisis de series."""
from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.models import Alert, DataRecord, Measurement, Sensor, User
from app.models.common import new_id
from app.neurodata.service import absolute_path
from app.neurodata.validators import read_csv_rows
from app.modules.terrain import series

MAX_ROWS = 50_000
MAX_ERRORS_SHOWN = 20
LEVEL_BY_STATE = {"estable": "bajo", "en_movimiento": "medio", "acelerando": "alto", "indeterminado": "bajo"}


class TerrainError(Exception):
    """Error de validación o de estado (el API lo traduce a 4xx)."""

    def __init__(self, messages: list[str] | str, status_code: int = 422):
        self.messages = [messages] if isinstance(messages, str) else messages
        self.status_code = status_code
        super().__init__("; ".join(self.messages))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def sensor_dict(db: Session, s: Sensor) -> dict:
    rows = db.execute(select(Measurement.variable, func.count(), func.min(Measurement.observed_at),
                             func.max(Measurement.observed_at)).where(Measurement.sensor_id == s.id)
                      .group_by(Measurement.variable)).all()
    return {"id": s.id, "name": s.name, "kind": s.kind, "latitude": s.latitude, "longitude": s.longitude,
            "territory_id": s.territory_id, "is_active": s.is_active, "created_at": s.created_at,
            "variables": [{"variable": v, "n": n, "first": _utc(a).isoformat() if a else None,
                           "last": _utc(b).isoformat() if b else None} for v, n, a, b in rows]}


def get_sensor(db: Session, sensor_id: str) -> Sensor:
    s = db.get(Sensor, sensor_id)
    if s is None:
        raise TerrainError("Sensor no encontrado.", 404)
    return s


def _parse_dt(text: str) -> datetime:
    return _utc(datetime.fromisoformat(text.strip()))  # ISO 8601; sin zona = UTC


def parse_rows(raw: bytes, spec: dict) -> tuple[list[tuple], list[str]]:
    """Lee el CSV y devuelve ([(fecha, variable, valor, unidad)], errores). No toca la BD."""
    headers, rows = read_csv_rows(raw)
    if len(rows) > MAX_ROWS:
        raise TerrainError(f"El CSV tiene {len(rows)} filas; el máximo es {MAX_ROWS}.")
    if not rows:
        raise TerrainError("El CSV no tiene filas de datos.")
    wide = spec["format"] == "ancho"
    need = [spec["date_column"]] + ([] if wide else [spec["variable_column"], spec["value_column"]]) \
        + list(spec.get("value_columns") or [])
    if spec.get("unit_column") and not wide:
        need.append(spec["unit_column"])
    missing = [c for c in need if c not in headers]
    if missing:
        raise TerrainError(f"Columnas no encontradas en el CSV: {', '.join(missing)}. Disponibles: {', '.join(headers)}.")
    units = spec.get("units") or {}
    default_unit = spec.get("default_unit", "")
    out: list[tuple] = []
    errors: list[str] = []

    def num(text: str | None, line: int, col: str) -> float | None:
        try:
            v = float((text or "").strip())
        except ValueError:
            errors.append(f"Fila {line}: valor no numérico en '{col}': {text!r}.")
            return None
        if not math.isfinite(v):
            errors.append(f"Fila {line}: valor no finito en '{col}'.")
            return None
        return v

    for i, row in enumerate(rows, start=2):  # fila 1 = encabezado
        try:
            when = _parse_dt(row.get(spec["date_column"]) or "")
        except ValueError:
            errors.append(f"Fila {i}: fecha no interpretable en '{spec['date_column']}': {row.get(spec['date_column'])!r}.")
            continue
        if wide:
            for col in spec["value_columns"]:
                if (row.get(col) or "").strip() == "":
                    continue  # celda vacía en formato ancho = sin medición
                v = num(row.get(col), i, col)
                if v is not None:
                    out.append((when, col, v, units.get(col, default_unit)))
        else:
            var = (row.get(spec["variable_column"]) or "").strip()
            if not var or len(var) > 64:
                errors.append(f"Fila {i}: variable vacía o de más de 64 caracteres.")
                continue
            v = num(row.get(spec["value_column"]), i, spec["value_column"])
            if v is not None:
                unit = (row.get(spec["unit_column"]) or "").strip() if spec.get("unit_column") else default_unit
                out.append((when, var, v, unit[:32] or default_unit))
    return out, errors


def check_order(items: list[tuple], normalize: bool) -> tuple[list[tuple], list[str]]:
    """Orden temporal y duplicados por variable. Con normalize=True ordena y quita duplicados idénticos."""
    errors: list[str] = []
    by_var: dict[str, list[tuple]] = {}
    for it in items:
        by_var.setdefault(it[1], []).append(it)
    result: list[tuple] = []
    for var, lst in by_var.items():
        if not normalize:
            for a, b in zip(lst, lst[1:]):
                if b[0] < a[0]:
                    errors.append(f"'{var}': fechas fuera de orden ({b[0].isoformat()} después de {a[0].isoformat()}).")
                    break
        lst = sorted(lst, key=lambda x: x[0])
        seen: dict[datetime, float] = {}
        clean = []
        for it in lst:
            if it[0] in seen:
                if seen[it[0]] != it[2]:
                    errors.append(f"'{var}': fecha duplicada {it[0].isoformat()} con valores distintos.")
                elif not normalize:
                    errors.append(f"'{var}': fecha duplicada {it[0].isoformat()}.")
                continue
            seen[it[0]] = it[2]
            clean.append(it)
        result.extend(clean)
    return result, errors


def import_measurements(db: Session, user: User, sensor: Sensor, spec: dict) -> dict:
    rec = db.get(DataRecord, spec["data_record_id"])
    if rec is None:
        raise TerrainError("Registro de NEURODATA no encontrado.", 404)
    if rec.data_type != "csv" or rec.validation_status != "valido" or not rec.file_path:
        raise TerrainError("El registro debe ser un CSV válido de NEURODATA.")
    if db.scalar(select(func.count()).select_from(Measurement).where(
            Measurement.sensor_id == sensor.id, Measurement.data_record_id == rec.id)):
        raise TerrainError("Este CSV ya fue importado a este sensor (evita duplicar mediciones).", 409)
    try:
        raw = absolute_path(rec).read_bytes()
    except (OSError, ValueError) as exc:
        raise TerrainError("No se pudo leer el archivo del registro.", 404) from exc
    items, errors = parse_rows(raw, spec)
    ordered, order_errors = check_order(items, bool(spec.get("normalize")))
    errors += order_errors
    if errors:
        shown = errors[:MAX_ERRORS_SHOWN] + ([f"... y {len(errors) - MAX_ERRORS_SHOWN} error(es) más."]
                                              if len(errors) > MAX_ERRORS_SHOWN else [])
        audit(db, "terrain_importacion_rechazada", user_id=user.id, target_type="sensor", target_id=sensor.id,
              success=False, details={"record": rec.id, "errores": len(errors)})
        raise TerrainError(shown)
    if not ordered:
        raise TerrainError("El CSV no produjo ninguna medición.")
    db.execute(insert(Measurement), [
        {"id": new_id(), "sensor_id": sensor.id, "data_record_id": rec.id, "variable": var, "value": val,
         "unit": unit, "observed_at": when, "is_simulated": rec.is_simulated}
        for when, var, val, unit in ordered])
    audit(db, "terrain_importar_mediciones", user_id=user.id, target_type="sensor", target_id=sensor.id,
          details={"record": rec.id, "n": len(ordered), "simulado": rec.is_simulated}, commit=False)
    db.commit()
    vars_ = Counter(o[1] for o in ordered)
    return {"sensor_id": sensor.id, "data_record_id": rec.id, "importadas": len(ordered), "variables": dict(vars_),
            "is_simulated": rec.is_simulated, "descartadas_duplicadas": len(items) - len(ordered)}


def _load(db: Session, sensor: Sensor, variable: str | None) -> tuple[str, list[tuple]]:
    names = [v for (v,) in db.execute(select(Measurement.variable).where(Measurement.sensor_id == sensor.id)
                                      .distinct().order_by(Measurement.variable))]
    if not names:
        raise TerrainError("El sensor no tiene mediciones. Importe un CSV primero.", 404)
    if variable is None:
        if len(names) > 1:
            raise TerrainError(f"El sensor tiene varias variables ({', '.join(names)}); indique ?variable=.")
        variable = names[0]
    elif variable not in names:
        raise TerrainError(f"Variable '{variable}' sin mediciones en este sensor. Disponibles: {', '.join(names)}.", 404)
    rows = db.execute(select(Measurement.observed_at, Measurement.value, Measurement.unit, Measurement.is_simulated)
                      .where(Measurement.sensor_id == sensor.id, Measurement.variable == variable)
                      .order_by(Measurement.observed_at)).all()
    return variable, rows


def analyze_sensor(db: Session, sensor: Sensor, variable: str | None, cfg: series.Config) -> dict:
    try:
        cfg.validate()
    except series.SeriesError as exc:
        raise TerrainError(str(exc)) from exc
    variable, rows = _load(db, sensor, variable)
    # Mediciones de importaciones distintas pueden coincidir en fecha: se conserva la primera por fecha.
    uniq: dict[float, tuple] = {}
    for r in rows:
        uniq.setdefault(_utc(r[0]).timestamp(), r)
    keys = sorted(uniq)
    units = Counter(uniq[k][2] for k in keys)
    unit = units.most_common(1)[0][0]
    try:
        res = series.analyze(keys, [uniq[k][1] for k in keys], cfg, unit)
    except series.SeriesError as exc:
        raise TerrainError(str(exc)) from exc
    if len(units) > 1:
        res["notas"].append(f"Atención: la serie mezcla unidades ({', '.join(f'{u or chr(45)}' for u in units)}); no se convierten.")
    simulated = any(uniq[k][3] for k in keys)
    for p in res["puntos"]:
        p["t"] = datetime.fromtimestamp(p["t"], UTC).isoformat()
    for a in res["anomalias"]:
        a["observed_at"] = datetime.fromtimestamp(a.pop("observed_at_epoch"), UTC).isoformat()
    res.update({"sensor_id": sensor.id, "sensor_name": sensor.name, "variable": variable, "unit": unit,
                "is_simulated": simulated, "first": res["puntos"][0]["t"], "last": res["puntos"][-1]["t"]})
    if simulated:
        res["notas"].append("La serie contiene mediciones SIMULADAS (heredadas del registro de origen).")
    return res


def create_alert(db: Session, user: User, sensor: Sensor, variable: str | None, cfg: series.Config,
                 level: str | None, notes: str) -> Alert:
    """Alerta EXPERIMENTAL pedida explícitamente por un analista. Nunca se crea sola."""
    res = analyze_sensor(db, sensor, variable, cfg)
    cls = res["clasificacion"]
    vr = res["velocidad_reciente"] or res["velocidad_total"]
    alert = Alert(
        title=f"[NEUROTERRAIN] {sensor.name}: {cls['estado'].replace('_', ' ')} ({res['variable']})"[:256],
        description=(notes.strip() + "\n\n" if notes.strip() else "") + series.AVISO,
        module_key="terrain", level=level or LEVEL_BY_STATE[cls["estado"]], alert_kind="experimental",
        latitude=sensor.latitude, longitude=sensor.longitude,
        evidence=("Métricas calculadas por NEUROTERRAIN: "
                  f"desplazamiento acumulado {res['desplazamiento_acumulado']:.4g} {res['unit']}; "
                  f"velocidad reciente {vr['velocidad']:.4g} {vr['unidad']} (ventana {res['ventana_dias']:.1f} d); "
                  f"aceleración {'n/d' if res['aceleracion'] is None else format(res['aceleracion']['valor'], '.3g')}; "
                  f"{len(res['anomalias'])} anomalía(s); n={res['n_mediciones']}; clasificación experimental: {cls['estado']}. "
                  f"Umbrales de EJEMPLO: {res['umbrales']['vel_threshold']:g} {res['unit']}/día, cociente {res['umbrales']['acc_ratio']:g}."),
        source_name=f"NEUROTERRAIN · sensor {sensor.name}"[:128],
        observed_at=_utc(datetime.fromisoformat(res["last"])),
        uncertainty=("Indicador por umbrales de ejemplo sobre una serie corta/ruidosa, sin validación geotécnica "
                     "ni calibración del sensor. " + series.AVISO),
        validation_status="no_validada", is_simulated=res["is_simulated"], created_by=user.id)
    db.add(alert)
    db.flush()
    audit(db, "terrain_crear_alerta", user_id=user.id, target_type="alert", target_id=alert.id,
          details={"sensor": sensor.id, "estado": cls["estado"], "nivel": alert.level}, commit=False)
    db.commit()
    return alert
