import { useState, type CSSProperties } from "react";
import { ErrorText, Loading, Notice } from "../components/Notice";
import { fmtDate } from "../services/api";
import { useApi } from "../services/useApi";

type Tipo = "observacion_real" | "dato_historico" | "resultado_procesamiento" | "estimacion_modelo"
  | "simulacion" | "prediccion" | "alerta_verificada" | "alerta_experimental";

interface CatalogItem {
  id: string;
  tipo: Tipo;
  titulo: string;
  ubicacion: { lat?: number; lon?: number; bbox?: number[] } | null;
  fecha_analisis: string | null;
  fecha_observacion: string | null;
  datos_utilizados: Record<string, string>[];
  modelo: string | null;
  version: string | null;
  horizonte_temporal: string | null;
  resultado: string;
  probabilidad: number | null;
  probabilidad_nota: string;
  incertidumbre: string;
  evidencias: string[];
  limitaciones: string[];
  recomendaciones_de_verificacion: string;
  simulated: boolean;
  verificado: boolean;
}

interface Catalog { total: number; totales_por_tipo: Record<Tipo, number>; limit: number; offset: number; items: CatalogItem[] }
interface Kind { tipo: Tipo; etiqueta: string; definicion: string; regla: string; verificado: boolean }

/** Una insignia de color distinta por tipo (clases existentes; teal y naranja se añaden en línea). */
const BADGE: Record<Tipo, { cls: string; style?: CSSProperties }> = {
  observacion_real: { cls: "badge-ok" },
  dato_historico: { cls: "badge-low" },
  resultado_procesamiento: { cls: "badge-partial" },
  estimacion_modelo: { cls: "badge-dev" },
  simulacion: { cls: "badge-sim" },
  prediccion: { cls: "badge", style: { background: "#ccfbf1", color: "#0f766e" } },
  alerta_verificada: { cls: "badge-high" },
  alerta_experimental: { cls: "badge", style: { background: "#ffedd5", color: "#9a3412" } },
};

const PAGE = 50;

function TipoBadge({ tipo, label }: { tipo: Tipo; label: string }) {
  const b = BADGE[tipo];
  return <span className={`badge ${b.cls}`} style={b.style}>{label}</span>;
}

const place = (u: CatalogItem["ubicacion"]) =>
  !u ? "—" : u.lat !== undefined && u.lon !== undefined ? `${u.lat.toFixed(4)}, ${u.lon.toFixed(4)}`
    : u.bbox ? `bbox ${u.bbox.map((n) => n.toFixed(2)).join(", ")}` : "—";

