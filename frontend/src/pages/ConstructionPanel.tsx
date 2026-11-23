import { useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";

const NOTICE = "No reemplaza evaluaciones profesionales ni autorizaciones oficiales.";

interface TerrainLite { id: string; title: string; bbox: number[]; extra: { grid: { res: number } } }
interface ClassPct { label: string; pct: number }
interface SlopeBlock { cells: number; mean_deg: number | null; max_deg: number | null; classes: ClassPct[] }
interface Result {
  site: { type: string; lon: number; lat: number }; site_cells: number; buffer_m: number; cell_size_m: number;
  elevation: { min: number; mean: number; max: number };
  slope_site: SlopeBlock; slope_environment: SlopeBlock;
  susceptibility: { dominant: string; classes: { label: string; pct: number }[]; note: string };
  flood: null | { rise_m: number; site_flooded_pct: number; site_max_depth_m: number; flooded_km2: number; touches_dem_border: boolean; disclaimer: string };
  observations: string[]; notice: string;
}
interface Analysis { id: string; title: string; received_at: string; is_simulated: boolean; extra: { dem_id: string; name: string; result: Result } }

const EXAMPLE = '{"type":"Polygon","coordinates":[[[-77.52,-9.52],[-77.51,-9.52],[-77.51,-9.51],[-77.52,-9.51],[-77.52,-9.52]]]}';

/** NEUROCONSTRUCTION: análisis preliminar del emplazamiento de un proyecto sobre un DEM real registrado. */
export function ConstructionPanel() {
  const terrains = useApi<TerrainLite[]>("/api/neuro3d/terrains");
  const analyses = useApi<Analysis[]>("/api/construction/analyses");
  const writable = canWrite(session.user());
  const [demId, setDemId] = useState("");
  const [mode, setMode] = useState<"point" | "geojson">("point");
  const [lon, setLon] = useState("");
  const [lat, setLat] = useState("");
  const [geojson, setGeojson] = useState("");
  const [buffer, setBuffer] = useState("500");
  const [useFlood, setUseFlood] = useState(false);
  const [rise, setRise] = useState("5");
  const [floodLon, setFloodLon] = useState("");
  const [floodLat, setFloodLat] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);

  const list = terrains.data ?? [];
  const dem = list.find((t) => t.id === demId) ?? null;
  useEffect(() => {
    if (!demId && list.length) setDemId(list[0].id);
  }, [list, demId]);
  useEffect(() => {
    if (!dem) return;
    const cx = ((dem.bbox[0] + dem.bbox[2]) / 2).toFixed(4), cy = ((dem.bbox[1] + dem.bbox[3]) / 2).toFixed(4);
    setLon(cx); setLat(cy); setFloodLon(cx); setFloodLat(cy);
  }, [dem?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run() {
    setBusy(true); setError(null);
    try {
      let site: Record<string, unknown>;
      if (mode === "point") site = { point: { lon: Number(lon), lat: Number(lat) } };
      else {
        try { site = { geojson: JSON.parse(geojson) }; } catch { throw new Error("El GeoJSON pegado no es JSON válido."); }
      }
      const flood = useFlood ? { flood: { lon: Number(floodLon), lat: Number(floodLat), rise_m: Number(rise) } } : {};
      const r = await post<Analysis>("/api/construction/site-analysis", { dem_id: demId, buffer_m: Number(buffer), name, ...site, ...flood });
      setResult(r);
      analyses.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const res = result?.extra.result;
  return (
    <div className="stack">
      <Notice kind="dev"><strong>{NOTICE}</strong> Análisis preliminar sobre un DEM de ≈100 m: no hay capa de ríos ni de zonificación, por lo que no se evalúa
        proximidad a cauces ni compatibilidad territorial.</Notice>

      {terrains.loading && !terrains.data && <Loading what="terrenos" />}
      {terrains.data && list.length === 0 && (
        <Notice kind="info">Primero descargue un terreno real (DEM) en NEURO 3D LAB; no se usa ningún terreno de ejemplo.</Notice>
      )}

      {list.length > 0 && writable && (
        <div className="card stack">
          <h2>Análisis de sitio</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field"><label htmlFor="cdem">Terreno (DEM)</label>
              <select id="cdem" value={demId} onChange={(e) => setDemId(e.target.value)}>
                {list.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></div>
            <div className="field"><label htmlFor="cname">Nombre del proyecto (opcional)</label>
              <input id="cname" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} /></div>
            <div className="field"><label htmlFor="cbuf">Entorno (m)</label>
              <input id="cbuf" type="number" min={0} max={5000} step={50} value={buffer} onChange={(e) => setBuffer(e.target.value)} /></div>
          </div>
          <div className="row" role="radiogroup" aria-label="Tipo de emplazamiento" style={{ gap: 16 }}>
            <label><input type="radio" checked={mode === "point"} onChange={() => setMode("point")} /> Punto</label>
            <label><input type="radio" checked={mode === "geojson"} onChange={() => setMode("geojson")} /> Polígono GeoJSON</label>
          </div>
          {mode === "point" ? (
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="field"><label htmlFor="clon">Longitud</label><input id="clon" type="number" step="0.0001" value={lon} onChange={(e) => setLon(e.target.value)} /></div>
              <div className="field"><label htmlFor="clat">Latitud</label><input id="clat" type="number" step="0.0001" value={lat} onChange={(e) => setLat(e.target.value)} /></div>
            </div>
          ) : (
            <div className="field"><label htmlFor="cgj">GeoJSON (Polygon, MultiPolygon o Feature; coordenadas lon, lat)</label>
              <textarea id="cgj" rows={5} value={geojson} placeholder={EXAMPLE} onChange={(e) => setGeojson(e.target.value)} style={{ width: "100%", fontFamily: "monospace" }} /></div>
          )}
          <label className="row" style={{ gap: 8, fontWeight: 400 }}>
            <input type="checkbox" checked={useFlood} onChange={(e) => setUseFlood(e.target.checked)} />
            Comprobar contra una inundación demostrativa (modelo de bañera, hipotética)
          </label>
          {useFlood && (
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="field"><label htmlFor="cfl">Origen del agua: longitud</label><input id="cfl" type="number" step="0.0001" value={floodLon} onChange={(e) => setFloodLon(e.target.value)} /></div>
              <div className="field"><label htmlFor="cfa">Latitud</label><input id="cfa" type="number" step="0.0001" value={floodLat} onChange={(e) => setFloodLat(e.target.value)} /></div>
              <div className="field"><label htmlFor="cfr">Subida de nivel (0,5 a 50 m)</label><input id="cfr" type="number" min={0.5} max={50} step={0.5} value={rise} onChange={(e) => setRise(e.target.value)} /></div>
            </div>
          )}
          <div><button className="btn" disabled={busy || !demId || (mode === "geojson" && !geojson.trim())} onClick={run}>{busy ? "Analizando…" : "Analizar sitio"}</button></div>
        </div>
      )}
      {!writable && list.length > 0 && <p className="small muted">Solo analistas pueden ejecutar análisis; puede consultar los guardados.</p>}
      <ErrorText error={error} />

      {res && <ResultCard res={res} title={result!.title} />}

      <div className="card">
        <h2>Análisis guardados</h2>
        {analyses.data?.length === 0 && <p className="muted small">Aún no hay análisis de sitio.</p>}
        <div className="table-wrap"><table><tbody>{analyses.data?.map((a) => (
          <tr key={a.id}><td className="small">{a.title}</td><td className="small">{fmtDate(a.received_at)}</td>
            <td><button className="btn" onClick={() => setResult(a)}>Ver</button></td></tr>
        ))}</tbody></table></div>
      </div>
    </div>
  );
}

function ResultCard({ res, title }: { res: Result; title: string }) {
  const s = res.slope_site, e = res.slope_environment;
  return (
    <div className="card stack">
      <h2>Resultado · {title}</h2>
      <p className="small" style={{ margin: 0 }}>
        Elevación del emplazamiento: mín. <strong>{res.elevation.min} m</strong>, media <strong>{res.elevation.mean} m</strong>, máx. <strong>{res.elevation.max} m</strong>.
        El emplazamiento ocupa {res.site_cells} celda(s) de ≈{res.cell_size_m} m.
      </p>
      <div className="table-wrap"><table>
        <thead><tr><th></th><th>Pendiente media</th><th>Pendiente máx.</th>{s.classes.map((c) => <th key={c.label}>{c.label} (%)</th>)}</tr></thead>
        <tbody>
          <tr><td>Emplazamiento</td><td>{s.mean_deg}°</td><td>{s.max_deg}°</td>{s.classes.map((c) => <td key={c.label}>{c.pct}</td>)}</tr>
          <tr><td>Entorno ({res.buffer_m} m)</td><td>{e.mean_deg}°</td><td>{e.max_deg}°</td>{e.classes.map((c) => <td key={c.label}>{c.pct}</td>)}</tr>
        </tbody>
      </table></div>
      <p className="small" style={{ margin: 0 }}>Susceptibilidad heurística (solo pendiente): predomina <strong>{res.susceptibility.dominant}</strong>
        {" "}<span className="badge badge-sim">HEURÍSTICO</span></p>
      <p className="small muted" style={{ margin: 0 }}>{res.susceptibility.note}</p>
      {res.flood && (
        <Notice kind="dev"><strong>SIMULACIÓN — escenario hipotético, no es una predicción.</strong> Subida de +{res.flood.rise_m} m: {res.flood.site_flooded_pct} % del emplazamiento
          bajo el agua (profundidad máx. {res.flood.site_max_depth_m} m). {res.flood.disclaimer}</Notice>
      )}
      <div><strong className="small">Observaciones automáticas (reglas sobre los números anteriores)</strong>
        <ul className="small">{res.observations.map((o) => <li key={o}>{o}</li>)}</ul></div>
      <Notice kind="info"><strong>{res.notice}</strong></Notice>
    </div>
  );
}
