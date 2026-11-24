import { useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";

interface TerrainLite { id: string; title: string; bbox: number[] }
interface Inventory { id: string; title: string; bbox: number[]; received_at: string; source: string; license: string; eventos: number; tipos_peligro: Record<string, number> }
interface Cv { auc_mean: number | null; auc_sd: number | null; folds: number }
interface Variant {
  n_presencias: number; n_ausencias: number; auc_heuristico_pendiente: number; auc_solo_elevacion_baja: number;
  regresion_logistica: { espacial: Cv; aleatoria_referencia: Cv }; bosque_aleatorio: { espacial: Cv; aleatoria_referencia: Cv };
  elevacion_media_eventos: number; elevacion_media_ausencias: number; rango_elevacion_m?: number[];
}
interface Report {
  ausencias_libres: Variant; ausencias_mismo_rango_elevacion: Variant; conclusion_automatica: string[];
  advertencias: string[]; interpretacion_auc: string; descartados: Record<string, number>; dataset_record_id?: string; simulado?: boolean;
}
interface RunRow { id: string; run_type: string; status: string; started_at: string; parameters: Record<string, unknown>; result_summary: (Report & { error?: string }) | null }

const ANCASH_HUARAZ = "-77.75,-9.78,-77.25,-9.28";
const cv = (c: Cv) => (c.auc_mean == null ? "—" : `${c.auc_mean.toFixed(2)} ± ${(c.auc_sd ?? 0).toFixed(2)}`);

/** NEURODISASTER: inventario real de INGEMMET y validación espacial de la susceptibilidad. */
export function DisasterPanel() {
  const terrains = useApi<TerrainLite[]>("/api/neuro3d/terrains");
  const inventories = useApi<Inventory[]>("/api/disasters/inventories");
  const runs = useApi<RunRow[]>("/api/disasters/runs");
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

  async function validate() {
    setBusy("validate"); setError(null);
    try {
      const r = await post<Report>("/api/disasters/susceptibility/validate", { dem_id: demId, inventory_id: invId });
      setReport(r); runs.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  return (
    <div className="stack">
      <Notice kind="dev"><strong>Inventario de eventos REALES de INGEMMET (GEOCATMIN, 2013).</strong> Licencia no declarada por el servicio:
        uso interno de investigación, citando a INGEMMET y sin redistribuir. El inventario es incompleto y está sesgado hacia zonas pobladas y vías.</Notice>

      {writable && (
        <div className="card stack">
          <h2>1. Importar inventario</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <div className="field"><label htmlFor="dbb">Recorte (minLon,minLat,maxLon,maxLat; máx. 2,5° por lado)</label>
              <input id="dbb" value={bbox} onChange={(e) => setBbox(e.target.value)} style={{ minWidth: 280 }} /></div>
            <button className="btn" disabled={busy !== null} onClick={importInv}>{busy === "import" ? "Consultando INGEMMET…" : "Importar eventos"}</button>
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
              <button className="btn" disabled={busy !== null || !demId || !invId} onClick={validate}>{busy === "validate" ? "Validando…" : "Validar"}</button>
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
  const a = r.ausencias_libres, b = r.ausencias_mismo_rango_elevacion;
  const rows: [string, string, string][] = [
    ["Índice heurístico (solo pendiente)", a.auc_heuristico_pendiente.toFixed(2), b.auc_heuristico_pendiente.toFixed(2)],
    ["Solo elevación", a.auc_solo_elevacion_baja.toFixed(2), b.auc_solo_elevacion_baja.toFixed(2)],
    ["Regresión logística · validación espacial", cv(a.regresion_logistica.espacial), cv(b.regresion_logistica.espacial)],
    ["Bosque aleatorio · validación espacial", cv(a.bosque_aleatorio.espacial), cv(b.bosque_aleatorio.espacial)],
    ["Regresión logística · aleatoria (solo referencia)", cv(a.regresion_logistica.aleatoria_referencia), cv(b.regresion_logistica.aleatoria_referencia)],
  ];
  return (
    <div className="card stack">
      <h2>Informe de validación {r.simulado && <span className="badge badge-sim">SIMULADO</span>}</h2>
      <p className="small" style={{ margin: 0 }}>{a.n_presencias} eventos y {a.n_ausencias} pseudo-ausencias. {r.interpretacion_auc}</p>
      <div className="table-wrap"><table>
        <thead><tr><th>AUC</th><th>Ausencias libres</th><th>Ausencias en el rango de elevación {b.rango_elevacion_m ? `${b.rango_elevacion_m[0]}–${b.rango_elevacion_m[1]} m` : ""}</th></tr></thead>
        <tbody>{rows.map(([k, x, y]) => <tr key={k}><td className="small">{k}</td><td>{x}</td><td>{y}</td></tr>)}</tbody>
      </table></div>
      <div><strong className="small">Conclusiones automáticas</strong>
        <ul className="small">{r.conclusion_automatica.map((c) => <li key={c}>{c}</li>)}</ul></div>
      <Notice kind="info"><ul className="small" style={{ margin: 0 }}>{r.advertencias.map((w) => <li key={w}>{w}</li>)}</ul></Notice>
      {r.dataset_record_id && <p className="small muted" style={{ margin: 0 }}>Dataset para NEURAL TRAINING registrado en NEURODATA (columna objetivo «evento»).
        Ningún modelo queda validado automáticamente.</p>}
    </div>
  );
}
