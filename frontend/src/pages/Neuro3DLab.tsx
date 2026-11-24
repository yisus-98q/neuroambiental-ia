import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import type { Layer, MeshData, PathPoint, ScenarioGrid } from "../maps/Terrain3D";
import { CHANGE_CLASSES, FLOOD_STOPS, HYPSO_STOPS, NDVI_STOPS, NO_DATA_COLOR, SLOPE_CLASSES, SUSC_CLASSES } from "../maps/terrainPalette";
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
const BANNER = "SIMULACIÓN — escenario hipotético, no es una predicción";
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
  const [grid, setGrid] = useState<ScenarioGrid | null>(null);
  const [ov, setOv] = useState<OverlayGrid | null>(null);

  const list = terrains.data ?? [];
  const sel = list.find((t) => t.id === selId) ?? null;

  useEffect(() => { if (!selId && list.length) setSelId(list[0].id); }, [list, selId]);

  useEffect(() => {
    setMesh(null); setScenario(null); setGrid(null); setOv(null);
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
            <span className="small muted">Máximo unos 0,46° por lado con la resolución por defecto (~100 m; la malla del visor admite 512 px). Por defecto: Huaraz / Cordillera Blanca.</span>
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
            {layer === "scenario" && grid && <div className="notice notice-dev" role="note"><strong>{BANNER}</strong></div>}
            {layer === "overlay" && ov && <div className="notice notice-info" role="note">{ov.note}</div>}
            {!mesh && <Loading what="malla 3D" />}
            {mesh && (
              <Suspense fallback={<Loading what="visor 3D" />}>
                <Terrain3D mesh={mesh} exaggeration={exag} layer={layer} path={scenario?.path ?? null} scenario={grid} overlay={ov} />
              </Suspense>
            )}
            <p className="small muted" style={{ margin: 0 }}>Arrastre para rotar, rueda para acercar, clic derecho para desplazar. Se dibuja solo cuando usted mueve la vista.</p>
            <div className="row" style={{ flexWrap: "wrap", gap: 16 }}>
              <div className="field"><label htmlFor="t3ex">Exageración vertical: {exag}x</label>
                <input id="t3ex" type="range" min={1} max={5} step={0.5} value={exag} onChange={(e) => setExag(Number(e.target.value))} /></div>
              <div className="field"><label htmlFor="t3ly">Capa</label>
                <select id="t3ly" value={layer} onChange={(e) => setLayer(e.target.value as Layer)}>
                  <option value="elevation">Elevación (hipsométrica)</option><option value="slope">Pendiente</option>
                  <option value="overlay" disabled={!ov}>NDVI / cambio (observado){ov ? "" : " — elija un raster abajo"}</option>
                  <option value="scenario" disabled={!grid}>Escenario (SIMULACIÓN){grid ? "" : " — calcule uno primero"}</option></select></div>
            </div>
            <Legend layer={layer} min={elev?.min} max={elev?.max} grid={grid} ov={ov} />
            {mesh && <OverlayPicker dem={sel} bbox={mesh.bbox} onOverlay={(g) => { setOv(g); if (g) setLayer("overlay"); else setLayer((l) => (l === "overlay" ? "elevation" : l)); }} />}
            <p className="small muted" style={{ margin: 0 }}>{sel.extra.attribution}</p>
          </div>

          <div className="stack">
            <div className="card">
              <h2>Resultados</h2>
              {elev && <p className="small">Elevación: mínima <strong>{elev.min} m</strong>, máxima <strong>{elev.max} m</strong>, media {elev.mean} m.</p>}
              <p className="small">Pendiente media {sel.extra.slope_stats.mean_deg}° (máx. {sel.extra.slope_stats.max_deg}°).</p>
              {mesh && mesh.valid_pct !== undefined && <p className="small">Celdas con dato real: <strong>{mesh.valid_pct} %</strong>{mesh.valid_pct < 100 && " (las celdas sin dato se dibujan en gris)"}.</p>}
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
            <SimulationPanel dem={sel} bbox={mesh?.bbox ?? sel.bbox} lon={lon} lat={lat} writable={writable}
              onGrid={(g) => { setGrid(g); if (g) setLayer("scenario"); else setLayer((l) => (l === "scenario" ? "elevation" : l)); }} />
          </div>
        </div>
      )}
    </div>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return <span><span style={{ display: "inline-block", width: 12, height: 12, background: color, marginRight: 4, verticalAlign: "middle" }} />{label}</span>;
}

