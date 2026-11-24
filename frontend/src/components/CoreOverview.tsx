import { useState } from "react";
import { canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";
import { EmptyState } from "./EmptyState";

interface Overview {
  modulos: { total: number; por_estado: Record<string, number> };
  datasets: { por_tipo: Record<string, { reales: number; simulados: number }>; contenidos_duplicados_sha256: number };
  modelos: { por_estado: Record<string, number>; validados: number };
  validacion_cientifica: { experimentos: number; por_estado: Record<string, number> };
  actividad_reciente: { id: string; tipo: string; modulo: string; estado: string; inicio: string; duracion_s: number | null }[];
  recursos: {
    perfil: { name: string; ram_max_gb: number; ram_target_gb: number; n_jobs: number };
    ram_total_gb: number; ram_disponible_gb: number; proceso_actual_mb: number;
    trabajo_en_curso: { nombre: string; duracion_s: number; estimacion_mb: number; cancelacion_pedida: boolean } | null;
  };
  nota: string;
}

const d1 = (v: number) => v.toFixed(1).replace(".", ",");

/** Centro de coordinación NEUROCORE: todo lo que muestra sale de /api/neurocore/overview (datos reales). */
export function CoreOverview() {
  const ov = useApi<Overview>("/api/neurocore/overview");
  const [msg, setMsg] = useState<string | null>(null);
  const o = ov.data;
  if (!o) return null;
  const ds = Object.values(o.datasets.por_tipo).reduce((a, d) => ({ r: a.r + d.reales, s: a.s + d.simulados }), { r: 0, s: 0 });
  const job = o.recursos.trabajo_en_curso;
  async function cancel() {
    try { const r = await post<{ detalle: string }>("/api/system/jobs/cancel"); setMsg(r.detalle); ov.reload(); }
    catch (e) { setMsg((e as Error).message); }
  }
  return (
    <div className="stack">
      <div className="grid grid-4">
        <div className="card"><div className="kpi-label">Módulos</div><div className="kpi">{o.modulos.total}</div>
          <div className="small muted">{o.modulos.por_estado.operativo ?? 0} operativos · {o.modulos.por_estado.parcial ?? 0} parciales · {o.modulos.por_estado.en_desarrollo ?? 0} en desarrollo</div></div>
        <div className="card"><div className="kpi-label">Datasets</div><div className="kpi">{ds.r + ds.s}</div>
          <div className="small muted">{ds.r} reales · {ds.s} simulados · {o.datasets.contenidos_duplicados_sha256} contenidos duplicados</div></div>
        <div className="card"><div className="kpi-label">Modelos validados</div><div className="kpi">{o.modelos.validados}</div>
          <div className="small muted">{Object.entries(o.modelos.por_estado).map(([k, v]) => `${v} ${k}`).join(" · ") || "ningún modelo registrado"}</div></div>
        <div className="card"><div className="kpi-label">Experimentos científicos</div><div className="kpi">{o.validacion_cientifica.experimentos}</div>
          <div className="small muted">{Object.entries(o.validacion_cientifica.por_estado).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(" · ") || "sin experimentos"}</div></div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h2>Recursos del equipo</h2>
          <p className="small" style={{ margin: 0 }}>Perfil <strong>{o.recursos.perfil.name}</strong> · RAM {d1(o.recursos.ram_disponible_gb)} GB libres de {d1(o.recursos.ram_total_gb)} GB ·
            tope por trabajo {d1(o.recursos.perfil.ram_max_gb)} GB · {o.recursos.perfil.n_jobs} hilo(s) · servidor {Math.round(o.recursos.proceso_actual_mb)} MB</p>
          {job ? (
            <div className="notice notice-info small" style={{ marginTop: 8 }}><span className="spinner" /> En curso: <strong>{job.nombre}</strong> ({Math.round(job.duracion_s)} s,
              estimación {Math.round(job.estimacion_mb)} MB){job.cancelacion_pedida ? " — cancelación pedida" : ""}
              {canWrite(session.user()) && !job.cancelacion_pedida && <> {" "}<button className="btn btn-ghost" style={{ padding: "3px 10px" }} onClick={cancel}>Cancelar</button></>}</div>
          ) : <p className="small muted" style={{ marginBottom: 0 }}>No hay ningún trabajo pesado en curso.</p>}
          {msg && <p className="small muted" style={{ margin: 0 }}>{msg}</p>}
        </div>
        <div className="card">
          <h2>Actividad reciente</h2>
          {o.actividad_reciente.length === 0 ? <EmptyState title="Sin actividad todavía">Las importaciones, validaciones y entrenamientos aparecerán aquí.</EmptyState> : (
            <div className="table-wrap"><table><tbody>{o.actividad_reciente.slice(0, 8).map((r) => (
              <tr key={r.id}><td className="small">{r.tipo.replace(/_/g, " ")}</td><td className="small">{r.modulo}</td>
                <td><span className={`badge ${r.estado === "ok" ? "badge-ok" : r.estado === "error" ? "badge-high" : "badge-partial"}`}>{r.estado}</span></td>
                <td className="small">{fmtDate(r.inicio)}{r.duracion_s != null ? ` · ${Math.round(r.duracion_s)} s` : ""}</td></tr>
            ))}</tbody></table></div>
          )}
        </div>
      </div>
      <p className="small muted" style={{ margin: 0 }}>{o.nota} Puede preguntar por cualquier módulo al asistente NEUROVOICE (botón inferior derecho).</p>
    </div>
  );
}
