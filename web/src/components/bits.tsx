// Small shared pieces: base note, change chip, states, section card.
import type { ReactNode } from "react";
import type { Wave } from "../api";
import type { Format } from "../csv";
import { pts, SMALL_BASE, significant } from "../stats";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

export function BaseNote({ base, label = "base" }: { base: number; label?: string }) {
  const content = (
    <span className={`base ${base < SMALL_BASE ? "small" : ""}`}>
      {label} n={base.toLocaleString("en-US")}{base < SMALL_BASE ? " · small" : ""}
    </span>
  );
  if (base < SMALL_BASE) {
    return (
      <Tooltip>
        <TooltipTrigger render={content} />
        <TooltipContent side="top">Small base (n &lt; 50): sample estimates carry wider margins of error</TooltipContent>
      </Tooltip>
    );
  }
  return content;
}

/** Change vs a comparison wave. Only a statistically significant change is emphasised (red); others stay grey. */
export function Change({ now, base, before, beforeBase, label, routing }:
  { now?: number; base: number; before: number | null; beforeBase: number | null; label: string; routing?: boolean }) {
  if (now == null) return null;
  if (routing) {
    return (
      <Tooltip>
        <TooltipTrigger render={<span className="chip warn">{label}: base changed</span>} />
        <TooltipContent side="top">Who was asked this question changed, so the two numbers are not comparable</TooltipContent>
      </Tooltip>
    );
  }
  if (before == null || !beforeBase) return <span className="chip none">{label}: –</span>;
  const d = now - before;
  const sig = significant(now, base, before, beforeBase);
  const chip = (
    <span className={`chip ${sig ? "sig" : "flat"}`}>
      {Math.abs(d) < 0.05 ? "no change" : `${d > 0 ? "▲" : "▼"} ${pts(d).replace(/^[+−]/, "")}`} <small>{label}</small>
    </span>
  );
  return (
    <Tooltip>
      <TooltipTrigger render={chip} />
      <TooltipContent side="top">
        {sig ? "Statistically significant at 95% confidence (two-proportion z-test)" : "Not statistically significant at 95% confidence"}
      </TooltipContent>
    </Tooltip>
  );
}

export function Card({ title, sub, aside, children, className = "", as = "h2" }:
  { title?: ReactNode; sub?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; as?: "h2" | "h3" }) {
  const Heading = as;
  return <section className={`card ${className}`}>
    {(title || aside) && <header className="card-head"><div><Heading>{title}</Heading>{sub && <p className="sub">{sub}</p>}</div>{aside}</header>}
    {children}
  </section>;
}

export function Loading({ what = "data" }: { what?: string }) {
  return <div className="state" role="status"><span className="spinner" aria-hidden /> Loading {what}…</div>;
}

export function Failure({ error }: { error: unknown }) {
  return (
    <div className="state error" role="alert">
      <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Could not load: {error instanceof Error ? error.message : String(error)}</p>
      <button className="btn" onClick={() => window.location.reload()}>Refresh to try again</button>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

/** The line competitors put under every chart (YouGov, OWID, Civiqs): who, when, how many, how tested. */
const PLATFORM = { forsta: "Forsta", qualtrics: "Qualtrics", surveymonkey: "SurveyMonkey" };
const istTime = (utc: string) => new Date(utc.replace(" ", "T") + "Z").toLocaleString("en-GB", { timeZone: "Asia/Kolkata",
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

/** Where a wave came from: platform, its source reference, and the fielding window when the platform recorded one. */
export function provenance(w?: Wave | null): string {
  if (!w?.platform) return "";
  const window = w.field_start && w.field_end ? ` · in field ${istTime(w.field_start)} – ${istTime(w.field_end)} IST` : "";
  return `${PLATFORM[w.platform]} ${w.source_ref ?? ""}${window}`.trim();
}

export function SourceLine({ wave, base, asked, extra, from }: { wave: string; base: string; asked?: string | null; extra?: string; from?: Wave | null }) {
  const origin = provenance(from);
  return <p className="source-line" title="Unweighted percentages of qualified respondents. Changes are tested with a two-proportion z-test at 95 %; the What changed list also corrects for testing many answers at once (Benjamini–Hochberg).">
    Source: Coresight Research US Consumer Survey · US adults 18+ · fielded week of {wave} · {asked ? `asked of ${asked} · ` : ""}{base} · unweighted · significance at 95 %{extra ? ` · ${extra}` : ""}
    {origin && <><br />Data: {origin}</>}
  </p>;
}

export const sourceText = (wave: string, base: string, from?: Wave | null) =>
  `Source: Coresight Research US Consumer Survey · US adults 18+ · fielded week of ${wave} · ${base} · unweighted${from?.platform ? ` · ${provenance(from)}` : ""}`;

export function IconDownload() {
  return <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/></svg>;
}

export function IconImage() {
  return <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" fill="currentColor"/></svg>;
}

export function IconLink() {
  return <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" fill="currentColor"/></svg>;
}

export async function copyLink(button: HTMLButtonElement) {
  const target = button.querySelector("span") || button;
  const original = target.textContent;
  try {
    await navigator.clipboard.writeText(location.href);
    target.textContent = "Link copied";
  } catch {
    target.textContent = "Copy the address bar";
  }
  setTimeout(() => { target.textContent = original; }, 1800);
}

/** CSV, Excel and PowerPoint of the same table: every download on every screen carries the same rows and notes. */
export function ExportButtons({ onExport }: { onExport: (format: Format) => unknown }) {
  return <div className="seg export" role="group" aria-label="Download">
    {([["csv", "CSV"], ["xlsx", "Excel"], ["pptx", "PowerPoint"]] as const).map(([format, label]) =>
      <button key={format} onClick={() => onExport(format)} title={`Download this table as ${label}`}><IconDownload /> {label}</button>)}
    <button onClick={() => onExport("board")} title="Pin this table, as it is now, to a board you can share and download as a deck">
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M16 3l5 5-3 1-4 4 1 5-2 2-4-4-5 5-1-1 5-5-4-4 2-2 5 1 4-4z" /></svg> Board
    </button>
  </div>;
}
