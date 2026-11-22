import type { ReactNode } from "react";

type Kind = "dev" | "info" | "danger" | "ok";

export function Notice({ kind = "info", children }: { kind?: Kind; children: ReactNode }) {
  return <div className={`notice notice-${kind}`} role={kind === "danger" ? "alert" : "note"}>{children}</div>;
}

export function Loading({ what = "datos" }: { what?: string }) {
  return <p className="muted">Cargando {what}…</p>;
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? <p className="error" role="alert">{error}</p> : null;
}
