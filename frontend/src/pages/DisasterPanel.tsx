import { useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";

interface TerrainLite { id: string; title: string; bbox: number[] }
interface Inventory { id: string; title: string; bbox: number[]; received_at: string; source: string; license: string; eventos: number; tipos_peligro: Record<string, number> }
interface Conf { vp: number; fp: number; fn: number; vn: number }
interface Cv {
  auc_mean: number | null; auc_sd: number | null; folds: number;
  auc_ic95_bloques?: number[] | null; pr_auc?: number; pr_auc_azar?: number; brier?: number; confusion?: Conf;
  precision?: number; recall?: number; f1?: number; auc_semillas?: { media: number | null; sd: number | null; n: number };
}
interface Variant {
  n_presencias: number; n_ausencias: number; auc_heuristico_pendiente: number; auc_solo_elevacion_baja: number;
  regresion_logistica: { espacial: Cv; aleatoria_referencia: Cv }; bosque_aleatorio: { espacial: Cv; aleatoria_referencia: Cv };
  regresion_logistica_base?: { espacial: Cv };
  regresion_logistica_geo?: { espacial: Cv };
  regresion_logistica_ndvi?: { espacial: Cv };
  puntos_sin_dato_descartados?: { eventos: number; ausencias: number };
  por_variable?: Record<string, { auc: number; auc_discriminante: number; direccion: string; mediana_eventos: number; mediana_ausencias: number }>;
  elevacion_media_eventos: number; elevacion_media_ausencias: number; rango_elevacion_m?: number[];
}
interface Assessment {
  ausencias_libres: Variant; ausencias_mismo_rango_elevacion: Variant; conclusion_automatica: string[];
  geologia_razon_frecuencia?: Record<string, FreqRow[]>;
}
interface Report extends Assessment {
  advertencias: string[]; interpretacion_auc: string; descartados: Record<string, number>; dataset_record_id?: string; simulado?: boolean;
  por_proceso?: Record<string, Assessment>; procesos_omitidos_por_pocos_eventos?: Record<string, unknown>; nota_codigos?: string;
  protocolo?: {
    tamano_bloque_km: number[]; zona_exclusion_m: number; semillas_ausencias: number; pendiente: string[];
    bloques_automaticos?: boolean; variograma?: { alcance_mediano_m: number | null; bloque_cubre_alcance: boolean };
  };
  variables_descripcion?: Record<string, string>;
  interpretacion_metricas?: Record<string, string>;
}
interface GeoLayer { id: string; title: string; capa: string; campo: string; clases: Record<string, number>; received_at: string; license: string }
interface FreqRow { clase: string; pct_area: number; pct_eventos: number; razon_frecuencia: number }
interface RunRow { id: string; run_type: string; status: string; started_at: string; parameters: Record<string, unknown>; result_summary: (Report & { error?: string }) | null }

const ANCASH_HUARAZ = "-77.75,-9.78,-77.25,-9.28";
const d2 = (v: number) => v.toFixed(2).replace(".", ",");
const cv = (c: Cv) => (c.auc_mean == null ? "—" : `${d2(c.auc_mean)} ± ${d2(c.auc_sd ?? 0)}`);

/** NEURODISASTER: inventario real de INGEMMET y validación espacial de la susceptibilidad. */
export function DisasterPanel() {
  const terrains = useApi<TerrainLite[]>("/api/neuro3d/terrains");
  const inventories = useApi<Inventory[]>("/api/disasters/inventories");
  const runs = useApi<RunRow[]>("/api/disasters/runs");
  const geoLayers = useApi<GeoLayer[]>("/api/disasters/geology");
  const [geoSel, setGeoSel] = useState<string[]>([]);
  const ndvis = useApi<{ id: string; title: string; bbox: number[] }[]>("/api/neurodata/records?data_type=raster_ndvi");
  const [ndviId, setNdviId] = useState("");
  const [capa, setCapa] = useState("litologia");
  const writable = canWrite(session.user());
  const [bbox, setBbox] = useState(ANCASH_HUARAZ);
  const [demId, setDemId] = useState("");
  const [invId, setInvId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const dems = terrains.data ?? [], invs = inventories.data ?? [];
  useEffect(() => { if (!demId && dems.length) setDemId(dems[0].id); }, [dems, demId]);
  useEffect(() => { if (!invId && invs.length) setInvId(invs[0].id); }, [invs, invId]);

  async function importInv() {
    setBusy("import"); setError(null);
    try {
      const b = bbox.split(",").map((v) => Number(v.trim()));
      if (b.length !== 4 || b.some((v) => !Number.isFinite(v))) throw new Error("Recorte inválido: minLon,minLat,maxLon,maxLat.");
      const r = await post<Inventory & { id: string }>("/api/disasters/inventory/import", { bbox: b });
      inventories.reload(); runs.reload(); setInvId(r.id);
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  async function importGeo() {
    setBusy("geo"); setError(null);
    try {
      const b = bbox.split(",").map((v) => Number(v.trim()));
      if (b.length !== 4 || b.some((v) => !Number.isFinite(v))) throw new Error("Recorte inválido: minLon,minLat,maxLon,maxLat.");
      await post("/api/disasters/geology/import", { capa, bbox: b });
      geoLayers.reload(); runs.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  async function validate() {
    setBusy("validate"); setError(null);
    try {
      const r = await post<Report>("/api/disasters/susceptibility/validate", { dem_id: demId, inventory_id: invId, geology_ids: geoSel, ndvi_id: ndviId || null });
      setReport(r); runs.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  return (
    <div className="stack">
      <Notice kind="dev"><strong>Inventario de eventos REALES de INGEMMET (GEOCATMIN).</strong> La fecha de cada evento es desconocida (FECHA parece la del estudio). Licencia no declarada por el servicio:
        uso interno de investigación, citando a INGEMMET y sin redistribuir. El inventario es incompleto y está sesgado hacia zonas pobladas y vías.</Notice>

      {writable && (
        <div className="card stack">
          <h2>1. Importar inventario</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <div className="field"><label htmlFor="dbb">Recorte (minLon,minLat,maxLon,maxLat; máx. 2,5° por lado)</label>
              <input id="dbb" value={bbox} onChange={(e) => setBbox(e.target.value)} style={{ minWidth: 280 }} /></div>
            <button className="btn" disabled={busy !== null} onClick={importInv}>{busy === "import" ? "Consultando INGEMMET…" : "Importar eventos"}</button>
          </div>
          <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <div className="field"><label htmlFor="dcapa">Capa geológica INGEMMET (mismo recorte; uso interno, sin licencia abierta)</label>
              <select id="dcapa" value={capa} onChange={(e) => setCapa(e.target.value)}>
                <option value="litologia">Litología 1:50 000 (TIPO_UNIDAD)</option>
                <option value="geomorfologia">Geomorfología (SUBUNIDAD)</option>
              </select></div>
            <button className="btn" disabled={busy !== null} onClick={importGeo}>{busy === "geo" ? "Consultando INGEMMET…" : "Importar capa"}</button>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Inventarios importados</h2>
        {inventories.loading && !inventories.data && <Loading what="inventarios" />}
        {inventories.data?.length === 0 && <p className="muted small">Aún no hay inventarios importados.</p>}
        <div className="table-wrap"><table><tbody>{invs.map((i) => (
          <tr key={i.id}><td className="small">{i.title} <span className="badge">REAL</span></td>
            <td className="small">{Object.entries(i.tipos_peligro ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</td>
            <td className="small">{fmtDate(i.received_at)}</td></tr>
        ))}</tbody></table></div>
      </div>

      {writable && invs.length > 0 && (
        <div className="card stack">
          <h2>2. Validar la susceptibilidad con los eventos</h2>
          {dems.length === 0 ? (
            <Notice kind="info">Descargue primero un terreno real (DEM) del mismo recorte en NEURO 3D LAB.</Notice>
          ) : (
            <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <div className="field"><label htmlFor="ddem">Terreno (DEM)</label>
                <select id="ddem" value={demId} onChange={(e) => setDemId(e.target.value)}>{dems.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></div>
              <div className="field"><label htmlFor="dinv">Inventario</label>
                <select id="dinv" value={invId} onChange={(e) => setInvId(e.target.value)}>{invs.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></div>
              {(geoLayers.data ?? []).length > 0 && (
                <fieldset className="field" style={{ border: 0, padding: 0 }}><legend className="small">Capas geológicas (opcional, máx. 2)</legend>
                  {(geoLayers.data ?? []).map((g) => (
                    <label key={g.id} className="small" style={{ display: "block", fontWeight: 400 }}>
                      <input type="checkbox" checked={geoSel.includes(g.id)} disabled={!geoSel.includes(g.id) && geoSel.length >= 2}
                        onChange={(e) => setGeoSel(e.target.checked ? [...geoSel, g.id] : geoSel.filter((x) => x !== g.id))} /> {g.title}
                    </label>))}
                </fieldset>
              )}
              {(ndvis.data ?? []).length > 0 && (
                <div className="field"><label htmlFor="dndvi">NDVI candidato (opcional; misma malla que el DEM)</label>
                  <select id="dndvi" value={ndviId} onChange={(e) => setNdviId(e.target.value)}>
                    <option value="">Sin NDVI</option>{(ndvis.data ?? []).map((n) => <option key={n.id} value={n.id}>{n.title}</option>)}
                  </select></div>
              )}
              <button className="btn" disabled={busy !== null || !demId || !invId} onClick={validate}>{busy === "validate" ? "Validando (≈1–2 min)…" : "Validar"}</button>
            </div>
          )}
        </div>
      )}
      <ErrorText error={error} />

      {report && <ReportCard r={report} />}

      <div className="card">
        <h2>Ejecuciones</h2>
        {runs.data?.length === 0 && <p className="muted small">Sin ejecuciones.</p>}
        <div className="table-wrap"><table><tbody>{runs.data?.map((x) => (
          <tr key={x.id}><td className="small">{x.run_type}</td><td className="small">{x.status}</td><td className="small">{fmtDate(x.started_at)}</td>
            <td>{x.run_type === "validacion_susceptibilidad" && x.status === "ok" && x.result_summary &&
              <button className="btn" onClick={() => setReport(x.result_summary)}>Ver</button>}
              {x.result_summary?.error && <span className="small muted">{x.result_summary.error}</span>}</td></tr>
        ))}</tbody></table></div>
      </div>
    </div>
  );
}

function ReportCard({ r }: { r: Report }) {
  const p = r.protocolo;
  return (
    <div className="card stack">
      <h2>Informe de validación {r.simulado && <span className="badge badge-sim">SIMULADO</span>}</h2>
      <p className="small" style={{ margin: 0 }}>{r.interpretacion_auc}</p>
      {p && <p className="small muted" style={{ margin: 0 }}>Protocolo: bloques de ≈{p.tamano_bloque_km.map((v) => d2(v)).join(" × ")} km,
        zona de exclusión de {p.zona_exclusion_m} m entre entrenamiento y prueba, {p.semillas_ausencias} sorteos de pseudo-ausencias.
        {p.variograma?.alcance_mediano_m != null && <> Bloques {p.bloques_automaticos ? "elegidos automáticamente" : "fijados a mano"}; alcance
        mediano del variograma de las variables ≈{d2(p.variograma.alcance_mediano_m / 1000)} km ({p.variograma.bloque_cubre_alcance ? "el bloque lo cubre" : "el bloque NO lo cubre: puede haber fuga espacial"}).</>}
        {" "}Pendiente de mejorar: {p.pendiente.join("; ")}.</p>}
      {r.variables_descripcion && <ul className="small muted" style={{ margin: 0 }}>{Object.entries(r.variables_descripcion).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>}
      <AssessmentBlock title="Todos los movimientos en masa" a={r} />
      {r.por_proceso && Object.keys(r.por_proceso).length > 0 && (
        <>
          <h3 style={{ margin: "8px 0 0" }}>Por tipo de proceso (código INGEMMET)</h3>
          {r.nota_codigos && <p className="small muted" style={{ margin: 0 }}>{r.nota_codigos}</p>}
          {Object.entries(r.por_proceso).map(([code, a]) => <AssessmentBlock key={code} title={`Código ${code}`} a={a} />)}
        </>
      )}
      {r.procesos_omitidos_por_pocos_eventos && Object.keys(r.procesos_omitidos_por_pocos_eventos).length > 0 && (
        <p className="small muted" style={{ margin: 0 }}>Omitidos por pocos eventos: {Object.entries(r.procesos_omitidos_por_pocos_eventos).map(([k, v]) => `${k} (${String(v)})`).join(", ")}.</p>
      )}
      {r.interpretacion_metricas && <ul className="small muted" style={{ margin: 0 }}>{Object.entries(r.interpretacion_metricas).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>}
      <Notice kind="info"><ul className="small" style={{ margin: 0 }}>{r.advertencias.map((w) => <li key={w}>{w}</li>)}</ul></Notice>
      {r.dataset_record_id && <p className="small muted" style={{ margin: 0 }}>Dataset para NEURAL TRAINING registrado en NEURODATA (columna objetivo «evento»).
        Tiene coordenadas: NEURAL TRAINING no permitirá validar un modelo con un corte aleatorio. Ningún modelo queda validado automáticamente.</p>}
    </div>
  );
}

function AssessmentBlock({ title, a }: { title: string; a: Assessment }) {
  const x = a.ausencias_libres, y = a.ausencias_mismo_rango_elevacion;
  const ic = (c: Cv) => (c.auc_ic95_bloques ? `${d2(c.auc_ic95_bloques[0])}–${d2(c.auc_ic95_bloques[1])}` : "—");
  const seeds = (c: Cv) => (c.auc_semillas?.media == null ? "—" : `${d2(c.auc_semillas.media)} ± ${d2(c.auc_semillas.sd ?? 0)} (n=${c.auc_semillas.n})`);
  const opt = (v?: number) => (v == null ? "—" : d2(v));
  const conf = (c: Cv) => (c.confusion ? `VP ${c.confusion.vp} · FP ${c.confusion.fp} · FN ${c.confusion.fn} · VN ${c.confusion.vn}` : "—");
  const lrX = x.regresion_logistica.espacial, lrY = y.regresion_logistica.espacial;
  const rows: [string, string, string][] = [
    ["Índice heurístico (solo pendiente)", d2(x.auc_heuristico_pendiente), d2(y.auc_heuristico_pendiente)],
    ["Solo elevación", d2(x.auc_solo_elevacion_baja), d2(y.auc_solo_elevacion_baja)],
    ...(x.regresion_logistica_base && y.regresion_logistica_base
      ? [["Regresión logística · solo pendiente y elevación (base)", cv(x.regresion_logistica_base.espacial), cv(y.regresion_logistica_base.espacial)] as [string, string, string]]
      : []),
    ["Regresión logística · AUC espacial por pliegue", cv(lrX), cv(lrY)],
    ...(x.regresion_logistica_ndvi && y.regresion_logistica_ndvi
      ? [["Regresión logística · topografía + NDVI (mismos puntos)", cv(x.regresion_logistica_ndvi.espacial), cv(y.regresion_logistica_ndvi.espacial)] as [string, string, string],
         ["  · IC 95 % (bootstrap de bloques)", ic(x.regresion_logistica_ndvi.espacial), ic(y.regresion_logistica_ndvi.espacial)] as [string, string, string]]
      : []),
    ...(x.regresion_logistica_geo && y.regresion_logistica_geo
      ? [["Regresión logística · topografía + geología", cv(x.regresion_logistica_geo.espacial), cv(y.regresion_logistica_geo.espacial)] as [string, string, string],
         ["  · IC 95 % (bootstrap de bloques)", ic(x.regresion_logistica_geo.espacial), ic(y.regresion_logistica_geo.espacial)] as [string, string, string]]
      : []),
    ["  · IC 95 % (bootstrap de bloques)", ic(lrX), ic(lrY)],
    ["  · Variación entre sorteos de ausencias", seeds(lrX), seeds(lrY)],
    ["  · PR-AUC (azar)", `${opt(lrX.pr_auc)} (${opt(lrX.pr_auc_azar)})`, `${opt(lrY.pr_auc)} (${opt(lrY.pr_auc_azar)})`],
    ["  · Precisión / recall / F1", `${opt(lrX.precision)} / ${opt(lrX.recall)} / ${opt(lrX.f1)}`, `${opt(lrY.precision)} / ${opt(lrY.recall)} / ${opt(lrY.f1)}`],
    ["  · Matriz de confusión", conf(lrX), conf(lrY)],
    ["  · Brier (solo comparativo)", opt(lrX.brier), opt(lrY.brier)],
    ["Bosque aleatorio · AUC espacial por pliegue", cv(x.bosque_aleatorio.espacial), cv(y.bosque_aleatorio.espacial)],
    ["  · IC 95 % (bootstrap de bloques)", ic(x.bosque_aleatorio.espacial), ic(y.bosque_aleatorio.espacial)],
    ["Regresión logística · aleatoria (solo referencia)", cv(x.regresion_logistica.aleatoria_referencia), cv(y.regresion_logistica.aleatoria_referencia)],
  ];
  return (
    <div className="stack" style={{ borderTop: "1px solid var(--border, #ddd)", paddingTop: 8 }}>
      <strong>{title}</strong>
      <p className="small" style={{ margin: 0 }}>{x.n_presencias} eventos y {x.n_ausencias} pseudo-ausencias por sorteo.</p>
      <div className="table-wrap"><table>
        <thead><tr><th>Métrica</th><th>Ausencias libres</th><th>Ausencias en la franja de altura {y.rango_elevacion_m ? `${y.rango_elevacion_m[0]}–${y.rango_elevacion_m[1]} m` : ""}</th></tr></thead>
        <tbody>{rows.map(([k, v1, v2]) => <tr key={k}><td className="small" style={{ whiteSpace: "pre" }}>{k}</td><td>{v1}</td><td>{v2}</td></tr>)}</tbody>
      </table></div>
      {y.por_variable && (
        <div className="table-wrap"><table>
          <thead><tr><th>Variable sola (franja de altura)</th><th>AUC</th><th>Dirección</th><th>Mediana eventos / ausencias</th></tr></thead>
          <tbody>{Object.entries(y.por_variable).map(([k, u]) => (
            <tr key={k}><td className="small">{k}</td><td>{d2(u.auc_discriminante)}</td><td className="small">{u.direccion}</td>
              <td className="small">{d2(u.mediana_eventos)} / {d2(u.mediana_ausencias)}</td></tr>))}</tbody>
        </table></div>
      )}
      {a.geologia_razon_frecuencia && Object.entries(a.geologia_razon_frecuencia).map(([capaN, rowsF]) => (
        <div className="table-wrap" key={capaN}><table>
          <thead><tr><th>{capaN} (descriptivo, todos los eventos)</th><th>% área</th><th>% eventos</th><th>Razón de frecuencia</th></tr></thead>
          <tbody>{rowsF.filter((f) => f.pct_area >= 2).map((f) => (
            <tr key={f.clase}><td className="small">{f.clase}</td><td>{d2(f.pct_area)}</td><td>{d2(f.pct_eventos)}</td><td>{d2(f.razon_frecuencia)}</td></tr>))}</tbody>
        </table></div>
      ))}
      <ul className="small" style={{ margin: 0 }}>{a.conclusion_automatica.map((c) => <li key={c}>{c}</li>)}</ul>
    </div>
  );
}
