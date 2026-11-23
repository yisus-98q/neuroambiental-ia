/** Paletas del terreno 3D. Sin dependencias de three.js: la leyenda del panel puede importarlas
 *  sin arrastrar three.js al bundle principal (el visor se carga aparte con React.lazy). */
export const HYPSO_STOPS: [number, string][] = [
  [0, "#2e7d32"], [0.25, "#9ccc65"], [0.5, "#e6d27a"], [0.75, "#9a6b45"], [1, "#f5f5f5"],
];
export const SLOPE_CLASSES: { max: number; color: string; label: string }[] = [
  { max: 15, color: "#43a047", label: "0-15°" },
  { max: 25, color: "#fdd835", label: "15-25°" },
  { max: 35, color: "#fb8c00", label: "25-35°" },
  { max: 91, color: "#d32f2f", label: ">35°" },
];
export const NO_DATA_COLOR = "#9e9e9e";

export function hexToRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16);
  return [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
}

/** 256 colores hipsométricos precalculados (r,g,b en 0..1), para no interpolar por vértice. */
export const HYPSO_LUT: Float32Array = (() => {
  const lut = new Float32Array(256 * 3);
  const stops = HYPSO_STOPS.map(([t, c]) => [t, ...hexToRgb(c)] as [number, number, number, number]);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    let j = 1;
    while (j < stops.length - 1 && x > stops[j][0]) j++;
    const [t0, r0, g0, b0] = stops[j - 1];
    const [t1, r1, g1, b1] = stops[j];
    const f = Math.min(1, Math.max(0, (x - t0) / (t1 - t0)));
    lut.set([r0 + (r1 - r0) * f, g0 + (g1 - g0) * f, b0 + (b1 - b0) * f], i * 3);
  }
  return lut;
})();

/** Color por pendiente (grados enteros 0..90) precalculado. */
export const SLOPE_LUT: Float32Array = (() => {
  const lut = new Float32Array(91 * 3);
  for (let d = 0; d <= 90; d++) {
    const cls = SLOPE_CLASSES.find((q) => d < q.max) ?? SLOPE_CLASSES[SLOPE_CLASSES.length - 1];
    lut.set(hexToRgb(cls.color), d * 3);
  }
  return lut;
})();
