/** Menú principal (15 entradas, en el orden de la orden maestra). */
export interface MenuItem { path: string; label: string; moduleKey?: string }

export const MENU: MenuItem[] = [
  { path: "/inicio", label: "Inicio" },
  { path: "/mapa", label: "Mapa territorial" },
  { path: "/modulo/environmental", label: "Predicción ambiental", moduleKey: "environmental" },
  { path: "/modulo/mining", label: "Inteligencia minera", moduleKey: "mining" },
  { path: "/modulo/biodiversity", label: "Fauna y flora", moduleKey: "biodiversity" },
  { path: "/modulo/terrain", label: "Movimientos territoriales", moduleKey: "terrain" },
  { path: "/modulo/disasters", label: "Catástrofes", moduleKey: "disasters" },
  { path: "/modulo/construction", label: "Construcción", moduleKey: "construction" },
  { path: "/alertas", label: "Alertas", moduleKey: "alerts" },
  { path: "/neurocore", label: "NEUROCORE IA" },
  { path: "/neurodata", label: "NEURODATA ENGINE", moduleKey: "neurodata" },
  { path: "/neurotraining", label: "NEUROTRAINING", moduleKey: "neurotraining" },
  { path: "/neurovoice", label: "NEUROVOICE IA", moduleKey: "neurovoice" },
  { path: "/informes", label: "Informes" },
  { path: "/configuracion", label: "Configuración" },
];

export const STATUS_LABEL: Record<string, string> = {
  operativo: "Operativo",
  parcial: "Parcial",
  en_desarrollo: "En desarrollo",
};
