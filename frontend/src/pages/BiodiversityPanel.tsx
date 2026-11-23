import { useState, type FormEvent } from "react";
import { SimBadge } from "../components/Badges";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { api, canWrite, fmtDate, post, session } from "../services/api";
import type { DataRecord } from "../services/types";
import { useApi } from "../services/useApi";

export interface Species {
  id: string; nombre_cientifico: string; nombre_comun: string; reino: string | null; clase: string | null;
  orden: string | null; familia: string | null; categoria_conservacion: string | null;
  fuente_taxonomica: string; notas: string; created_at: string; aviso_categoria: string;
}
export interface BioObservation {
  id: string; species_id: string | null; nombre_cientifico: string | null; nombre_comun: string;
  latitude: number; longitude: number; fecha_observacion: string; observador: string; cantidad: number;
  metodo: string; photo_record_id: string | null; confianza_identificacion: string;
  estado_validacion: "no_validada" | "validada" | "descartada"; validation_note: string;
  is_simulated: boolean; created_at: string;
}
export interface BioSummary {
  total_observaciones: number; truncado: boolean;
  por_especie: { species_id: string | null; nombre_cientifico: string; observaciones: number; individuos: number }[];
  por_mes: { mes: string; observaciones: number }[];
  por_estado: Record<string, number>;
  riqueza_especies: number; riqueza_especies_solo_reales: number; riqueza_nota: string; aviso: string;
}

const CATEGORIES = ["EX", "EW", "CR", "EN", "VU", "NT", "LC", "DD", "NE"];
const METHODS = ["avistamiento", "camara_trampa", "huella", "audio", "muestra", "otro"];
const STATE_LABEL: Record<string, string> = { no_validada: "No validada", validada: "Validada", descartada: "Descartada" };

function StateBadge({ state }: { state: string }) {
  const cls = state === "validada" ? "badge-ok" : state === "descartada" ? "badge-high" : "badge-low";
  return <span className={`badge ${cls}`}>{STATE_LABEL[state] ?? state}</span>;
}

export function BiodiversityPanel() {
  const user = session.user();
  const writable = canWrite(user);
  const [q, setQ] = useState("");
  const species = useApi<Species[]>(`/api/biodiversity/species?limit=500${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ""}`);
  const allSpecies = useApi<Species[]>("/api/biodiversity/species?limit=500");
  const obs = useApi<BioObservation[]>("/api/biodiversity/observations?limit=200");
  const summary = useApi<BioSummary>("/api/biodiversity/summary");
  const refresh = () => { species.reload(); allSpecies.reload(); obs.reload(); summary.reload(); };

  return (
    <div className="stack">
      <Notice kind="info">
        <strong>Registro de biodiversidad.</strong> La especie de cada observación la declara quien observa y el sistema
        no la verifica: no hay reconocimiento automático de especies ni análisis de fotografías. El catálogo empieza vacío.
      </Notice>
      <SummaryCard summary={summary} />
      <div className="grid grid-2">
        <div className="card stack">
          <h2>Especies</h2>
          <div className="field"><label htmlFor="sp-q">Buscar por nombre científico o común</label>
            <input id="sp-q" value={q} onChange={(e) => setQ(e.target.value)} maxLength={100} /></div>
          <ErrorText error={species.error} />
          {species.loading && <Loading what="especies" />}
          {species.data?.length === 0 && <p className="muted">No hay especies{q ? " que coincidan" : " registradas"}.</p>}
          <div className="table-wrap"><table>
            <thead><tr><th>Científico</th><th>Común</th><th>Conservación*</th><th>Fuente</th></tr></thead>
            <tbody>{species.data?.map((s) => (
              <tr key={s.id}><td><em>{s.nombre_cientifico}</em></td><td>{s.nombre_comun || "—"}</td>
                <td>{s.categoria_conservacion ?? "—"}</td><td className="small">{s.fuente_taxonomica}</td></tr>
            ))}</tbody>
          </table></div>
          <p className="small muted">* Categoría tipo UICN según la fuente indicada; el sistema no la evalúa.</p>
          {writable ? <SpeciesForm onCreated={refresh} /> : <p className="small muted">Su rol es de solo lectura.</p>}
        </div>
        {writable
          ? <div className="card stack"><h2>Nueva observación</h2><ObservationForm species={allSpecies.data ?? []} onCreated={refresh} /></div>
          : <div className="card muted">Solo analistas y administradores pueden registrar observaciones.</div>}
      </div>
      <div className="card stack">
        <div className="card-head"><h2>Observaciones</h2>
          <a className="btn btn-ghost" href="/mapa">Ver en el mapa</a></div>
        <ErrorText error={obs.error} />
        {obs.loading && <Loading what="observaciones" />}
        {obs.data?.length === 0 && <p className="muted">No hay observaciones registradas.</p>}
        <div className="table-wrap"><table>
          <thead><tr><th>Especie</th><th>Fecha</th><th>Ubicación</th><th>Cant.</th><th>Método / confianza</th><th>Estado</th><th></th></tr></thead>
          <tbody>{obs.data?.map((o) => (
            <ObservationRow key={o.id} o={o} admin={user?.role_key === "admin"} onChanged={refresh} />
          ))}</tbody>
        </table></div>
      </div>
    </div>
  );
}

