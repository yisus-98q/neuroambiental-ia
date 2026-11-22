import { useState, type FormEvent } from "react";
import { post, session } from "../services/api";
import type { User } from "../services/types";
import { ErrorText } from "../components/Notice";

export function LoginPage({ onLogin }: { onLogin: (u: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await post<{ access_token: string; user: User }>("/api/auth/login", { username, password });
      session.save(r.access_token, r.user);
      onLogin(r.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card stack" onSubmit={submit}>
        <div>
          <h1 style={{ marginBottom: 2 }}>NEUROAMBIENTAL IA</h1>
          <p className="muted" style={{ marginTop: 0 }}>Sistema inteligente de predicción ambiental territorial</p>
        </div>
        <div className="field"><label htmlFor="u">Usuario</label>
          <input id="u" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></div>
        <div className="field"><label htmlFor="p">Contraseña</label>
          <input id="p" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
        <button className="btn" disabled={busy}>{busy ? "Ingresando…" : "Ingresar"}</button>
        <ErrorText error={error} />
        <p className="small muted">¿Primera vez? Cree el administrador con <code>scripts\crear-admin.bat</code>.</p>
      </form>
    </div>
  );
}
