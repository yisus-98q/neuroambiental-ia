import { STATUS_LABEL } from "../modules/menu";

export function StatusBadge({ status }: { status: string }) {
  const cls = status === "operativo" ? "badge-ok" : status === "parcial" ? "badge-partial" : "badge-dev";
  return <span className={`badge ${cls}`}>{STATUS_LABEL[status] ?? status}</span>;
}

export function SimBadge({ simulated }: { simulated: boolean }) {
  return simulated
    ? <span className="badge badge-sim" title="Dato simulado o de prueba">SIMULADO</span>
    : <span className="badge badge-ok" title="Declarado como dato real por quien lo cargó">REAL</span>;
}

export function LevelBadge({ level }: { level: string }) {
  const cls = level === "alto" ? "badge-high" : level === "medio" ? "badge-mid" : "badge-low";
  return <span className={`badge ${cls}`}>{level.toUpperCase()}</span>;
}