function SummaryCard({ summary }: { summary: ReturnType<typeof useApi<BioSummary>> }) {
  const s = summary.data;
  return (
    <div className="card stack">
      <h2>Resumen</h2>
      <ErrorText error={summary.error} />
      {summary.loading && !s && <Loading what="resumen" />}
      {s && (
        <>
          <div className="grid grid-3">
            <div><div className="small muted">Observaciones</div><strong>{s.total_observaciones}</strong></div>
            <div><div className="small muted">Riqueza observada (especies distintas)</div>
              <strong>{s.riqueza_especies}</strong> <span className="small muted">({s.riqueza_especies_solo_reales} con datos reales)</span></div>
            <div><div className="small muted">Por estado</div>
              <span className="small">{Object.entries(s.por_estado).map(([k, v]) => `${STATE_LABEL[k] ?? k}: ${v}`).join(" · ")}</span></div>
          </div>
          <p className="small muted">{s.aviso}</p>
          {s.truncado && <p className="small error">Resumen truncado: hay más observaciones de las que se procesan.</p>}
          <div className="grid grid-2">
            <div><h3>Por especie</h3>
              {s.por_especie.length === 0 ? <p className="small muted">Sin datos.</p> : (
                <ul className="small">{s.por_especie.map((e) => (
                  <li key={e.species_id ?? "x"}><em>{e.nombre_cientifico}</em>: {e.observaciones} obs., {e.individuos} individuos</li>
                ))}</ul>)}</div>
            <div><h3>Por mes</h3>
              {s.por_mes.length === 0 ? <p className="small muted">Sin datos.</p> : (
                <ul className="small">{s.por_mes.map((m) => <li key={m.mes}>{m.mes}: {m.observaciones}</li>)}</ul>)}</div>
          </div>
        </>
      )}
    </div>
  );
}

