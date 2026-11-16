// The mic button in every Ask CIP box: the Home page's (screens/Home.tsx) and the Ask CIP page's (screens/Ask.tsx).
// Press it and speak; the words appear in the box, and the person still presses Ask. It uses the browser's own
// speech-to-text (Web Speech API): Chrome and Edge send the audio to Google's or Microsoft's speech service, Safari to
// Apple's; nothing reaches CIP's servers and CIP pays nothing. Visible and user-started only: the browser asks permission
// the first time and shows while it is listening. Where the browser has no speech-to-text (Firefox) the button is not
// drawn. (15 Nov 2026)
import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";

type HeardEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Dictation = { lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void; abort(): void;
  onresult: ((e: HeardEvent) => void) | null; onend: (() => void) | null; onerror: (() => void) | null };

/** The browser's speech-to-text, or null where it is missing. */
const speechRecognition = (): (new () => Dictation) | null => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => Dictation; webkitSpeechRecognition?: new () => Dictation };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

/** Press to speak, press again to stop; the words are added after what is already typed in the box. */
export default function MicButton({ text, setText }: { text: string; setText: (text: string) => void }) {
  const [Recogniser] = useState(speechRecognition);
  const [listening, setListening] = useState(false);
  const hearing = useRef<Dictation | null>(null);
  useEffect(() => () => hearing.current?.abort(), []);   // leaving the screen stops the mic
  if (!Recogniser) return null;
  const dictate = () => {
    if (hearing.current) { hearing.current.stop(); return; }
    const r = new Recogniser();
    r.lang = "en-US"; r.interimResults = true; r.continuous = false;
    const before = text.trim() ? text.trim() + " " : "";
    r.onresult = e => setText(before + Array.from(e.results, said => said[0].transcript).join(""));
    r.onend = r.onerror = () => { hearing.current = null; setListening(false); };
    hearing.current = r; setListening(true); r.start();
  };
  return <button type="button" className={`btn ask-mic${listening ? " on" : ""}`} aria-pressed={listening}
    aria-label={listening ? "Stop dictation" : "Speak your question"} title={listening ? "Listening — press to stop" : "Speak your question"}
    onClick={dictate}><Mic size={16} aria-hidden="true" />{listening ? "Listening…" : ""}</button>;
}