function Legend({ layer, min, max, grid, ov }: { layer: Layer; min?: number; max?: number; grid?: ScenarioGrid | null; ov?: OverlayGrid | null }) {
  if (layer === "overlay" && ov) {
    if (ov.kind === "ndvi") {
      return (
        <div aria-label="Leyenda de NDVI">
          <div style={{ height: 12, background: `linear-gradient(to right, ${NDVI_STOPS.map(([t, c]) => `${c} ${((t + 1) / 2) * 100}%`).join(", ")})`, borderRadius: 4 }} />
          <div className="row small" style={{ justifyContent: "space-between" }}><span>-1</span><span>gris = sin dato · cobertura {ov.coverage_pct} %</span><span>1</span></div>
        </div>
      );
    }
    return (
      <div className="row small" style={{ flexWrap: "wrap", gap: 12 }} aria-label="Leyenda de cambio de NDVI">
        {CHANGE_CLASSES.map((c) => <Swatch key={c.value} color={c.color} label={c.label} />)}
        <Swatch color={NO_DATA_COLOR} label={`sin dato · cobertura ${ov.coverage_pct} %`} />
      </div>
    );
  }
  if (layer === "scenario" && grid) {
    if (grid.kind === "susceptibilidad") {
      return (
        <div className="row small" style={{ flexWrap: "wrap", gap: 12 }} aria-label="Leyenda de susceptibilidad (simulación)">
          {SUSC_CLASSES.map((c) => <Swatch key={c.value} color={c.color} label={`${c.label} (índice heurístico)`} />)}
          <Swatch color={NO_DATA_COLOR} label="sin dato" />
        </div>
      );
    }
    return (
      <div aria-label="Leyenda de profundidad de inundación (simulación)">
        <div style={{ height: 12, background: `linear-gradient(to right, ${FLOOD_STOPS[0][1]}, ${FLOOD_STOPS[1][1]})`, borderRadius: 4 }} />
        <div className="row small" style={{ justifyContent: "space-between" }}><span>0 m (somera)</span><span>fuera del agua: color de elevación · gris = sin dato</span><span>{grid.max_depth_m ?? "—"} m</span></div>
      </div>
    );
  }
  if (layer === "slope") {
    return (
      <div className="row small" style={{ flexWrap: "wrap", gap: 12 }} aria-label="Leyenda de pendiente">
        {SLOPE_CLASSES.map((c) => (
          <span key={c.label}><span style={{ display: "inline-block", width: 12, height: 12, background: c.color, marginRight: 4, verticalAlign: "middle" }} />{c.label}</span>
        ))}
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: NO_DATA_COLOR, marginRight: 4, verticalAlign: "middle" }} />sin dato</span>
      </div>
    );
  }
  const grad = `linear-gradient(to right, ${HYPSO_STOPS.map(([t, c]) => `${c} ${t * 100}%`).join(", ")})`;
  return (
    <div aria-label="Leyenda de elevación">
      <div style={{ height: 12, background: grad, borderRadius: 4 }} />
      <div className="row small" style={{ justifyContent: "space-between" }}><span>{min ?? "—"} m</span><span>gris = sin dato</span><span>{max ?? "—"} m</span></div>
    </div>
  );
}

