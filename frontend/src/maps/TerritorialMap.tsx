import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapMouseEvent, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre 6 procesa los datos en un web worker que vive en un archivo aparte:
// Vite lo copia a dist/assets y nos da su URL.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { Layer } from "../services/types";
import { ALERT_COLORS, PALETTE } from "./colors";

// Mapa base LOCAL: países de Natural Earth 1:110m (dominio público), servido por la propia app.
// Funciona sin internet y sin depender de servidores de terceros.
// OpenStreetMap queda como capa OPCIONAL (desactivada por defecto): sus servidores pueden
// rechazar teselas según su política de uso (https://operations.osmfoundation.org/policies/tiles/).
const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    paises: {
      type: "geojson",
      data: "/basemap/paises.geojson",
      attribution: 'Países: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a> (dominio público)',
    },
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    },
  },
  layers: [
    { id: "fondo", type: "background", paint: { "background-color": "#cfe0ec" } },
    { id: "paises-fill", type: "fill", source: "paises", paint: {
      "fill-color": ["case", ["==", ["get", "iso"], "PER"], "#e6f2e9", "#f3f1ea"] } },
    { id: "paises-borde", type: "line", source: "paises", paint: {
      "line-color": ["case", ["==", ["get", "iso"], "PER"], "#2e9e6a", "#a9b4bf"],
      "line-width": ["case", ["==", ["get", "iso"], "PER"], 2, 0.6] } },
    { id: "osm", type: "raster", source: "osm", layout: { visibility: "none" } },
  ],
};
const PERU_CENTER: [number, number] = [-75.0, -9.2];

maplibregl.setWorkerUrl(workerUrl);
// Un solo worker: suficiente para capas pequeñas y ahorra memoria en equipos de 4 GB.
maplibregl.setWorkerCount(1);

interface Props {
  layers: Layer[];
  visible: Set<string>;
  alerts?: GeoJSON.FeatureCollection | null;
  showAlerts?: boolean;
  compact?: boolean;
  markerMode?: boolean;
  focusBbox?: number[] | null;
  osmBase?: boolean;
  onSelect?: (props: Record<string, unknown> | null) => void;
}

function popupNode(props: Record<string, unknown>): HTMLElement {
  // Construido con textContent: nunca se inyecta HTML de los datos (previene XSS).
  const box = document.createElement("div");
  for (const [k, v] of Object.entries(props).slice(0, 12)) {
    const row = document.createElement("div");
    const b = document.createElement("strong");
    b.textContent = `${k}: `;
    row.appendChild(b);
    row.appendChild(document.createTextNode(String(v ?? "")));
    box.appendChild(row);
  }
  return box;
}

export default function TerritorialMap({ layers, visible, alerts, showAlerts = true, compact, markerMode, focusBbox, osmBase = false, onSelect }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markerModeRef = useRef(markerMode);
  const onSelectRef = useRef(onSelect);
  const interactive = useRef<string[]>([]);
  const [ready, setReady] = useState(false);
  const [coords, setCoords] = useState("—");

  markerModeRef.current = markerMode;
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({ container: box.current, style: BASE_STYLE, center: PERU_CENTER, zoom: compact ? 4 : 4.6, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    m.on("load", () => setReady(true));
    m.on("mousemove", (e: MapMouseEvent) => setCoords(`lat ${e.lngLat.lat.toFixed(5)}, lon ${e.lngLat.lng.toFixed(5)}`));
    m.on("click", (e: MapMouseEvent) => {
      const ids = interactive.current.filter((id) => m.getLayer(id));
      const feats = ids.length ? m.queryRenderedFeatures(e.point, { layers: ids }) : [];
      if (feats.length) {
        const props = feats[0].properties as Record<string, unknown>;
        new maplibregl.Popup({ maxWidth: "300px" }).setLngLat(e.lngLat).setDOMContent(popupNode(props)).addTo(m);
        onSelectRef.current?.(props);
      } else if (markerModeRef.current) {
        const el = new maplibregl.Marker({ color: "#2e9e6a" }).setLngLat(e.lngLat).addTo(m);
        el.getElement().title = "Marcador local (no se guarda)";
        onSelectRef.current?.({ marcador: "local, no guardado", lat: e.lngLat.lat.toFixed(5), lon: e.lngLat.lng.toFixed(5) });
      } else {
        onSelectRef.current?.(null);
      }
    });
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, [compact]);

  // Sincroniza las capas de datos con el mapa.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const ids: string[] = [];
    layers.forEach((layer, i) => {
      const src = `rec-${layer.record_id}`;
      const color = PALETTE[i % PALETTE.length];
      if (!m.getSource(src)) {
        m.addSource(src, { type: "geojson", data: layer.geojson });
        m.addLayer({ id: `${src}-fill`, type: "fill", source: src, filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": color, "fill-opacity": 0.22 } });
        m.addLayer({ id: `${src}-line`, type: "line", source: src, filter: ["in", ["geometry-type"], ["literal", ["Polygon", "LineString"]]], paint: { "line-color": color, "line-width": 2, ...(layer.is_simulated ? { "line-dasharray": [2, 2] } : {}) } });
        m.addLayer({ id: `${src}-pt`, type: "circle", source: src, filter: ["==", ["geometry-type"], "Point"], paint: { "circle-color": color, "circle-radius": 6, "circle-stroke-width": 2, "circle-stroke-color": layer.is_simulated ? "#8e44ad" : "#ffffff" } });
      } else {
        (m.getSource(src) as GeoJSONSource).setData(layer.geojson);
      }
      const vis = visible.has(layer.record_id) ? "visible" : "none";
      for (const suffix of ["fill", "line", "pt"]) m.setLayoutProperty(`${src}-${suffix}`, "visibility", vis);
      ids.push(`${src}-fill`, `${src}-line`, `${src}-pt`);
    });
    if (alerts) {
      if (!m.getSource("alerts")) {
        m.addSource("alerts", { type: "geojson", data: alerts });
        m.addLayer({ id: "alerts-pt", type: "circle", source: "alerts", paint: {
          "circle-color": ["match", ["get", "level"], "alto", ALERT_COLORS.alto, "medio", ALERT_COLORS.medio, ALERT_COLORS.bajo],
          "circle-radius": 8, "circle-stroke-width": 2, "circle-stroke-color": "#ffffff" } });
      } else {
        (m.getSource("alerts") as GeoJSONSource).setData(alerts);
      }
      m.setLayoutProperty("alerts-pt", "visibility", showAlerts ? "visible" : "none");
      ids.push("alerts-pt");
    }
    interactive.current = ids;
  }, [layers, visible, alerts, showAlerts, ready]);

  useEffect(() => {
    const m = map.current;
    if (m && ready && m.getLayer("osm")) m.setLayoutProperty("osm", "visibility", osmBase ? "visible" : "none");
  }, [osmBase, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !focusBbox || focusBbox.length !== 4) return;
    const [a, b, c, d] = focusBbox;
    if (a === c && b === d) m.flyTo({ center: [a, b], zoom: 11 });
    else m.fitBounds([[a, b], [c, d]], { padding: 40, maxZoom: 13 });
  }, [focusBbox, ready]);

  return (
    <div className={`map-box${compact ? " compact" : ""}`} aria-label="Mapa territorial">
      <div ref={box} style={{ position: "absolute", inset: 0 }} />
      <div className="map-coords">{coords}</div>
    </div>
  );
}
