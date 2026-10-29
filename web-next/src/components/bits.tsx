// Small shared pieces: base note, change chip, states, section card, source line, undo bar.
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { allowed, useMe } from "../api";
import type { Wave } from "../api";
import type { Format } from "../csv";
import type { Move } from "../moves";
import { pts, SMALL_BASE } from "../stats";
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

/** What "significant" means wherever a change is called one (moves.ts). */
export const SIG_RULE = "Significant: survives the correction for testing every answer of this wave at once (two-proportion z-test, Benjamini–Hochberg, 5 % false discoveries)";

/** Change vs the comparison wave. Red only when the wave's one significance rule (moves.ts) calls it significant. */
export function Change({ now, before, label, routing, move }:
  { now?: number; before: number | null; label: string; routing?: boolean; move?: Move }) {
  if (now == null) return null;
  if (routing) {
    return (
      <Tooltip>
        <TooltipTrigger render={<span className="chip warn">{label}: base changed</span>} />
        <TooltipContent side="top">Who was asked this question changed, so the two numbers are not comparable</TooltipContent>
      </Tooltip>
    );
  }
  if (before == null) return <span className="chip none">{label}: –</span>;
  const d = now - before;
  const sig = !!move?.sig;
  const chip = (
    <span className={`chip ${sig ? "sig" : "flat"}`}>
      {Math.abs(d) < 0.05 ? "no change" : `${d > 0 ? "▲" : "▼"} ${pts(d).replace(/^[+−]/, "")}`} <small>{label}</small>
    </span>
  );
  return (
    <Tooltip>
      <TooltipTrigger render={chip} />
      <TooltipContent side="top">
        {sig ? SIG_RULE : move?.testable ? "Not significant once corrected for testing every answer of this wave (Benjamini–Hochberg)"
          : "Not tested: fewer than 30 people on one side, or the question changed"}
      </TooltipContent>
    </Tooltip>
  );
}

export function Card({ title, sub, aside, children, className = "", as = "h2" }:
  { title?: ReactNode; sub?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; as?: "h1" | "h2" | "h3" }) {
  const Heading = as;
  return <section className={`card ${className}`}>
    {(title || aside) && <header className="card-head"><div><Heading>{title}</Heading>{sub && <p className="sub">{sub}</p>}</div>{aside}</header>}
    {children}
  </section>;
}

export function Loading({ what = "data" }: { what?: string }) {
  return <div className="state" role="status"><span className="spinner" aria-hidden /> Loading {what}…</div>;
}

/** A grey block the size of what is coming, so nothing jumps when it arrives (shimmer off under reduced motion). */
export function Skeleton({ height, width = "100%", className = "", label }: { height: number | string; width?: number | string; className?: string; label?: string }) {
  return <div className={`skel ${className}`} style={{ height, width }} {...(label ? { role: "status" } : { "aria-hidden": true })}>
    {label && <span className="sr-only">Loading {label}…</span>}
  </div>;
}

const SkeletonHead = () => <div className="page-head"><div style={{ flex: 1 }}><Skeleton height={34} width="min(620px, 90%)" /><Skeleton height={16} width="min(480px, 70%)" className="skel-line" /></div></div>;

/** The layout of a main screen while its data loads: the same boxes at the same sizes as the real page. */
export function SkeletonScreen({ kind }: { kind: "page" | "library" | "overview" | "question" }) {
  const body = {
    page: <SkeletonHead />,
    library: <><SkeletonHead /><div className="hero"><Skeleton height={232} className="card" /><div className="grid g2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} height={132} className="card" />)}</div></div>
      <div className="card">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} height={40} className="skel-line" />)}</div></>,
    overview: <><SkeletonHead /><Skeleton height={236} className="glance-block" />
      <div className="grid g5" style={{ marginBottom: 16 }}>{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} height={148} className="card" />)}</div>
      <div className="grid g3"><Skeleton height={360} className="card span2" /><Skeleton height={360} className="card" /></div></>,
    question: <div className="split"><Skeleton height="min(640px, calc(100vh - 100px))" className="qnav" />
      <div className="stack"><Skeleton height={176} className="card" /><Skeleton height={460} className="card" /></div></div>,
  }[kind];
  return <div role="status" aria-busy="true"><span className="sr-only">Loading…</span>{body}</div>;
}