// ---------------------------------------------------------------- Escenarios simplificados (SIMULACIÓN)
interface RasterLite { id: string; data_type: string; title: string; bbox: number[] | null }
interface ScenarioRecord { id: string; title: string; extra: { kind: string; stats: Record<string, unknown>; disclaimer: string; params: Record<string, unknown> } }
interface ClassStat { class: number; label: string; km2: number; pct: number }
interface Metrics { classes?: ClassStat[]; valid_km2?: number; flooded_km2?: number; volume_m3?: number; max_depth_m?: number; touches_dem_border?: boolean }
interface CompareOut {
  banner: string; saved: boolean;
  observed: { label: string; area_km2: number; elevation: { min: number; max: number; mean: number }; slope_stats: { mean_deg: number | null } };
  scenarios: { label: string; kind: string; params: Record<string, number>; metrics: Metrics; disclaimer: string }[];
}
type SimKind = "susceptibilidad" | "inundacion_demostrativa";
const SUSC_TXT = "Índice heurístico NO calibrado; no predice deslizamientos ni fechas. Evaluado con el inventario real de INGEMMET (181 movimientos en masa, Huaraz): la pendiente sola NO discrimina los eventos (AUC 0,49, igual al azar). No usar como indicador de susceptibilidad.";
const FLOOD_TXT = "Modelo de bañera simplificado: ignora caudal, cauce, rugosidad, tiempo y drenaje; no es una simulación hidráulica.";
const overlaps = (a: number[] | null, b: number[]) => !!a && a.length === 4 && a[2] > b[0] && a[0] < b[2] && a[3] > b[1] && a[1] < b[3];

