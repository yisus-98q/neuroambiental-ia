import { useState, type FormEvent } from "react";
import { StatusBadge } from "../components/Badges";
import { ErrorText, Loading } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import type { ModuleInfo, ReportItem, User } from "../services/types";
import { useApi } from "../services/useApi";

interface CoreInfo { name: string; version: string; status: string; description: string; interpreter: string; modules_registered: number }
interface Op { id: string; at: string; action: string; target_type: string; success: boolean }
interface Interp { intent: string; module_key: string | null; matched_keywords: string[]; method: string; module_status: string | null }

export function NeurocorePage() {
  const info = useApi<CoreInfo>("/api/neurocore");
  const mods = useApi<ModuleInfo[]>("/api/neurocore/modules");
  const user = session.user();
  const ops = useApi<Op[]>(canWrite(user) ? "/api/neurocore/operations?limit=30" : null);
  const [text, setText] = useState("");
  const [res, setRes] = useState<Interp | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function test(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try { setRes(await post<Interp>("/api/neurocore/interpret", { text })); } catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><h1>NEUROCORE IA</h1>{info.data && <StatusBadge status={info.data.status} />}</div>
        <p className="muted">{info.data?.description}</p>
        <p className="small">Módulos registrados: <strong>{info.data?.modules_registered}</strong> · Intérprete: <code>{info.data?.interpreter}</code></p>
      </div>
      <div className="card">
        <h2>Registro de módulos</h2>
        {mods.loading && <Loading />}
        <div className="table-wrap"><table>
          <thead><tr><th>Módulo</th><th>Versión</th><th>Capacidades</th><th>Dependencias</th><th>Estado</th></tr></thead>
          <tbody>{mods.data?.map((m) => (
            <tr key={m.key}><td>{m.name}</td><td>{m.version}</td><td>{m.implemented_count}/{m.capabilities.length}</td>
              <td className="small">{m.dependencies.join(", ") || "—"}</td><td><StatusBadge status={m.status} /></td></tr>
          ))}</tbody>
        </table></div>
        <p className="small muted">El estado se calcula a partir de las capacidades implementadas: un módulo con solo su interfaz siempre figura «En desarrollo».</p>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h2>Probar interpretación de solicitudes</h2>
          <form onSubmit={test} className="row"><input value={text} onChange={(e) => setText(e.target.value)} placeholder="p. ej. riesgo de huaycos en Huaraz" required style={{ flex: 1 }} /><button className="btn">Interpretar</button></form>
          <ErrorText error={error} />
          {res && <table style={{ marginTop: 10 }}><tbody>
            <tr><th>Intención</th><td>{res.intent}</td></tr><tr><th>Módulo</th><td>{res.module_key ?? "—"} {res.module_status && <StatusBadge status={res.module_status} />}</td></tr>
            <tr><th>Palabras clave</th><td>{res.matched_keywords.join(", ") || "—"}</td></tr><tr><th>Método</th><td>{res.method}</td></tr>
          </tbody></table>}
        </div>
        <div className="card">
          <h2>Registro de operaciones</h2>
          {!canWrite(user) ? <p className="muted small">Requiere rol analista o administrador.</p> : (
            <ul className="small" style={{ paddingLeft: 18, maxHeight: 300, overflowY: "auto" }}>
              {ops.data?.map((o) => <li key={o.id}>{fmtDate(o.at)} — {o.action} {o.target_type && `(${o.target_type})`}{!o.success && " ✗"}</li>)}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export function ReportsPage() {
  const reports = useApi<ReportItem[]>("/api/reports");
  const [open, setOpen] = useState<ReportItem | null>(null);
  return (
    <div className="stack">
      <h1>Informes</h1>
      <p className="muted" style={{ margin: 0 }}>Informes generados por la plataforma (por ahora, informes de alertas).</p>
      <div className="grid grid-2">
        <div className="card">
          {reports.loading && <Loading />}
          {reports.data?.length === 0 && <p className="muted">Aún no hay informes. Genere uno desde una alerta.</p>}
          <table><tbody>{reports.data?.map((r) => (
            <tr key={r.id} onClick={() => setOpen(r)} style={{ cursor: "pointer" }}><td>{r.title}</td><td className="small muted">{fmtDate(r.created_at)}</td></tr>
          ))}</tbody></table>
        </div>
        <div className="card">{open ? <pre className="report">{open.content_md}</pre> : <p className="muted">Seleccione un informe.</p>}</div>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const user = session.user();
  const limits = useApi<{ max_upload_mb: number; max_csv_rows: number; allowed_extensions: string[] }>("/api/neurodata/limits");
  const health = useApi<{ status: string; database: string; version: string }>("/api/health");
  const isAdmin = user?.role_key === "admin";
  const users = useApi<User[]>(isAdmin ? "/api/auth/users" : null);
  const [f, setF] = useState({ username: "", full_name: "", password: "", role_key: "lector" });
  const [error, setError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try { await post("/api/auth/users", f); setF({ username: "", full_name: "", password: "", role_key: "lector" }); users.reload(); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="stack">
      <h1>Configuración</h1>
      <div className="grid grid-3">
        <div className="card"><h2>Mi cuenta</h2><p className="small">Usuario: <strong>{user?.username}</strong><br />Rol: {user?.role_key}</p></div>
        <div className="card"><h2>Sistema</h2><p className="small">Versión: {health.data?.version}<br />Base de datos: {health.data?.database}<br />Estado: {health.data?.status}</p></div>
        <div className="card"><h2>Límites de carga</h2><p className="small">Máx. por archivo: {limits.data?.max_upload_mb} MB<br />Máx. filas CSV: {limits.data?.max_csv_rows}<br />Formatos: {limits.data?.allowed_extensions.join(" ")}</p></div>
      </div>
      {isAdmin && (
        <div className="grid grid-2">
          <div className="card"><h2>Usuarios</h2><table><tbody>{users.data?.map((u) => (
            <tr key={u.id}><td>{u.username}</td><td>{u.full_name}</td><td>{u.role_key}</td><td>{u.is_active ? "activo" : "inactivo"}</td></tr>
          ))}</tbody></table></div>
          <form className="card stack" onSubmit={create}>
            <h2>Crear usuario</h2>
            <div className="grid grid-2">
              <div className="field"><label htmlFor="s-u">Usuario</label><input id="s-u" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} required pattern="[a-zA-Z0-9_.\-]+" minLength={3} /></div>
              <div className="field"><label htmlFor="s-n">Nombre</label><input id="s-n" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>
              <div className="field"><label htmlFor="s-p">Contraseña (mín. 10)</label><input id="s-p" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required minLength={10} /></div>
              <div className="field"><label htmlFor="s-r">Rol</label><select id="s-r" value={f.role_key} onChange={(e) => setF({ ...f, role_key: e.target.value })}>
                <option value="lector">Lector</option><option value="analista">Analista</option><option value="admin">Administrador</option></select></div>
            </div>
            <div><button className="btn">Crear</button></div>
            <ErrorText error={error} />
          </form>
        </div>
      )}
    </div>
  );
}
