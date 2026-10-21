// Small shared pieces: base note, change chip, states, section card.
import type { ReactNode } from "react";
import { pts, SMALL_BASE, significant } from "../stats";

export function BaseNote({ base, label = "base" }: { base: number; label?: string }) {
  return <span className={`base ${base < SMALL_BASE ? "small" : ""}`} title={base < SMALL_BASE ? "Small base: read with caution" : undefined}>
    {label} n={base.toLocaleString("en-US")}{base < SMALL_BASE ? " · small" : ""}
  </span>;
}

/** Change vs a comparison wave. Only a statistically significant change is emphasised (red); others stay grey. */
export function Change({ now, base, before, beforeBase, label, routing }:
  { now?: number; base: number; before: number | null; beforeBase: number | null; label: string; routing?: boolean }) {
  if (now == null) return null;
  if (routing) return <span className="chip warn" title="Who was asked this question changed, so the two numbers are not comparable">{label}: base changed</span>;
  if (before == null || !beforeBase) return <span className="chip none">{label}: –</span>;
  const d = now - before;
  const sig = significant(now, base, before, beforeBase);
  return <span className={`chip ${sig ? "sig" : "flat"}`} title={sig ? "Significant at 95 %" : "Not significant at 95 %"}>
    {Math.abs(d) < 0.05 ? "no change" : `${d > 0 ? "▲" : "▼"} ${pts(d).replace(/^[+−]/, "")}`} <small>{label}</small>
  </span>;
}

export function Card({ title, sub, aside, children, className = "" }:
  { title?: ReactNode; sub?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>
    {(title || aside) && <header className="card-head"><div><h3>{title}</h3>{sub && <p className="sub">{sub}</p>}</div>{aside}</header>}
    {children}
  </section>;
}

export function Loading({ what = "data" }: { what?: string }) {
  return <div className="state" role="status"><span className="spinner" aria-hidden /> Loading {what}…</div>;
}
export function Failure({ error }: { error: unknown }) {
  return <div className="state error" role="alert">Could not load: {error instanceof Error ? error.message : String(error)}. Refresh to try again.</div>;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

/** The line competitors put under every chart (YouGov, OWID, Civiqs): who, when, how many, how tested. */
export function SourceLine({ wave, base, asked, extra }: { wave: string; base: string; asked?: string | null; extra?: string }) {
  return <p className="source-line" title="Unweighted percentages of qualified respondents. Changes are tested with a two-proportion z-test at 95 %; the What changed list also corrects for testing many answers at once (Benjamini–Hochberg).">
    Source: Coresight Research US Consumer Survey · US adults 18+ · fielded week of {wave} · {asked ? `asked of ${asked} · ` : ""}{base} · unweighted · significance at 95 %{extra ? ` · ${extra}` : ""}
  </p>;
}

export const sourceText = (wave: string, base: string) =>
  `Source: Coresight Research US Consumer Survey · US adults 18+ · fielded week of ${wave} · ${base} · unweighted`;

export async function copyLink(button: HTMLButtonElement) {
  try { await navigator.clipboard.writeText(location.href); button.textContent = "Link copied"; }
  catch { button.textContent = "Copy the address bar"; }
  setTimeout(() => { button.textContent = "Copy link"; }, 1800);
}
