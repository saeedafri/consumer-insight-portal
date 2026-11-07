// The public home page (/): what the portal is, read like the front page of the weekly report. Every figure on it
// is real and built when the site is built (pipeline.ts reads the published files): the latest wave, its size and
// topics, and a calendar of the weeks the tracker was fielded. No survey answer appears here: those stay behind
// sign-in until a finding is cleared for public release (this-week/page.tsx FEATURED).
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

// What a subscriber opens, in the order they meet it: the screens of the portal.
const INSIDE = [
  ["Weekly report", "The US Consumer Survey Insights report for any week: 13-week tables, sentiment by income, three data points to watch."],
  ["Question explorer", "Every question of every wave, by gender, generation, income and region, tested against the previous wave."],
  ["Trends", "One question across every wave that asked it, four-week averages and the margin of error drawn in."],
  ["Cross-tabs", "A question by two cuts at once, for one week or the last four pooled."],
  ["Sector databank", "Thirteen retail sectors since 2022: who bought, and from which retailers, brands and categories."],
  ["Expected vs actual", "What shoppers planned before Halloween, Black Friday or Prime Day, against what they did afterwards."],
  ["Audiences", "Build a group such as Gen Z grocery shoppers and see where it over- and under-indexes."],
  ["Exports and boards", "Every table to Excel, CSV or PowerPoint; pin charts to a board your team shares."],
];

const DEFEND = [
  ["Unweighted by default", "Census weighting is one click away; significance is always tested on the unweighted counts."],
  ["Reconciled every wave", "Each wave is checked answer by answer against the survey platform before it is marked verified."],
  ["Small bases flagged", "A group of fewer than 50 respondents is marked, never hidden and never coloured as a change."],
  ["Versioned questions", "A reworded question is a new version. A trend never joins two versions."],
];


const longDate = (iso: string) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });

const DAY = 86_400_000;

/** Every week from the tracker's first wave to its latest, one row per year, each week marked when a tracker wave was
 *  fielded within it (a wave fielded off its Monday still counts for that week). */
function fieldedYears(dates: string[], first: string, latest: string) {
  const asked = dates.map((d) => Date.parse(d + "T00:00:00Z"));
  const years: { year: string; weeks: { day: string; fielded: boolean }[] }[] = [];
  for (let monday = Date.parse(first + "T00:00:00Z"); monday <= Date.parse(latest + "T00:00:00Z"); monday += 7 * DAY) {
    const day = new Date(monday).toISOString().slice(0, 10);
    const week = { day, fielded: asked.some((t) => t >= monday - 3 * DAY && t < monday + 4 * DAY) };
    const year = day.slice(0, 4);
    if (years.at(-1)?.year === year) years.at(-1)!.weeks.push(week); else years.push({ year, weeks: [week] });
  }
  return years;
}

export default function Home() {
  const f = siteFacts();
  const years = fieldedYears(f.trackerDates, f.firstTracker, f.latestDate);
  const all = years.flatMap((y) => y.weeks);
  const fielded = all.filter((w) => w.fielded).length;
  const thousands = Math.floor(f.responses / 1000).toLocaleString("en-US");
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />
    <div className="wrap front">
      <div className="front-copy">
        <h1>Know what US consumers did this week.</h1>
        <p className="lede">Every week about 400 US adults answer Coresight Research&apos;s consumer survey. The portal holds every
          wave since {longDate(f.firstTracker).replace(/ \d+,/, "")}, ready to cut by audience, compare over time and test for
          significance, the morning the wave closes.</p>
        <div className="actions">
          <Link className="btn primary" href="/sign-in/">Request access</Link>
          <Link className="btn" href="/features/">See what&apos;s inside</Link>
        </div>
      </div>

      <aside className="ledger" aria-labelledby="latest">
        <h2 id="latest">{f.latestLabel}</h2>
        <dl className="ledger-facts">
          <div><dt>Respondents</dt><dd>{f.latestN.toLocaleString("en-US")} US adults 18+</dd></div>
          <div><dt>Questions</dt><dd>{f.questions}</dd></div>
        </dl>
        {f.latestTopics.length > 0 && <ul className="topics" aria-label="Topics this week">
          {f.latestTopics.map((t) => <li key={t}>{t}</li>)}
        </ul>}
        <figure className="calendar">
          <div className="years" role="img" aria-label={`A survey wave in ${fielded} of the ${all.length} weeks since ${longDate(f.firstTracker)}`}>
            {years.map((y) => <div className="year" key={y.year}><span className="year-label">{y.year}</span><div className="weeks">
              {y.weeks.map((w) => <i key={w.day} className={w.fielded ? "on" : undefined} title={`Week of ${longDate(w.day)}${w.fielded ? "" : ": no wave"}`} />)}
            </div></div>)}
          </div>
          <figcaption>A wave in {fielded} of the {all.length} weeks since {longDate(f.firstTracker)}: one row a year, one square a week, this week in red.</figcaption>
        </figure>
      </aside>
    </div>

    <div className="wrap">
      <dl className="facts">
        <div><dt>Survey waves</dt><dd>{f.waves.toLocaleString("en-US")}</dd></div>
        <div><dt>Qualified responses</dt><dd>{thousands},000+</dd></div>
        <div><dt>Weekly tracker waves</dt><dd>{f.trackers.toLocaleString("en-US")}</dd></div>
        <div><dt>Annual and ad hoc studies</dt><dd>{f.annual + f.adhoc}</dd></div>
      </dl>
    </div>

    <section className="wrap section inside" aria-labelledby="inside">
      <div className="inside-head">
        <h2 id="inside">From question to answer in one place</h2>
        <p>Search in plain English, slice by any audience, and share what moved. More on the <a href="/data/">weekly consumer dataset</a>.</p>
      </div>
      <dl className="inside-list">
        {INSIDE.map(([t, d]) => <div key={t} className="reveal"><dt>{t}</dt><dd>{d}</dd></div>)}
      </dl>
    </section>

    <section className="dark" aria-labelledby="defend"><div className="wrap inner">
      <h2 id="defend">Numbers you can defend</h2>
      <div className="defend">
        {DEFEND.map(([t, d]) => <div className="col" key={t}><h3>{t}</h3><p>{d}</p></div>)}
      </div>
    </div></section>

    <section className="wrap section api" id="api" aria-labelledby="api-title">
      <div>
        <h2 id="api-title">Plug the data into your tools</h2>
        <p>A personal API key reads the same figures as the screens. The MCP connector lets an AI assistant query the portal
          directly, with your entitlements and in the audit log.</p>
      </div>
      <pre className="code" aria-label="Example request for one question across every wave"><span className="mut">GET</span> /api/v1/questions/CSI-US/tracker/q4{"\n"}<span className="k">Authorization</span>: Bearer {"<your key>"}{"\n"}{"\n"}{"{ "}<span className="s">&quot;qcode&quot;</span>: <span className="s">&quot;q4&quot;</span>, <span className="s">&quot;waves&quot;</span>: [[{f.latestId || 532}, <span className="s">&quot;{f.latestDate}&quot;</span>, …]], …{" }"}</pre>
    </section>

    <section className="cta" aria-labelledby="cta"><div className="wrap inner">
      <h2 id="cta">See this week&apos;s wave for yourself.</h2>
      <Link className="btn primary" href="/sign-in/">Sign in with your work account</Link>
    </div></section>
  </>;
}
