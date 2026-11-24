// Home (/app/, the first page after sign-in; the Survey library moved to /app/library): "What would you like to
// understand?" A question box that hands off to Ask CIP (screens/Ask.tsx answers it on arrival), then "This week at a
// glance", always open so Home never looks empty: six cards from the newest weekly survey, picked by the ETL
// (etl/glance.py → api/v1/glance; the research team's layout of 23 Nov 2026), then sections that
// open on a click, all closed on every visit (16 Nov 2026): the research areas, filtered by how often each runs; this
// week's grocery buying in store and online from the newest weekly survey; a way into the cross-tabs; the latest wave.
// Everything comes from files the ETL already publishes (the waves list, the newest wave's book): nothing is computed
// on the server when the page opens. Cards and the box show only what this person's package includes (config/access.yml).
import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowRight, CalendarDays, ChevronDown, Cpu, Fuel, Gauge, Gift, Globe, Layers, MessageSquareText, Percent, Pill, Share2,
  ShoppingBag, Store, Table2, Wallet } from "lucide-react";
import MicButton from "../components/MicButton";
import type { LucideIcon } from "lucide-react";
import { allowed, useBook, useGlance, useMe, useReportWaves, useWaves } from "../api";
import type { Book } from "../api";
import { Delta, FigureCard } from "../components/Glance";
import { Failure, SkeletonScreen } from "../components/bits";
import { fmtDate } from "../stats";
import { dashboardFeature } from "../trackers";

const EXAMPLES = ["How worried are people about tariffs?", "Are consumers using GenAI to shop?", "What share started holiday shopping?"];
// this week's grocery buying, from the weekly questions q2 (in a store) and q3 (online), matched by the answer's first words
const THEMES: [string, string, string][] = [["Groceries in store", "q2", "Food or beverages"], ["Groceries online", "q3", "Food or beverages"]];
const RUNS = ["Weekly", "Monthly", "Quarterly", "Seasonal"] as const;
type Runs = typeof RUNS[number];
// The topic trackers on Home, with how often each runs, measured from the waves that carry each (median gap, 16 Nov
// 2026): tariffs, financial health and GLP-1 every 28 days; gas prices weekly (Apr to Aug 2026); social commerce every
// 84 days with its sector; the holiday two through the season only. GenAI has its own card above them.
const TRACKER_CARDS: [string, string, Runs, LucideIcon, string][] = [
  ["tariffs_inflation", "Tariffs & inflation", "Monthly", Percent, "How worried people are about tariffs and prices, and what they change because of them."],
  ["financial_health", "Financial health", "Monthly", Wallet, "How people feel about their own finances: saving, debt and making ends meet."],
  ["glp1", "GLP-1 impact", "Monthly", Pill, "Who takes GLP-1 drugs, and how they change what people eat and buy."],
  ["mideast_gas", "Gas prices & geopolitics", "Weekly", Fuel, "How gas prices and the Middle East conflict change spending and travel."],
  ["social_commerce", "Social commerce", "Quarterly", Share2, "Buying on social media: which platforms, what and how often."],
  ["holiday_tracker", "Holiday shopping tracker", "Seasonal", Gift, "Where people are with their holiday shopping, week by week through the season."],
  ["holiday_outlook", "Holiday outlook", "Seasonal", CalendarDays, "What people expect to spend this holiday season, and where."],
];

/** A research area: its icon, what it is for, how often it runs, and where it opens. */
function Area({ icon: Glyph, title, to, runs, children }: { icon: LucideIcon; title: string; to: string; runs: Runs; children: ReactNode }) {
  return <Link className="card area-card" to={to}>
    <span className="area-icon" aria-hidden="true"><Glyph size={18} strokeWidth={1.8} /></span>
    <h3>{title}</h3>
    <p>{children}</p>
    <span className="area-go">{runs} · Open <ArrowRight size={13} aria-hidden="true" /></span>
  </Link>;
}

