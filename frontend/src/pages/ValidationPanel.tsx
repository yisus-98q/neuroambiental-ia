import { useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { api, canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";

interface Criteria { auc_min: number; ic95_inf_min: number; mejora_min: number; referencia: string }
interface Decision { reviewer_id: string | null; decision: string; comment: string; created_at: string }
interface Detail { valor?: number | null; minimo?: number; cumple: boolean }
interface Evaluation {
  id: string; partition: string; run_id: string | null; model_ref: string; criteria_met: boolean; created_at: string;
  metrics: { auc: number; ic95: number[] | null; auc_referencia: number | null; referencia: string; n_eventos: number | null };
  criteria_detail: Record<string, Detail>; decisions: Decision[];
}
interface Experiment {
  id: string; title: string; question: string; criteria: Criteria; test_region: number[] | null; protocol_sha256: string;
  status: string; estado_cientifico: string; created_at: string; protocol_text?: string; evaluations?: Evaluation[];
}
interface RunRow { id: string; run_type: string; status: string; started_at: string }

const STATE_LABEL: Record<string, string> = {
  borrador: "Borrador", evaluado_interno: "Evaluado internamente", evaluado_independiente: "Evaluado con prueba independiente",
  validado_condicional: "VALIDADO (condicional)", retirado: "Retirado",
};
const d2 = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2).replace(".", ","));
const MODELS = ["regresion_logistica_geo", "regresion_logistica", "regresion_logistica_base", "bosque_aleatorio"];

