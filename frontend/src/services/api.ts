/** Cliente HTTP mínimo (fetch nativo, sin dependencias). */
import type { User } from "./types";

const TOKEN_KEY = "neuro_token";
const USER_KEY = "neuro_user";

export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

// sessionStorage: la sesión se cierra al cerrar el navegador.
function store(): Storage | null {
  try { return window.sessionStorage; } catch { return null; }
}

export const session = {
  token: (): string | null => store()?.getItem(TOKEN_KEY) ?? null,
  user: (): User | null => {
    try { return JSON.parse(store()?.getItem(USER_KEY) ?? "null"); } catch { return null; }
  },
  save(token: string, user: User) {
    store()?.setItem(TOKEN_KEY, token);
    store()?.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    store()?.removeItem(TOKEN_KEY);
    store()?.removeItem(USER_KEY);
  },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: string }).msg) : String(d))).join(" · ");
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; errors?: string[] };
    return [d.message, ...(d.errors ?? [])].filter(Boolean).join(" ");
  }
  return "Error desconocido";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = session.token();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el backend. ¿Está iniciado?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) { session.clear(); onUnauthorized(); }
    throw new ApiError(res.status, describe(body?.detail), body?.detail);
  }
  return body as T;
}

export const post = <T,>(path: string, data?: unknown) =>
  api<T>(path, { method: "POST", body: data instanceof FormData ? data : JSON.stringify(data ?? {}) });

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" }) : "—";

export const canWrite = (u: User | null) => u?.role_key === "admin" || u?.role_key === "analista";