/** A section that opens on a click: native <details>, closed on every visit, its title and a chevron to show it opens. */
function Fold({ title, children }: { title: string; children: ReactNode }) {
  return <details className="home-fold">
    <summary><h2 className="report-section">{title}</h2><ChevronDown size={18} className="fold-icon" aria-hidden="true" /></summary>
    <div className="fold-body">{children}</div>
  </details>;
}

export default function Home() {
  const me = useMe().data;
  const { data: waves, isLoading, error } = useWaves();
  const reports = useReportWaves().data;
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [runs, setRuns] = useState<Runs | "All">("All");
  if (isLoading) return <SkeletonScreen kind="page" />;
  if (error || !waves) return <Failure error={error} />;
  const tracker = waves.filter(w => w.survey_family === "CSI-US" && w.study_type === "tracker" && w.rows_built !== 0);   // newest first
  const latest = tracker[0];
  const genai = tracker.find(w => w.modules?.includes("GenAI"));
  const china = waves.find(w => w.survey_family === "CSI-CN" && w.rows_built !== 0);
  const report = reports?.length ? Math.max(...reports) : null;
  const ask = (question: string) => question.trim().length >= 3 && navigate(`/ask?q=${encodeURIComponent(question.trim())}`);
  // [shown to this person, how often it runs, icon, title, where it opens, what it is for]
  const areas = ([
    [!!latest, "Weekly", ShoppingBag, "Shopping & Spending Survey", `/w/${latest?.survey_id}`, "Where people shop, what they buy and how spending changes, every week."],
    [!!latest && allowed(me, "explorer"), "Weekly", Layers, "In store vs online", "/channels", "Which categories people bought in a store, and which online, in the past two weeks."],
    [!!report && allowed(me, "report"), "Weekly", Gauge, "Consumer sentiment & outlook", `/w/${report}/report`, "Personal finances and the economy over the next 12 months, by household income."],
    [allowed(me, "retailers"), "Weekly", Store, "Retailer databank", "/retailers", "Any retailer or sector, alone or side by side, over the weeks you choose: how many shop there and who they are."],
    [!!china && allowed(me, "china_tracker"), "Weekly", Globe, "China weekly tracker", `/w/${china?.survey_id}`, "A weekly survey of consumers in China: how they shop and spend."],
    [!!genai, "Monthly", Cpu, "GenAI Survey", "/trackers/genai", `How people use generative AI in their lives and when they shop${genai ? ` (${fmtDate(genai.wave_date)})` : ""}.`],
    ...TRACKER_CARDS.map(([code, title, every, icon, about]) =>
      [allowed(me, dashboardFeature(code)) && waves.some(w => w.dashboards?.includes(code)), every, icon, title, `/trackers/${code}`, about]),
    [allowed(me, "sectors"), "Quarterly", Table2, "Sector databank", "/sectors", "Who bought in each retail sector, and where: each sector is asked every 12 weeks."],
  ] as [boolean, Runs, LucideIcon, string, string, string][]).filter(([shown]) => shown)
    .sort((x, y) => RUNS.indexOf(x[1]) - RUNS.indexOf(y[1]));   // weekly first, as the filter reads
  const offered = RUNS.filter(r => areas.some(([, every]) => every === r));
  return <div className="stack home">
    <section className="ask-hero" aria-labelledby="home-title">
      <h1 id="home-title">What would you like to understand?</h1>
      {allowed(me, "ask") && <>
        <p>Ask a question in your own words.</p>
        <form className="ask-box" onSubmit={e => { e.preventDefault(); ask(text); }}>
          <MessageSquareText size={17} strokeWidth={1.8} aria-hidden="true" />
          <label className="sr-only" htmlFor="home-ask">Your question</label>
          <input id="home-ask" value={text} onChange={e => setText(e.target.value)} placeholder="e.g. How are consumers feeling about inflation?" />
          <MicButton text={text} setText={setText} />
          <button className="btn primary" disabled={text.trim().length < 3}>Ask <ArrowRight size={15} aria-hidden="true" /></button>
        </form>
        <div className="try"><span>Try asking</span>{EXAMPLES.map(q => <button key={q} type="button" onClick={() => ask(q)}>{q}</button>)}</div>
      </>}
    </section>

    {latest && allowed(me, "us_tracker") && <ThisWeek />}

    {areas.length > 0 && <Fold title="Explore key research">
      <div className="runs-filter"><span>Show research that runs</span>
        <div className="seg small" role="group" aria-label="How often the research runs">
          {(["All", ...offered] as const).map(r => <button key={r} aria-pressed={runs === r} onClick={() => setRuns(r)}>{r}</button>)}
        </div>
      </div>
      <div className="grid g3">{areas.filter(([, every]) => runs === "All" || every === runs).map(([, every, icon, title, to, about]) =>
        <Area key={title} icon={icon} title={title} to={to} runs={every}>{about}</Area>)}</div>
    </Fold>}

    {latest && <WeeklyThemes id={latest.survey_id} />}

    {latest && allowed(me, "crosstab") && <Fold title="Need to dig deeper?">
      <section className="card dig-deeper">
        <div><p className="muted">Open the cross-tabs to compare any answer by gender, generation, income and more.</p></div>
        <Link className="btn primary" to={`/w/${latest.survey_id}/crosstab`}>Open cross-tabs <ArrowRight size={15} aria-hidden="true" /></Link>
      </section>
    </Fold>}

    {latest && <Link className="chip sig latest-pill" to={`/w/${latest.survey_id}`}><span aria-hidden="true">●</span> Latest wave: {fmtDate(latest.wave_date)}{latest.qualified_n ? ` · ${latest.qualified_n.toLocaleString("en-US")} adults` : ""}</Link>}
  </div>;
}

