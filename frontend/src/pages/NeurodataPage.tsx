import { useState, type FormEvent } from "react";
import { SimBadge, StatusBadge } from "../components/Badges";
import { ErrorText, Loading } from "../components/Notice";
import { UploadForm } from "../components/UploadForm";
import { canWrite, fmtDate, post, session } from "../services/api";
import type { DataRecord, ModuleInfo } from "../services/types";
import { useApi } from "../services/useApi";

interface Source { id: string; name: string; kind: string; license: string; url: string }

export function NeurodataPage() {
  const mod = useApi<ModuleInfo>("/api/neurocore/modules/neurodata");
  const [filter, setFilter] = useState("");
  const records = useApi<DataRecord[]>(`/api/neurodata/records?limit=200${filter ? `&data_type=${filter}` : ""}`);
  const sources = useApi<Source[]>("/api/neurodata/sources");
  const [detail, setDetail] = useState<DataRecord | null>(null);
  const user = session.user();
  const reload = () => { records.reload(); sources.reload(); };

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>NEURODATA ENGINE</h1><p className="muted" style={{ margin: 0 }}>Recepción, validación, metadatos y procedencia de cada dato.</p></div>
        {mod.data && <StatusBadge status={mod.data.status} />}
      </div>
      {canWrite(user) && (
        <div className="grid grid-2">
          <div className="card"><h2>Cargar archivo</h2><p className="small muted">CSV, GeoJSON, PNG, JPG o PDF. Se valida antes de guardarse.</p><UploadForm onUploaded={reload} /></div>
          <div className="card"><h2>Registro manual</h2><ManualForm onCreated={reload} /></div>
        </div>
      )}
      <div className="card">
        <div className="card-head"><h2>Datos recibidos</h2>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: "auto" }} aria-label="Filtrar por tipo">
            <option value="">Todos los tipos</option>
            {["csv", "geojson", "imagen", "documento", "medicion_manual"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select></div>
        <ErrorText error={records.error} />
        {records.loading && <Loading />}
        {records.data?.length === 0 && <p className="muted">No hay datos registrados.</p>}
        <div className="table-wrap"><table>
          <thead><tr><th>Título</th><th>Tipo</th><th>Fuente</th><th>Recibido</th><th>Validación</th><th>Origen</th></tr></thead>
          <tbody>{records.data?.map((r) => (
            <tr key={r.id} onClick={() => setDetail(r)} style={{ cursor: "pointer" }}>
              <td>{r.title}</td><td>{r.data_type}</td><td>{r.source_name}</td><td>{fmtDate(r.received_at)}</td>
              <td>{r.validation_status}{r.validation_messages.length > 0 && " ⚠"}</td><td><SimBadge simulated={r.is_simulated} /></td>
            </tr>
          ))}</tbody>
        </table></div>
      </div>
      {detail && (
        <div className="card">
          <div className="card-head"><h2>Metadatos: {detail.title}</h2><button className="btn btn-ghost" onClick={() => setDetail(null)}>Cerrar</button></div>
          <div className="table-wrap"><table><tbody>
            {([["ID", detail.id], ["Tipo", detail.data_type], ["Formato", detail.file_format], ["Fuente", detail.source_name],
              ["Ubicación", detail.latitude != null ? `${detail.latitude}, ${detail.longitude}` : "—"], ["Extensión (bbox)", detail.bbox?.join(", ") ?? "—"],
              ["Fecha de observación", fmtDate(detail.observed_at)], ["Fecha de recepción", fmtDate(detail.received_at)],
              ["Valor / unidad", detail.value != null ? `${detail.value} ${detail.unit}` : "—"], ["Calidad", detail.quality],
              ["Estado de validación", detail.validation_status], ["Observaciones", detail.validation_messages.join(" ") || "—"],
              ["Procedencia", detail.provenance], ["Simulado", detail.is_simulated ? "SÍ" : "no"],
              ["Tamaño", detail.file_size != null ? `${(detail.file_size / 1024).toFixed(1)} KB` : "—"], ["SHA-256", detail.sha256 ?? "—"],
              ["Detalles", JSON.stringify(detail.extra)]] as [string, string][]).map(([k, v]) => <tr key={k}><th>{k}</th><td style={{ wordBreak: "break-all" }}>{v}</td></tr>)}
          </tbody></table></div>
        </div>
      )}
      <div className="card">
        <h2>Fuentes</h2>
        {sources.data?.length === 0 && <p className="muted">Sin fuentes.</p>}
        <ul className="small">{sources.data?.map((s) => <li key={s.id}>{s.name} — {s.kind}; licencia: {s.license}</li>)}</ul>
      </div>
    </div>
  );
}

function ManualForm({ onCreated }: { onCreated: () => void }) {
  const empty = { title: "", variable: "", value: "", unit: "", latitude: "", longitude: "", observed_at: "", source_name: "", provenance: "", is_simulated: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const num = (v: string) => (v === "" ? null : Number(v));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(false);
    try {
      await post("/api/neurodata/records/manual", {
        ...f, value: num(f.value), latitude: num(f.latitude), longitude: num(f.longitude), is_simulated: f.is_simulated === "true",
        observed_at: f.observed_at ? new Date(f.observed_at).toISOString() : null,
      });
      setF(empty); setOk(true); onCreated();
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="m-t">Título *</label><input id="m-t" value={f.title} onChange={set("title")} required /></div>
      <div className="grid grid-3">
        <div className="field"><label htmlFor="m-v">Variable</label><input id="m-v" value={f.variable} onChange={set("variable")} placeholder="caudal" /></div>
        <div className="field"><label htmlFor="m-val">Valor</label><input id="m-val" type="number" step="any" value={f.value} onChange={set("value")} /></div>
        <div className="field"><label htmlFor="m-u">Unidad</label><input id="m-u" value={f.unit} onChange={set("unit")} placeholder="m3/s" /></div>
        <div className="field"><label htmlFor="m-lat">Latitud</label><input id="m-lat" type="number" step="any" value={f.latitude} onChange={set("latitude")} /></div>
        <div className="field"><label htmlFor="m-lon">Longitud</label><input id="m-lon" type="number" step="any" value={f.longitude} onChange={set("longitude")} /></div>
        <div className="field"><label htmlFor="m-o">Fecha</label><input id="m-o" type="datetime-local" value={f.observed_at} onChange={set("observed_at")} /></div>
      </div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="m-s">Fuente *</label><input id="m-s" value={f.source_name} onChange={set("source_name")} required /></div>
        <div className="field"><label htmlFor="m-sim">¿Simulado? *</label>
          <select id="m-sim" value={f.is_simulated} onChange={set("is_simulated")} required>
            <option value="">Seleccione…</option><option value="false">No, dato real</option><option value="true">Sí, prueba</option></select></div>
      </div>
      <div className="field"><label htmlFor="m-p">Procedencia</label><input id="m-p" value={f.provenance} onChange={set("provenance")} /></div>
      <div><button className="btn">Registrar</button></div>
      <ErrorText error={error} />
      {ok && <p className="small" style={{ color: "var(--green-500)" }}>Registro guardado.</p>}
    </form>
  );
}