/** SCIENTIFIC VALIDATION ENGINE: experimentos con criterios previos, prueba sellada y doble aprobación. */
export function ValidationPanel() {
  const list = useApi<Experiment[]>("/api/validation/experiments");
  const runs = useApi<RunRow[]>("/api/disasters/runs");
  const user = session.user();
  const writable = canWrite(user);
  const isAdmin = user?.role_key === "admin";
  const [selId, setSelId] = useState<string | null>(null);
  const [sel, setSel] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "", question: "", protocol_text: "", auc_min: "0.70", ic95_inf_min: "0.60", mejora_min: "0.05",
    referencia: "auc_solo_elevacion_baja", test_region: "",
  });
  const [ev, setEv] = useState({ run_id: "", group: "todos", model: MODELS[0], partition: "cv" });
  const [dec, setDec] = useState({ evaluation_id: "", decision: "aprobar", comment: "" });

  useEffect(() => {
    if (!selId) { setSel(null); return; }
    api<Experiment>(`/api/validation/experiments/${selId}`).then(setSel).catch((e) => setError((e as Error).message));
  }, [selId]);

  async function act(fn: () => Promise<Experiment | unknown>) {
    setBusy(true); setError(null);
    try {
      const r = await fn();
      if (r && typeof r === "object" && "id" in (r as Experiment)) { setSel(r as Experiment); setSelId((r as Experiment).id); }
      list.reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const create = () => act(() => {
    const region = form.test_region.trim() ? form.test_region.split(",").map((v) => Number(v.trim())) : null;
    return post<Experiment>("/api/validation/experiments", {
      title: form.title, module_key: "disasters", question: form.question, protocol_text: form.protocol_text,
      criteria: { auc_min: Number(form.auc_min), ic95_inf_min: Number(form.ic95_inf_min), mejora_min: Number(form.mejora_min), referencia: form.referencia },
      test_region: region,
    });
  });
  const addEval = () => act(() => post<Experiment>(`/api/validation/experiments/${selId}/evaluations`,
    { run_id: ev.run_id, model_ref: `${ev.group}/${ev.model}`, partition: ev.partition }));
  const decide = () => act(() => post<Experiment>(`/api/validation/experiments/${selId}/decisions`, dec));

  const valRuns = (runs.data ?? []).filter((r) => r.run_type === "validacion_susceptibilidad" && r.status === "ok");
  return (
    <div className="stack">
      <Notice kind="dev"><strong>Los criterios se fijan ANTES de evaluar y no se pueden editar.</strong> Una evaluación interna (cv) no puede usar
        un DEM que toque la región de prueba; la prueba independiente (test) es sellada (una por protocolo) y la validación condicional exige
        dos aprobaciones de administradores distintos de los autores. Hoy no existe ninguna región de prueba evaluada.</Notice>

      <div className="card">
        <h2>Experimentos</h2>
        {list.loading && !list.data && <Loading what="experimentos" />}
        {list.data?.length === 0 && <p className="muted small">Aún no hay experimentos.</p>}
        <div className="table-wrap"><table><tbody>{list.data?.map((x) => (
          <tr key={x.id}><td className="small">{x.title}</td>
            <td><span className={`badge ${x.estado_cientifico === "validado_condicional" ? "" : "badge-sim"}`}>{STATE_LABEL[x.estado_cientifico] ?? x.estado_cientifico}</span></td>
            <td className="small">{fmtDate(x.created_at)}</td>
            <td><button className="btn" onClick={() => setSelId(x.id)}>Abrir</button></td></tr>
        ))}</tbody></table></div>
      </div>

      {writable && (
        <div className="card stack">
          <h2>Nuevo experimento (NEURODISASTER)</h2>
          <div className="field"><label htmlFor="vt">Título</label><input id="vt" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="vq">Pregunta científica</label><input id="vq" value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} /></div>
          <div className="field"><label htmlFor="vp">Protocolo (variables, bloques, ausencias, qué se considera éxito)</label>
            <textarea id="vp" rows={3} value={form.protocol_text} onChange={(e) => setForm({ ...form, protocol_text: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field"><label htmlFor="va">AUC mínimo</label><input id="va" type="number" step="0.01" value={form.auc_min} onChange={(e) => setForm({ ...form, auc_min: e.target.value })} /></div>
            <div className="field"><label htmlFor="vi">IC 95 % inferior mínimo</label><input id="vi" type="number" step="0.01" value={form.ic95_inf_min} onChange={(e) => setForm({ ...form, ic95_inf_min: e.target.value })} /></div>
            <div className="field"><label htmlFor="vm">Mejora mínima sobre la referencia</label><input id="vm" type="number" step="0.01" value={form.mejora_min} onChange={(e) => setForm({ ...form, mejora_min: e.target.value })} /></div>
            <div className="field"><label htmlFor="vr">Referencia</label>
              <select id="vr" value={form.referencia} onChange={(e) => setForm({ ...form, referencia: e.target.value })}>
                <option value="auc_solo_elevacion_baja">Solo elevación</option><option value="auc_heuristico_pendiente">Índice de pendiente</option>
                <option value="regresion_logistica_base">Regresión logística base</option></select></div>
            <div className="field"><label htmlFor="vg">Región de prueba (minLon,minLat,maxLon,maxLat; fuera del área de entrenamiento)</label>
              <input id="vg" value={form.test_region} placeholder="opcional" onChange={(e) => setForm({ ...form, test_region: e.target.value })} style={{ minWidth: 260 }} /></div>
          </div>
          <div><button className="btn" disabled={busy || !form.title || !form.question || !form.protocol_text} onClick={create}>Crear y congelar criterios</button></div>
        </div>
      )}
      <ErrorText error={error} />

      {sel && (
        <div className="card stack">
          <h2>{sel.title} · <span className="badge">{STATE_LABEL[sel.estado_cientifico] ?? sel.estado_cientifico}</span></h2>
          <p className="small" style={{ margin: 0 }}>{sel.question}</p>
          <p className="small muted" style={{ margin: 0 }}>Criterios congelados: AUC ≥ {d2(sel.criteria.auc_min)}, IC 95 % inferior ≥ {d2(sel.criteria.ic95_inf_min)},
            mejora ≥ {d2(sel.criteria.mejora_min)} sobre «{sel.criteria.referencia}». Región de prueba: {sel.test_region ? sel.test_region.join(", ") : "no definida"}.
            SHA-256: {sel.protocol_sha256.slice(0, 16)}…</p>
          {sel.protocol_text && <p className="small" style={{ margin: 0, whiteSpace: "pre-wrap" }}>{sel.protocol_text}</p>}
          <div className="table-wrap"><table>
            <thead><tr><th>Partición</th><th>Modelo</th><th>AUC</th><th>IC 95 %</th><th>Referencia</th><th>Cumple</th><th>Decisiones</th></tr></thead>
            <tbody>{(sel.evaluations ?? []).map((e) => (
              <tr key={e.id}><td className="small">{e.partition === "test" ? "PRUEBA independiente" : "interna (cv)"}</td>
                <td className="small">{e.model_ref}</td><td>{d2(e.metrics.auc)}</td>
                <td>{e.metrics.ic95 ? `${d2(e.metrics.ic95[0])}–${d2(e.metrics.ic95[1])}` : "—"}</td>
                <td className="small">{d2(e.metrics.auc_referencia)}</td>
                <td>{e.criteria_met ? "Sí" : "No"} <span className="small muted">({Object.entries(e.criteria_detail).filter(([, d]) => !d.cumple).map(([k]) => k).join(", ") || "todos"})</span></td>
                <td className="small">{e.decisions.map((d) => `${d.decision}: ${d.comment}`).join(" · ") || "—"}</td></tr>
            ))}</tbody>
          </table></div>
          {writable && sel.status !== "retirado" && (
            <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <div className="field"><label htmlFor="er">Ejecución de validación</label>
                <select id="er" value={ev.run_id} onChange={(e) => setEv({ ...ev, run_id: e.target.value })}>
                  <option value="">—</option>{valRuns.map((r) => <option key={r.id} value={r.id}>{fmtDate(r.started_at)} · {r.id.slice(0, 8)}</option>)}</select></div>
              <div className="field"><label htmlFor="eg">Grupo</label>
                <select id="eg" value={ev.group} onChange={(e) => setEv({ ...ev, group: e.target.value })}>
                  {["todos", "1000|1100", "1000|1300", "1000|1500"].map((g) => <option key={g}>{g}</option>)}</select></div>
              <div className="field"><label htmlFor="em">Modelo</label>
                <select id="em" value={ev.model} onChange={(e) => setEv({ ...ev, model: e.target.value })}>{MODELS.map((m) => <option key={m}>{m}</option>)}</select></div>
              <div className="field"><label htmlFor="ep">Partición</label>
                <select id="ep" value={ev.partition} onChange={(e) => setEv({ ...ev, partition: e.target.value })}>
                  <option value="cv">Interna (cv)</option><option value="test">Prueba independiente (sellada)</option></select></div>
              <button className="btn" disabled={busy || !ev.run_id} onClick={addEval}>Registrar evaluación</button>
            </div>
          )}
          {isAdmin && (sel.evaluations ?? []).length > 0 && (
            <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <div className="field"><label htmlFor="de">Evaluación</label>
                <select id="de" value={dec.evaluation_id} onChange={(e) => setDec({ ...dec, evaluation_id: e.target.value })}>
                  <option value="">—</option>{(sel.evaluations ?? []).map((e) => <option key={e.id} value={e.id}>{e.partition} · {e.model_ref}</option>)}</select></div>
              <div className="field"><label htmlFor="dd">Decisión</label>
                <select id="dd" value={dec.decision} onChange={(e) => setDec({ ...dec, decision: e.target.value })}>
                  <option value="aprobar">Aprobar</option><option value="rechazar">Rechazar</option></select></div>
              <div className="field"><label htmlFor="dc">Justificación (mín. 20 caracteres)</label>
                <input id="dc" value={dec.comment} onChange={(e) => setDec({ ...dec, comment: e.target.value })} style={{ minWidth: 280 }} /></div>
              <button className="btn" disabled={busy || !dec.evaluation_id} onClick={decide}>Registrar decisión</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
