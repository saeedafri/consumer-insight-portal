// Expected vs actual (/app/expectations): for a retail event (Halloween, Black Friday…), what people said before it they
// would do against what people said afterwards they did, from two different weekly surveys, as the seasonal "US Consumer
// Survey Insights Extra" report shows it; with the median spend and the market size where the survey asks how much.
// Every number is built by the ETL when data is published (etl/expectations.py → api/v1/expectations.json.gz); which
// events and questions: config/expectations.yml. This screen only draws.
// Opened from the left menu ("Expected vs actual"); the event and comparison are kept in the address.
import { useSearchParams } from "react-router";
import { useExpectations } from "../api";
import type { EventComparison, SpendSide } from "../api";
import { Card, Empty, Failure, SkeletonScreen } from "../components/bits";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtDate } from "../stats";

/** A gap in percentage points, signed: +4.9, −8.7. */
const points = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`;
const dollars = (v: number | undefined) => v == null ? "–" : `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const label = (c: EventComparison) =>
  `Expected ${fmtDate(c.expected.date)} vs actual ${fmtDate(c.actual.date)}${c.same_season ? "" : " (the year before)"}`;

export default function Expectations() {
  const { data, isLoading, error } = useExpectations();
  const [params, setParams] = useSearchParams();
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404) return <Empty>Expected vs actual has not been published yet.</Empty>;
  if (error || !data) return <Failure error={error} />;
  const event = data.events.find(e => e.name === params.get("event")) ?? data.events[0];
  if (!event) return <Empty>No event has been asked about before and after yet.</Empty>;
  const at = Math.max(0, Math.min(Number(params.get("pair")) || 0, event.comparisons.length - 1));   // any address value is safe
  const shown = event.comparisons[at];
  const pick = (key: string, value: string) => setParams(p => { p.set(key, value); if (key === "event") p.delete("pair"); return p; }, { replace: true });
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Expected vs actual</h1>
      <p className="lede">What consumers said before a retail event they would do, against what consumers said afterwards they did:
        two different weekly surveys of about 400 US adults. Differences are in percentage points (PPTs), coloured when statistically significant.</p>
    </div></div>
    <div className="toolbar one-row">
      <Tabs value={event.name} onValueChange={name => pick("event", name)}><TabsList>
        {data.events.map(e => <TabsTrigger key={e.name} value={e.name}>{e.name}</TabsTrigger>)}
      </TabsList></Tabs>
      <label className="sr-only" htmlFor="pair">Surveys compared</label>
      <select id="pair" value={at} onChange={e => pick("pair", e.target.value)} style={{ maxWidth: "100%" }}>
        {event.comparisons.map((c, i) => <option key={i} value={i}>{label(c)}</option>)}
      </select>
    </div>
    {shown.spend && <Spend spend={shown.spend} adults={data.us_adults_millions} comparison={shown} />}
    {shown.questions.map(q => <Card key={q.expected_code} title={q.expected_text}
        sub={`Afterwards: "${q.actual_text}" Base: ${q.expected_base.toLocaleString("en-US")} before, ${q.actual_base.toLocaleString("en-US")} after.`}
        aside={q.net && <span className="chip flat" title="% more minus % less">Net more: {points(q.net.expected)} expected, {points(q.net.actual)} actual</span>}>
      <div className="table-wrap"><table className="data report-table">
        <thead><tr><th>Answer</th><th className="num">Expected<br /><small>{fmtDate(shown.expected.date)}</small></th>
          <th className="num">Actual<br /><small>{fmtDate(shown.actual.date)}</small></th><th className="num" title="Expected minus actual, percentage points">Difference</th></tr></thead>
        <tbody>{q.rows.map(r => <tr key={r.label}>
          <th scope="row" title={r.actual_label !== r.label ? `Afterwards: ${r.actual_label}` : undefined}>{r.label}</th>
          <td className="num"><span className="vs-bar" style={{ width: r.expected * 1.2 }} />{r.expected.toFixed(1)}%</td>
          <td className="num"><span className="vs-bar actual" style={{ width: r.actual * 1.2 }} />{r.actual.toFixed(1)}%</td>
          <td className={`num ${r.significant ? "change-sig" : ""}`} title={r.significant ? "Statistically significant" : undefined}>{points(r.difference)}</td>
        </tr>)}</tbody>
      </table></div>
    </Card>)}
  </div>;
}

/** Median spend and the market size it implies (share who spend x US adults x median), before and after. */
function Spend({ spend, adults, comparison }: { spend: NonNullable<EventComparison["spend"]>; adults: number; comparison: EventComparison }) {
  const side = (name: string, date: string, s: SpendSide | null) => <div className="card kpi">
    <div className="k-label">{name} median spend · {fmtDate(date)}</div>
    <div className="k-value">{dollars(s?.median)}</div>
    <div className="k-note">{s ? <>Market size about <b>${s.market_billions ?? "–"} billion</b>: {s.spenders ?? "–"}% spend, from {s.answers} answers</> : "Not asked"}</div>
  </div>;
  return <div className="stack">
    <div className="grid g2">
      {side("Expected", comparison.expected.date, spend.expected)}
      {side("Actual", comparison.actual.date, spend.actual)}
    </div>
    <p className="muted">Market size = share of US adults who spend x {adults} million US adults 18+ x the median spend (spending by adults 18+ only).</p>
  </div>;
}