function ObservationRow({ o, admin, onChanged }: { o: BioObservation; admin: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function validate(estado: "validada" | "descartada") {
    const nota = window.prompt(`Nota obligatoria para marcar como ${estado}:`);
    if (!nota || nota.trim().length < 3) return;
    setError(null);
    try { await post(`/api/biodiversity/observations/${o.id}/validate`, { estado, nota: nota.trim() }); onChanged(); }
    catch (e) { setError((e as Error).message); }
  }
  return (
    <tr>
      <td>{o.nombre_cientifico ? <em>{o.nombre_cientifico}</em> : <span className="muted">No identificada</span>}
        <div className="small"><SimBadge simulated={o.is_simulated} /></div></td>
      <td>{fmtDate(o.fecha_observacion)}<div className="small muted">{o.observador}</div></td>
      <td className="small">{o.latitude.toFixed(4)}, {o.longitude.toFixed(4)}</td>
      <td>{o.cantidad}</td>
      <td className="small">{o.metodo}<div className="muted">confianza declarada: {o.confianza_identificacion}</div>
        {o.photo_record_id && <div className="muted">con foto</div>}</td>
      <td><StateBadge state={o.estado_validacion} />
        {o.validation_note && <div className="small muted">{o.validation_note}</div>}<ErrorText error={error} /></td>
      <td>{admin && <div className="row">
        <button className="btn btn-green" onClick={() => validate("validada")}>Validar</button>
        <button className="btn btn-ghost" onClick={() => validate("descartada")}>Descartar</button></div>}</td>
    </tr>
  );
}

function SpeciesForm({ onCreated }: { onCreated: () => void }) {
  const empty = { nombre_cientifico: "", nombre_comun: "", reino: "", clase: "", orden: "", familia: "", categoria_conservacion: "", fuente_taxonomica: "", notas: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await post("/api/biodiversity/species", { ...f, categoria_conservacion: f.categoria_conservacion || null });
      setF(empty); onCreated();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="stack">
      <h3>Nueva especie</h3>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="s-sci">Nombre científico *</label><input id="s-sci" value={f.nombre_cientifico} onChange={set("nombre_cientifico")} required minLength={3} /></div>
        <div className="field"><label htmlFor="s-com">Nombre común</label><input id="s-com" value={f.nombre_comun} onChange={set("nombre_comun")} /></div>
        <div className="field"><label htmlFor="s-rei">Reino</label><input id="s-rei" value={f.reino} onChange={set("reino")} /></div>
        <div className="field"><label htmlFor="s-cla">Clase</label><input id="s-cla" value={f.clase} onChange={set("clase")} /></div>
        <div className="field"><label htmlFor="s-ord">Orden</label><input id="s-ord" value={f.orden} onChange={set("orden")} /></div>
        <div className="field"><label htmlFor="s-fam">Familia</label><input id="s-fam" value={f.familia} onChange={set("familia")} /></div>
        <div className="field"><label htmlFor="s-cat">Categoría de conservación (según la fuente)</label>
          <select id="s-cat" value={f.categoria_conservacion} onChange={set("categoria_conservacion")}>
            <option value="">Sin indicar</option>{CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
        <div className="field"><label htmlFor="s-fue">Fuente taxonómica *</label><input id="s-fue" value={f.fuente_taxonomica} onChange={set("fuente_taxonomica")} required minLength={3} placeholder="Libro, base de datos, autor…" /></div>
      </div>
      <div className="field"><label htmlFor="s-not">Notas</label><textarea id="s-not" value={f.notas} onChange={set("notas")} /></div>
      <div><button className="btn" disabled={busy}>{busy ? "Guardando…" : "Registrar especie"}</button></div>
      <ErrorText error={error} />
    </form>
  );
}

function ObservationForm({ species, onCreated }: { species: Species[]; onCreated: () => void }) {
  const images = useApi<DataRecord[]>("/api/neurodata/records?data_type=imagen&limit=100");
  const empty = { species_id: "", latitude: "", longitude: "", fecha_observacion: "", observador: "", cantidad: "1", metodo: "avistamiento", confianza_identificacion: "baja", photo_record_id: "", is_simulated: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await api("/api/biodiversity/observations", { method: "POST", body: JSON.stringify({
        species_id: f.species_id || null, latitude: Number(f.latitude), longitude: Number(f.longitude),
        fecha_observacion: new Date(f.fecha_observacion).toISOString(), observador: f.observador,
        cantidad: Number(f.cantidad), metodo: f.metodo, confianza_identificacion: f.confianza_identificacion,
        photo_record_id: f.photo_record_id || null, is_simulated: f.is_simulated === "true" }) });
      setF(empty); onCreated();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="o-sp">Especie</label>
        <select id="o-sp" value={f.species_id} onChange={set("species_id")}>
          <option value="">No identificada</option>
          {species.map((s) => <option key={s.id} value={s.id}>{s.nombre_cientifico}{s.nombre_comun ? ` (${s.nombre_comun})` : ""}</option>)}</select></div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="o-lat">Latitud *</label><input id="o-lat" type="number" step="any" min={-90} max={90} value={f.latitude} onChange={set("latitude")} required /></div>
        <div className="field"><label htmlFor="o-lon">Longitud *</label><input id="o-lon" type="number" step="any" min={-180} max={180} value={f.longitude} onChange={set("longitude")} required /></div>
        <div className="field"><label htmlFor="o-fec">Fecha y hora *</label><input id="o-fec" type="datetime-local" max={new Date().toISOString().slice(0, 16)} value={f.fecha_observacion} onChange={set("fecha_observacion")} required /></div>
        <div className="field"><label htmlFor="o-obs">Observador *</label><input id="o-obs" value={f.observador} onChange={set("observador")} required minLength={2} /></div>
        <div className="field"><label htmlFor="o-can">Cantidad *</label><input id="o-can" type="number" min={1} step={1} value={f.cantidad} onChange={set("cantidad")} required /></div>
        <div className="field"><label htmlFor="o-met">Método *</label>
          <select id="o-met" value={f.metodo} onChange={set("metodo")}>{METHODS.map((m) => <option key={m} value={m}>{m}</option>)}</select></div>
        <div className="field"><label htmlFor="o-con">Confianza en la identificación (declarada) *</label>
          <select id="o-con" value={f.confianza_identificacion} onChange={set("confianza_identificacion")}>
            <option value="baja">Baja</option><option value="media">Media</option><option value="alta">Alta</option></select></div>
        <div className="field"><label htmlFor="o-foto">Foto ya cargada en NEURODATA</label>
          <select id="o-foto" value={f.photo_record_id} onChange={set("photo_record_id")}>
            <option value="">Sin foto</option>
            {images.data?.map((r) => <option key={r.id} value={r.id}>{r.title || r.id.slice(0, 8)}</option>)}</select></div>
        <div className="field"><label htmlFor="o-sim">¿Dato simulado? *</label>
          <select id="o-sim" value={f.is_simulated} onChange={set("is_simulated")} required>
            <option value="">Seleccione…</option><option value="false">No, es una observación real</option><option value="true">Sí, es una prueba</option></select></div>
      </div>
      <div><button className="btn" disabled={busy}>{busy ? "Guardando…" : "Registrar observación"}</button></div>
      <ErrorText error={error} />
    </form>
  );
}
