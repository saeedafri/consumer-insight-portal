// The business team's Databank block for a module wave: "This week at a glance" tiles and "Key takeaways",
// every number from config/dashboards.yml built by api/dashboards.py (vs prior week and vs last year); drawn by a
// wave's Overview and the Trackers page. Also FigureCard, one figure as a card, for Home's week at a glance and the
// Sector and Retailer databanks' cards, and Delta, the change chip Home and In store vs online use.
import { words } from "../trackers";
import type { ReactNode } from "react";
import { Link } from "react-router";
import CountUp from "./CountUp";
import type { Change, Metric } from "../api";
import { useDashboard } from "../api";
import { direction, fmtDate, HIDDEN_BASE } from "../stats";
import { Failure, Skeleton } from "./bits";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

const RULE: Record<string, string> = { same_wave_number: "same wave number last season", same_calendar_week: "same calendar week last year",
                                       nearest_year_ago: "closest wave a year earlier" };

export function Delta({ d, label, flags }: { d: number | null; label: string; flags: string[] }) {
  if (flags.includes(`base_changed_${label === "vs LY" ? "ly" : "prior"}`)) {
    return (
      <Tooltip>
        <TooltipTrigger render={<span className="chip warn">{label}: base changed</span>} />
        <TooltipContent side="top">Who was asked this question changed, so the two numbers are not comparable</TooltipContent>
      </Tooltip>
    );
  }
  if (d == null) return <span className="chip none">{label}: –</span>;
  return <span className={`chip flat ${direction(d)}`}><span className="nowrap">{d > 0 ? "▲" : d < 0 ? "▼" : "±"} {Math.abs(d).toFixed(1)} pts</span> <small>{label}</small></span>;
}

/** One figure, as its own card (the 9 Nov 2026 redesign); the first of a block carries the red tab, the rest light blue. */
function Tile({ title, m, value, note, prior, lead }: { title: string; m: Metric | null; value?: string; note?: string; prior: string; lead?: boolean }) {
  if (!m) return null;
  return <div className={`card kpi glance-tile${lead ? " lead" : ""}`} title={`n=${m.n} of ${m.base}`}>
    <div className="k-label">{title}</div>
    <div className={`k-value${value && value.length > 14 ? " k-text" : ""}`}>{value ?? (m.pct == null ? `n<${HIDDEN_BASE}` : <CountUp text={`${m.pct.toFixed(1)}%`} />)}</div>
    {note && <div className="k-note">{note}</div>}
    <div className="k-note"><Delta d={m.vs_ly} label="vs LY" flags={m.flags} /> <Delta d={m.vs_prior} label={`vs ${prior}`} flags={m.flags} /></div>
    {m.flags.includes("small_base") && <div className="k-note" style={{ marginTop: 2 }}>
      <span style={{ color: "var(--warn)", fontWeight: 600 }}>Small base (n={m.base})</span>
    </div>}
  </div>;
}

/** One figure as a card (Home's week at a glance, the Sector and Retailer databanks' cards): a link with `to`, a
 *  button with `onClick`, else plain. `badge` names where it comes from (the sector, "New this week"); `changes` are
 *  its change badges, as the at-a-glance tiles above show theirs. `children` replaces the value and note (several
 *  retailers, one line each). */
export function FigureCard({ badge, title, value = "", note, changes = [], lead, to, onClick, children }: { badge?: string; title: string;
  value?: string; note?: string; changes?: Change[]; lead?: boolean; to?: string; onClick?: () => void; children?: ReactNode }) {
  const body = <>{badge && <span className="chip flat k-badge">{badge}</span>}<div className="k-label">{title}</div>
    {children ?? <><div className={`k-value${value.length > 14 ? " k-text" : ""}`}>{value}</div><div className="k-note">{note}</div>
      {changes.length > 0 && <div className="k-note">{changes.map(c => <Delta key={c.label} d={c.d} label={c.label} flags={c.flags ?? []} />)}</div>}</>}</>;
  const look = `card kpi glance-tile${lead ? " lead" : ""}`;
  return to ? <Link className={look} to={to}>{body}</Link>
    : onClick ? <button type="button" className={look} onClick={onClick}>{body}</button> : <div className={look}>{body}</div>;
}

/** Balanced rows at every width: 4 tiles are 4, then 2 × 2, never 3 + 1. */
const columns = (n: number) => ({ "--cols": n, "--cols-mid": n > 3 ? Math.ceil(n / 2) : n, "--cols-narrow": Math.min(n, 2) }) as React.CSSProperties;

export default function Glance({ code, id }: { code: string; id: number }) {
  const { data: d, isLoading, error } = useDashboard(code, id);
  if (isLoading) return <Skeleton height={236} className="glance-block" label="tracker" />;
  if (error || !d) return <Failure error={error} />;
  const prior = (d.prior_label ?? "prior week").replace(/^the /, "");
  const label = (k: string) => d.tile_labels?.[k] ?? words(k);
  const highlights = d.highlights ?? [];
  return <>
    <section className="glance-block" aria-label={d.title}>
      <header className="glance-head">
        <h2>{d.title}: at a glance</h2>
        <p>Wave {d.wave.wave_no} · week of {fmtDate(d.wave.week_of)}
          {d.prior ? ` · compared with ${prior} (${fmtDate(d.prior.week_of)})` : ""} · last year = {RULE[d.ly_rule] ?? d.ly_rule}
          {d.last_year ? ` (wave ${d.last_year.wave_no}, ${fmtDate(d.last_year.week_of)}${d.last_year.loaded ? "" : ", not loaded"})` : " (none)"}
          {d.data_as_of ? ` · data as of ${d.data_as_of.slice(0, 10)}` : ""}</p>
      </header>
      <div className="glance-tiles" style={columns(Object.values(d.tiles).filter(Boolean).length + highlights.length)}>
        {Object.entries(d.tiles).map(([k, m], i) => <Tile key={k} title={label(k)} m={m} prior={prior} lead={i === 0} />)}
        {highlights.map(h => { const top = d.lists[h.list]?.[0]; return top && <Tile key={h.list} title={h.title} m={top} value={top.label} prior={prior}
          note={`${top.pct == null ? `n<${HIDDEN_BASE}` : `${top.pct.toFixed(1)}%`} ${h.of}${top.ly_pct != null ? ` · last year ${top.ly_pct.toFixed(1)}%` : ""}`} />; })}
      </div>
      {d.takeaways.length > 0 && <div className="card glance-takeaways">
        <h3>Key takeaways</h3>
        <p className="sub">Written from the numbers above, so they can never disagree with them</p>
        <ul className="takeaways">{d.takeaways.map(t => { const [head, ...rest] = t.split(": "); return <li key={t}><b>{head}:</b> {rest.join(": ")}</li>; })}</ul>
      </div>}
    </section>
  </>;
}

