import type { ModuleInfo } from "../services/types";
import { StatusBadge } from "./Badges";
import { Notice } from "./Notice";

/** Ficha honesta de un módulo: lo que funciona, lo que no y sus límites. */
export function ModuleOverview({ module }: { module: ModuleInfo }) {
  const pending = module.capabilities.length - module.implemented_count;
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <div>
            <h1>{module.name}</h1>
            <p className="muted" style={{ margin: 0 }}>{module.description}</p>
          </div>
          <StatusBadge status={module.status} />
        </div>
        {module.status === "en_desarrollo" && (
          <Notice kind="dev">
            <strong>Módulo en desarrollo.</strong> Solo existe su contrato (entradas, salidas y capacidades previstas).
            Ningún análisis de este módulo está implementado todavía; no se muestran resultados.
          </Notice>
        )}
        {module.status === "parcial" && (
          <Notice kind="info">
            Funcionan {module.implemented_count} de {module.capabilities.length} capacidades. {pending} siguen pendientes.
          </Notice>
        )}
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h2>Capacidades</h2>
          <ul className="cap-list">
            {module.capabilities.map((c) => (
              <li key={c.key}>
                <span className="cap-dot" style={{ background: c.implemented ? "var(--green-500)" : "var(--gray-300)" }} />
                <span style={{ flex: 1 }}>{c.description}</span>
                <span className={`badge ${c.implemented ? "badge-ok" : "badge-dev"}`}>
                  {c.implemented ? "Implementada" : "Pendiente"}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card stack">
          <div><h3>Entradas</h3><p className="small">{module.inputs.join(" · ") || "—"}</p></div>
          <div><h3>Salidas</h3><p className="small">{module.outputs.join(" · ") || "—"}</p></div>
          <div><h3>Dependencias</h3><p className="small">{module.dependencies.join(", ") || "ninguna"}</p></div>
          <div><h3>Errores posibles</h3><p className="small">{module.possible_errors.map((e) => <code key={e} style={{ marginRight: 4 }}>{e}</code>)}</p></div>
          <div><h3>Versión</h3><p className="small">{module.version}</p></div>
        </div>
      </div>

      {module.limitations.length > 0 && (
        <div className="card">
          <h2>Limitaciones declaradas</h2>
          <ul className="small">{module.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
