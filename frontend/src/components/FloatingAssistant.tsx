import { useEffect, useRef, useState, type FormEvent } from "react";
import { post } from "../services/api";
import { Icon } from "./Icon";

/* Asistente flotante NEUROVOICE IA (Fase 5 de NEUROAMBIENTAL IA 2.0).
   - Responde con DATOS REALES del servidor (/api/neurovoice/chat); nunca genera cifras en el navegador.
   - Contexto: envía el módulo de la pantalla actual para resolver «explícame esto».
   - Voz: reconocimiento Web Speech (el audio va a Google: requiere consentimiento explícito por sesión)
     y síntesis local del navegador (voz automática del sistema; nunca la voz del usuario).
   - Idiomas: las respuestas se generan en español. Inglés y portugués solo para reconocimiento/síntesis
     (NO probados); quechua y aimara no tienen voz disponible en el navegador. */

interface RecEvent { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
interface Rec {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: RecEvent) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type RecCtor = new () => Rec;
const getRec = (): RecCtor | null => {
  const w = window as unknown as { SpeechRecognition?: RecCtor; webkitSpeechRecognition?: RecCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

const CONSENT_KEY = "neurovoice_asr_consent";   // el mismo que la página NEUROVOICE
const LANGS = [
  { code: "es-PE", label: "Español (Perú)", ok: true },
  { code: "es-ES", label: "Español (España)", ok: true },
  { code: "en-US", label: "English (no probado)", ok: true },
  { code: "pt-BR", label: "Português (no probado)", ok: true },
  { code: "qu", label: "Quechua (sin voz disponible)", ok: false },
  { code: "ay", label: "Aimara (sin voz disponible)", ok: false },
];
type State = "inactivo" | "escuchando" | "procesando" | "respondiendo";
const STATE_LABEL: Record<State, string> = { inactivo: "Listo", escuchando: "Escuchando…", procesando: "Consultando datos reales…", respondiendo: "Respondiendo…" };
interface Msg { role: "usuario" | "asistente"; content: string }

export function moduleFromRoute(route: string): string | null {
  if (route.startsWith("/modulo/")) return route.slice("/modulo/".length);
  const map: Record<string, string> = { "/neurodata": "neurodata", "/neurotraining": "neurotraining",
    "/neurovoice": "neurovoice", "/alertas": "alerts" };
  return map[route] ?? null;
}

export function FloatingAssistant({ route }: { route: string }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [conv, setConv] = useState<string | null>(null);
  const [state, setState] = useState<State>("inactivo");
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState("es-PE");
  const [voiceOn, setVoiceOn] = useState(true);
  const [volume, setVolume] = useState(0.9);
  const [consent, setConsent] = useState(() => { try { return sessionStorage.getItem(CONSENT_KEY) === "si"; } catch { return false; } });
  const recRef = useRef<Rec | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const Ctor = getRec();
  const tts = typeof window !== "undefined" && "speechSynthesis" in window;
  const ctx = moduleFromRoute(route);
  const langOk = LANGS.find((l) => l.code === lang)?.ok ?? false;

  useEffect(() => () => { recRef.current?.abort(); if (tts) window.speechSynthesis.cancel(); }, [tts]);
  useEffect(() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight }); }, [msgs, state]);

