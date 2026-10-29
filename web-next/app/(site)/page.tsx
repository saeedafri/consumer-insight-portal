import Link from "next/link";
import { NAME, SITE } from "../site";
import { siteFacts } from "./pipeline";

export const metadata = {
  title: { absolute: "Weekly US Consumer Survey Data & Retail Trends | Coresight Consumer Insight Portal" },
  alternates: { canonical: "/" },
};

const schema = {
  "@context": "https://schema.org", "@type": "WebApplication",
  name: NAME, url: SITE, applicationCategory: "BusinessApplication", operatingSystem: "Web",
  publisher: { "@id": SITE + "/#org" },
  description: "Explore Coresight Research's weekly US consumer survey data by question, demographic and wave: spending, shopping behavior and sentiment across retail categories.",
};

const FEATURES = [
  ["Question explorer", "Any question by generation, gender, income and region — with significance against the previous wave."],
  ["Trends", "Follow a question across every wave it was asked, with year-on-year comparison."],
  ["Cross-tabs", "One question by two cuts at once, for a single week or the last four pooled."],
  ["Audience index", "Pick a group like Gen Z shoppers and see where they over- and under-index."],
  ["Ask CIP", "Ask in plain words. Answers come only from published figures, every source cited."],
  ["Boards & exports", "Pin charts, download decks to PowerPoint, tables to CSV and Excel."],
];

const DEFEND = [
  ["Unweighted by default", "Census-weighting toggle available; significance always tested on unweighted counts."],
  ["Reconciled every wave", "Each wave is checked against the survey platform before it's marked verified."],
  ["Small bases flagged", "Groups under 50 are clearly marked — nothing is hidden."],
  ["Versioned questions", "A reworded question is a new version. Trends never join two versions."],
];

const CAN = ["Explore every question", "Compare every wave", "Track every trend", "Ask in plain English"];

// Illustrative sample highlights, shown in the slider.
const INSIGHTS = [
  ["Spending", "61% of Gen Z plan to cut non-essential spending — ▲ 3 pts"],
  ["Grocery", "Still the category shoppers won't trim, 8 waves running"],
  ["Back to school", "Millennials lift category spend, ▲ 5 pts year on year"],
  ["Holiday", "Purchase intent ticks up across every income band"],
  ["Value", "Private label keeps gaining share with Boomers"],
  ["AI tools", "Curiosity rising fastest among 18–29s"],
];

const BARS = [41, 44, 46, 45, 48, 50, 49, 52, 54, 53, 56, 59];

