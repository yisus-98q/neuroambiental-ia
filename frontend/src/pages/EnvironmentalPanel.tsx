import { useEffect, useState, type FormEvent } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import type { Analysis, RasterRecord, Scene } from "../services/types";
import { useApi } from "../services/useApi";

interface Defaults { bbox: number[]; area_name: string; resolution_deg: number; max_span_deg: number; source: string; source_url: string }

const n = (v: unknown, d = 2) => (typeof v === "number" ? v.toFixed(d) : "—");

/** Fase 2: Sentinel-2 → NDVI → detección de cambios, con datos reales y límites honestos. */
export function EnvironmentalPanel() {
  const defaults = useApi<Defaults>("/api/environmental/defaults");
  const rasters = useApi<RasterRecord[]>("/api/environmental/rasters");
  const runs = useApi<Analysis[]>("/api/environmental/analyses");
  const writable = canWrite(session.user());
  const reload = () => { rasters.reload(); runs.reload(); };

  return (
    <div className="stack">
      <Notice kind="info">
        Imágenes reales <strong>Sentinel-2 L2A</strong> del programa Copernicus, leídas gratis y sin cuenta desde
        {" "}<a href={defaults.data?.source_url} target="_blank" rel="noopener noreferrer">AWS Open Data</a>. Solo se descarga
        el recorte del área (≈15-20 MB por fecha). Cada cálculo tarda de 1 a 3 minutos y se procesa uno a la vez.
      </Notice>
      {writable && defaults.data && <SceneSearch defaults={defaults.data} onDone={reload} />}
      <div className="grid grid-2">
        <NdviList rasters={rasters.data} loading={rasters.loading} writable={writable} onDone={reload} />
        <ChangeResults rasters={rasters.data} />
      </div>
      <div className="card">
        <h2>Historial de análisis</h2>
        {runs.data?.length === 0 && <p className="muted small">Aún no hay análisis.</p>}
        <div className="table-wrap"><table>
          <tbody>{runs.data?.map((r) => (
            <tr key={r.id}>
              <td>{r.run_type}</td><td className="small">{fmtDate(r.started_at)}</td>
              <td><span className={`badge ${r.status === "ok" ? "badge-ok" : r.status === "error" ? "badge-high" : "badge-partial"}`}>{r.status}</span></td>
              <td className="small muted">{r.status === "error" ? String(r.result_summary.error ?? "") : ""}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </div>
    </div>
  );
}

function SceneSearch({ defaults, onDone }: { defaults: Defaults; onDone: () => void }) {
  const [bbox, setBbox] = useState(defaults.bbox.map(String));
  const [from, setFrom] = useState("2025-06-01");
  const [to, setTo] = useState("2025-09-30");
  const [cloud, setCloud] = useState("10");
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const box = bbox.map(Number);

  async function search(e: FormEvent) {
    e.preventDefault();
    setBusy("buscar"); setError(null); setScenes(null);
    try { setScenes(await post<Scene[]>("/api/environmental/scenes/search", { bbox: box, date_from: from, date_to: to, max_cloud: Number(cloud) })); }
    catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  }

  async function ndvi(id: string) {
    setBusy(id); setError(null); setMsg(null);
    try {
      const r = await post<RasterRecord>("/api/environmental/ndvi", { item_id: id, bbox: box, resolution_deg: defaults.resolution_deg });
      setMsg(`NDVI listo: ${r.title}. Válido: ${n(r.extra.stats.valid_pct, 1)} % del área.`);
      onDone();
    } catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  }

  const labels = ["Longitud mín.", "Latitud mín.", "Longitud máx.", "Latitud máx."];
  return (
    <div className="card stack">
      <h2>1. Buscar escenas Sentinel-2</h2>
      <form onSubmit={search} className="stack">
        <p className="small muted" style={{ margin: 0 }}>Área: {defaults.area_name}. Máximo {defaults.max_span_deg}° por lado.</p>
        <div className="grid grid-4">
          {labels.map((l, i) => (
            <div className="field" key={l}><label htmlFor={`bb${i}`}>{l}</label>
              <input id={`bb${i}`} type="number" step="0.01" value={bbox[i]} onChange={(e) => setBbox(bbox.map((v, j) => (j === i ? e.target.value : v)))} required /></div>
          ))}
          <div className="field"><label htmlFor="d1">Desde</label><input id="d1" type="date" value={from} onChange={(e) => setFrom(e.target.value)} required /></div>
          <div className="field"><label htmlFor="d2">Hasta</label><input id="d2" type="date" value={to} onChange={(e) => setTo(e.target.value)} required /></div>
          <div className="field"><label htmlFor="cc">Nubosidad máx. (%)</label><input id="cc" type="number" min={0} max={100} value={cloud} onChange={(e) => setCloud(e.target.value)} /></div>
          <div className="field" style={{ alignSelf: "end" }}><button className="btn" disabled={busy !== null}>{busy === "buscar" ? "Buscando…" : "Buscar"}</button></div>
        </div>
      </form>
      <ErrorText error={error} />
      {msg && <Notice kind="ok">{msg}</Notice>}
      {scenes && scenes.length === 0 && <p className="muted small">Sin escenas para esos filtros. Amplíe fechas o nubosidad.</p>}
      {scenes && scenes.length > 0 && (
        <div className="table-wrap"><table>
          <thead><tr><th>Escena</th><th>Fecha</th><th>Nubes</th><th>Tesela</th><th></th></tr></thead>
          <tbody>{scenes.map((s) => (
            <tr key={s.id}><td className="small">{s.id}</td><td>{s.datetime.slice(0, 10)}</td><td>{s.cloud_cover.toFixed(1)} %</td><td>{s.mgrs_tile}</td>
              <td><button className="btn btn-green" disabled={busy !== null} onClick={() => ndvi(s.id)}>{busy === s.id ? "Procesando… (1-3 min)" : "2. Calcular NDVI"}</button></td></tr>
          ))}</tbody>
        </table></div>
      )}
    </div>
  );
}

function NdviList({ rasters, loading, writable, onDone }: { rasters: RasterRecord[] | null; loading: boolean; writable: boolean; onDone: () => void }) {
  const ndvis = (rasters ?? []).filter((r) => r.data_type === "raster_ndvi");
  const [sel, setSel] = useState<string[]>([]);
  const [thr, setThr] = useState("0.2");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Si cambia la lista, se descartan selecciones de NDVI que ya no existen.
  useEffect(() => setSel((s) => s.filter((id) => (rasters ?? []).some((r) => r.id === id))), [rasters]);

  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));

  async function change() {
    setBusy(true); setError(null);
    try { await post("/api/environmental/change", { before_id: sel[0], after_id: sel[1], threshold: Number(thr) }); setSel([]); onDone(); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="card stack">
      <h2>NDVI calculados</h2>
      {loading && <Loading />}
      {ndvis.length === 0 && <p className="muted small">Aún no hay NDVI. Busque una escena y calcule su NDVI.</p>}
      <table><tbody>{ndvis.map((r) => {
        const st = r.extra.stats;
        return (
          <tr key={r.id}>
            {writable && <td><input type="checkbox" aria-label={`Seleccionar ${r.title}`} checked={sel.includes(r.id)} onChange={() => toggle(r.id)} /></td>}
            <td><strong className="small">{r.title}</strong>
              <div className="small muted">NDVI medio {n(st.ndvi_mean)} · válido {n(st.valid_pct, 1)} % · nubes/sombras {n(st.cloud_shadow_masked_pct, 1)} % · nieve {n(st.snow_pct, 1)} %</div></td>
          </tr>
        );
      })}</tbody></table>
      {writable && ndvis.length >= 2 && (
        <div className="row">
          <span className="small">3. Seleccione 2 fechas (misma área) · Umbral ±</span>
          <input type="number" step="0.05" min={0.05} max={0.8} value={thr} onChange={(e) => setThr(e.target.value)} style={{ width: 80 }} aria-label="Umbral" />
          <button className="btn" disabled={sel.length !== 2 || busy} onClick={change}>{busy ? "Comparando…" : "Detectar cambios"}</button>
        </div>
      )}
      <ErrorText error={error} />
    </div>
  );
}

function ChangeResults({ rasters }: { rasters: RasterRecord[] | null }) {
  const changes = (rasters ?? []).filter((r) => r.data_type === "raster_cambio");
  return (
    <div className="card stack">
      <h2>Detección de cambios</h2>
      {changes.length === 0 && <p className="muted small">Sin comparaciones todavía.</p>}
      {changes.map((r) => {
        const st = r.extra.stats;
        return (
          <div key={r.id} className="stack" style={{ borderBottom: "1px dashed var(--gray-100)", paddingBottom: 8 }}>
            <div className="row" style={{ justifyContent: "space-between" }}><strong className="small">{r.title}</strong>
              <span className="badge badge-dev">{r.extra.validated ? "validado" : "sin validar"}</span></div>
            <table><tbody>
              <tr><th>Área comparable</th><td>{n(st.common_valid_km2, 1)} km² ({n(st.common_valid_pct, 1)} %)</td></tr>
              <tr><th>Disminución de NDVI</th><td>{n(st.ndvi_decrease_km2, 2)} km² ({n(st.ndvi_decrease_pct, 2)} %)</td></tr>
              <tr><th>Aumento de NDVI</th><td>{n(st.ndvi_increase_km2, 2)} km² ({n(st.ndvi_increase_pct, 2)} %)</td></tr>
              <tr><th>NDVI medio antes → después</th><td>{n(st.ndvi_mean_before, 3)} → {n(st.ndvi_mean_after, 3)}</td></tr>
              <tr><th>Umbral</th><td>±{String(st.threshold)}</td></tr>
            </tbody></table>
            <p className="small muted" style={{ margin: 0 }}>{r.extra.uncertainty}</p>
            <a className="small" href="#/mapa">Ver en el mapa →</a>
          </div>
        );
      })}
    </div>
  );
}
