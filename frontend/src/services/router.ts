import { useEffect, useState } from "react";

/** Router por hash (#/ruta). Sin dependencias y compatible con servir desde FastAPI. */
export function useHashRoute(): string {
  const read = () => window.location.hash.replace(/^#/, "") || "/inicio";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => { setRoute(read()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export const go = (path: string) => { window.location.hash = path; };
