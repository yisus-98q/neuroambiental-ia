import { useEffect, useState } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { apiBlobUrl, canWrite, fmtDate, post, session } from "../services/api";
import { useApi } from "../services/useApi";

interface Param { name: string; type: string; default: number | boolean; min: number | null; max: number | null; description: string }
interface Operation { key: string; label: string; description: string; params: Param[] }
interface OpsInfo { operations: Operation[]; max_side_px: number; max_megapixels: number; confidence_note: string; limitations: string[]; opencv_version: string }
interface ImageRecord { id: string; title: string; is_simulated: boolean; file_format: string }
interface Region { id: number; area_px: number; area_pct: number; bbox: number[]; centroid: number[] }
interface VisionResult {
  id: string; title: string; is_simulated: boolean; provenance: string; sha256: string | null;
  image_url: string; overlay_url: string | null; received_at: string;
  extra: {
    kind: string; operation: string; params: Record<string, unknown>; source_record?: string; record_a?: string; record_b?: string;
    features: Record<string, unknown>; regions: Region[]; regions_total: number; regions_truncated: boolean;
    confidence: number | null; confidence_note: string; limitations: string[]; opencv_version: string;
  };
}

/** NEUROVISION: procesamiento clásico con OpenCV de imágenes registradas en NEURODATA. Sin modelos entrenados. */
export function NeurovisionPanel() {
  const ops = useApi<OpsInfo>("/api/neurovision/operations");
  const images = useApi<ImageRecord[]>("/api/neurodata/records?data_type=imagen&limit=200");
  const results = useApi<VisionResult[]>("/api/neurovision/results");
  const writable = canWrite(session.user());
  const [shown, setShown] = useState<VisionResult | null>(null);

  const done = (r: VisionResult) => { setShown(r); results.reload(); };

  return (
    <div className="stack">
      <Notice kind="info">
        Procesamiento <strong>clásico y determinista</strong> con OpenCV{ops.data ? ` ${ops.data.opencv_version}` : ""} sobre imágenes ya
        cargadas en NEURODATA. No hay clasificación ni detección con modelos entrenados. Las imágenes se reducen a
        {" "}{ops.data?.max_side_px ?? 2048} px por lado y se procesan de una en una.
      </Notice>
      {ops.error && <ErrorText error={String(ops.error)} />}
      {images.loading && <Loading what="imágenes" />}
      {writable && ops.data && images.data && (
        <div className="grid grid-2">
          <Analyze ops={ops.data} images={images.data} onDone={done} />
          <Compare images={images.data} onDone={done} />
        </div>
      )}
      {!writable && <Notice kind="dev">Su rol es de solo lectura: puede ver resultados, no ejecutar análisis.</Notice>}
      {images.data?.length === 0 && <p className="muted small">No hay imágenes en NEURODATA. Cargue una PNG/JPG primero.</p>}
      {shown && <ResultView result={shown} />}
      <div className="card stack">
        <h2>Resultados recientes</h2>
        {results.data?.length === 0 && <p className="muted small">Aún no hay resultados.</p>}
        <div className="table-wrap"><table>
          <tbody>{results.data?.map((r) => (
            <tr key={r.id}>
              <td className="small">{r.title}</td><td className="small">{fmtDate(r.received_at)}</td>
              <td>{r.is_simulated && <span className="badge badge-partial">simulado</span>}</td>
              <td><button className="btn" onClick={() => setShown(r)}>Ver</button></td>
            </tr>
          ))}</tbody>
        </table></div>
      </div>
    </div>
  );
}

function Analyze({ ops, images, onDone }: { ops: OpsInfo; images: ImageRecord[]; onDone: (r: VisionResult) => void }) {
  const [rid, setRid] = useState("");
  const [op, setOp] = useState(ops.operations[0]?.key ?? "");
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operation = ops.operations.find((o) => o.key === op);
  useEffect(() => setValues({}), [op]);

  async function run() {
    setBusy(true); setError(null);
    const params: Record<string, number | boolean> = {};
    for (const p of operation?.params ?? []) {
      const v = values[p.name];
      if (v === undefined || v === "") continue;
      params[p.name] = p.type === "bool" ? v === "true" : Number(v);
    }
    try { onDone(await post<VisionResult>("/api/neurovision/analyze", { record_id: rid, operation: op, params })); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="card stack">
      <h2>Analizar una imagen</h2>
      <div className="field"><label htmlFor="nv-img">Imagen (NEURODATA)</label>
        <select id="nv-img" value={rid} onChange={(e) => setRid(e.target.value)}>
          <option value="">Seleccione…</option>
          {images.map((i) => <option key={i.id} value={i.id}>{i.title}{i.is_simulated ? " (simulada)" : ""}</option>)}
        </select></div>
      <div className="field"><label htmlFor="nv-op">Operación</label>
        <select id="nv-op" value={op} onChange={(e) => setOp(e.target.value)}>
          {ops.operations.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select></div>
      {operation && <p className="small muted" style={{ margin: 0 }}>{operation.description}</p>}
      <div className="grid grid-2">
        {operation?.params.map((p) => (
          <div className="field" key={p.name}><label htmlFor={`nv-${p.name}`} title={p.description}>{p.name}</label>
            {p.type === "bool"
              ? <select id={`nv-${p.name}`} value={values[p.name] ?? String(p.default)} onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}>
                <option value="false">no</option><option value="true">sí</option></select>
              : <input id={`nv-${p.name}`} type="number" step="any" min={p.min ?? undefined} max={p.max ?? undefined}
                placeholder={String(p.default)} value={values[p.name] ?? ""} onChange={(e) => setValues({ ...values, [p.name]: e.target.value })} />}
          </div>
        ))}
      </div>
      <div><button className="btn" disabled={!rid || busy} onClick={run}>{busy ? "Procesando…" : "Analizar"}</button></div>
      <ErrorText error={error} />
    </div>
  );
}

function Compare({ images, onDone }: { images: ImageRecord[]; onDone: (r: VisionResult) => void }) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true); setError(null);
    try { onDone(await post<VisionResult>("/api/neurovision/compare", { record_a: a, record_b: b })); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  const opts = images.map((i) => <option key={i.id} value={i.id}>{i.title}</option>);
  return (
    <div className="card stack">
      <h2>Comparar dos imágenes</h2>
      <p className="small muted" style={{ margin: 0 }}>
        Solo para fotos comparables de la misma escena. Se alinea la segunda con la primera (ORB + RANSAC); no usa
        georreferenciación ni corrige diferencias de sensor.
      </p>
      <div className="field"><label htmlFor="nv-a">Imagen A (referencia)</label>
        <select id="nv-a" value={a} onChange={(e) => setA(e.target.value)}><option value="">Seleccione…</option>{opts}</select></div>
      <div className="field"><label htmlFor="nv-b">Imagen B (a comparar)</label>
        <select id="nv-b" value={b} onChange={(e) => setB(e.target.value)}><option value="">Seleccione…</option>{opts}</select></div>
      <div><button className="btn" disabled={!a || !b || a === b || busy} onClick={run}>{busy ? "Comparando…" : "Detectar cambios"}</button></div>
      <ErrorText error={error} />
    </div>
  );
}

