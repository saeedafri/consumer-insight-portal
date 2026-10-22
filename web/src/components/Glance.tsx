// The business team's Databank block for a module wave: "This week at a glance" tiles and "Key takeaways",
// every number from config/dashboards.yml built by api/dashboards.py (vs prior week and vs last year).
import CountUp from "./CountUp";
import type { Metric } from "../api";
import { useDashboard } from "../api";
import { fmtDate } from "../stats";
import { Card, Failure, Loading } from "./bits";
import Profiled from "./Profiled";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

const RULE: Record<string, string> = { same_wave_number: "same wave number last season", same_calendar_week: "same calendar week last year",
                                       nearest_year_ago: "closest wave a year earlier" };

function Delta({ d, label, flags }: { d: number | null; label: string; flags: string[] }) {
  if (flags.includes(`base_changed_${label === "vs LY" ? "ly" : "prior"}`)) {
    return (
      <Tooltip>
        <TooltipTrigger render={<span className="chip warn">{label}: base changed</span>} />
        <TooltipContent side="top">Who was asked this question changed, so the two numbers are not comparable</TooltipContent>
      </Tooltip>
    );
  }
  if (d == null) return <span className="chip none">{label}: –</span>;
  return <span className="chip flat"><span className="nowrap">{d > 0 ? "▲" : d < 0 ? "▼" : "±"} {Math.abs(d).toFixed(1)} pts</span> <small>{label}</small></span>;
}

function Tile({ title, m, value, note, prior }: { title: string; m: Metric | null; value?: string; note?: string; prior: string }) {
  if (!m) return null;
  return <div className="glance-tile" title={`n=${m.n} of ${m.base}`}>
    <div className="k-label">{title}</div>
    <div className={`k-value${value && value.length > 14 ? " k-text" : ""}`}>{value ?? (m.pct == null ? "n<30" : <CountUp text={`${m.pct.toFixed(1)}%`} />)}</div>
    {note && <div className="k-note">{note}</div>}
    <div className="k-note"><Delta d={m.vs_ly} label="vs LY" flags={m.flags} /> <Delta d={m.vs_prior} label={`vs ${prior}`} flags={m.flags} /></div>
    {m.flags.includes("small_base") && <div className="k-note" style={{ marginTop: 2 }}>
      <span style={{ color: "var(--warn)", fontWeight: 600 }}>Small base (n={m.base})</span>
    </div>}
  </div>;
}

/** Balanced rows at every width: 4 tiles are 4, then 2 × 2, never 3 + 1. */
const columns = (n: number) => ({ "--cols": n, "--cols-mid": n > 3 ? Math.ceil(n / 2) : n, "--cols-narrow": Math.min(n, 2) }) as React.CSSProperties;

export default function Glance({ code, id }: { code: string; id: number }) {
  const { data: d, isLoading, error } = useDashboard(code, id);
  if (isLoading) return <Loading what="tracker" />;
  if (error || !d) return <Failure error={error} />;
  const prior = (d.prior_label ?? "prior week").replace(/^the /, "");
  const label = (k: string) => d.tile_labels?.[k] ?? k.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase());
  const highlights = d.highlights ?? [];
  return <Profiled id={`Glance:${code}`}>
    <section className="glance-block" aria-label={d.title}>
      <header className="glance-head">
        <h2>{d.title}: at a glance</h2>
        <p>Wave {d.wave.wave_no} · week of {fmtDate(d.wave.week_of)}
          {d.prior ? ` · compared with ${prior} (${fmtDate(d.prior.week_of)})` : ""} · last year = {RULE[d.ly_rule] ?? d.ly_rule}
          {d.last_year ? ` (wave ${d.last_year.wave_no}, ${fmtDate(d.last_year.week_of)}${d.last_year.loaded ? "" : ", not loaded"})` : " (none)"}
          {d.data_as_of ? ` · data as of ${d.data_as_of.slice(0, 10)}` : ""}</p>
      </header>
      <div className="glance-tiles" style={columns(Object.values(d.tiles).filter(Boolean).length + highlights.length)}>
        {Object.entries(d.tiles).map(([k, m]) => <Tile key={k} title={label(k)} m={m} prior={prior} />)}
        {highlights.map(h => { const top = d.lists[h.list]?.[0]; return top && <Tile key={h.list} title={h.title} m={top} value={top.label} prior={prior}
          note={`${top.pct == null ? "n<30" : `${top.pct.toFixed(1)}%`} ${h.of}${top.ly_pct != null ? ` · last year ${top.ly_pct.toFixed(1)}%` : ""}`} />; })}
      </div>
      <Card title="Key takeaways" sub="Written from the numbers above, so they can never disagree with them">
        <ul className="takeaways">{d.takeaways.map(t => { const [head, ...rest] = t.split(": "); return <li key={t}><b>{head}:</b> {rest.join(": ")}</li>; })}</ul>
      </Card>
    </section>
  </Profiled>;
}

