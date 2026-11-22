import { useState, type FormEvent } from "react";
import { post } from "../services/api";
import type { DataRecord } from "../services/types";
import { ErrorText, Notice } from "./Notice";

interface Props { onUploaded?: (r: DataRecord) => void; moduleKey?: string; accept?: string }

export function UploadForm({ onUploaded, moduleKey, accept = ".csv,.geojson,.json,.png,.jpg,.jpeg,.pdf" }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [license, setLicense] = useState("");
  const [title, setTitle] = useState("");
  const [observed, setObserved] = useState("");
  const [provenance, setProvenance] = useState("");
  const [simulated, setSimulated] = useState<"" | "true" | "false">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<DataRecord | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || !source || !simulated) return;
    setBusy(true); setError(null); setDone(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_name", source);
    fd.append("is_simulated", simulated);
    if (license) fd.append("source_license", license);
    if (title) fd.append("title", title);
    if (observed) fd.append("observed_at", new Date(observed).toISOString());
    if (provenance) fd.append("provenance", provenance);
    if (moduleKey) fd.append("module_key", moduleKey);
    try {
      const rec = await post<DataRecord>("/api/neurodata/upload", fd);
      setDone(rec);
      onUploaded?.(rec);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <div className="field">
        <label htmlFor="up-file">Archivo (máx. 10 MB)</label>
        <input id="up-file" type="file" accept={accept} onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
      </div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="up-src">Fuente *</label>
          <input id="up-src" value={source} onChange={(e) => setSource(e.target.value)} placeholder="p. ej. SENAMHI, trabajo de campo" required /></div>
        <div className="field"><label htmlFor="up-lic">Licencia de la fuente</label>
          <input id="up-lic" value={license} onChange={(e) => setLicense(e.target.value)} placeholder="p. ej. CC-BY 4.0" /></div>
        <div className="field"><label htmlFor="up-title">Título</label>
          <input id="up-title" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
        <div className="field"><label htmlFor="up-obs">Fecha de observación</label>
          <input id="up-obs" type="datetime-local" value={observed} onChange={(e) => setObserved(e.target.value)} /></div>
      </div>
      <div className="field"><label htmlFor="up-prov">Procedencia</label>
        <textarea id="up-prov" value={provenance} onChange={(e) => setProvenance(e.target.value)} placeholder="Cómo y dónde se obtuvo el dato" /></div>
      <fieldset className="field" style={{ border: "1px solid var(--gray-100)", borderRadius: 6 }}>
        <legend className="small"><strong>¿Los datos son reales o simulados? *</strong></legend>
        <div className="row">
          <label className="row" style={{ fontWeight: 400 }}><input type="radio" name="sim" checked={simulated === "false"} onChange={() => setSimulated("false")} /> Reales (medidos u obtenidos de una fuente)</label>
          <label className="row" style={{ fontWeight: 400 }}><input type="radio" name="sim" checked={simulated === "true"} onChange={() => setSimulated("true")} /> Simulados / de prueba</label>
        </div>
      </fieldset>
      <div><button className="btn" disabled={busy || !file || !source || !simulated}>{busy ? "Validando…" : "Cargar y validar"}</button></div>
      <ErrorText error={error} />
      {done && (
        <Notice kind="ok">
          Archivo aceptado: <strong>{done.title}</strong> ({done.data_type}). {done.validation_messages.length > 0 && (
            <>Observaciones: {done.validation_messages.join(" ")}</>
          )}
        </Notice>
      )}
    </form>
  );
}
