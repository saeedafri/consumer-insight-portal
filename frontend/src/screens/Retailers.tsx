// Retailer comparison (/app/retailers): two retailers side by side from the weekly tracker: how many people bought from
// each in the past two weeks, who their shoppers are (gender, generation, household income, next to all adults), and
// how positive people feel about them where the apparel grid asked. Every number is built by the ETL when data is
// published (etl/retailers.py → api/v1/retailers.json.gz; rules in config/retailers.yml); this screen only draws.
// Opened from the left menu (Research data → Retailer comparison); the retailers and week are kept in the address.
import { Link, useSearchParams } from "react-router";
import { useRetailers } from "../api";
import type { Profile, Retailers as Data } from "../api";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import { fmtDate } from "../stats";

const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
const DIMENSIONS: [keyof Profile, string][] = [["gender", "Gender"], ["generation", "Generation"], ["income", "Household income"]];

/** One measure for both retailers: a labelled bar each, A in red, B in blue, the value at the end. */
function Pair({ a, b, names, sub }: { a: number | null; b: number | null; names: [string, string]; sub?: [string, string] }) {
  return <div className="pair">
    {[a, b].map((v, i) => <div key={i} className={`pair-row ${i ? "b" : "a"}`}>
      <span className="pair-name">{names[i]}{sub && <small>{sub[i]}</small>}</span>
      <span className="pair-track"><i style={{ width: `${Math.min(100, v ?? 0)}%` }} /></span>
      <b>{pct(v)}</b>
    </div>)}
  </div>;
}

export default function Retailers() {
  const { data, isLoading, error } = useRetailers();
  const [params, setParams] = useSearchParams();
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404) return <Empty>The retailer comparison has not been published yet.</Empty>;
  if (error || !data) return <Failure error={error} />;
  if (data.retailers.length < 2 || !data.weeks.length) return <Empty>Not enough retailers asked yet.</Empty>;
  const names = data.retailers.map(r => r.name);
  const pick = (k: string, v: string) => setParams(p => { p.set(k, v); return p; }, { replace: true });
  const find = (name: string | null, fallback: string) => data.retailers.find(r => r.name === name) ?? data.retailers.find(r => r.name === fallback) ?? data.retailers[0];
  const a = find(params.get("a"), "Walmart");
  const b = find(params.get("b"), "Costco");
  const at = Math.max(0, data.weeks.findIndex(w => String(w.survey_id) === params.get("w")));
  const week = data.weeks[at];
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Retailer comparison</h1>
      <p className="lede">Two retailers side by side: how many people bought from each in the past two weeks, who their shoppers are,
        and how positive people feel about them. Each figure adds {week.weeks === 1 ? "one week" : `${week.weeks} weekly surveys`} together, so smaller retailers have enough shoppers to describe.</p>
    </div>
      <div className="seg" role="group" aria-label="Compare by"><button aria-pressed="true">By retailer</button><Link className="seg-link" to="/sectors">By sector</Link></div>
    </div>

    <section className="card compare-bar" aria-label="Choose what to compare">
      <label><span>Retailer</span><select value={a.name} onChange={e => pick("a", e.target.value)}>{names.map(n => <option key={n}>{n}</option>)}</select></label>
      <span className="vs" aria-hidden="true">vs</span>
      <label><span>Retailer</span><select value={b.name} onChange={e => pick("b", e.target.value)}>{names.map(n => <option key={n}>{n}</option>)}</select></label>
      <label><span>Weeks</span><select value={week.survey_id} onChange={e => pick("w", e.target.value)}>
        {data.weeks.map(w => <option key={w.survey_id} value={w.survey_id}>{w.weeks > 1 ? `${fmtDate(w.from)} to ${fmtDate(w.date)}` : fmtDate(w.date)}</option>)}</select></label>
      <span className="chip sig">n={week.respondents.toLocaleString("en-US")} respondents</span>
    </section>

    <div className="grid g2">
      <Card title="Bought in the past two weeks" sub={`% of all respondents · any product, then food and nonfood · ${week.weeks} weeks to ${fmtDate(week.date)}`}>
        <Pair a={a.reach.any[at]} b={b.reach.any[at]} names={[a.name, b.name]}
              sub={[`food ${pct(a.reach.food[at])} · nonfood ${pct(a.reach.nonfood[at])}`, `food ${pct(b.reach.food[at])} · nonfood ${pct(b.reach.nonfood[at])}`]} />
      </Card>
      <Card title="How positive people feel" sub="Very or somewhat positive, among those asked: the apparel survey, asked about 28 apparel retailers every few months">
        {a.sentiment || b.sentiment
          ? <><Pair a={a.sentiment?.positive ?? null} b={b.sentiment?.positive ?? null} names={[a.name, b.name]}
                    sub={[a.sentiment ? `n=${a.sentiment.n} · ${fmtDate(a.sentiment.date)}` : "not asked", b.sentiment ? `n=${b.sentiment.n} · ${fmtDate(b.sentiment.date)}` : "not asked"]} /></>
          : <p className="muted">Neither retailer is in the apparel survey's list, so there is no sentiment figure for them.</p>}
      </Card>
    </div>

    <ShopperProfile data={data} a={a} b={b} at={at} />
    <p className="source-line">Source: Coresight Research US Consumer Survey, weekly tracker, {week.weeks} weeks from {fmtDate(week.from)} to {fmtDate(week.date)} (n={week.respondents.toLocaleString("en-US")}).
      Unweighted. Shopper profiles shown only from {data.min_buyers} shoppers; groups do not add to 100% where people preferred not to say.</p>
  </div>;
}

/** Who shops at each: the share of each retailer's shoppers in every group, with all adults' share for reference. */
function ShopperProfile({ data, a, b, at }: { data: Data; a: Data["retailers"][number]; b: Data["retailers"][number]; at: number }) {
  const pa = a.profile[at], pb = b.profile[at], all = data.everyone[at];
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `Shopper profile - ${a.name} vs ${b.name}`,
    ["Group", a.name, b.name, "All adults"],
    DIMENSIONS.flatMap(([d, title]) => data.groups[d].map((g, i) => [`${title}: ${g}`, pa?.[d][i] ?? null, pb?.[d][i] ?? null, all[d][i]])),
    [`Shopper profile: ${a.name} vs ${b.name}`, "% of each retailer's shoppers in the past two weeks", "Source: Coresight Research US Consumer Survey"]);
  return <Card title="Shopper profile" sub={`Who bought from each in the past two weeks: ${a.name} n=${a.buyers[at]}, ${b.name} n=${b.buyers[at]} shoppers`}
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="grid g3 profile-grid">
      {DIMENSIONS.map(([d, title]) => <section key={d}>
        <h3>{title}</h3>
        <table className="profile-table">
          <thead><tr><th scope="col"><span className="sr-only">Group</span></th><th scope="col" className="a">{a.name}</th><th scope="col" className="b">{b.name}</th><th scope="col">All adults</th></tr></thead>
          <tbody>{data.groups[d].map((g, i) => <tr key={g}>
            <th scope="row">{g}</th>
            {[pa, pb].map((p, k) => <td key={k} className={k ? "b" : "a"}>
              {p ? <><span className="pair-track"><i style={{ width: `${Math.min(100, p[d][i] ?? 0)}%` }} /></span>{pct(p[d][i])}</> : <span className="muted">n&lt;{data.min_buyers}</span>}</td>)}
            <td className="muted">{pct(all[d][i])}</td>
          </tr>)}</tbody>
        </table>
      </section>)}
    </div>
  </Card>;
}
