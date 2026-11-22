import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import type { Layer, MeshData, PathPoint } from "../maps/Terrain3D";
import { HYPSO_STOPS, SLOPE_CLASSES } from "../maps/Terrain3D";
import { api, canWrite, post, session } from "../services/api";
import { useApi } from "../services/useApi";

const Terrain3D = lazy(() => import("../maps/Terrain3D"));

const DEFAULT_BBOX = [-77.60, -9.60, -77.30, -9.35];
const LABELS = ["Longitud mín.", "Latitud mín.", "Longitud máx.", "Latitud máx."];

interface SlopeStats { classes: { label: string; pct: number }[]; mean_deg: number | null; max_deg: number | null }
interface TerrainRecord {
  id: string; title: string; bbox: number[]; provenance: string; is_simulated: boolean;
  extra: { elevation: { min: number; max: number; mean: number }; slope_stats: SlopeStats;
           grid: { width: number; height: number; res: number }; download?: { bytes?: number }; attribution: string };
}
interface Mesh extends MeshData { attribution: string; slope_stats: SlopeStats }
interface Scenario {
  id: string; path: PathPoint[]; length_km: number; drop_m: number; steps: number; mean_slope_deg: number;
  end_reason: string; disclaimer: string; uncertainty: string; start: { lon: number; lat: number };
}

const END_TEXT: Record<string, string> = {
  minimo_local: "mínimo local (depresión)", borde: "borde del DEM", max_pasos: "límite de 2000 pasos",
};
const mb = (b?: number) => (b ? `${(b / 1048576).toFixed(1)} MB` : "—");

