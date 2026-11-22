import { ModuleOverview } from "../components/ModuleOverview";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { UploadForm } from "../components/UploadForm";
import { SimBadge } from "../components/Badges";
import { canWrite, fmtDate, session } from "../services/api";
import type { DataRecord, ModuleInfo } from "../services/types";
import { useApi } from "../services/useApi";
import { EnvironmentalPanel } from "./EnvironmentalPanel";

/** Página genérica para los módulos especializados. */
export function ModulePage({ moduleKey }: { moduleKey: string }) {
  const mod = useApi<ModuleInfo>(`/api/neurocore/modules/${moduleKey}`);
  if (mod.error) return <ErrorText error={mod.error} />;
  if (!mod.data) return <Loading what="módulo" />;
  return (
    <div className="stack">
      <ModuleOverview module={mod.data} />
      {moduleKey === "environmental" && <EnvironmentalPanel />}
      {moduleKey === "construction" && <ConstructionDocs />}
      {moduleKey === "disasters" && (
        <Notice kind="danger">
          Este sistema <strong>no predice la fecha exacta</strong> de terremotos, explosiones ni otros eventos.
          Para emergencias oficiales consulte INDECI / COEN.
        </Notice>
      )}
    </div>
  );
}

function ConstructionDocs() {
  const docs = useApi<DataRecord[]>("/api/neurodata/records?limit=50");
  const user = session.user();
  const items = (docs.data ?? []).filter((r) => ["documento", "imagen", "geojson", "csv"].includes(r.data_type));
  return (
    <div className="grid grid-2">
      <div className="card">
        <h2>Cargar plano o documento</h2>
        <Notice kind="info">La carga y validación funcionan. El análisis automático del proyecto (pendientes, ríos, riesgos) aún no está implementado.</Notice>
        {canWrite(user)
          ? <UploadForm moduleKey="construction" accept=".pdf,.png,.jpg,.jpeg,.geojson,.json,.csv" onUploaded={docs.reload} />
          : <p className="muted">Su rol ({user?.role_key}) solo permite consultar.</p>}
      </div>
      <div className="card">
        <h2>Documentos y planos cargados</h2>
        {items.length === 0 ? <p className="muted">No hay documentos.</p> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Título</th><th>Tipo</th><th>Recibido</th><th></th></tr></thead>
            <tbody>{items.map((r) => (
              <tr key={r.id}><td>{r.title}</td><td>{r.data_type}</td><td>{fmtDate(r.received_at)}</td><td><SimBadge simulated={r.is_simulated} /></td></tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  );
}
