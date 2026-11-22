import { useEffect, useMemo, useState, type FormEvent } from "react";
import { SimBadge, StatusBadge } from "../components/Badges";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { canWrite, fmtDate, post, session } from "../services/api";
import type { AIModel, DataRecord, ModuleInfo, PredictResult } from "../services/types";
import { useApi } from "../services/useApi";

/** Estados honestos del ciclo de vida (sección 11 del prompt de integración). */
const STATE_LABEL: Record<string, [string, string]> = {
  planificado: ["Modelo configurado · entrenamiento pendiente", "badge-dev"],
  entrenado: ["Entrenado y evaluado · EXPERIMENTAL", "badge-partial"],
  validado: ["Aprobado (validado por un administrador)", "badge-ok"],
  retirado: ["Retirado", "badge-low"],
};

const fmt = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : String(v ?? "—"));

export function TrainingCenter() {
  const mod = useApi<ModuleInfo>("/api/neurocore/modules/neurotraining");
  const models = useApi<AIModel[]>("/api/neurotraining/models");
  const datasets = useApi<DataRecord[]>("/api/neurodata/records?data_type=csv&limit=200");
  const runs = useApi<{ id: string; run_type: string; status: string; started_at: string; result_summary: Record<string, unknown> }[]>("/api/neurotraining/runs");
  const [selected, setSelected] = useState<string | null>(null);
  const user = session.user();
  const model = models.data?.find((m) => m.id === selected) ?? null;
  const reload = () => { models.reload(); runs.reload(); };

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>NEURAL TRAINING CENTER</h1>
          <p className="muted" style={{ margin: 0 }}>Datasets → entrenamiento → evaluación con filas reservadas del mismo CSV → validación humana con datos externos.</p></div>
        {mod.data && <StatusBadge status={mod.data.status} />}
      </div>
      <Notice kind="info">
        Modelos ligeros de scikit-learn (sin redes neuronales profundas todavía). Terminar un entrenamiento <strong>no aprueba</strong> un modelo:
        solo un administrador puede validarlo, con evidencia, y nunca si se entrenó con datos simulados.
      </Notice>
      <div className="grid grid-2">
        <DatasetPanel datasets={datasets.data} loading={datasets.loading} />
        <ModelList models={models.data} selected={selected} onSelect={setSelected} onCreated={reload} writable={canWrite(user)} />
      </div>
      {model && <ModelDetail key={model.id + model.version} model={model} datasets={datasets.data ?? []} onChange={reload}
        writable={canWrite(user)} isAdmin={user?.role_key === "admin"} />}
      <div className="card">
        <h2>Historial de entrenamientos</h2>
        {runs.data?.filter((r) => r.run_type === "entrenamiento").length === 0 && <p className="muted small">Sin entrenamientos.</p>}
        <div className="table-wrap"><table><tbody>
          {runs.data?.filter((r) => r.run_type === "entrenamiento").map((r) => (
            <tr key={r.id}><td className="small">{fmtDate(r.started_at)}</td>
              <td><span className={`badge ${r.status === "ok" ? "badge-ok" : r.status === "error" ? "badge-high" : "badge-partial"}`}>{r.status}</span></td>
              <td className="small">{r.status === "ok" ? `v${String(r.result_summary.version)} · accuracy ${fmt(r.result_summary.accuracy)} · F1 ${fmt(r.result_summary.f1_macro)} · MAE ${fmt(r.result_summary.mae)}` : String(r.result_summary.error ?? "")}</td></tr>
          ))}
        </tbody></table></div>
      </div>
    </div>
  );
}

