/** Menú principal agrupado (arquitectura de integración avanzada, sección 13). */
export interface MenuItem { path: string; label: string; moduleKey?: string; icon?: string }
export interface MenuGroup { title: string; items: MenuItem[] }

export const MENU_GROUPS: MenuGroup[] = [
  { title: "General", items: [
    { path: "/inicio", icon: "home", label: "Inicio" },
    { path: "/mapa", icon: "map", label: "Mapa territorial" },
    { path: "/alertas", icon: "alert", label: "Centro de alertas", moduleKey: "alerts" },
  ] },
  { title: "Núcleo inteligente", items: [
    { path: "/neurocore", icon: "core", label: "NEUROCORE IA" },
    { path: "/neurodata", icon: "data", label: "NEURODATA ENGINE", moduleKey: "neurodata" },
    { path: "/neurotraining", icon: "brain", label: "NEURAL TRAINING CENTER", moduleKey: "neurotraining" },
    { path: "/modulo/neuroprediction", icon: "chart", label: "NEURO PREDICTION ENGINE", moduleKey: "neuroprediction" },
    { path: "/neurovoice", icon: "voice", label: "NEUROVOICE IA", moduleKey: "neurovoice" },
  ] },
  { title: "Modelos especializados", items: [
    { path: "/modulo/neurovision", icon: "eye", label: "NEUROVISION", moduleKey: "neurovision" },
    { path: "/modulo/terrain", icon: "terrain", label: "NEUROTERRAIN", moduleKey: "terrain" },
    { path: "/modulo/neurogeo", icon: "geo", label: "NEUROGEO", moduleKey: "neurogeo" },
    { path: "/modulo/mining", icon: "mining", label: "NEUROMINING", moduleKey: "mining" },
    { path: "/modulo/environmental", icon: "leaf", label: "NEUROENVIRONMENT", moduleKey: "environmental" },
    { path: "/modulo/disasters", icon: "disaster", label: "NEURODISASTER", moduleKey: "disasters" },
    { path: "/modulo/neuroindustrial", icon: "factory", label: "NEUROINDUSTRIAL", moduleKey: "neuroindustrial" },
    { path: "/modulo/construction", icon: "build", label: "NEUROCONSTRUCTION", moduleKey: "construction" },
    { path: "/modulo/biodiversity", icon: "paw", label: "Fauna y flora", moduleKey: "biodiversity" },
  ] },
  { title: "Validación científica", items: [
    { path: "/modulo/validation", icon: "check", label: "SCIENTIFIC VALIDATION", moduleKey: "validation" },
  ] },
  { title: "Simulación", items: [
    { path: "/modulo/neuro3d", icon: "cube", label: "NEURO 3D LAB", moduleKey: "neuro3d" },
  ] },
  { title: "Sistema", items: [
    { path: "/informes", icon: "report", label: "Informes" },
    { path: "/configuracion", icon: "settings", label: "Configuración" },
  ] },
];

export const MENU: MenuItem[] = MENU_GROUPS.flatMap((g) => g.items);

export const STATUS_LABEL: Record<string, string> = {
  operativo: "Operativo",
  parcial: "Parcial",
  en_desarrollo: "En desarrollo",
};
