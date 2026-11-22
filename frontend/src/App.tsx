import { useEffect, useState } from "react";
import { Shell } from "./layouts/Shell";
import { MENU } from "./modules/menu";
import { AlertsPage } from "./pages/AlertsPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { MapPage } from "./pages/MapPage";
import { ModulePage } from "./pages/ModulePage";
import { NeurodataPage } from "./pages/NeurodataPage";
import { NeurocorePage, NeurovoicePage, ReportsPage, SettingsPage } from "./pages/SystemPages";
import { TrainingCenter } from "./pages/TrainingCenter";
import { api, session, setUnauthorizedHandler } from "./services/api";
import { go, useHashRoute } from "./services/router";
import type { User } from "./services/types";

function Page({ route }: { route: string }) {
  if (route.startsWith("/modulo/")) return <ModulePage key={route} moduleKey={route.slice("/modulo/".length)} />;
  switch (route) {
    case "/inicio": return <HomePage />;
    case "/mapa": return <MapPage />;
    case "/alertas": return <AlertsPage />;
    case "/neurocore": return <NeurocorePage />;
    case "/neurodata": return <NeurodataPage />;
    case "/neurotraining": return <TrainingCenter />;
    case "/neurovoice": return <NeurovoicePage />;
    case "/informes": return <ReportsPage />;
    case "/configuracion": return <SettingsPage />;
    default: return <div className="card"><h1>Página no encontrada</h1><a href="#/inicio">Volver al inicio</a></div>;
  }
}

export default function App() {
  const route = useHashRoute();
  const [user, setUser] = useState<User | null>(session.user());

  useEffect(() => { setUnauthorizedHandler(() => setUser(null)); }, []);

  useEffect(() => {
    const label = MENU.find((m) => route.startsWith(m.path))?.label;
    document.title = label ? `${label} · NEUROAMBIENTAL IA` : "NEUROAMBIENTAL IA";
  }, [route]);

  if (!user) return <LoginPage onLogin={(u) => { setUser(u); go("/inicio"); }} />;

  const logout = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* la sesión se limpia igual */ }
    session.clear();
    setUser(null);
  };

  return <Shell route={route} user={user} onLogout={logout}><Page route={route} /></Shell>;
}
