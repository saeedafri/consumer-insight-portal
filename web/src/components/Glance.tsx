// The business team's Databank block for a module wave: "This week at a glance" tiles and "Key takeaways",
// every number from config/dashboards.yml built by api/dashboards.py (vs prior week and vs last year).
import type { Metric } from "../api";
import { useDashboard } from "../api";
import { fmtDate } from "../stats";
import { Card, Failure, Loading } from "./bits";

const RULE: Record<string, string> = { same_wave_number: "same wave number last season", same_calendar_week: "same calendar week last year" };

function Delta({ d, label, flags }: { d: number | null; label: string; flags: string[] }) {
  if (flags.includes(`base_changed_${label === "vs LY" ? "ly" : "prior"}`))
    return <span className="chip warn" title="Who was asked this question changed, so the two numbers are not comparable">{label}: base changed</span>;
  if (d == null) return <span className="chip none">{label}: –</span>;
  return <span className="chip flat">{d > 0 ? "▲" : d < 0 ? "▼" : "±"} {Math.abs(d).toFixed(1)} pts <small>{label}</small></span>;
}

function Tile({ title, m, value, note }: { title: string; m: Metric | null; value?: string; note?: string }) {
  if (!m) return null;
  return <div className="card kpi glance" title={`n=${m.n} of ${m.base}`}>
    <div className="k-label">{title}</div>
    <div className="k-value">{value ?? `${m.pct.toFixed(1)}%`}</div>
    {note && <div className="k-note">{note}</div>}
    <div className="k-note"><Delta d={m.vs_ly} label="vs LY" flags={m.flags} /> <Delta d={m.vs_prior} label="vs prior week" flags={m.flags} /></div>
    {m.flags.includes("small_base") && <div className="k-note" style={{ color: "var(--warn)" }}>Small base (n={m.base})</div>}
  </div>;
}

export default function Glance({ code, id }: { code: string; id: number }) {
  const { data: d, isLoading, error } = useDashboard(code, id);
  if (isLoading) return <Loading what="tracker" />;
  if (error || !d) return <Failure error={error} />;
  const top = d.lists.retailers?.[0];
  const label = (k: string) => k.replace(/_/g, " ").replace("7d", "in past 7 days").replace(/^\w/, c => c.toUpperCase());
  return <section className="glance-block" aria-label={d.title}>
    <header className="glance-head">
      <h2>{d.title}: this week at a glance</h2>
      <p>Wave {d.wave.wave_no} · week of {fmtDate(d.wave.week_of)} · last year = {RULE[d.ly_rule] ?? d.ly_rule}
        {d.last_year ? ` (wave ${d.last_year.wave_no}, ${fmtDate(d.last_year.week_of)}${d.last_year.loaded ? "" : ", not loaded"})` : " (none)"}
        {d.data_as_of ? ` · data as of ${d.data_as_of.slice(0, 10)}` : ""}</p>
    </header>
    <div className="grid g5">
      {Object.entries(d.tiles).map(([k, m]) => <Tile key={k} title={label(k)} m={m} />)}
      {top && <Tile title="#1 holiday retailer" m={top} value={top.label} note={`${top.pct.toFixed(1)}% of purchasers${top.ly_pct != null ? ` · LY same wave ${top.ly_pct.toFixed(1)}%` : ""}`} />}
    </div>
    <Card title="Key takeaways" sub="Written from the numbers above, so they can never disagree with them">
      <ul className="takeaways">{d.takeaways.map(t => { const [head, ...rest] = t.split(": "); return <li key={t}><b>{head}:</b> {rest.join(": ")}</li>; })}</ul>
    </Card>
  </section>;
}

