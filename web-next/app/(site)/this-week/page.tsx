import Link from "next/link";
import { SITE } from "../../site";
import { Jsonld, Breadcrumbs } from "../seo";
import { siteFacts, featuredFindings, type Featured } from "../pipeline";

export const metadata = {
  title: { absolute: "This Week in US Consumer Data | Coresight Consumer Insight Portal" },
  description: "This week in US consumer data: spending intentions, category spend, online share and generational shifts from Coresight's weekly US consumer survey. Updated every week from the latest wave.",
  alternates: { canonical: "/this-week/" },
};

// APPROVED FOR PUBLIC RELEASE — add { cat, qid, row } entries (ids from the latest wave's book) and the cards below
// show real figures from the pipeline automatically, with the delta computed against the prior wave. While this is
// empty, no survey answer is published: the cards fall back to the clearly-labelled illustrative examples.
const FEATURED: Featured[] = [];

// Illustrative examples, shown until FEATURED is populated.
type Finding = { cat: string; head: string; delta: string; sig: boolean; kind: "line" | "bars"; series: number[]; labels?: string[] };
const SAMPLE: Finding[] = [
  { cat: "Spending", head: "61% of US consumers plan to cut back on non-essential spending", delta: "▲ 3 pts vs prior wave", sig: true, kind: "line", series: [53, 55, 54, 56, 57, 56, 58, 57, 59, 58, 60, 61] },
  { cat: "Grocery", head: "Grocery holds as the category shoppers are least likely to trim", delta: "Flat — 8 waves running", sig: false, kind: "bars", series: [71, 58, 44, 39, 33, 27], labels: ["Grocery", "Household", "Apparel", "Dining", "Electronics", "Travel"] },
  { cat: "Channel", head: "Online edges up to 38% of planned retail spend", delta: "▲ 1 pt vs prior wave", sig: false, kind: "line", series: [34, 35, 34, 36, 35, 36, 37, 36, 37, 37, 38, 38] },
  { cat: "Generation", head: "Gen Z leads the shift to private label and value brands", delta: "▲ 4 pts vs prior wave", sig: true, kind: "bars", series: [48, 39, 33, 27], labels: ["Gen Z", "Millennial", "Gen X", "Boomer"] },
];

function Chart({ f }: { f: Finding }) {
  const w = 360, h = 120, pad = 8;
  if (f.kind === "line") {
    const min = Math.min(...f.series) - 4, max = Math.max(...f.series) + 4;
    const x = (i: number) => pad + (i * (w - pad * 2)) / (f.series.length - 1);
    const y = (v: number) => h - 12 - ((v - min) / (max - min)) * (h - 24);
    return <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${f.cat} trend over the last 12 weeks`}>
      <polyline points={f.series.map((v, i) => `${x(i)},${y(v)}`).join(" ")} fill="none" stroke="var(--red)" strokeWidth="2.5" />
      {f.series.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={i === f.series.length - 1 ? 4 : 2.5} fill="var(--red)" />)}
    </svg>;
  }
  const max = Math.max(...f.series), bw = (w - pad * 2) / f.series.length;
  return <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${f.cat} by group`}>
    {f.series.map((v, i) => { const bh = (v / max) * (h - 30); return <g key={i}>
      <rect x={pad + i * bw + 4} y={h - 18 - bh} width={bw - 8} height={bh} rx="2" fill={i === 0 ? "var(--red)" : "var(--steel)"} />
      <text x={pad + i * bw + bw / 2} y={h - 5} textAnchor="middle" fontSize="8" fill="var(--ink-2)">{f.labels?.[i]}</text>
    </g>; })}
  </svg>;
}

export default function ThisWeek() {
  const f = siteFacts();
  const real = featuredFindings(FEATURED);
  const article = {
    "@context": "https://schema.org", "@type": "Article",
    headline: "This Week in US Consumer Data — " + f.latestLabel,
    datePublished: f.latestDate, dateModified: f.latestDate,
    author: { "@id": SITE + "/#org" }, publisher: { "@id": SITE + "/#org" },
    about: ["US consumer spending", "Retail consumer trends", "Consumer sentiment"],
    isPartOf: { "@type": "DataCatalog", name: "Coresight Consumer Insight Portal", url: SITE + "/data/" },
    url: SITE + "/this-week/", image: SITE + "/og.png",
  };
  return <article className="wrap prose data-page">
    <Breadcrumbs items={[["Home", "/"], ["This week", "/this-week/"]]} />
    <p className="eyebrow">This week in US consumer data</p>
    <h1>What US consumers did this week</h1>
    <p className="lede">A weekly read on the US consumer from Coresight&apos;s ongoing survey — spending intentions, category spend, shopping channel and generational shifts, updated every week from the latest wave. <time dateTime={f.latestDate}>{f.latestLabel}</time>, drawn from {f.waves} waves and {f.responses.toLocaleString()} responses since December 2020.</p>
    {real.length === 0 &&
      <p className="preview-note" role="note">Illustrative preview. Real weekly figures publish once questions are cleared for release; the full breakdowns are in the <Link href="/data/">portal dataset</Link>.</p>}

    <div className="week-grid">
      {real.length > 0
        ? real.map((r) => <section className="week-card reveal" key={r.cat}>
            <p className="week-cat">{r.cat}</p>
            <h2>{r.head}</h2>
            <p className="week-big"><b>{r.val}%</b> answered &ldquo;{r.row}&rdquo;</p>
            {r.delta != null && <p className={`week-delta ${r.delta > 0 ? "sig" : ""}`}>{r.delta > 0 ? "▲ " : r.delta < 0 ? "▼ " : ""}{Math.abs(r.delta)} pts vs prior wave</p>}
            <p className="week-src">Source: Coresight Consumer Insight Portal · {f.latestLabel}</p>
          </section>)
        : SAMPLE.map((s) => <section className="week-card reveal" key={s.cat}>
            <p className="week-cat">{s.cat}</p>
            <h2>{s.head}</h2>
            <p className={`week-delta ${s.sig ? "sig" : ""}`}>{s.delta}{s.sig ? " · significant" : ""}</p>
            <Chart f={s} />
            <p className="week-src">Illustrative · Source: Coresight Consumer Insight Portal</p>
          </section>)}
    </div>

    <h2>Read the full week</h2>
    <p>These are the headline moves. The portal holds every question behind them — by generation, gender, income and region, with significance tested against the prior wave and the same week last year. See how the weekly tracker is built on the <Link href="/data/">consumer data page</Link> and the <Link href="/methodology/">methodology</Link>, or <Link href="/sign-in/">request access</Link> to explore every figure.</p>

    <p className="data-cta"><Link className="btn primary" href="/sign-in/">Request access to the full data</Link></p>
    <Jsonld data={article} />
  </article>;
}
