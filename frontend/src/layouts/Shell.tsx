import { useState, type ReactNode } from "react";
import { MENU_GROUPS } from "../modules/menu";
import type { User } from "../services/types";

interface Props { route: string; user: User; onLogout: () => void; children: ReactNode }

export function Shell({ route, user, onLogout, children }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="shell">
      <aside className={`sidebar${open ? " open" : ""}`} aria-label="Menú principal">
        <div className="brand">
          <div className="brand-title">NEURO<span>AMBIENTAL</span> IA</div>
          <div className="brand-sub">Inteligencia ambiental territorial · Perú</div>
        </div>
        <nav>
          {MENU_GROUPS.map((g) => (
            <div key={g.title}>
              <div className="nav-group">{g.title}</div>
              <ul className="nav">
                {g.items.map((item) => (
                  <li key={item.path}>
                    <a href={`#${item.path}`} className={route.startsWith(item.path) ? "active" : ""} onClick={() => setOpen(false)}>
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="small" style={{ marginTop: "auto", padding: 16, color: "#7f93ab" }}>
          Versión 0.3.0 · Fase 3<br />Software libre · costo 0 USD
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <button className="btn btn-ghost menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Abrir menú">☰</button>
            <span className="small muted">Las alertas de esta plataforma son <strong>experimentales</strong>, no emergencias oficiales.</span>
          </div>
          <div className="row">
            <span className="small"><strong>{user.username}</strong> · {user.role_key}</span>
            <button className="btn btn-ghost" onClick={onLogout}>Salir</button>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
