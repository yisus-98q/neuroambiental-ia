/** Menú principal agrupado (arquitectura de integración avanzada, sección 13). */
export interface MenuItem { path: string; label: string; moduleKey?: string }
export interface MenuGroup { title: string; items: MenuItem[] }

export const MENU_GROUPS: MenuGroup[] = [
  { title: "General", items: [
    { path: "/inicio", label: "Inicio" },
    { path: "/mapa", label: "Mapa territorial" },
    { path: "/alertas", label: "Centro de alertas", moduleKey: "alerts" },
  ] },
  { title: "Núcleo inteligente", items: [
    { path: "/neurocore", label: "NEUROCORE IA" },
    { path: "/neurodata", label: "NEURODATA ENGINE", moduleKey: "neurodata" },
    { path: "/neurotraining", label: "NEURAL TRAINING CENTER", moduleKey: "neurotraining" },
    { path: "/modulo/neuroprediction", label: "NEURO PREDICTION ENGINE", moduleKey: "neuroprediction" },
    { path: "/neurovoice", label: "NEUROVOICE IA", moduleKey: "neurovoice" },
  ] },
  { title: "Modelos especializados", items: [
    { path: "/modulo/neurovision", label: "NEUROVISION", moduleKey: "neurovision" },
    { path: "/modulo/terrain", label: "NEUROTERRAIN", moduleKey: "terrain" },
    { path: "/modulo/neurogeo", label: "NEUROGEO", moduleKey: "neurogeo" },
    { path: "/modulo/mining", label: "NEUROMINING", moduleKey: "mining" },
    { path: "/modulo/environmental", label: "NEUROENVIRONMENT", moduleKey: "environmental" },
    { path: "/modulo/disasters", label: "NEURODISASTER", moduleKey: "disasters" },
    { path: "/modulo/neuroindustrial", label: "NEUROINDUSTRIAL", moduleKey: "neuroindustrial" },
    { path: "/modulo/construction", label: "NEUROCONSTRUCTION", moduleKey: "construction" },
    { path: "/modulo/biodiversity", label: "Fauna y flora", moduleKey: "biodiversity" },
  ] },
  { title: "Simulación", items: [
    { path: "/modulo/neuro3d", label: "NEURO 3D LAB", moduleKey: "neuro3d" },
  ] },
  { title: "Sistema", items: [
    { path: "/informes", label: "Informes" },
    { path: "/configuracion", label: "Configuración" },
  ] },
];

export const MENU: MenuItem[] = MENU_GROUPS.flatMap((g) => g.items);

export const STATUS_LABEL: Record<string, string> = {
  operativo: "Operativo",
  parcial: "Parcial",
  en_desarrollo: "En desarrollo",
};