/** Descarga una imagen autenticada como blob y la muestra; libera la URL al desmontar. */
function AuthImage({ path, alt }: { path: string | null; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let url: string | null = null; let live = true;
    setSrc(null); setErr(false);
    if (path) apiBlobUrl(path).then((u) => { url = u; if (live) setSrc(u); else URL.revokeObjectURL(u); }).catch(() => live && setErr(true));
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (!path) return <p className="muted small">No aplica.</p>;
  if (err) return <p className="error">No se pudo cargar la imagen.</p>;
  return src ? <img src={src} alt={alt} style={{ maxWidth: "100%", height: "auto" }} /> : <Loading what="imagen" />;
}

const fmt = (v: unknown) => (Array.isArray(v) ? v.join(" / ") : typeof v === "number" ? String(v) : String(v ?? "—"));

function ResultView({ result }: { result: VisionResult }) {
  const ex = result.extra;
  const isCompare = ex.kind === "comparacion";
  const originalId = ex.source_record ?? ex.record_a ?? "";
  return (
    <div className="card stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{result.title}</h2>
        {result.is_simulated && <span className="badge badge-partial">datos simulados</span>}
      </div>
      <div className="grid grid-2">
        <div className="stack"><strong className="small">Imagen original{isCompare ? " (A)" : ""}</strong>
          <AuthImage path={originalId ? `/api/neurodata/records/${originalId}/file` : null} alt="Imagen original" /></div>
        <div className="stack"><strong className="small">{isCompare ? "Cambios detectados (rojo)" : "Imagen procesada"}</strong>
          <AuthImage path={result.image_url} alt="Imagen procesada" /></div>
      </div>
      {result.overlay_url && (
        <div className="stack"><strong className="small">Superposición de regiones</strong>
          <AuthImage path={result.overlay_url} alt="Superposición de regiones" /></div>
      )}
      <div className="grid grid-2">
        <div className="stack"><strong className="small">Características</strong>
          <table><tbody>{Object.entries(ex.features).map(([k, v]) => (
            <tr key={k}><th className="small">{k.replace(/_/g, " ")}</th><td>{fmt(v)}</td></tr>
          ))}</tbody></table></div>
        <div className="stack"><strong className="small">Regiones ({ex.regions_total}{ex.regions_truncated ? `, se muestran ${ex.regions.length}` : ""})</strong>
          {ex.regions.length === 0 ? <p className="muted small">Esta operación no produce regiones o no se encontraron.</p> : (
            <div className="table-wrap" style={{ maxHeight: 280, overflowY: "auto" }}><table>
              <thead><tr><th>#</th><th>Área px</th><th>% imagen</th><th>Caja x,y,an,al</th><th>Centroide</th></tr></thead>
              <tbody>{ex.regions.map((r) => (
                <tr key={r.id}><td>{r.id}</td><td>{r.area_px}</td><td>{r.area_pct}</td><td>{r.bbox.join(", ")}</td><td>{r.centroid.join(", ")}</td></tr>
              ))}</tbody>
            </table></div>
          )}</div>
      </div>
      <div className="stack">
        <p style={{ margin: 0 }}><strong>Nivel de confianza:</strong> {ex.confidence === null ? ex.confidence_note : String(ex.confidence)}</p>
        <strong className="small">Limitaciones</strong>
        <ul className="small" style={{ margin: 0 }}>{ex.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        <p className="small muted" style={{ margin: 0 }}>Procedencia: {result.provenance}</p>
        <p className="small muted" style={{ margin: 0 }}>sha256: {result.sha256 ?? "—"}</p>
      </div>
    </div>
  );
}
