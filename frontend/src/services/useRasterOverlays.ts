import { useEffect, useState } from "react";
import { apiBlobUrl } from "./api";
import type { RasterOverlay, RasterRecord } from "./types";

/** Convierte registros raster en capas del mapa descargando sus vistas previas (con sesión). */
export function useRasterOverlays(records: RasterRecord[] | null): RasterOverlay[] {
  const [overlays, setOverlays] = useState<RasterOverlay[]>([]);
  useEffect(() => {
    if (!records) return;
    let alive = true;
    const urls: string[] = [];
    Promise.all(records.map(async (r) => {
      try {
        const url = await apiBlobUrl(`/api/neurodata/records/${r.id}/preview`);
        urls.push(url);
        return { id: r.id, title: r.title, kind: r.extra.kind, bbox: r.bbox, url, is_simulated: r.is_simulated } as RasterOverlay;
      } catch {
        return null;
      }
    })).then((list) => {
      if (alive) setOverlays(list.filter((x): x is RasterOverlay => x !== null));
    });
    return () => { alive = false; urls.forEach((u) => URL.revokeObjectURL(u)); };
  }, [records]);
  return overlays;
}
