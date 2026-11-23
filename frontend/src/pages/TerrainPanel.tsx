import { useState, type FormEvent } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import type { DataRecord } from "../services/types";
import { useApi } from "../services/useApi";

interface VarInfo { variable: string; n: number; first: string | null; last: string | null }
interface Sensor { id: string; name: string; kind: string; latitude: number | null; longitude: number | null; created_at: string; variables: VarInfo[] }
interface Vel { velocidad: number; error_estandar: number; r2: number; n: number; unidad: string }
interface Point { t: string; v: number; d: number; a: boolean }
interface Analysis {
  sensor_name: string; variable: string; unit: string; is_simulated: boolean; n_mediciones: number; submuestreada: boolean;
  duracion_dias: number; desplazamiento_acumulado: number; ventana_dias: number;
  velocidad_total: Vel | null; velocidad_reciente: Vel | null; velocidad_previa: Vel | null;
  aceleracion: { valor: number; significativa: boolean; unidad: string } | null;
  anomalias: { index: number; observed_at: string; increment: number }[];
  clasificacion: { estado: string; motivo: string; aviso: string };
  umbrales: { vel_threshold: number; acc_ratio: number; window_days: number; k_mad: number; rotulo: string };
  notas: string[]; aviso: string; puntos: Point[];
}
interface ImportResult { importadas: number; variables: Record<string, number>; is_simulated: boolean }

const KINDS = ["gps", "inclinometro", "piezometro", "extensometro", "otro"];
const num = (v: number | null | undefined, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");
const BADGE: Record<string, string> = { estable: "badge-ok", en_movimiento: "badge-partial", acelerando: "badge-high" };

/** NEUROTERRAIN: series de sensores (CSV de NEURODATA) con indicadores EXPERIMENTALES por umbrales. */
export function TerrainPanel() {
  const sensors = useApi<Sensor[]>("/api/terrain/sensors");
  const [sel, setSel] = useState<string | null>(null);
  const writable = canWrite(session.user());
  const current = sensors.data?.find((s) => s.id === sel) ?? null;
  return (
    <div className="stack">
      <Notice kind="danger">
        Indicador experimental por umbrales; no es una predicción de falla ni sustituye el criterio geotécnico.
        Los umbrales por defecto son <strong>valores de ejemplo configurables</strong>, no oficiales. Los datos entran solo por CSV
        registrado en NEURODATA (sin conexión en vivo con equipos ni InSAR).
      </Notice>
      <div className="grid grid-2">
        <SensorList sensors={sensors.data} loading={sensors.loading} error={sensors.error} sel={sel} onSel={setSel}
          writable={writable} onChange={sensors.reload} />
        {current && writable ? <ImportForm sensor={current} onDone={sensors.reload} />
          : <div className="card"><h2>Importar mediciones</h2><p className="muted small">Seleccione un sensor{writable ? "" : " (su rol solo permite consultar)"}.</p></div>}
      </div>
      {current && <SeriesView key={current.id} sensor={current} writable={writable} />}
    </div>
  );
}

function SensorList({ sensors, loading, error, sel, onSel, writable, onChange }: {
  sensors: Sensor[] | null; loading: boolean; error: string | null; sel: string | null;
  onSel: (id: string) => void; writable: boolean; onChange: () => void;
}) {
  const [f, setF] = useState({ name: "", kind: "gps", lat: "", lon: "" });
  const [err, setErr] = useState<string | null>(null);
  async function add(e: FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      const s = await post<Sensor>("/api/terrain/sensors", {
        name: f.name, kind: f.kind, latitude: f.lat === "" ? null : Number(f.lat), longitude: f.lon === "" ? null : Number(f.lon) });
      setF({ name: "", kind: "gps", lat: "", lon: "" }); onChange(); onSel(s.id);
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <div className="card stack">
      <h2>Sensores</h2>
      {loading && <Loading what="sensores" />}
      <ErrorText error={error} />
      {sensors?.length === 0 && <p className="muted small">Aún no hay sensores.</p>}
      <div className="table-wrap"><table>
        <thead><tr><th></th><th>Nombre</th><th>Tipo</th><th>Variables</th></tr></thead>
        <tbody>{sensors?.map((s) => (
          <tr key={s.id}>
            <td><input type="radio" name="sensor" aria-label={`Elegir ${s.name}`} checked={sel === s.id} onChange={() => onSel(s.id)} /></td>
            <td>{s.name}<div className="small muted">{fmtDate(s.created_at)}</div></td><td>{s.kind}</td>
            <td className="small">{s.variables.map((v) => `${v.variable} (${v.n})`).join(", ") || "sin mediciones"}</td>
          </tr>
        ))}</tbody>
      </table></div>
      {writable && (
        <form onSubmit={add} className="stack">
          <h3>Nuevo sensor</h3>
          <div className="grid grid-4">
            <div className="field"><label htmlFor="sn">Nombre</label><input id="sn" value={f.name} minLength={2} maxLength={128} required onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="sk">Tipo</label><select id="sk" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{KINDS.map((k) => <option key={k}>{k}</option>)}</select></div>
            <div className="field"><label htmlFor="sla">Latitud (opc.)</label><input id="sla" type="number" step="any" min={-90} max={90} value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} /></div>
            <div className="field"><label htmlFor="slo">Longitud (opc.)</label><input id="slo" type="number" step="any" min={-180} max={180} value={f.lon} onChange={(e) => setF({ ...f, lon: e.target.value })} /></div>
          </div>
          <div><button className="btn">Crear sensor</button></div>
          <ErrorText error={err} />
        </form>
      )}
    </div>
  );
}

