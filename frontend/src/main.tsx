import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/global.css";
import { applyPrefs, type Theme } from "./services/prefs";

// Tema y modo rendimiento antes del primer pintado (evita destellos).
(() => {
  let theme: Theme = "auto"; let perf: boolean | null = null;
  try { theme = (localStorage.getItem("na_theme") as Theme) || "auto"; const p = localStorage.getItem("na_perf"); perf = p === null ? null : p === "on"; } catch { /* sin almacenamiento */ }
  const nav = navigator as Navigator & { deviceMemory?: number };
  applyPrefs(theme, perf ?? ((nav.hardwareConcurrency ?? 8) <= 4 && (nav.deviceMemory ?? 8) <= 4));
})();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