function DatasetPanel({ datasets, loading }: { datasets: DataRecord[] | null; loading: boolean }) {
  return (
    <div className="card">
      <div className="card-head"><h2>Datasets (CSV)</h2><a className="small" href="#/neurodata">Importar en NEURODATA →</a></div>
      {loading && <Loading />}
      {datasets?.length === 0 && <p className="muted small">No hay CSV. Cárguelos en NEURODATA indicando si son reales o simulados.</p>}
      <div className="table-wrap"><table><tbody>
        {datasets?.map((d) => (
          <tr key={d.id}><td><strong className="small">{d.title}</strong>
            <div className="small muted">{String(d.extra.rows ?? "?")} filas · {(d.extra.columns as string[] | undefined)?.length ?? "?"} columnas · {d.source_name}</div></td>
            <td><SimBadge simulated={d.is_simulated} /></td></tr>
        ))}
      </tbody></table></div>
    </div>
  );
}

function ModelList({ models, selected, onSelect, onCreated, writable }: { models: AIModel[] | null; selected: string | null;
  onSelect: (id: string) => void; onCreated: () => void; writable: boolean }) {
  const [name, setName] = useState("");
  const [moduleKey, setModuleKey] = useState("disasters");
  const all = useApi<ModuleInfo[]>("/api/neurocore/modules");
  const [error, setError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try { const m = await post<AIModel>("/api/neurotraining/models", { name, module_key: moduleKey }); setName(""); onCreated(); onSelect(m.id); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="card stack">
      <h2>Registro de modelos</h2>
      {models?.length === 0 && <p className="muted small">Ningún modelo registrado.</p>}
      <table><tbody>{models?.map((m) => {
        const [label, cls] = STATE_LABEL[m.status] ?? [m.status, "badge-low"];
        return (
          <tr key={m.id} onClick={() => onSelect(m.id)} style={{ cursor: "pointer", background: selected === m.id ? "var(--gray-50)" : undefined }}>
            <td><strong className="small">{m.name}</strong><div className="small muted">{m.module_key} · v{m.version} · {m.algorithm || "sin algoritmo"}</div></td>
            <td><span className={`badge ${cls}`}>{label}</span>{m.trained_with_simulated && <> <SimBadge simulated /></>}</td>
          </tr>
        );
      })}</tbody></table>
      {writable && (
        <form className="row" onSubmit={create}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre del nuevo modelo" required minLength={2} style={{ flex: 1 }} aria-label="Nombre del modelo" />
          <select value={moduleKey} onChange={(e) => setModuleKey(e.target.value)} style={{ width: "auto" }} aria-label="Módulo">
            {all.data?.map((m) => <option key={m.key} value={m.key}>{m.codename ?? m.name}</option>)}
          </select>
          <button className="btn">Registrar</button>
        </form>
      )}
      <ErrorText error={error} />
    </div>
  );
}

function ModelDetail({ model, datasets, onChange, writable, isAdmin }: { model: AIModel; datasets: DataRecord[];
  onChange: () => void; writable: boolean; isAdmin: boolean }) {
  return (
    <div className="grid grid-2">
      <div className="stack">
        <Metrics model={model} />
        {isAdmin && model.status === "entrenado" && <ValidateForm model={model} onChange={onChange} />}
        {model.status === "validado" && <div className="card"><h3>Evidencia de validación</h3><p className="small">{model.validation_evidence}</p></div>}
      </div>
      <div className="stack">
        {writable && model.status !== "validado" && model.status !== "retirado" && <TrainForm model={model} datasets={datasets} onDone={onChange} />}
        {writable && (model.status === "entrenado" || model.status === "validado") && <PredictForm model={model} datasets={datasets} />}
      </div>
    </div>
  );
}

function Metrics({ model }: { model: AIModel }) {
  const m = model.metrics as Record<string, unknown>;
  if (model.status === "planificado") return <div className="card"><h2>{model.name}</h2><p className="muted small">Aún no se ha entrenado: no hay métricas.</p></div>;
  const cm = m.confusion_matrix as { labels: string[]; matrix: number[][] } | undefined;
  const perClass = m.per_class as Record<string, { false_positives: number; false_negatives: number; support: number }> | undefined;
  const keys = model.task === "clasificacion"
    ? [["accuracy", "Accuracy"], ["baseline_majority", "Línea base (clase mayoritaria)"], ["precision_macro", "Precisión (macro)"], ["recall_macro", "Recall (macro)"], ["f1_macro", "F1 (macro)"], ["roc_auc", "ROC-AUC"], ["brier_score", "Brier (calibración, menor es mejor)"]]
    : [["mae", "MAE"], ["baseline_mae_mean", "MAE de la línea base (media)"], ["rmse", "RMSE"], ["r2", "R²"]];
  return (
    <div className="card stack">
      <div className="card-head"><h2>{model.name} · v{model.version}</h2>{model.trained_with_simulated && <SimBadge simulated />}</div>
      <p className="small muted" style={{ margin: 0 }}>{model.task} · objetivo «{model.target}» · entradas: {model.features.join(", ")} · entrenado {fmtDate(model.trained_at)} · {String(m.n_train)} filas de entrenamiento / {String(m.n_test)} de prueba</p>
      <table><tbody>{keys.filter(([k]) => k in m).map(([k, l]) => <tr key={k}><th>{l}</th><td>{fmt(m[k])}</td></tr>)}</tbody></table>
      {cm && (
        <div className="table-wrap"><h3>Matriz de confusión (filas: real, columnas: predicho)</h3><table>
          <thead><tr><th></th>{cm.labels.map((l) => <th key={l}>{l}</th>)}</tr></thead>
          <tbody>{cm.matrix.map((row, i) => <tr key={i}><th>{cm.labels[i]}</th>{row.map((v, j) => <td key={j} style={{ fontWeight: i === j ? 700 : 400 }}>{v}</td>)}</tr>)}</tbody>
        </table></div>
      )}
      {perClass && <p className="small">{Object.entries(perClass).map(([c, v]) => `${c}: ${v.false_positives} falsos positivos, ${v.false_negatives} falsos negativos`).join(" · ")}</p>}
      <p className="small" style={{ margin: 0 }}>Evaluación: {String(m.evaluated_on ?? "")}</p>
      {Array.isArray(m.warnings) && (m.warnings as string[]).map((w) => <Notice key={w} kind="dev">{w}</Notice>)}
      <p className="small muted" style={{ margin: 0 }}>Huella del artefacto: <code>{model.artifact_sha256?.slice(0, 16)}…</code></p>
    </div>
  );
}

function TrainForm({ model, datasets, onDone }: { model: AIModel; datasets: DataRecord[]; onDone: () => void }) {
  const [dsId, setDsId] = useState(model.dataset_record_id ?? "");
  const [task, setTask] = useState<"clasificacion" | "regresion">(model.task ?? "clasificacion");
  const [target, setTarget] = useState(model.target ?? "");
  const [features, setFeatures] = useState<string[]>(model.features ?? []);
  const [algorithm, setAlgorithm] = useState(model.algorithm || "random_forest");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const columns = useMemo(() => (datasets.find((d) => d.id === dsId)?.extra.columns as string[] | undefined) ?? [], [datasets, dsId]);
  const algos = task === "clasificacion" ? ["random_forest", "regresion_logistica"] : ["random_forest", "ridge"];
  // Al cambiar de tarea, el algoritmo debe ser válido para ella.
  useEffect(() => { if (!algos.includes(algorithm)) setAlgorithm(algos[0]); }, [task]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { await post(`/api/neurotraining/models/${model.id}/train`, { dataset_record_id: dsId, task, target, features, algorithm }); onDone(); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{model.status === "planificado" ? "Entrenar" : "Reentrenar (nueva versión)"}</h2>
      <div className="field"><label htmlFor="tr-ds">Dataset</label>
        <select id="tr-ds" value={dsId} onChange={(e) => { setDsId(e.target.value); setFeatures([]); setTarget(""); }} required>
          <option value="">Seleccione un CSV…</option>
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.title} {d.is_simulated ? "(SIMULADO)" : "(real)"}</option>)}
        </select></div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="tr-task">Tarea</label>
          <select id="tr-task" value={task} onChange={(e) => setTask(e.target.value as "clasificacion" | "regresion")}>
            <option value="clasificacion">Clasificación</option><option value="regresion">Regresión</option></select></div>
        <div className="field"><label htmlFor="tr-alg">Algoritmo</label>
          <select id="tr-alg" value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>{algos.map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
      </div>
      <div className="field"><label htmlFor="tr-target">Columna objetivo</label>
        <select id="tr-target" value={target} onChange={(e) => { setTarget(e.target.value); setFeatures((f) => f.filter((x) => x !== e.target.value)); }} required>
          <option value="">Seleccione…</option>{columns.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
      <fieldset className="field" style={{ border: "1px solid var(--gray-100)", borderRadius: 6 }}>
        <legend className="small"><strong>Columnas de entrada (numéricas)</strong></legend>
        <div className="row">{columns.filter((c) => c !== target).map((c) => (
          <label key={c} className="row" style={{ fontWeight: 400 }}><input type="checkbox" checked={features.includes(c)}
            onChange={() => setFeatures((f) => (f.includes(c) ? f.filter((x) => x !== c) : [...f, c]))} /> {c}</label>
        ))}{columns.length === 0 && <span className="small muted">Elija un dataset.</span>}</div>
      </fieldset>
      <div><button className="btn" disabled={busy || !dsId || !target || features.length === 0}>{busy ? "Entrenamiento en ejecución…" : "Entrenar"}</button></div>
      {busy && <p className="small muted" style={{ margin: 0 }}>El entrenamiento se ejecuta en el servidor; esta pantalla espera el resultado real (sin barra de progreso simulada).</p>}
      <ErrorText error={error} />
    </form>
  );
}

function ValidateForm({ model, onChange }: { model: AIModel; onChange: () => void }) {
  const [evidence, setEvidence] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try { await post(`/api/neurotraining/models/${model.id}/validate`, { evidence, version: model.version, artifact_sha256: model.artifact_sha256 }); onChange(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Validación (administrador)</h2>
      {model.trained_with_simulated
        ? <Notice kind="dev">Entrenado con datos simulados: no puede validarse. Entrene con datos reales.</Notice>
        : <>
          <div className="field"><label htmlFor="val-ev">Evidencia: datos externos independientes usados, métricas obtenidas y quién revisó (aprueba la versión v{model.version} mostrada)</label>
            <textarea id="val-ev" value={evidence} onChange={(e) => setEvidence(e.target.value)} minLength={40} required /></div>
          <div><button className="btn btn-green">Aprobar modelo</button></div>
        </>}
      <ErrorText error={error} />
    </form>
  );
}

function PredictForm({ model, datasets }: { model: AIModel; datasets: DataRecord[] }) {
  const [dsId, setDsId] = useState("");
  const [res, setRes] = useState<PredictResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setRes(null);
    try { setRes(await post<PredictResult>(`/api/neurotraining/models/${model.id}/predict`, { dataset_record_id: dsId })); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Predecir</h2>
      <div className="row">
        <select value={dsId} onChange={(e) => setDsId(e.target.value)} required style={{ flex: 1 }} aria-label="Dataset para predecir">
          <option value="">CSV con las columnas: {model.features.join(", ")}</option>
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.title} {d.is_simulated ? "(SIMULADO)" : "(real)"}</option>)}
        </select>
        <button className="btn">Predecir</button>
      </div>
      <ErrorText error={error} />
      {res && (
        <>
          <Notice kind={res.is_validated ? "info" : "dev"}>{res.uncertainty}</Notice>
          <p className="small">{res.n} filas predichas · {res.skipped} omitidas · resumen: {JSON.stringify(res.summary)}</p>
          <div className="table-wrap" style={{ maxHeight: 220, overflowY: "auto" }}><table>
            <thead><tr><th>Fila</th><th>Predicción</th><th>Probabilidad del modelo (no calibrada)</th></tr></thead>
            <tbody>{res.rows.slice(0, 50).map((r) => <tr key={r.row}><td>{r.row + 1}</td><td>{String(r.prediction)}</td><td>{r.model_probability ?? "—"}</td></tr>)}</tbody>
          </table></div>
        </>
      )}
    </form>
  );
}