/** NEURO 3D LAB: terreno real (Copernicus GLO-30) en 3D y un escenario demostrativo simplificado. */
export function Neuro3DLab() {
  const terrains = useApi<TerrainRecord[]>("/api/neuro3d/terrains");
  const writable = canWrite(session.user());
  const [bbox, setBbox] = useState(DEFAULT_BBOX.map(String));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [mesh, setMesh] = useState<Mesh | null>(null);
  const [exag, setExag] = useState(2);
  const [layer, setLayer] = useState<Layer>("elevation");
  const [lon, setLon] = useState("");
  const [lat, setLat] = useState("");
  const [scenario, setScenario] = useState<Scenario | null>(null);

  const list = terrains.data ?? [];
  const sel = list.find((t) => t.id === selId) ?? null;

  useEffect(() => { if (!selId && list.length) setSelId(list[0].id); }, [list, selId]);

  useEffect(() => {
    setMesh(null); setScenario(null);
    if (!selId) return;
    let alive = true;
    api<Mesh>(`/api/neuro3d/terrains/${selId}/mesh?max_size=256`)
      .then((m) => {
        if (!alive) return;
        setMesh(m);
        setLon(((m.bbox[0] + m.bbox[2]) / 2).toFixed(4));
        setLat(((m.bbox[1] + m.bbox[3]) / 2).toFixed(4));
      })
      .catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [selId]);

  async function download() {
    setBusy(true); setError(null);
    try {
      const r = await post<TerrainRecord>("/api/neuro3d/terrain", { bbox: bbox.map(Number) });
      terrains.reload();
      setSelId(r.id);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function runScenario() {
    if (!sel) return;
    setBusy(true); setError(null);
    try {
      setScenario(await post<Scenario>(`/api/neuro3d/terrains/${sel.id}/flow-path`, { lon: Number(lon), lat: Number(lat) }));
    } catch (e) { setError((e as Error).message); setScenario(null); } finally { setBusy(false); }
  }

  const elev = sel?.extra.elevation;
  return (
    <div className="stack">
      <div><h1>NEURO 3D LAB</h1>
        <p className="muted" style={{ margin: 0 }}>Relieve real en 3D a partir del modelo digital de elevación Copernicus GLO-30 (30 m, remuestreado a ≈100 m).</p></div>

      {writable && (
        <div className="card stack">
          <h2>1. Territorio</h2>
          <div className="grid grid-4">
            {LABELS.map((l, i) => (
              <div className="field" key={l}><label htmlFor={`t3b${i}`}>{l}</label>
                <input id={`t3b${i}`} type="number" step="0.01" value={bbox[i]} onChange={(e) => setBbox(bbox.map((v, j) => (j === i ? e.target.value : v)))} /></div>
            ))}
          </div>
          <div className="row">
            <button className="btn" disabled={busy} onClick={download}>{busy && !mesh ? "Descargando… (puede tardar un minuto)" : "Descargar terreno real (DEM)"}</button>
            <span className="small muted">Máximo 0,5° x 0,5°. Por defecto: Huaraz / Cordillera Blanca.</span>
          </div>
        </div>
      )}
      <ErrorText error={error} />

      {terrains.loading && !terrains.data && <Loading what="terrenos" />}
      {terrains.data && list.length === 0 && (
        <Notice kind="info">Todavía no hay un terreno real cargado. {writable ? "Use «Descargar terreno real (DEM)» para obtenerlo." : "Pida a un analista que descargue uno."} No se muestra ningún terreno de ejemplo.</Notice>
      )}

      {list.length > 0 && (
        <div className="card">
          <h2>Terrenos cargados</h2>
          <div className="table-wrap"><table>
            <thead><tr><th></th><th>Terreno</th><th>Elevación</th><th>Malla</th><th>Descarga</th></tr></thead>
            <tbody>{list.map((t) => (
              <tr key={t.id} style={t.id === selId ? { background: "rgba(0,120,90,.10)" } : undefined}>
                <td><button className="btn" onClick={() => setSelId(t.id)} disabled={t.id === selId}>{t.id === selId ? "En visor" : "Ver"}</button></td>
                <td className="small">{t.title}</td>
                <td className="small">{t.extra.elevation.min}–{t.extra.elevation.max} m</td>
                <td className="small">{t.extra.grid.width}x{t.extra.grid.height}</td>
                <td className="small">{mb(t.extra.download?.bytes)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}

      {sel && (
        <div className="grid grid-2" style={{ alignItems: "start" }}>
          <div className="card stack">
            <h2>2. Visor 3D</h2>
            {!mesh && <Loading what="malla 3D" />}
            {mesh && (
              <Suspense fallback={<Loading what="visor 3D" />}>
                <Terrain3D mesh={mesh} exaggeration={exag} layer={layer} path={scenario?.path ?? null} />
              </Suspense>
            )}
            <p className="small muted" style={{ margin: 0 }}>Arrastre para rotar, rueda para acercar, clic derecho para desplazar. Se dibuja solo cuando usted mueve la vista.</p>
            <div className="row" style={{ flexWrap: "wrap", gap: 16 }}>
              <div className="field"><label htmlFor="t3ex">Exageración vertical: {exag}x</label>
                <input id="t3ex" type="range" min={1} max={5} step={0.5} value={exag} onChange={(e) => setExag(Number(e.target.value))} /></div>
              <div className="field"><label htmlFor="t3ly">Capa</label>
                <select id="t3ly" value={layer} onChange={(e) => setLayer(e.target.value as Layer)}>
                  <option value="elevation">Elevación (hipsométrica)</option><option value="slope">Pendiente</option></select></div>
            </div>
            <Legend layer={layer} min={elev?.min} max={elev?.max} />
            <p className="small muted" style={{ margin: 0 }}>{sel.extra.attribution}</p>
          </div>

          <div className="stack">
            <div className="card">
              <h2>Resultados</h2>
              {elev && <p className="small">Elevación: mínima <strong>{elev.min} m</strong>, máxima <strong>{elev.max} m</strong>, media {elev.mean} m.</p>}
              <p className="small">Pendiente media {sel.extra.slope_stats.mean_deg}° (máx. {sel.extra.slope_stats.max_deg}°).</p>
              <div className="table-wrap"><table>
                <thead><tr><th>Clase</th><th>% del área</th></tr></thead>
                <tbody>{sel.extra.slope_stats.classes.map((c) => <tr key={c.label}><td>{c.label}</td><td>{c.pct.toFixed(1)} %</td></tr>)}</tbody>
              </table></div>
              <p className="small muted" style={{ marginBottom: 0 }}>Dato real (no simulado). Resolución de la malla ≈{Math.round(sel.extra.grid.res * 111320)} m: las pendientes locales fuertes se suavizan.</p>
            </div>

            <div className="card stack">
              <h2>3. Escenario demostrativo</h2>
              <Notice kind="dev"><strong>Escenario demostrativo simplificado (camino de máxima pendiente). No es una simulación geotécnica ni predice un evento.</strong></Notice>
              {writable ? (
                <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
                  <div className="field"><label htmlFor="t3lo">Longitud</label><input id="t3lo" type="number" step="0.001" value={lon} onChange={(e) => setLon(e.target.value)} /></div>
                  <div className="field"><label htmlFor="t3la">Latitud</label><input id="t3la" type="number" step="0.001" value={lat} onChange={(e) => setLat(e.target.value)} /></div>
                  <button className="btn" disabled={busy || !lon || !lat} onClick={runScenario}>Trazar trayectoria</button>
                </div>
              ) : <p className="small muted">Solo analistas pueden trazar escenarios.</p>}
              {scenario && (
                <>
                  <p className="small" style={{ margin: 0 }}>
                    Longitud aproximada <strong>{scenario.length_km} km</strong> · desnivel <strong>{scenario.drop_m} m</strong> ·
                    pendiente media {scenario.mean_slope_deg}° · {scenario.steps} pasos · termina en {END_TEXT[scenario.end_reason] ?? scenario.end_reason}.
                  </p>
                  <p className="small muted" style={{ margin: 0 }}>Punto blanco = inicio, punto azul = fin. Línea roja = trayectoria (SIMULACIÓN DEMOSTRATIVA).</p>
                  <Notice kind="info"><strong>Incertidumbre:</strong> {scenario.uncertainty}</Notice>
                </>
              )}
              <a href="#/mapa" className="small">Ver en el mapa 2D</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Legend({ layer, min, max }: { layer: Layer; min?: number; max?: number }) {
  if (layer === "slope") {
    return (
      <div className="row small" style={{ flexWrap: "wrap", gap: 12 }} aria-label="Leyenda de pendiente">
        {SLOPE_CLASSES.map((c) => (
          <span key={c.label}><span style={{ display: "inline-block", width: 12, height: 12, background: c.color, marginRight: 4, verticalAlign: "middle" }} />{c.label}</span>
        ))}
      </div>
    );
  }
  const grad = `linear-gradient(to right, ${HYPSO_STOPS.map(([t, c]) => `${c} ${t * 100}%`).join(", ")})`;
  return (
    <div aria-label="Leyenda de elevación">
      <div style={{ height: 12, background: grad, borderRadius: 4 }} />
      <div className="row small" style={{ justifyContent: "space-between" }}><span>{min ?? "—"} m</span><span>{max ?? "—"} m</span></div>
    </div>
  );
}