export function PredictionPanel() {
  const [tipo, setTipo] = useState<Tipo | "">("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const kinds = useApi<Kind[]>("/api/neuroprediction/kinds");
  const cat = useApi<Catalog>(`/api/neuroprediction/catalog?limit=${PAGE}&offset=${offset}${tipo ? `&tipo=${tipo}` : ""}`);
  const label = (t: Tipo) => kinds.data?.find((k) => k.tipo === t)?.etiqueta ?? t;
  const item = cat.data?.items.find((i) => i.id === selected) ?? null;
  const pick = (t: Tipo | "") => { setTipo(t); setOffset(0); setSelected(null); };
  const totals = cat.data?.totales_por_tipo;

  return (
    <div className="stack">
      <h1>NEURO PREDICTION ENGINE</h1>
      <Notice kind="info">
        Cada resultado pertenece a <strong>un solo tipo</strong>: una observación real no es una estimación de un modelo, una
        simulación no es una predicción y una alerta sin validar no es una alerta verificada. Lo simulado lleva siempre la insignia
        SIMULADO y nunca se presenta como observación ni predicción. Las probabilidades solo aparecen con modelos validados y no
        están calibradas; el sistema no define horizontes temporales.
      </Notice>

      <div className="row">
        <button type="button" className={tipo === "" ? "btn" : "btn btn-ghost"} onClick={() => pick("")}>
          Todos ({totals ? Object.values(totals).reduce((a, b) => a + b, 0) : "…"})
        </button>
        {(Object.keys(BADGE) as Tipo[]).map((t) => (
          <button key={t} type="button" className={tipo === t ? "btn" : "btn btn-ghost"} onClick={() => pick(t)}>
            {label(t)} ({totals ? totals[t] : "…"})
          </button>
        ))}
      </div>
      {tipo && kinds.data && (
        <p className="muted">
          {kinds.data.find((k) => k.tipo === tipo)?.definicion} <em>Regla: {kinds.data.find((k) => k.tipo === tipo)?.regla}</em>
        </p>
      )}

      <div className="card">
        {cat.loading && <Loading what="catálogo" />}
        <ErrorText error={cat.error} />
        {cat.data && cat.data.items.length === 0 && <p className="muted small">Sin elementos de este tipo todavía.</p>}
        {cat.data && cat.data.items.length > 0 && (
          <div className="table-wrap"><table>
            <thead><tr><th>Tipo</th><th>Título</th><th>Ubicación</th><th>Análisis</th><th>Observación</th>
              <th>Modelo / versión</th><th>Incertidumbre</th><th></th></tr></thead>
            <tbody>
              {cat.data.items.map((i) => (
                <tr key={`${i.tipo}-${i.id}`} onClick={() => setSelected(i.id)} style={{ cursor: "pointer" }}
                  aria-selected={i.id === selected}>
                  <td><TipoBadge tipo={i.tipo} label={label(i.tipo)} /></td>
                  <td>{i.titulo}</td>
                  <td className="small">{place(i.ubicacion)}</td>
                  <td className="small">{fmtDate(i.fecha_analisis)}</td>
                  <td className="small">{fmtDate(i.fecha_observacion)}</td>
                  <td className="small">{i.modelo ? `${i.modelo}${i.version ? ` v${i.version}` : ""}` : "—"}</td>
                  <td className="small">{i.incertidumbre.length > 70 ? `${i.incertidumbre.slice(0, 70)}…` : i.incertidumbre}</td>
                  <td>{i.simulated && <span className="badge badge-sim">SIMULADO</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        {cat.data && cat.data.total > PAGE && (
          <div className="row" style={{ marginTop: 8 }}>
            <button type="button" className="btn btn-ghost" disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}>Anterior</button>
            <span className="muted small">{offset + 1}–{Math.min(offset + PAGE, cat.data.total)} de {cat.data.total}</span>
            <button type="button" className="btn btn-ghost" disabled={offset + PAGE >= cat.data.total}
              onClick={() => setOffset(offset + PAGE)}>Siguiente</button>
          </div>
        )}
      </div>

      {item && <Detail item={item} label={label(item.tipo)} />}
    </div>
  );
}

function Detail({ item, label }: { item: CatalogItem; label: string }) {
  const list = (xs: string[]) => xs.length === 0 ? <p className="muted small">Sin información registrada.</p>
    : <ul>{xs.map((x, n) => <li key={n} className="small">{x}</li>)}</ul>;
  return (
    <div className="card stack">
      <div className="row">
        <TipoBadge tipo={item.tipo} label={label} />
        {item.simulated && <span className="badge badge-sim">SIMULADO</span>}
        {!item.verificado && <span className="badge badge-low">NO VERIFICADO</span>}
        <h2 style={{ margin: 0 }}>{item.titulo}</h2>
      </div>
      <p>{item.resultado || "—"}</p>
      <div className="grid grid-2">
        <div>
          <p className="small"><strong>Probabilidad:</strong> {item.probabilidad === null ? "no disponible" : item.probabilidad.toFixed(3)}
            {" "}<span className="muted">({item.probabilidad_nota})</span></p>
          <p className="small"><strong>Horizonte temporal:</strong> {item.horizonte_temporal ?? "no definido"}</p>
          <p className="small"><strong>Incertidumbre:</strong> {item.incertidumbre}</p>
          <p className="small"><strong>Datos utilizados:</strong> {item.datos_utilizados.length === 0 ? "—"
            : item.datos_utilizados.map((d) => Object.entries(d).map(([k, v]) => `${k}: ${v}`).join(" · ")).join(" | ")}</p>
        </div>
        <div>
          <h3>Evidencias</h3>{list(item.evidencias)}
          <h3>Limitaciones</h3>{list(item.limitaciones)}
          <h3>Cómo verificar</h3><p className="small">{item.recomendaciones_de_verificacion}</p>
        </div>
      </div>
    </div>
  );
}
