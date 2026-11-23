import { useEffect, useRef, useState, type FormEvent } from "react";
import { StatusBadge } from "../components/Badges";
import { ErrorText, Notice } from "../components/Notice";
import { post } from "../services/api";
import type { ModuleInfo } from "../services/types";
import { useApi } from "../services/useApi";

/* NEUROVOICE IA — Fase 7: voz en el navegador.
   - Reconocimiento: Web Speech API de Chrome/Edge (el AUDIO SE ENVÍA A GOOGLE; requiere consentimiento).
   - Síntesis: speechSynthesis con las voces instaladas (local).
   - La lógica del asistente sigue en el servidor (/api/neurovoice/chat): los proveedores de voz son
     intercambiables sin tocar NEUROCORE. */

interface RecognitionResultEvent { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
interface Recognition {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: RecognitionResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type RecognitionCtor = new () => Recognition;

function getRecognition(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const CONSENT_KEY = "neurovoice_asr_consent";
const LANGS = [
  { code: "es-PE", label: "Español (Perú)" },
  { code: "es-ES", label: "Español (España)" },
];
const ERRORS: Record<string, string> = {
  "not-allowed": "Permiso de micrófono denegado por el navegador.",
  "no-speech": "No se detectó voz. Intente de nuevo.",
  network: "Sin conexión con el servicio de reconocimiento (requiere internet).",
  "audio-capture": "No se encontró un micrófono.",
};

interface Msg { role: "usuario" | "asistente"; content: string; via?: "voz" | "texto" }

export function VoicePage() {
  const mod = useApi<ModuleInfo>("/api/neurocore/modules/neurovoice");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [conv, setConv] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState("es-PE");
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [speak, setSpeak] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [consent, setConsent] = useState(() => { try { return localStorage.getItem(CONSENT_KEY) === "si"; } catch { return false; } });
  const recRef = useRef<Recognition | null>(null);
  const Ctor = getRecognition();
  const ttsAvailable = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => () => { recRef.current?.abort(); if (ttsAvailable) window.speechSynthesis.cancel(); }, [ttsAvailable]);

  function say(textToSay: string) {
    if (!speak || !ttsAvailable) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(textToSay);
    u.lang = lang;
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("es"));
    if (voice) u.voice = voice;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  }

  function stopSpeaking() {
    if (ttsAvailable) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  async function ask(message: string, via: "voz" | "texto") {
    const m = message.trim();
    if (!m) return;
    stopSpeaking();   // interrumpe la respuesta anterior
    setBusy(true); setError(null);
    setMsgs((x) => [...x, { role: "usuario", content: m, via }]);
    try {
      const r = await post<{ conversation_id: string; reply: string }>("/api/neurovoice/chat", { message: m, conversation_id: conv });
      setConv(r.conversation_id);
      setMsgs((x) => [...x, { role: "asistente", content: r.reply }]);
      say(r.reply);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  function send(e: FormEvent) {
    e.preventDefault();
    const m = text;
    setText("");
    void ask(m, "texto");
  }

  function startListening() {
    if (!Ctor || !consent) return;
    stopSpeaking();
    setError(null); setInterim("");
    const rec = new Ctor();
    rec.lang = lang; rec.interimResults = true; rec.continuous = false;
    rec.onresult = (e) => {
      let finalText = "", partial = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript; else partial += r[0].transcript;
      }
      setInterim(partial);
      if (finalText) { setInterim(""); void ask(finalText, "voz"); }
    };
    rec.onerror = (e) => { setError(ERRORS[e.error] ?? `Error de reconocimiento: ${e.error}`); };
    rec.onend = () => { setListening(false); setInterim(""); };
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  function stopListening() { recRef.current?.stop(); }

  function acceptConsent(v: boolean) {
    setConsent(v);
    try { localStorage.setItem(CONSENT_KEY, v ? "si" : "no"); } catch { /* sin almacenamiento: se pide de nuevo */ }
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}><h1>NEUROVOICE IA</h1>{mod.data && <StatusBadge status={mod.data.status} />}</div>
      <Notice kind="info">
        Texto y voz en español. El asistente interpreta palabras clave (no usa un modelo de lenguaje), consulta a NEUROCORE y
        responde solo con datos reales; las simulaciones se presentan como simulaciones. Quechua y aimara: no soportados todavía.
      </Notice>

      <div className="card stack">
        <h2>Voz</h2>
        {!Ctor && <Notice kind="dev">Este navegador no ofrece reconocimiento de voz (Web Speech API). Use Chrome o Edge, o escriba su consulta.</Notice>}
        {Ctor && (
          <label className="row" style={{ fontWeight: 400, alignItems: "flex-start" }}>
            <input type="checkbox" checked={consent} onChange={(e) => acceptConsent(e.target.checked)} style={{ marginTop: 3 }} />
            <span className="small">Entiendo que, al usar el micrófono, <strong>el audio se envía a los servidores de Google</strong> para
              transcribirse (servicio del navegador Chrome). El texto resultante se procesa en NEUROAMBIENTAL IA.</span>
          </label>
        )}
        <div className="row">
          <select value={lang} onChange={(e) => setLang(e.target.value)} style={{ width: "auto" }} aria-label="Idioma de voz">
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          {!listening
            ? <button className="btn btn-green" onClick={startListening} disabled={!Ctor || !consent || busy}>🎤 Hablar</button>
            : <button className="btn" onClick={stopListening}>■ Detener micrófono</button>}
          <label className="row" style={{ fontWeight: 400 }}>
            <input type="checkbox" checked={speak} onChange={(e) => { setSpeak(e.target.checked); if (!e.target.checked) stopSpeaking(); }} disabled={!ttsAvailable} />
            <span className="small">Responder en voz alta {ttsAvailable ? "(voces del navegador, local)" : "(no disponible)"}</span>
          </label>
          {speaking && <button className="btn btn-ghost" onClick={stopSpeaking}>Interrumpir respuesta</button>}
        </div>
        {listening && <p className="small" aria-live="polite">Escuchando… {interim && <em>«{interim}»</em>}</p>}
      </div>

      <div className="card stack">
        <div className="chat" aria-live="polite">
          {msgs.length === 0 && <p className="muted small">Pruebe: «estado de los módulos», «¿cuántas alertas hay?», «explícame la simulación», «¿qué predicciones hay?», «¿cómo está el NDVI?», y luego «explícame más».</p>}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role === "usuario" ? "msg-user" : "msg-bot"}`}>
              {m.content}{m.via === "voz" && <span className="small" style={{ opacity: 0.8 }}> 🎤</span>}
            </div>
          ))}
        </div>
        <form onSubmit={send} className="row">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Escriba su consulta en español…" style={{ flex: 1 }} maxLength={2000} aria-label="Mensaje" />
          <button className="btn" disabled={busy}>Enviar</button>
          {conv && <button type="button" className="btn btn-ghost" onClick={() => { stopSpeaking(); setConv(null); setMsgs([]); }}>Nueva conversación</button>}
        </form>
        <ErrorText error={error} />
      </div>
    </div>
  );
}