/** "This week at a glance": the ETL's six cards in their two rows of three (a card the week lacks leaves a gap, so each
 *  row keeps its subject); a card links on only when this person has its screen. */
function ThisWeek() {
  const me = useMe().data;
  const { data } = useGlance();
  if (!data?.cards.some(Boolean)) return null;
  return <section aria-labelledby="glance-title">
    <h2 id="glance-title" className="report-section">This week at a glance</h2>
    <p className="muted section-note">Weekly survey of {fmtDate(data.wave_date)} · {data.respondents.toLocaleString("en-US")} US adults
      {data.sector ? ` · this week's sector: ${data.sector}` : ""}</p>
    {[data.cards.slice(0, 3), data.cards.slice(3)].map((row, r) => <div key={r} className="grid g3 glance-row">{row.map((c, i) => c &&
      <FigureCard key={c.title} {...c} lead={i === 0} to={allowed(me, c.feature) ? c.link : undefined} />)}</div>)}
  </section>;
}

/** This week's grocery buying in store and online: two figures from the newest weekly survey, each with its change vs last week. */
function WeeklyThemes({ id }: { id: number }) {
  const { data: book } = useBook(id);
  if (!book) return null;
  const find = (code: string, start: string) => {
    const q = book.questions.find((x: Book["questions"][number]) => x.id === code);
    const row = q?.groups[0].rows.find(r => r.label.startsWith(start));
    return q && row ? { q, row } : null;
  };
  const shown = THEMES.map(([title, code, start]) => ({ title, hit: find(code, start) })).filter(t => t.hit);
  if (!shown.length) return null;
  const base = shown[0].hit!.q.groups[0].bases.Total;
  return <Fold title="This week's grocery shopping">
    <p className="muted section-note">Bought food or beverages in a store or online in the past two weeks · weekly survey of {fmtDate(book.wave.wave_date)} · n={base?.toLocaleString("en-US")}</p>
    <div className="grid g2">
      {shown.map(({ title, hit }, i) => {
        const { q, row } = hit!;
        return <Link key={title} className={`card kpi ${i === 0 ? "lead" : ""}`} to={`/w/${id}/questions/${q.id}`}>
          <div className="k-label">{title}</div>
          <div className="k-value">{row.Total == null ? "–" : `${row.Total.toFixed(1)}%`}</div>
          <div className="k-note"><Delta d={row.Total != null && row.prior != null && !row.flags.includes("wording_changed_prior") ? row.Total - row.prior : null}
                                         label="vs last week" flags={row.flags.split(/[\s,;|]+/)} /></div>
        </Link>;
      })}
    </div>
  </Fold>;
}