  function speak(content: string) {
    if (!tts || !voiceOn || !langOk) { setState("inactivo"); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(content);
    u.lang = lang; u.volume = volume;
    u.onend = () => setState("inactivo"); u.onerror = () => setState("inactivo");
    setState("respondiendo");
    window.speechSynthesis.speak(u);
  }

  async function ask(message: string) {
    if (!message.trim()) return;
    setError(null); setMsgs((m) => [...m, { role: "usuario", content: message }]); setText(""); setState("procesando");
    try {
      const r = await post<{ conversation_id: string; reply: string }>("/api/neurovoice/chat",
        { message, conversation_id: conv, context_module: ctx });
      setConv(r.conversation_id);
      setMsgs((m) => [...m, { role: "asistente", content: r.reply }]);
      speak(r.reply);
    } catch (e) { setError((e as Error).message); setState("inactivo"); }
  }

  function listen() {
    if (!Ctor || !consent || !langOk) return;
    const rec = new Ctor();
    rec.lang = lang; rec.interimResults = false; rec.continuous = false;
    rec.onresult = (e) => { const t = Array.from(e.results).map((r) => r[0].transcript).join(" "); ask(t); };
    rec.onerror = (e) => { setError(e.error === "not-allowed" ? "Permiso de micrófono denegado." : `Reconocimiento: ${e.error}`); setState("inactivo"); };
    rec.onend = () => setState((s) => (s === "escuchando" ? "inactivo" : s));
    recRef.current = rec; setState("escuchando"); rec.start();
  }

  function giveConsent() {
    try { sessionStorage.setItem(CONSENT_KEY, "si"); } catch { /* solo para esta vista */ }
    setConsent(true);
  }

  const submit = (e: FormEvent) => { e.preventDefault(); ask(text); };

  return (
    <>
      {open && (
        <section className="assistant-panel" role="dialog" aria-label="Asistente NEUROVOICE IA">
          <div className="assistant-head">
            <div>
              <strong style={{ color: "var(--text-strong)" }}>NEUROVOICE IA</strong>
              <div className="assistant-state" aria-live="polite">
                {state === "escuchando" || state === "respondiendo" ? <span className="wave" aria-hidden><i /><i /><i /><i /><i /></span>
                  : state === "procesando" ? <span className="spinner" aria-hidden /> : <span className="pulse-dot" aria-hidden />}
                {STATE_LABEL[state]}{ctx ? ` · contexto: ${ctx}` : ""}
              </div>
            </div>
            <button className="btn btn-ghost btn-icon" onClick={() => setOpen(false)} aria-label="Cerrar asistente"><Icon name="close" /></button>
          </div>
          <div className="assistant-body" ref={bodyRef}>
            {msgs.length === 0 && (
              <p className="small muted" style={{ margin: 0 }}>Pregunte por alertas, datasets, modelos, validaciones o el módulo que está viendo
                («explícame esto»). Respondo solo con datos registrados en el sistema; si no hay datos, lo digo.</p>
            )}
            {msgs.map((m, i) => <div key={i} className={`msg ${m.role === "usuario" ? "msg-user" : "msg-bot"}`}>{m.content}</div>)}
            {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
          </div>
          <div className="assistant-foot">
            <form className="row" onSubmit={submit} style={{ flexWrap: "nowrap" }}>
              <input aria-label="Escriba su consulta" value={text} onChange={(e) => setText(e.target.value)} placeholder="Escriba su consulta…" style={{ flex: 1, minWidth: 0 }} />
              <button className="btn btn-icon" disabled={!text.trim() || state === "procesando"} aria-label="Enviar"><Icon name="send" /></button>
              <button type="button" className="btn btn-icon btn-green" onClick={listen} disabled={!Ctor || !consent || !langOk || state !== "inactivo"}
                aria-label="Hablar" data-tip={!Ctor ? "Su navegador no tiene reconocimiento de voz" : !consent ? "Primero autorice el micrófono" : "Hablar"}><Icon name="mic" /></button>
            </form>
            {!consent && Ctor && (
              <div className="notice notice-info small">El reconocimiento de voz del navegador envía el audio a Google. ¿Lo autoriza para esta sesión?
                {" "}<button className="btn btn-ghost" style={{ padding: "3px 10px" }} onClick={giveConsent}>Autorizar micrófono</button></div>
            )}
            <div className="row" style={{ justifyContent: "space-between" }}>
              <label className="switch"><input type="checkbox" checked={voiceOn} onChange={(e) => { setVoiceOn(e.target.checked); if (!e.target.checked && tts) window.speechSynthesis.cancel(); }} /> Voz</label>
              <label className="row small" style={{ gap: 6 }}><Icon name={voiceOn ? "volume" : "mute"} size={16} />
                <input type="range" min={0} max={1} step={0.05} value={volume} onChange={(e) => setVolume(Number(e.target.value))} aria-label="Volumen" style={{ width: 80 }} /></label>
              <select aria-label="Idioma de voz" value={lang} onChange={(e) => setLang(e.target.value)} style={{ maxWidth: 170, padding: "4px 8px" }}>
                {LANGS.map((l) => <option key={l.code} value={l.code} disabled={!l.ok}>{l.label}</option>)}
              </select>
            </div>
            <p className="small muted" style={{ margin: 0 }}>Respuestas en español generadas con datos reales. Historial completo en <a href="#/neurovoice">NEUROVOICE</a>.</p>
          </div>
        </section>
      )}
      <button className={`assistant-fab${state === "escuchando" ? " listening" : ""}`} onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Cerrar asistente NEUROVOICE" : "Abrir asistente NEUROVOICE"} aria-expanded={open}>
        <Icon name={open ? "close" : "voice"} />
      </button>
    </>
  );
}
