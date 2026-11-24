import { useState, type ReactNode } from "react";
import { FloatingAssistant } from "../components/FloatingAssistant";
import { Icon } from "../components/Icon";
import { MENU, MENU_GROUPS } from "../modules/menu";
import { usePrefs, type Theme } from "../services/prefs";
import type { ModuleInfo, User } from "../services/types";
import { useApi } from "../services/useApi";

interface Props { route: string; user: User; onLogout: () => void; children: ReactNode }

const STATUS_COLOR: Record<string, string> = { operativo: "var(--green-500)", parcial: "var(--tech-400)", en_desarrollo: "#6f87a3" };
const THEMES: { v: Theme; icon: string; label: string }[] = [
  { v: "light", icon: "sun", label: "Tema claro" }, { v: "dark", icon: "moon", label: "Tema oscuro" }, { v: "auto", icon: "settings", label: "Tema del sistema" },
];

function readClosed(): string[] {
  try { return JSON.parse(localStorage.getItem("na_closed_groups") || "[]"); } catch { return []; }
}

export function Shell({ route, user, onLogout, children }: Props) {
  const [open, setOpen] = useState(false);
  const [closed, setClosed] = useState<string[]>(readClosed);
  const { theme, setTheme, perf, setPerf, collapsed, setCollapsed } = usePrefs();
  const mods = useApi<ModuleInfo[]>("/api/neurocore/modules");
  const status = Object.fromEntries((mods.data ?? []).map((m) => [m.key, m.status]));
  const current = MENU.find((m) => route.startsWith(m.path));

  function toggleGroup(t: string) {
    const next = closed.includes(t) ? closed.filter((x) => x !== t) : [...closed, t];
    setClosed(next);
    try { localStorage.setItem("na_closed_groups", JSON.stringify(next)); } catch { /* opcional */ }
  }
  const nextTheme = THEMES[(THEMES.findIndex((t) => t.v === theme) + 1) % THEMES.length];

  return (
    <div className={`shell${collapsed ? " collapsed" : ""}`}>
      <aside className={`sidebar${open ? " open" : ""}`} aria-label="Menú principal">
        <div className="brand">
          <div className="brand-logo"><Icon name="leaf" /></div>
          <div className="brand-text">
            <div className="brand-title">NEURO<span>AMBIENTAL</span> IA</div>
            <div className="brand-sub">Inteligencia ambiental territorial · Perú</div>
          </div>
        </div>
        <nav>
          {MENU_GROUPS.map((g) => (
            <div key={g.title} className={`nav-group${closed.includes(g.title) ? " closed" : ""}`}>
              <button className="nav-group-btn" onClick={() => toggleGroup(g.title)} aria-expanded={!closed.includes(g.title)}>
                <span className="nav-group-title">{g.title}</span><span className="nav-chevron"><Icon name="chevron" size={14} /></span>
              </button>
              <ul className="nav">
                {g.items.map((item) => {
                  const st = item.moduleKey ? status[item.moduleKey] : undefined;
                  const active = route.startsWith(item.path);
                  return (
                    <li key={item.path}>
                      <a href={`#${item.path}`} className={active ? "active" : ""} onClick={() => setOpen(false)}
                        aria-current={active ? "page" : undefined} title={collapsed ? item.label : undefined}>
                        <Icon name={item.icon ?? "core"} />
                        <span className="nav-label">{item.label}</span>
                        {st && <span className="nav-dot" style={{ background: STATUS_COLOR[st] }} aria-label={`estado: ${st}`} />}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button className="collapse-btn desktop-only" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Expandir menú" : "Contraer menú"}>
            <Icon name={collapsed ? "expand" : "collapse"} />
          </button>
          <div className="sidebar-foot-text">Versión 2.0 · software libre · 0 USD<br />Punto verde: operativo · azul: parcial</div>
        </div>
      </aside>
      <div className={`scrim${open ? " show" : ""}`} onClick={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <div className="row" style={{ flexWrap: "nowrap", minWidth: 0 }}>
            <button className="btn btn-ghost btn-icon menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Abrir menú"><Icon name="menu" /></button>
            <span className="topbar-title">{current?.label ?? "NEUROAMBIENTAL IA"}</span>
            <span className="small muted desktop-only" style={{ marginLeft: 8 }}>Alertas y predicciones experimentales: no son avisos oficiales.</span>
          </div>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <button className="btn btn-ghost btn-icon" onClick={() => setTheme(nextTheme.v)} data-tip={`Cambiar a: ${nextTheme.label}`}
              aria-label={`Tema actual: ${theme}. Cambiar a ${nextTheme.label}`}>
              <Icon name={THEMES.find((t) => t.v === theme)?.icon ?? "sun"} />
            </button>
            <button className={`btn btn-icon ${perf ? "btn-green" : "btn-ghost"}`} onClick={() => setPerf(!perf)} aria-pressed={perf}
              data-tip={perf ? "Modo rendimiento: activado" : "Modo rendimiento: desactivado"} aria-label="Modo rendimiento"><Icon name="bolt" /></button>
            <span className="small desktop-only"><strong>{user.username}</strong> · {user.role_key}</span>
            <button className="btn btn-ghost btn-icon" onClick={onLogout} aria-label="Salir" data-tip="Salir"><Icon name="logout" /></button>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
      <FloatingAssistant route={route} />
    </div>
  );
}
