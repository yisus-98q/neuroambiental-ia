import { lazy, Suspense, useEffect, useState } from "react";
import { SimBadge } from "../components/Badges";
import { ErrorText, Loading } from "../components/Notice";
import { ALERT_COLORS, PALETTE } from "../maps/colors";
import type { Layer } from "../services/types";
import { useApi } from "../services/useApi";

const TerritorialMap = lazy(() => import("../maps/TerritorialMap"));

export function MapPage() {
  const layers = useApi<Layer[]>("/api/neurodata/layers");
  const alerts = useApi<GeoJSON.FeatureCollection>("/api/alerts/geojson");
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [showAlerts, setShowAlerts] = useState(true);
  const [markerMode, setMarkerMode] = useState(false);
  const [osmBase, setOsmBase] = useState(false);
  const [focus, setFocus] = useState<number[] | null>(null);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (layers.data) setVisible(new Set(layers.data.map((l) => l.record_id)));
  }, [layers.data]);

  const toggle = (id: string) => setVisible((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const fit = (l: Layer) => {
    const xs: number[] = [], ys: number[] = [];
    const walk = (c: unknown): void => {
      if (Array.isArray(c) && typeof c[0] === "number") { xs.push(c[0] as number); ys.push(c[1] as number); }
      else if (Array.isArray(c)) c.forEach(walk);
    };
    l.geojson.features.forEach((f: GeoJSON.Feature) => f.geometry && "coordinates" in f.geometry && walk(f.geometry.coordinates));
    if (xs.length) setFocus([Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]);
  };

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>Mapa territorial</h1>
          <p className="muted" style={{ margin: 0 }}>Capas cargadas en NEURODATA y alertas registradas. Haga clic en un elemento para consultar su información.</p></div>
        <label className="row" style={{ fontWeight: 400 }}>
          <input type="checkbox" checked={markerMode} onChange={(e) => setMarkerMode(e.target.checked)} /> Modo marcador (clic en el mapa)
        </label>
      </div>
      <ErrorText error={layers.error || alerts.error} />
      <div className="map-layout">
        <Suspense fallback={<Loading what="mapa" />}>
          <TerritorialMap layers={layers.data ?? []} visible={visible} alerts={alerts.data} showAlerts={showAlerts}
            markerMode={markerMode} focusBbox={focus} osmBase={osmBase} onSelect={setSelected} />
        </Suspense>
        <div className="stack">
          <div className="card">
            <h2>Capas</h2>
            {layers.loading && <Loading what="capas" />}
            {layers.data?.length === 0 && <p className="small muted">No hay capas. Cargue un CSV con latitud/longitud o un GeoJSON en NEURODATA.</p>}
            <div className="stack">
              {layers.data?.map((l, i) => (
                <div key={l.record_id} className="row" style={{ justifyContent: "space-between" }}>
                  <label className="row" style={{ fontWeight: 400, flex: 1, margin: 0 }}>
                    <input type="checkbox" checked={visible.has(l.record_id)} onChange={() => toggle(l.record_id)} />
                    <span className="legend-swatch" style={{ background: PALETTE[i % PALETTE.length] }} />
                    <span className="small">{l.title}</span>
                  </label>
                  <SimBadge simulated={l.is_simulated} />
                  <button className="btn btn-ghost small" style={{ padding: "2px 8px" }} onClick={() => fit(l)}>Ir</button>
                </div>
              ))}
              <label className="row" style={{ fontWeight: 400, margin: 0 }}>
                <input type="checkbox" checked={showAlerts} onChange={(e) => setShowAlerts(e.target.checked)} />
                <span className="small">Alertas experimentales ({alerts.data?.features.length ?? 0})</span>
              </label>
            </div>
          </div>
          <div className="card">
            <h2>Leyenda</h2>
            <div className="stack small">
              {Object.entries(ALERT_COLORS).map(([k, c]) => (
                <div key={k} className="row"><span className="legend-swatch" style={{ background: c, borderRadius: "50%" }} /> Alerta nivel {k}</div>
              ))}
              <div className="row"><span className="legend-swatch" style={{ border: "2px dashed #555" }} /> Borde punteado / contorno morado = dato simulado</div>
            </div>
          </div>
          <div className="card">
            <h2>Selección</h2>
            {!selected ? <p className="small muted">Ningún elemento seleccionado.</p> : (
              <table><tbody>
                {Object.entries(selected).map(([k, v]) => <tr key={k}><th>{k}</th><td>{String(v)}</td></tr>)}
              </tbody></table>
            )}
          </div>
          <div className="card">
            <h2>Mapa base</h2>
            <p className="small muted">Países de Natural Earth (dominio público), local y sin internet. Perú resaltado en verde.</p>
            <label className="row" style={{ fontWeight: 400, margin: 0 }}>
              <input type="checkbox" checked={osmBase} onChange={(e) => setOsmBase(e.target.checked)} />
              <span className="small">Detalle OpenStreetMap (opcional, requiere internet; sus servidores pueden rechazar teselas según su política de uso)</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
