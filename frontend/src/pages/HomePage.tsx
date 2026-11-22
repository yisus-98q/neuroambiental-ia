import { lazy, Suspense, useMemo } from "react";
import { StatusBadge } from "../components/Badges";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { fmtDate } from "../services/api";
import type { Dashboard, Layer } from "../services/types";
import { useApi } from "../services/useApi";

const TerritorialMap = lazy(() => import("../maps/TerritorialMap"));

const SHORTCUTS = [
  ["#/neurodata", "Cargar datos"], ["#/alertas", "Registrar alerta"], ["#/mapa", "Abrir mapa"],
  ["#/neurovoice", "Consultar a NEUROVOICE"], ["#/neurocore", "Estado de NEUROCORE"],
];

export function HomePage() {
  const dash = useApi<Dashboard>("/api/dashboard");
  const layers = useApi<Layer[]>("/api/neurodata/layers");
  const alerts = useApi<GeoJSON.FeatureCollection>("/api/alerts/geojson");
  const visible = useMemo(() => new Set((layers.data ?? []).map((l) => l.record_id)), [layers.data]);
  const d = dash.data;

  return (
    <div className="stack">
      <div>
        <h1>Inicio</h1>
        <p className="muted" style={{ margin: 0 }}>Todas las cifras provienen de la base de datos local. Ninguna es inventada.</p>
      </div>
      <ErrorText error={dash.error} />
      {d && (
        <div className="grid grid-4">
          <div className="card"><div className="kpi-label">Alertas experimentales</div><div className="kpi">{d.alerts.total}</div>
            <div className="small muted">Alto: {d.alerts.by_level.alto ?? 0} · Medio: {d.alerts.by_level.medio ?? 0} · Bajo: {d.alerts.by_level.bajo ?? 0}</div></div>
          <div className="card"><div className="kpi-label">Sin validar</div><div className="kpi">{d.alerts.by_status.no_validada ?? 0}</div>
            <div className="small muted">En revisión: {d.alerts.by_status.en_revision ?? 0}</div></div>
          <div className="card"><div className="kpi-label">Registros de datos</div><div className="kpi">{d.records.total}</div>
            <div className="small muted">Reales: {d.records.real} · Simulados: {d.records.simulated}</div></div>
          <div className="card"><div className="kpi-label">Fuentes registradas</div><div className="kpi">{d.sources.length}</div>
            <div className="small muted">Procesos en cola: {d.processing.queued_jobs}</div></div>
        </div>
      )}
      {d && d.records.total === 0 && (
        <Notice kind="info">Aún no hay datos cargados. Los indicadores ambientales aparecerán cuando se carguen datos en NEURODATA.</Notice>
      )}

      <div className="grid grid-2">
        <div className="card">
          <div className="card-head"><h2>Mapa principal</h2><a href="#/mapa" className="small">Abrir mapa completo →</a></div>
          <Suspense fallback={<Loading what="mapa" />}>
            <TerritorialMap compact layers={layers.data ?? []} visible={visible} alerts={alerts.data} />
          </Suspense>
        </div>
        <div className="card">
          <h2>Estado de módulos</h2>
          {!d ? <Loading /> : (
            <table><tbody>
              {d.modules.map((m) => (
                <tr key={m.key}><td>{m.name}</td><td style={{ textAlign: "right" }}><StatusBadge status={m.status} /></td></tr>
              ))}
            </tbody></table>
          )}
        </div>
      </div>

      <div className="grid grid-3">
        <div className="card">
          <h2>Actividad reciente</h2>
          {d && d.recent_activity.length === 0 && <p className="muted">Sin actividad registrada.</p>}
          <ul className="small" style={{ paddingLeft: 18 }}>
            {d?.recent_activity.map((a, i) => (
              <li key={i}>{fmtDate(a.at)} — {a.action}{a.success ? "" : " (fallido)"}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>Fuentes de datos</h2>
          {d && d.sources.length === 0 && <p className="muted">Ninguna fuente registrada todavía.</p>}
          <ul className="small" style={{ paddingLeft: 18 }}>
            {d?.sources.map((s) => <li key={s.name}>{s.name} <span className="muted">({s.kind}; licencia: {s.license})</span></li>)}
          </ul>
        </div>
        <div className="card">
          <h2>Accesos directos</h2>
          <div className="stack">
            {SHORTCUTS.map(([href, label]) => <a key={href} className="btn btn-ghost" href={href}>{label}</a>)}
          </div>
          <p className="small muted" style={{ marginTop: 12 }}>Procesamiento: {d?.processing.note}</p>
        </div>
      </div>
    </div>
  );
}
