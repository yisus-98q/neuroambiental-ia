/** Iconos SVG en línea (sin dependencias). Trazos simples de 24×24. */
const PATHS: Record<string, string> = {
  home: "M3 11l9-7 9 7M5 10v10h5v-6h4v6h5V10",
  map: "M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14",
  alert: "M12 3l10 18H2L12 3zM12 10v5M12 18v.5",
  core: "M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M19 5l-3 3M8 16l-3 3M12 8a4 4 0 100 8 4 4 0 000-8z",
  data: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  brain: "M9 4a3 3 0 00-3 3 3 3 0 00-2 5 3 3 0 002 5 3 3 0 006 0V4a3 3 0 00-3 0zM15 4a3 3 0 013 3 3 3 0 012 5 3 3 0 01-2 5 3 3 0 01-6 0",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  voice: "M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v3",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 100 6 3 3 0 000-6z",
  terrain: "M2 20l7-11 4 6 3-4 6 9H2z",
  geo: "M12 2l9 5v10l-9 5-9-5V7l9-5zM3 7l9 5 9-5M12 12v10",
  mining: "M14 4l6 6M4 20l9-9M11 7l6 6M7 3l4 4-4 4-4-4 4-4z",
  leaf: "M5 19c8 0 14-6 14-14-8 0-14 6-14 14zM5 19l7-7",
  disaster: "M13 2L4 14h7l-1 8 9-12h-7l1-8z",
  factory: "M3 21V11l6 4V11l6 4V7l6 4v10H3z",
  build: "M3 21h18M5 21V9l7-5 7 5v12M10 21v-6h4v6",
  paw: "M7 10a2 2 0 100-4 2 2 0 000 4zM17 10a2 2 0 100-4 2 2 0 000 4zM12 8a2 2 0 100-4 2 2 0 000 4zM12 12c-3 0-6 3-6 6 0 2 2 2 6 2s6 0 6-2c0-3-3-6-6-6z",
  cube: "M12 2l9 5v10l-9 5-9-5V7l9-5zM12 12l9-5M12 12L3 7M12 12v10",
  check: "M9 12l2 2 4-4M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z",
  report: "M6 2h9l5 5v15H6V2zM14 2v6h6M9 13h7M9 17h7",
  settings: "M12 9a3 3 0 100 6 3 3 0 000-6zM19 12l2-1-1-3-2 .3-1.5-1.5L17 5l-3-1-1 2h-2L10 4 7 5l.5 2.3L6 8.8 4 8.5 3 11.5l2 .5v0l-2 1 1 3 2-.3 1.5 1.5L7 19l3 1 1-2h2l1 2 3-1-.5-2.3 1.5-1.5 2 .3 1-3-2-1z",
  sun: "M12 7a5 5 0 100 10 5 5 0 000-10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 13A9 9 0 1111 3a7 7 0 0010 10z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7l1-8z",
  chevron: "M6 9l6 6 6-6",
  collapse: "M15 6l-6 6 6 6",
  expand: "M9 6l6 6-6 6",
  menu: "M3 6h18M3 12h18M3 18h18",
  close: "M6 6l12 12M18 6L6 18",
  send: "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z",
  mic: "M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v3",
  volume: "M11 5L6 9H2v6h4l5 4V5zM15.5 8.5a5 5 0 010 7M19 5a10 10 0 010 14",
  mute: "M11 5L6 9H2v6h4l5 4V5zM23 9l-6 6M17 9l6 6",
  logout: "M9 21H5V3h4M16 17l5-5-5-5M21 12H9",
  inbox: "M3 13l3-8h12l3 8v6H3v-6zM3 13h5l1 3h6l1-3h5",
};

export function Icon({ name, size = 18, title }: { name: string; size?: number; title?: string }) {
  const d = PATHS[name] ?? PATHS.core;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? "img" : undefined}>
      {title && <title>{title}</title>}
      <path d={d} />
    </svg>
  );
}
