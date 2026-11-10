// Home (/app/, the first page after sign-in; the Survey library moved to /app/library): "What would you like to
// understand?" A question box that hands off to Ask Coresight (screens/Ask.tsx answers it on arrival), cards for the main
// research areas, this week's in-store and online buying from the newest weekly survey, and a way into the cross-tabs.
// Everything comes from files the ETL already publishes (the waves list, the newest wave's book): nothing is computed
// on the server when the page opens. Cards and the box show only what this person's package includes (config/access.yml).
import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowRight, Cpu, Gauge, Layers, MessageSquareText, ShoppingBag, Store, Table2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { allowed, useBook, useMe, useReportWaves, useWaves } from "../api";
import type { Book } from "../api";
import { Delta } from "../components/Glance";
import { Failure, SkeletonScreen } from "../components/bits";
import { fmtDate } from "../stats";

const EXAMPLES = ["How worried are people about tariffs?", "Are consumers using GenAI to shop?", "What share started holiday shopping?"];
// this week's buying, from the weekly questions q2 (in a store) and q3 (online), matched by the answer's first words
const THEMES: [string, string, string][] = [["Groceries in store", "q2", "Food or beverages"], ["Groceries online", "q3", "Food or beverages"],
                                           ["Clothing in store", "q2", "Clothing, footwear"], ["Clothing online", "q3", "Clothing, footwear"]];

/** A research area: its icon, what it is for, and where it opens. */
function Area({ icon: Glyph, title, to, children }: { icon: LucideIcon; title: string; to: string; children: ReactNode }) {
  return <Link className="card area-card" to={to}>
    <span className="area-icon" aria-hidden="true"><Glyph size={18} strokeWidth={1.8} /></span>
    <h3>{title}</h3>
    <p>{children}</p>
    <span className="area-go">Open <ArrowRight size={13} aria-hidden="true" /></span>
  </Link>;
}

export default function Home() {
  const me = useMe().data;
  const { data: waves, isLoading, error } = useWaves();
  const reports = useReportWaves().data;
  const navigate = useNavigate();
  const [text, setText] = useState("");
  if (isLoading) return <SkeletonScreen kind="page" />;
  if (error || !waves) return <Failure error={error} />;
  const tracker = waves.filter(w => w.survey_family === "CSI-US" && w.study_type === "tracker" && w.rows_built !== 0);   // newest first
  const latest = tracker[0];
  const genai = tracker.find(w => w.modules?.includes("GenAI"));
  const report = reports?.length ? Math.max(...reports) : null;
  const since = waves.length ? waves.at(-1)!.wave_date.slice(0, 4) : "";
  const ask = (question: string) => question.trim().length >= 3 && navigate(`/ask?q=${encodeURIComponent(question.trim())}`);
  return <div className="stack home">
    <div className="page-head"><div>
      <h1>What would you like to understand?</h1>
      <p className="lede">Find answers across {waves.length.toLocaleString("en-US")} surveys, with research going back to {since}.</p>
    </div>
      {latest && <Link className="chip sig latest-pill" to={`/w/${latest.survey_id}`}><span aria-hidden="true">●</span> Latest wave: {fmtDate(latest.wave_date)}</Link>}
    </div>

    {allowed(me, "ask") && <section className="ask-hero" aria-labelledby="ask-hero">
      <h2 id="ask-hero">Ask Coresight</h2>
      <p>Ask a research question in your own words; the answer cites the survey questions and figures it comes from.</p>
      <form className="ask-box" onSubmit={e => { e.preventDefault(); ask(text); }}>
        <MessageSquareText size={17} strokeWidth={1.8} aria-hidden="true" />
        <label className="sr-only" htmlFor="home-ask">Your question</label>
        <input id="home-ask" value={text} onChange={e => setText(e.target.value)} placeholder="e.g. How are consumers feeling about inflation?" />
        <button className="btn primary" disabled={text.trim().length < 3}>Ask <ArrowRight size={15} aria-hidden="true" /></button>
      </form>
      <div className="try"><span>Try asking</span>{EXAMPLES.map(q => <button key={q} type="button" onClick={() => ask(q)}>{q}</button>)}</div>
    </section>}

    <section aria-labelledby="areas">
      <h2 className="report-section" id="areas">Explore key research</h2>
      <div className="grid g3">
        {latest && <Area icon={ShoppingBag} title="Shopping & Spending Survey" to={`/w/${latest.survey_id}`}>Where people shop, what they buy and how spending changes, every week.</Area>}
        {genai && <Area icon={Cpu} title="GenAI Survey" to="/trackers/genai">How people use generative AI in their lives and when they shop ({fmtDate(genai.wave_date)}).</Area>}
        {latest && allowed(me, "explorer") && <Area icon={Layers} title="In store vs online" to="/channels">Which categories people bought in a store, and which online, in the past two weeks.</Area>}
        {report && allowed(me, "report") && <Area icon={Gauge} title="Consumer sentiment & outlook" to={`/w/${report}/report`}>Personal finances and the economy over the next 12 months, by household income.</Area>}
        {allowed(me, "retailers") && <Area icon={Store} title="Retailer comparison" to="/retailers">Two retailers side by side: reach, who their shoppers are, and how people feel about them.</Area>}
        {allowed(me, "sectors") && <Area icon={Table2} title="Sector databank" to="/sectors">Who bought in each retail sector, and where, in every survey that asked.</Area>}
      </div>
    </section>

    {latest && <WeeklyThemes id={latest.survey_id} />}

    {latest && allowed(me, "crosstab") && <section className="card dig-deeper">
      <div><h2>Need to dig deeper?</h2><p className="muted">Open the cross-tabs to compare any answer by gender, generation, income and more.</p></div>
      <Link className="btn primary" to={`/w/${latest.survey_id}/crosstab`}>Open cross-tabs <ArrowRight size={15} aria-hidden="true" /></Link>
    </section>}
  </div>;
}

/** This week's buying in store and online: four figures from the newest weekly survey, each with its change vs last week. */
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
  return <section aria-labelledby="themes">
    <h2 className="report-section" id="themes">This week's shopping channels</h2>
    <p className="muted section-note">Bought in a store or online in the past two weeks · weekly survey of {fmtDate(book.wave.wave_date)} · n={base?.toLocaleString("en-US")}</p>
    <div className="grid g4">
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
  </section>;
}