export function Failure({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  const missing = /no such|not found|^404/i.test(message);   // a refresh cannot bring back what does not exist
  return (
    <div className="state error" role="alert">
      <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Could not load: {message}</p>
      {!missing && <button className="btn" onClick={() => window.location.reload()}>Refresh to try again</button>}{" "}
      <Link className="btn" to="/">Back to the survey library</Link>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

/** A time in US Eastern with its zone (EDT or EST): the portal's clients read US time. */
export const eastern = (at: Date, parts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) =>
  at.toLocaleString("en-US", { timeZone: "America/New_York", timeZoneName: "short", ...parts });

/** The line competitors put under every chart (YouGov, OWID, Civiqs): who, when, how many, how tested. */
const PLATFORM = { forsta: "Forsta", qualtrics: "Qualtrics", surveymonkey: "SurveyMonkey" };
const utc = (at: string) => new Date(at.replace(" ", "T") + (/[zZ]|[+-]\d\d:?\d\d$/.test(at) ? "" : "Z"));

/** Where a wave came from: platform, its source reference, and the fielding window when the platform recorded one. */
export function provenance(w?: Wave | null): string {
  if (!w?.platform) return "";
  const window = w.field_start && w.field_end ? ` · in field ${eastern(utc(w.field_start))} – ${eastern(utc(w.field_end))}` : "";
  return `${PLATFORM[w.platform]} ${w.source_ref ?? ""}${window}`.trim();
}

/** Who the sample stands for: the wave's own population, else the tracker's universe, never a guess for other studies. */
export const population = (w: Wave) => w.population || (w.study_type === "tracker" ? "US adults 18+" : "Survey respondents");
const survey = (w: Wave) => (w.study_type === "tracker" ? "Coresight Research US Consumer Survey" : `Coresight Research · ${w.title}`);
const weighting = (w: Wave) => (w.weighting && !/^(none|unweighted)$/i.test(w.weighting) ? `weighted (${w.weighting})` : "unweighted");
const partial = (w: Wave) => (w.in_field ? " · still in field: partial results" : "");

/** How this wave compares: a weekly tracker's previous wave is last week; other studies have a previous wave. */
export const compared = (w: Wave) => w.study_type === "tracker"
  ? { prior: "last week", Prior: "Last week", ly: "the same week last year" }
  : { prior: "the previous wave", Prior: "Previous wave", ly: "last year" };

export function SourceLine({ wave, base, asked, extra, from }: { wave: string; base: string; asked?: string | null; extra?: string; from: Wave }) {
  const origin = provenance(from);
  return <p className="source-line">
    Source: {survey(from)} · {population(from)} · fielded week of {wave} · {asked ? `asked of ${asked} · ` : ""}{base} · {weighting(from)}{partial(from)} · tested at 95 %{extra ? ` · ${extra}` : ""}
    {" · "}<Link to="/methodology">Methodology</Link>
    {origin && <><br />Data: {origin}</>}
  </p>;
}

/** The same source line as text, for a PNG footer and every download's notes. */
export const sourceText = (from: Wave, wave: string, base: string) =>
  `Source: ${survey(from)} · ${population(from)} · fielded week of ${wave} · ${base} · ${weighting(from)}${partial(from)}`
  + `${from.platform ? ` · ${provenance(from)}` : ""} · methodology: ${location.origin}/methodology`;

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

/** A small menu on native <details>: Escape or a click elsewhere closes it; `keep` leaves it open after a choice. */
export function Menu({ label, icon, children, keep = false }: { label: string; icon?: ReactNode; children: ReactNode; keep?: boolean }) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (e: Event) => {
      const d = menu.current;
      if (!d?.open) return;
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !d.contains(e.target as Node)) { d.open = false; if (e instanceof KeyboardEvent) d.querySelector("summary")?.focus(); }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, []);
  return <details ref={menu} className="menu">
    <summary className="btn" aria-label={icon && !label ? "More actions" : undefined}>{icon}{label}{label && <span aria-hidden className="caret">▾</span>}</summary>
    <div className="menu-list" onClick={e => { if (!keep && (e.target as HTMLElement).closest("button, a")) menu.current!.open = false; }}>{children}</div>
  </details>;
}

/** CSV, Excel, PowerPoint (and the chart as PNG) of the same table under one Export menu, and Pin to a board:
 *  every download on every screen carries the same rows and notes. */
export function ExportButtons({ onExport, png }: { onExport: (format: Format) => unknown; png?: () => unknown }) {
  const me = useMe().data;
  const [note, setNote] = useState("");
  const run = (format: Format) => { setNote(""); void Promise.resolve().then(() => onExport(format)).catch((e: Error) => setNote(e.message)); };
  const files = allowed(me, "export");
  if (!files && !png && !allowed(me, "boards")) return null;
  return <div className="head-actions export" role="group" aria-label="Download">
    {(files || png) && <Menu label="Export" icon={<IconDownload />}>
      {files && ([["csv", "CSV"], ["xlsx", "Excel"], ["pptx", "PowerPoint"]] as const).map(([format, label]) =>
        <button key={format} onClick={() => run(format)} aria-label={`Download this table as ${label}`}>{label}</button>)}
      {png && <button onClick={() => void png()} aria-label="Download the chart as a PNG image (light theme, with the source line)">PNG image</button>}
    </Menu>}
    {allowed(me, "boards") && <button className="btn" onClick={() => run("board")} aria-label="Pin this table, as it is now, to a board you can share and download as a deck">
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M16 3l5 5-3 1-4 4 1 5-2 2-4-4-5 5-1-1 5-5-4-4 2-2 5 1 4-4z" /></svg> Pin
    </button>}
    {note && <span className="muted" role="alert" style={{ alignSelf: "center", padding: "0 8px" }}>{note}</span>}
  </div>;
}

type Pending = { what: string; run: () => Promise<unknown>; undo?: () => void };
const WAIT = 6000;

/** A delete that can be taken back: the screen hides the thing now, and the request goes out after a few seconds
 *  unless Undo is pressed in the bar the shell shows (UndoBar). Leaving the page before then keeps the thing. */
export const deleteLater = (pending: Pending) => void window.dispatchEvent(new CustomEvent<Pending>("cip:undo", { detail: pending }));

export function UndoBar() {
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState("");
  const timer = useRef(0), current = useRef<Pending | null>(null);
  useEffect(() => {
    const go = (p: Pending) => void p.run().catch((e: Error) => { p.undo?.(); setError(`Could not delete ${p.what}: ${e.message}`); });
    const add = (e: Event) => {
      if (current.current) { clearTimeout(timer.current); go(current.current); }   // a second delete sends the first
      const p = (e as CustomEvent<Pending>).detail;
      current.current = p; setPending(p); setError("");
      timer.current = window.setTimeout(() => { current.current = null; setPending(null); go(p); }, WAIT);
    };
    window.addEventListener("cip:undo", add);
    return () => window.removeEventListener("cip:undo", add);
  }, []);
  const undo = () => { clearTimeout(timer.current); current.current?.undo?.(); current.current = null; setPending(null); };
  if (!pending && !error) return null;
  return <div className="undo-bar" role="status">
    {pending ? <>{pending.what} deleted. <button className="btn-chip" onClick={undo}>Undo</button></>
      : <>{error} <button className="btn-chip" onClick={() => setError("")}>Dismiss</button></>}
  </div>;
}
