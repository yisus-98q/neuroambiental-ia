import { useState, type FormEvent } from "react";
import { LevelBadge, SimBadge } from "../components/Badges";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { api, canWrite, fmtDate, post, session } from "../services/api";
import type { Alert } from "../services/types";
import { useApi } from "../services/useApi";

const STATES = ["no_validada", "en_revision", "validada", "descartada"];

export function AlertsPage() {
  const list = useApi<Alert[]>("/api/alerts");
  const [selected, setSelected] = useState<Alert | null>(null);
  const user = session.user();

  return (
    <div className="stack">
      <h1>Alertas y prevención</h1>
      <Notice kind="danger">
        <strong>Alertas EXPERIMENTALES.</strong> No son emergencias oficiales ni sustituyen los avisos de INDECI, COEN,
        SENAMHI u otras autoridades. Ante un peligro real, siga las indicaciones oficiales.
      </Notice>
      <div className="grid grid-2">
        <div className="card">
          <h2>Alertas registradas</h2>
          <ErrorText error={list.error} />
          {list.loading && <Loading what="alertas" />}
          {list.data?.length === 0 && <p className="muted">No hay alertas registradas.</p>}
          <div className="table-wrap"><table>
            <tbody>{list.data?.map((a) => (
              <tr key={a.id} onClick={() => setSelected(a)} style={{ cursor: "pointer", background: selected?.id === a.id ? "var(--gray-50)" : undefined }}>
                <td><LevelBadge level={a.level} /></td>
                <td><strong>{a.title}</strong><div className="small muted">{a.source_name} · {fmtDate(a.created_at)}</div></td>
                <td><span className="badge badge-low">{a.validation_status}</span></td>
                <td><SimBadge simulated={a.is_simulated} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
        {selected
          ? <AlertDetail alert={selected} onChange={(a) => { setSelected(a); list.reload(); }} writable={canWrite(user)} />
          : canWrite(user) ? <div className="card"><h2>Nueva alerta experimental</h2><AlertForm onCreated={list.reload} /></div>
          : <div className="card muted">Seleccione una alerta para ver el detalle.</div>}
      </div>
      {selected && canWrite(user) && (
        <div className="card"><div className="card-head"><h2>Nueva alerta experimental</h2>
          <button className="btn btn-ghost" onClick={() => setSelected(null)}>Cerrar detalle</button></div>
          <AlertForm onCreated={list.reload} /></div>
      )}
    </div>
  );
}

function AlertForm({ onCreated }: { onCreated: () => void }) {
  const empty = { title: "", description: "", level: "medio", evidence: "", source_name: "", uncertainty: "", latitude: "", longitude: "", observed_at: "", is_simulated: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await post("/api/alerts", {
        ...f, is_simulated: f.is_simulated === "true",
        latitude: f.latitude === "" ? null : Number(f.latitude), longitude: f.longitude === "" ? null : Number(f.longitude),
        observed_at: f.observed_at ? new Date(f.observed_at).toISOString() : null,
      });
      setF(empty); onCreated();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="a-t">Título *</label><input id="a-t" value={f.title} onChange={set("title")} required minLength={3} /></div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="a-l">Nivel *</label>
          <select id="a-l" value={f.level} onChange={set("level")}><option value="bajo">Bajo</option><option value="medio">Medio</option><option value="alto">Alto</option></select></div>
        <div className="field"><label htmlFor="a-s">Fuente *</label><input id="a-s" value={f.source_name} onChange={set("source_name")} required /></div>
        <div className="field"><label htmlFor="a-lat">Latitud</label><input id="a-lat" type="number" step="any" min={-90} max={90} value={f.latitude} onChange={set("latitude")} /></div>
        <div className="field"><label htmlFor="a-lon">Longitud</label><input id="a-lon" type="number" step="any" min={-180} max={180} value={f.longitude} onChange={set("longitude")} /></div>
        <div className="field"><label htmlFor="a-o">Fecha de observación</label><input id="a-o" type="datetime-local" value={f.observed_at} onChange={set("observed_at")} /></div>
        <div className="field"><label htmlFor="a-sim">¿Datos simulados? *</label>
          <select id="a-sim" value={f.is_simulated} onChange={set("is_simulated")} required>
            <option value="">Seleccione…</option><option value="false">No, es un reporte real</option><option value="true">Sí, es una prueba</option></select></div>
      </div>
      <div className="field"><label htmlFor="a-d">Descripción</label><textarea id="a-d" value={f.description} onChange={set("description")} /></div>
      <div className="field"><label htmlFor="a-e">Evidencia</label><textarea id="a-e" value={f.evidence} onChange={set("evidence")} placeholder="Fotos, mediciones, reportes que la sustentan" /></div>
      <div className="field"><label htmlFor="a-u">Incertidumbre *</label><textarea id="a-u" value={f.uncertainty} onChange={set("uncertainty")} required minLength={3} placeholder="¿Qué tan segura es esta alerta y por qué?" /></div>
      <div><button className="btn" disabled={busy}>{busy ? "Guardando…" : "Registrar alerta experimental"}</button></div>
      <ErrorText error={error} />
    </form>
  );
}

function AlertDetail({ alert, onChange, writable }: { alert: Alert; onChange: (a: Alert) => void; writable: boolean }) {
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");
  const [report, setReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function addFollowup(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const a = await post<Alert>(`/api/alerts/${alert.id}/followups`, { note, new_status: status || null });
      setNote(""); setStatus(""); onChange(a);
    } catch (err) { setError((err as Error).message); }
  }
  async function makeReport() {
    try { setReport((await post<{ content_md: string }>(`/api/alerts/${alert.id}/report`)).content_md); }
    catch (err) { setError((err as Error).message); }
  }
  async function refresh() { onChange(await api<Alert>(`/api/alerts/${alert.id}`)); }

  return (
    <div className="card stack">
      <div className="card-head"><h2>{alert.title}</h2><div className="row"><LevelBadge level={alert.level} /><SimBadge simulated={alert.is_simulated} /></div></div>
      <table><tbody>
        <tr><th>Tipo</th><td>{alert.alert_kind} (no oficial)</td></tr>
        <tr><th>Estado de validación</th><td>{alert.validation_status}</td></tr>
        <tr><th>Ubicación</th><td>{alert.latitude != null ? `${alert.latitude}, ${alert.longitude}` : "sin ubicación"}</td></tr>
        <tr><th>Fuente</th><td>{alert.source_name}</td></tr>
        <tr><th>Fecha observación</th><td>{fmtDate(alert.observed_at)}</td></tr>
        <tr><th>Evidencia</th><td>{alert.evidence || "—"}</td></tr>
        <tr><th>Incertidumbre</th><td>{alert.uncertainty}</td></tr>
        <tr><th>Descripción</th><td>{alert.description || "—"}</td></tr>
      </tbody></table>
      <div><h3>Seguimiento</h3>
        {alert.followups.length === 0 ? <p className="small muted">Sin seguimientos.</p> : (
          <ul className="small">{alert.followups.map((f) => <li key={f.id}>{fmtDate(f.created_at)}: {f.note}{f.new_status && ` → ${f.new_status}`}</li>)}</ul>
        )}</div>
      {writable && (
        <form onSubmit={addFollowup} className="stack">
          <div className="field"><label htmlFor="fu">Nota de seguimiento</label><textarea id="fu" value={note} onChange={(e) => setNote(e.target.value)} required minLength={3} /></div>
          <div className="row">
            <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: "auto" }} aria-label="Nuevo estado">
              <option value="">Mantener estado</option>{STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="btn">Agregar seguimiento</button>
            <button type="button" className="btn btn-green" onClick={makeReport}>Generar informe</button>
            <button type="button" className="btn btn-ghost" onClick={refresh}>Actualizar</button>
          </div>
        </form>
      )}
      <ErrorText error={error} />
      {report && <pre className="report">{report}</pre>}
    </div>
  );
}