export default function Home() {
  const f = siteFacts();
  const w = 440, h = 150, pad = 8, bw = (w - pad * 2) / BARS.length;
  const y = (v: number) => h - 10 - ((v - 35) / 30) * (h - 30);
  const line = BARS.map((v, i) => `${pad + bw * i + bw / 2},${y(v)}`).join(" ");
  const insightCard = ([k, t]: string[], i: number) => <div className="insight" key={k + i}><b>{k}</b><p>{t}</p></div>;
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />
    <div className="wrap hero">
      <div>
        <p className="eyebrow">Weekly US consumer tracker</p>
        <h1>Know what consumers did this week — not last quarter.</h1>
        <p className="lede">Every wave of our US consumer survey since December 2020, ready to explore by audience, compare over time and test for significance in seconds.</p>
        <p className="kw">Weekly US consumer survey data and retail trends — spending, shopping behavior and sentiment, cut by generation, income and region.</p>
        <div className="actions">
          <Link className="btn primary" href="/sign-in/">Request access</Link>
          <Link className="btn" href="/features/">See what&apos;s inside</Link>
        </div>
      </div>
      <div className="preview parallax" aria-label="Example tracker chart">
        <div className="phead"><span>Weekly tracker · preview</span><span>Last 12 waves</span></div>
        <div className="q"><span>Plan to cut back on non-essential spending</span><span aria-hidden="true">▾</span></div>
        <div className="pills"><span className="on">Total</span><span>Gen Z</span><span>Millennials</span><span>Gen X</span><span>Boomers</span></div>
        <div className="big"><b>59%</b><span className="wk">Week 12</span><span className="sig">▲ 3 pts vs prior wave · significant</span></div>
        <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Rising trend over the last 12 waves, sample data">
          {BARS.map((v, i) => <rect key={i} x={pad + bw * i + 3} y={y(v)} width={bw - 6} height={h - 10 - y(v)} rx="2" fill="var(--steel)" />)}
          <polyline points={line} fill="none" stroke="var(--red)" strokeWidth="2.5" />
          {BARS.map((v, i) => <circle key={i} cx={pad + bw * i + bw / 2} cy={y(v)} r="3" fill="var(--red)" />)}
        </svg>
        <p className="cap">Sample data for illustration. Unweighted; base n≈500 per wave.</p>
      </div>
    </div>

    <section className="stats"><div className="wrap inner">
      <div className="stat reveal"><b>{f.waves}</b><span>survey waves</span></div>
      <div className="stat reveal d1"><b>{Math.floor(f.responses / 1000).toLocaleString()},000+</b><span>consumer responses</span></div>
      <div className="stat reveal d2"><b>Weekly</b><span>since Dec 2020</span></div>
      <div className="stat reveal d3"><b>~2 ms</b><span>p95 screen load</span></div>
    </div></section>

    <section className="wrap section">
      <h2 className="roll"><span>From question to answer in one place</span></h2>
      <p className="sub reveal">Search in plain English, slice by any audience, and share what moved. See the <a href="/data/">weekly consumer dataset</a>.</p>
      <div className="grid3">
        {FEATURES.map(([t, d], i) => <div className={`cell reveal d${(i % 3) || ""}`} key={t}><h3>{t}</h3><p>{d}</p></div>)}
      </div>
    </section>

    <section className="wrap section" style={{ paddingTop: 0 }}>
      <div className="insights-col">
        <div>
          <p className="eyebrow">In the data this week</p>
          <p className="sub reveal" style={{marginBottom:18}}>Fresh highlights every week — see <a href="/this-week/">this week in US consumer data</a>.</p>
          <div className="roll-list">
            {CAN.map((c) => <div className="roll-item" key={c}>{c}</div>)}
          </div>
          <p className="insights-note">Illustrative sample highlights.</p>
        </div>
        <div className="insights-wrap reveal" aria-hidden="true">
          <div className="insights-track">
            {INSIGHTS.map(insightCard)}
            {INSIGHTS.map((x, i) => insightCard(x, i + 100))}
          </div>
        </div>
      </div>
    </section>

    <section className="dark"><div className="wrap inner">
      <h2 className="roll"><span>Numbers you can defend</span></h2>
      <div className="defend">
        {DEFEND.map(([t, d], i) => <div className={`col reveal d${(i % 3) || ""}`} key={t}><h3>{t}</h3><p>{d}</p></div>)}
      </div>
    </div></section>

    <section className="wrap section api" id="api">
      <div className="reveal">
        <h2 className="roll"><span>Plug the data into your tools</span></h2>
        <p>API keys give programmatic access to the same figures. The MCP connector lets AI assistants query the portal directly — with the same entitlements and audit log.</p>
      </div>
      <pre className="code parallax reveal d1"><span className="mut">GET</span> /api/trends?question=Q12&amp;cut=generation{"\n"}<span className="k">Authorization</span>: Bearer cip_live_••••{"\n"}{"\n"}{"{ "}<span className="s">&quot;wave&quot;</span>: 372, <span className="s">&quot;gen_z&quot;</span>: 0.61, <span className="s">&quot;sig&quot;</span>: true{" }"}</pre>
    </section>

    <section className="cta"><div className="wrap inner">
      <h2 className="roll"><span>See this week&apos;s wave for yourself.</span></h2>
      <Link className="btn primary reveal d1" href="/sign-in/">Sign in with your work account</Link>
    </div></section>
  </>;
}