function SimulationPanel({ dem, bbox, lon, lat, writable, onGrid }: {
  dem: TerrainRecord; bbox: number[]; lon: string; lat: string; writable: boolean; onGrid: (g: ScenarioGrid | null) => void;
}) {
  const [kind, setKind] = useState<SimKind>("susceptibilidad");
  const [wSlope, setWSlope] = useState(0.6);
  const [tMid, setTMid] = useState("0.33");
  const [tHigh, setTHigh] = useState("0.66");
  const [ndviId, setNdviId] = useState("");
  const [rise, setRise] = useState(5);
  const [variants, setVariants] = useState("0.5, 0.66, 0.8");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<ScenarioRecord | null>(null);
  const [cmp, setCmp] = useState<CompareOut | null>(null);
  const rasters = useApi<RasterLite[]>("/api/environmental/rasters");
  const saved = useApi<ScenarioRecord[]>(`/api/simulation/scenarios?dem_id=${dem.id}`);
  const ndvis = (rasters.data ?? []).filter((r) => r.data_type === "raster_ndvi" && overlaps(r.bbox, bbox));
  const susc = kind === "susceptibilidad";

  useEffect(() => { setCurrent(null); setCmp(null); onGrid(null); }, [dem.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  const suscParams = () => ({ w_pendiente: wSlope, w_vegetacion: Number((1 - wSlope).toFixed(4)), umbral_medio: Number(tMid), umbral_alto: Number(tHigh) });

  async function showGrid(id: string) {
    onGrid(await api<ScenarioGrid>(`/api/simulation/scenarios/${id}/grid?max_size=256`));
  }

  async function calculate() {
    setBusy(true); setError(null); setCmp(null);
    try {
      const rec = susc
        ? await post<ScenarioRecord>("/api/simulation/susceptibility", { dem_id: dem.id, ndvi_id: ndviId || null, ...suscParams() })
        : await post<ScenarioRecord>("/api/simulation/flood", { dem_id: dem.id, lon: Number(lon), lat: Number(lat), rise_m: rise });
      setCurrent(rec);
      await showGrid(rec.id);
      saved.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function compare() {
    setBusy(true); setError(null);
    try {
      const vals = variants.split(",").map((v) => Number(v.trim())).filter((v) => Number.isFinite(v));
      const configs = susc
        ? vals.map((v) => ({ kind, label: `Umbral alto ${v}`, ...suscParams(), umbral_alto: v }))
        : vals.map((v) => ({ kind, label: `Subida +${v} m`, lon: Number(lon), lat: Number(lat), rise_m: v }));
      setCmp(await post<CompareOut>("/api/simulation/compare", { dem_id: dem.id, ndvi_id: susc ? ndviId || null : null, configs }));
    } catch (e) { setError((e as Error).message); setCmp(null); } finally { setBusy(false); }
  }

  const st = current?.extra.stats as Metrics | undefined;
  const pct = (m: Metrics, k: number) => m.classes?.find((c) => c.class === k);
  return (
    <div className="card stack">
      <h2>4. Escenarios simulados</h2>
      <Notice kind="dev"><strong>{BANNER}</strong></Notice>
      {!writable && <p className="small muted">Solo analistas pueden calcular escenarios; puede ver los guardados.</p>}
      {writable && (
        <>
          <div className="field"><label htmlFor="simk">Tipo de escenario</label>
            <select id="simk" value={kind} onChange={(e) => { setKind(e.target.value as SimKind); setVariants(e.target.value === "susceptibilidad" ? "0.5, 0.66, 0.8" : "2, 5, 10"); setCmp(null); }}>
              <option value="susceptibilidad">Susceptibilidad heurística a deslizamientos</option>
              <option value="inundacion_demostrativa">Inundación por subida de nivel (bañera)</option></select></div>
          {susc ? (
            <div className="stack">
              <div className="field"><label htmlFor="simw">Peso de la pendiente: {wSlope.toFixed(2)} · peso de la vegetación (1 − NDVI): {(1 - wSlope).toFixed(2)}{!ndviId && " (sin NDVI se usa solo la pendiente)"}</label>
                <input id="simw" type="range" min={0} max={1} step={0.05} value={wSlope} onChange={(e) => setWSlope(Number(e.target.value))} /></div>
              <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
                <div className="field"><label htmlFor="simtm">Umbral medio</label><input id="simtm" type="number" min={0.01} max={0.98} step={0.01} value={tMid} onChange={(e) => setTMid(e.target.value)} /></div>
                <div className="field"><label htmlFor="simth">Umbral alto</label><input id="simth" type="number" min={0.02} max={0.99} step={0.01} value={tHigh} onChange={(e) => setTHigh(e.target.value)} /></div>
                <div className="field"><label htmlFor="simnd">NDVI (opcional)</label>
                  <select id="simnd" value={ndviId} onChange={(e) => setNdviId(e.target.value)}>
                    <option value="">Sin NDVI</option>
                    {ndvis.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}</select></div>
              </div>
              {ndvis.length === 0 && <p className="small muted" style={{ margin: 0 }}>No hay NDVI que se superponga a este terreno (se calcula en Predicción Ambiental).</p>}
            </div>
          ) : (
            <div className="stack">
              <p className="small muted" style={{ margin: 0 }}>Punto de partida del agua: longitud {lon}, latitud {lat} (los campos del escenario 3).</p>
              <div className="field"><label htmlFor="simr">Subida de nivel: {rise} m</label>
                <input id="simr" type="range" min={0.5} max={50} step={0.5} value={rise} onChange={(e) => setRise(Number(e.target.value))} /></div>
            </div>
          )}
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <button className="btn" disabled={busy} onClick={calculate}>{busy ? "Calculando…" : "Calcular escenario"}</button>
            <div className="field"><label htmlFor="simv">Comparar {susc ? "umbrales altos" : "subidas (m)"} (2 a 4, separados por coma)</label>
              <input id="simv" value={variants} onChange={(e) => setVariants(e.target.value)} /></div>
            <button className="btn" disabled={busy} onClick={compare}>Comparar escenarios</button>
          </div>
        </>
      )}
      <ErrorText error={error} />

      {current && st && (
        <div className="stack">
          <p className="small" style={{ margin: 0 }}><strong>{current.title}</strong></p>
          {current.extra.kind === "susceptibilidad" ? (
            <div className="table-wrap"><table>
              <thead><tr><th>Clase (simulada)</th><th>Área km²</th><th>% del área con dato</th></tr></thead>
              <tbody>{st.classes?.map((c) => <tr key={c.class}><td>{c.label}</td><td>{c.km2}</td><td>{c.pct}</td></tr>)}</tbody>
            </table></div>
          ) : (
            <p className="small" style={{ margin: 0 }}>Área inundada hipotética <strong>{st.flooded_km2} km²</strong> · volumen aprox. <strong>{Number(st.volume_m3).toLocaleString("es-PE")} m³</strong> · profundidad máx. <strong>{st.max_depth_m} m</strong>
              {st.touches_dem_border && " · el agua llega al borde del DEM: el resultado está truncado"}.</p>
          )}
          <Notice kind="info"><strong>Limitación:</strong> {current.extra.disclaimer}</Notice>
        </div>
      )}

      {cmp && (
        <div className="stack">
          <h3 style={{ margin: 0 }}>Comparación (no se guarda)</h3>
          <div className="table-wrap"><table>
            {cmp.scenarios[0]?.kind === "susceptibilidad" ? (
              <thead><tr><th>Escenario</th><th>Bajo km²</th><th>Medio km²</th><th>Alto km²</th><th>Alto %</th></tr></thead>
            ) : (
              <thead><tr><th>Escenario</th><th>Área inundada km²</th><th>Volumen m³</th><th>Prof. máx. m</th><th>Borde DEM</th></tr></thead>
            )}
            <tbody>
              <tr><td><strong>Estado actual (observado)</strong></td>
                <td colSpan={4} className="small">Dato real: elevación {cmp.observed.elevation.min}–{cmp.observed.elevation.max} m · pendiente media {cmp.observed.slope_stats.mean_deg}° · {cmp.observed.area_km2} km².</td></tr>
              {cmp.scenarios.map((r) => r.kind === "susceptibilidad" ? (
                <tr key={r.label}><td>{r.label} <span className="badge badge-sim">SIMULACIÓN</span></td>
                  <td>{pct(r.metrics, 1)?.km2}</td><td>{pct(r.metrics, 2)?.km2}</td><td>{pct(r.metrics, 3)?.km2}</td><td>{pct(r.metrics, 3)?.pct}</td></tr>
              ) : (
                <tr key={r.label}><td>{r.label} <span className="badge badge-sim">SIMULACIÓN</span></td>
                  <td>{r.metrics.flooded_km2}</td><td>{Number(r.metrics.volume_m3).toLocaleString("es-PE")}</td>
                  <td>{r.metrics.max_depth_m}</td><td>{r.metrics.touches_dem_border ? "sí (truncado)" : "no"}</td></tr>
              ))}
            </tbody>
          </table></div>
          <p className="small muted" style={{ margin: 0 }}>{cmp.scenarios[0]?.kind === "susceptibilidad" ? SUSC_TXT : FLOOD_TXT}</p>
        </div>
      )}

      {(saved.data?.length ?? 0) > 0 && (
        <div>
          <h3>Escenarios guardados para este terreno</h3>
          <div className="table-wrap"><table><tbody>{saved.data!.map((r) => (
            <tr key={r.id}><td className="small">{r.title}</td>
              <td><button className="btn" onClick={() => showGrid(r.id).catch((e: Error) => setError(e.message))}>Ver en el visor</button></td></tr>
          ))}</tbody></table></div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Capas NDVI / cambio (observadas) sobre el terreno
interface OverlayGrid extends ScenarioGrid { note: string; coverage_pct: number; title: string }

function OverlayPicker({ dem, bbox, onOverlay }: { dem: TerrainRecord; bbox: number[]; onOverlay: (g: OverlayGrid | null) => void }) {
  const rasters = useApi<RasterLite[]>("/api/environmental/rasters");
  const [recId, setRecId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const options = (rasters.data ?? []).filter((r) => overlaps(r.bbox, bbox));
  useEffect(() => { setRecId(""); }, [dem.id]);

  async function draw() {
    if (!recId) return;
    setBusy(true); setError(null);
    try { onOverlay(await api<OverlayGrid>(`/api/simulation/overlay?dem_id=${dem.id}&record_id=${recId}&max_size=256`)); }
    catch (e) { setError((e as Error).message); onOverlay(null); } finally { setBusy(false); }
  }
  return (
    <div className="stack">
      <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "end" }}>
        <div className="field"><label htmlFor="ovsel">Capa observada (NDVI o cambio de NDVI)</label>
          <select id="ovsel" value={recId} onChange={(e) => setRecId(e.target.value)}>
            <option value="">{options.length ? "Elija un raster" : "No hay rasters que se superpongan"}</option>
            {options.map((r) => <option key={r.id} value={r.id}>{r.data_type === "raster_cambio" ? "Cambio · " : "NDVI · "}{r.title}</option>)}</select></div>
        <button className="btn" disabled={!recId || busy} onClick={draw}>{busy ? "Preparando…" : "Dibujar sobre el terreno"}</button>
      </div>
      <ErrorText error={error} />
    </div>
  );
}