function ImportForm({ sensor, onDone }: { sensor: Sensor; onDone: () => void }) {
  const records = useApi<DataRecord[]>("/api/neurodata/records?data_type=csv&limit=100");
  const [f, setF] = useState({ rec: "", format: "largo", date: "fecha", variable: "variable", value: "valor", unit: "unidad",
    cols: "", defUnit: "", normalize: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const csvs = (records.data ?? []).filter((r) => r.data_type === "csv" && r.validation_status === "valido");
  const set = (k: string, v: string | boolean) => setF({ ...f, [k]: v });

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setOk(null);
    const wide = f.format === "ancho";
    try {
      const r = await post<ImportResult>(`/api/terrain/sensors/${sensor.id}/import`, {
        data_record_id: f.rec, format: f.format, date_column: f.date, default_unit: f.defUnit, normalize: f.normalize,
        ...(wide ? { value_columns: f.cols.split(",").map((c) => c.trim()).filter(Boolean) }
          : { variable_column: f.variable, value_column: f.value, unit_column: f.unit || null }) });
      setOk(`Importadas ${r.importadas} mediciones (${Object.keys(r.variables).join(", ")})${r.is_simulated ? " · SIMULADAS" : ""}.`);
      onDone();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Importar CSV a «{sensor.name}»</h2>
      <p className="small muted" style={{ margin: 0 }}>Suba antes el CSV en NEURODATA. Máx. 50 000 filas; fechas ISO 8601 (sin zona = UTC).</p>
      <div className="field"><label htmlFor="ir">Registro CSV de NEURODATA</label>
        <select id="ir" value={f.rec} required onChange={(e) => set("rec", e.target.value)}>
          <option value="">— elegir —</option>
          {csvs.map((r) => <option key={r.id} value={r.id}>{r.title}{r.is_simulated ? " (simulado)" : ""}</option>)}
        </select></div>
      <div className="grid grid-4">
        <div className="field"><label htmlFor="if">Formato</label><select id="if" value={f.format} onChange={(e) => set("format", e.target.value)}>
          <option value="largo">largo (fecha, variable, valor)</option><option value="ancho">ancho (una columna por variable)</option></select></div>
        <div className="field"><label htmlFor="id">Col. fecha</label><input id="id" value={f.date} onChange={(e) => set("date", e.target.value)} required /></div>
        {f.format === "largo" ? (<>
          <div className="field"><label htmlFor="iv">Col. variable</label><input id="iv" value={f.variable} onChange={(e) => set("variable", e.target.value)} /></div>
          <div className="field"><label htmlFor="ia">Col. valor</label><input id="ia" value={f.value} onChange={(e) => set("value", e.target.value)} /></div>
          <div className="field"><label htmlFor="iu">Col. unidad</label><input id="iu" value={f.unit} onChange={(e) => set("unit", e.target.value)} /></div>
        </>) : (
          <div className="field"><label htmlFor="ic">Columnas de valores (coma)</label><input id="ic" value={f.cols} required onChange={(e) => set("cols", e.target.value)} /></div>
        )}
        <div className="field"><label htmlFor="idu">Unidad por defecto</label><input id="idu" value={f.defUnit} placeholder="mm" onChange={(e) => set("defUnit", e.target.value)} /></div>
      </div>
      <label className="small"><input type="checkbox" checked={f.normalize} onChange={(e) => set("normalize", e.target.checked)} /> Ordenar por fecha y descartar duplicados idénticos</label>
      <div><button className="btn" disabled={busy || !f.rec}>{busy ? "Importando…" : "Importar"}</button></div>
      <ErrorText error={err} />
      {ok && <Notice kind="ok">{ok}</Notice>}
    </form>
  );
}

function SeriesView({ sensor, writable }: { sensor: Sensor; writable: boolean }) {
  const [variable, setVariable] = useState(sensor.variables[0]?.variable ?? "");
  const [p, setP] = useState({ window: "30", vel: "0.05", acc: "1.5" });
  const [query, setQuery] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const qs = (v: string) => `variable=${encodeURIComponent(v)}&window_days=${p.window}&vel_threshold=${p.vel}&acc_ratio=${p.acc}`;
  const res = useApi<Analysis>(query);

  async function requestAlert() {
    setErr(null); setAlertMsg(null);
    if (!window.confirm("¿Crear una alerta EXPERIMENTAL no validada con estas métricas?")) return;
    try {
      const r = await post<{ alert_id: string; level: string }>(`/api/terrain/sensors/${sensor.id}/alert`, {
        variable, window_days: Number(p.window), vel_threshold: Number(p.vel), acc_ratio: Number(p.acc) });
      setAlertMsg(`Alerta experimental creada (nivel ${r.level}, no validada). Revísela en Alertas.`);
    } catch (x) { setErr((x as Error).message); }
  }
  const a = res.data;
  return (
    <div className="card stack">
      <h2>Serie y análisis · {sensor.name}</h2>
      {sensor.variables.length === 0 ? <p className="muted small">El sensor no tiene mediciones: importe un CSV.</p> : (
        <form className="grid grid-4" onSubmit={(e) => { e.preventDefault(); setQuery(`/api/terrain/sensors/${sensor.id}/series?${qs(variable)}`); }}>
          <div className="field"><label htmlFor="tv">Variable</label><select id="tv" value={variable} onChange={(e) => setVariable(e.target.value)}>
            {sensor.variables.map((v) => <option key={v.variable}>{v.variable}</option>)}</select></div>
          <div className="field"><label htmlFor="tw">Ventana reciente (días)</label><input id="tw" type="number" min={1} step="any" value={p.window} onChange={(e) => setP({ ...p, window: e.target.value })} /></div>
          <div className="field"><label htmlFor="tt">Umbral velocidad (unid./día, ejemplo)</label><input id="tt" type="number" min={0} step="any" value={p.vel} onChange={(e) => setP({ ...p, vel: e.target.value })} /></div>
          <div className="field"><label htmlFor="ta">Cociente aceleración (ejemplo)</label><input id="ta" type="number" min={1.01} step="any" value={p.acc} onChange={(e) => setP({ ...p, acc: e.target.value })} /></div>
          <div><button className="btn">Analizar</button></div>
        </form>
      )}
      {res.loading && <Loading what="serie" />}
      <ErrorText error={res.error} />
      {a && (<>
        <Chart points={a.puntos} unit={a.unit} />
        <p className="small muted" style={{ margin: 0 }}>Línea: desplazamiento acumulado ({a.unit || "unidad"}). Puntos rojos: saltos/anomalías.
          {a.submuestreada ? ` Se muestran ${a.puntos.length} de ${a.n_mediciones} mediciones.` : ""}</p>
        <div className="row">
          <span className={`badge ${BADGE[a.clasificacion.estado] ?? "badge-dev"}`}>{a.clasificacion.estado.replace("_", " ")} (experimental)</span>
          {a.is_simulated && <span className="badge badge-dev">datos simulados</span>}
          <span className="small">{a.clasificacion.motivo}</span>
        </div>
        <Notice kind="danger">{a.clasificacion.aviso}</Notice>
        <div className="table-wrap"><table><tbody>
          <tr><th>Mediciones / duración</th><td>{a.n_mediciones} · {num(a.duracion_dias, 1)} días</td></tr>
          <tr><th>Desplazamiento acumulado</th><td>{num(a.desplazamiento_acumulado)} {a.unit}</td></tr>
          <tr><th>Velocidad (ventana completa)</th><td>{num(a.velocidad_total?.velocidad, 4)} {a.velocidad_total?.unidad} (R² {num(a.velocidad_total?.r2, 3)})</td></tr>
          <tr><th>Velocidad reciente ({num(a.ventana_dias, 1)} d)</th><td>{num(a.velocidad_reciente?.velocidad, 4)} ± {num(a.velocidad_reciente?.error_estandar, 4)} {a.velocidad_reciente?.unidad}</td></tr>
          <tr><th>Velocidad ventana previa</th><td>{num(a.velocidad_previa?.velocidad, 4)} {a.velocidad_previa?.unidad}</td></tr>
          <tr><th>Aceleración</th><td>{a.aceleracion ? `${a.aceleracion.valor.toExponential(2)} ${a.aceleracion.unidad} · ${a.aceleracion.significativa ? "significativa" : "no significativa"}` : "no evaluable"}</td></tr>
          <tr><th>Anomalías</th><td>{a.anomalias.length === 0 ? "ninguna" : a.anomalias.map((x) => `${x.observed_at.slice(0, 10)} (Δ ${num(x.increment, 2)})`).join(", ")}</td></tr>
        </tbody></table></div>
        <p className="small muted" style={{ margin: 0 }}>{a.umbrales.rotulo}</p>
        {a.notas.map((n) => <p key={n} className="small muted" style={{ margin: 0 }}>• {n}</p>)}
        {writable && <div><button className="btn" onClick={requestAlert}>Crear alerta experimental (a petición)</button></div>}
        <ErrorText error={err} />
        {alertMsg && <Notice kind="ok">{alertMsg}</Notice>}
      </>)}
    </div>
  );
}

function Chart({ points, unit }: { points: Point[]; unit: string }) {
  const W = 720, H = 260, L = 52, R = 12, T = 12, B = 28;
  if (points.length < 2) return null;
  const ts = points.map((p) => new Date(p.t).getTime());
  const [t0, t1] = [ts[0], ts[ts.length - 1]];
  const ds = points.map((p) => p.d);
  let lo = Math.min(...ds), hi = Math.max(...ds);
  if (hi === lo) { hi += 1; lo -= 1; }
  const x = (t: number) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
  const y = (d: number) => T + (1 - (d - lo) / (hi - lo)) * (H - T - B);
  const line = points.map((p, i) => `${x(ts[i]).toFixed(1)},${y(p.d).toFixed(1)}`).join(" ");
  const yTicks = [lo, (lo + hi) / 2, hi];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Serie de desplazamiento acumulado en ${unit || "unidades"}`} style={{ width: "100%", height: "auto", maxWidth: W }}>
      {yTicks.map((v) => (
        <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="currentColor" opacity={0.15} />
          <text x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor">{v.toFixed(2)}</text></g>
      ))}
      <text x={L} y={H - 8} fontSize="11" fill="currentColor">{new Date(t0).toLocaleDateString("es-PE")}</text>
      <text x={W - R} y={H - 8} fontSize="11" textAnchor="end" fill="currentColor">{new Date(t1).toLocaleDateString("es-PE")}</text>
      <polyline points={line} fill="none" stroke="#2563eb" strokeWidth={1.6} />
      {points.map((p, i) => p.a && <circle key={i} cx={x(ts[i])} cy={y(p.d)} r={5} fill="#dc2626" stroke="#fff" strokeWidth={1}><title>Anomalía {p.t.slice(0, 10)}</title></circle>)}
    </svg>
  );
}
