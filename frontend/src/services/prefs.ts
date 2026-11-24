/** Preferencias de interfaz por usuario de este navegador (tema, rendimiento, barra contraída).
 *  Se guardan en localStorage con try/catch: si el almacenamiento no está disponible, se usan los valores por defecto. */
import { useEffect, useState } from "react";

export type Theme = "auto" | "light" | "dark";

function read(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: solo dura la sesión */ }
}

/** Equipos con pocos núcleos y poca memoria arrancan en modo rendimiento (sin desenfoque ni animaciones). */
function defaultPerf(): boolean {
  const nav = navigator as Navigator & { deviceMemory?: number };
  return (nav.hardwareConcurrency ?? 8) <= 4 && (nav.deviceMemory ?? 8) <= 4;
}

export function applyPrefs(theme: Theme, perf: boolean) {
  const root = document.documentElement;
  const dark = theme === "dark" || (theme === "auto" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  root.setAttribute("data-theme", dark ? "dark" : "light");
  root.setAttribute("data-perf", perf ? "on" : "off");
}

export function usePrefs() {
  const [theme, setTheme] = useState<Theme>(() => (read("na_theme") as Theme) || "auto");
  const [perf, setPerf] = useState<boolean>(() => {
    const v = read("na_perf");
    return v === null ? defaultPerf() : v === "on";
  });
  const [collapsed, setCollapsed] = useState<boolean>(() => read("na_collapsed") === "1");
  useEffect(() => { write("na_theme", theme); write("na_perf", perf ? "on" : "off"); applyPrefs(theme, perf); }, [theme, perf]);
  useEffect(() => { write("na_collapsed", collapsed ? "1" : "0"); }, [collapsed]);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = () => applyPrefs(theme, perf);
    mq?.addEventListener?.("change", on);
    return () => mq?.removeEventListener?.("change", on);
  }, [theme, perf]);
  return { theme, setTheme, perf, setPerf, collapsed, setCollapsed };
}
