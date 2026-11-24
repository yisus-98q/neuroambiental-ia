import type { ModuleInfo } from "../services/types";
import { StatusBadge } from "./Badges";
import { Notice } from "./Notice";

/** Cómo leer los resultados de los módulos que ya producen resultados (texto fijo, verificable en sus informes). */
const INTERPRET: Record<string, string> = {
  disasters: "El AUC (0,5 = azar) mide si los eventos reales caen donde el modelo da valores altos, en zonas no usadas para entrenar. Mire el intervalo de confianza y la variante con la franja de altura: ningún modelo está validado.",
  environmental: "NDVI de −1 a 1: valores altos = vegetación vigorosa. Un cambio de NDVI no confirma deforestación ni daño: requiere verificación en campo.",
  neuro3d: "Los escenarios son hipotéticos (SIMULACIÓN): muestran qué pasaría bajo supuestos simples, no predicen eventos.",
  terrain: "Las series muestran desplazamientos medidos por sensores cargados; las alertas son experimentales y sus umbrales son de ejemplo.",
  validation: "El estado científico solo llega a «validado condicional» con una prueba independiente sellada que cumpla criterios fijados antes, y dos aprobaciones.",
  neurotraining: "Las métricas se calculan en datos reservados; con datos geoespaciales, un corte aleatorio sobreestima y no permite validar.",
  alerts: "Las alertas son experimentales: no son emergencias oficiales. Para emergencias consulte INDECI / COEN.",
};

/** Ficha honesta de un módulo: lo que funciona, lo que no y sus límites. */
export function ModuleOverview({ module }: { module: ModuleInfo }) {
  const pending = module.capabilities.length - module.implemented_count;
  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <div>
            {module.codename && module.codename !== module.name && <div className="small muted" style={{ letterSpacing: ".06em" }}>{module.codename}</div>}
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

      <div className="card">
        <h2>Cómo funciona este módulo</h2>
        <div className="explain-grid">
          <div className="explain-item"><h3>Qué es</h3><p>{module.description}</p></div>
          <div className="explain-item"><h3>Qué hace hoy</h3>
            {module.implemented_count > 0
              ? <ul>{module.capabilities.filter((c) => c.implemented).map((c) => <li key={c.key}>{c.description}</li>)}</ul>
              : <p>Nada todavía: solo existe su diseño (contrato).</p>}</div>
          <div className="explain-item"><h3>Qué datos utiliza</h3><p>{module.inputs.join(" · ") || "—"}</p></div>
          <div className="explain-item"><h3>Qué resultados ofrece</h3><p>{module.implemented_count > 0 ? (module.outputs.join(" · ") || "—") : "Ninguno hasta que se implemente."}</p></div>
          <div className="explain-item"><h3>Cómo se interpreta</h3><p>{INTERPRET[module.key] ?? (module.status === "en_desarrollo"
            ? "No hay resultados que interpretar." : "Los resultados son experimentales salvo que el módulo indique un modelo validado. Lea siempre las limitaciones.")}</p></div>
          <div className="explain-item"><h3>Limitaciones</h3><p>{module.limitations[0] ?? "Sin limitaciones declaradas."}{module.limitations.length > 1 ? ` (+${module.limitations.length - 1} más abajo)` : ""}</p></div>
        </div>
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
