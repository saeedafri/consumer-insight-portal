// Ask Coresight (/app/ask): a question in plain words, answered from the portal's own published survey figures with
// the chart that fits (api/assistant.py, no database). Each question is asked twice: quick (the nearest survey question
// by meaning, ~100 ms) is shown at once; when it says check, the AI model's reading follows and replaces it only if it
// found a differently worded question (the same wording asked by another study is the same answer). A conversation: each answer appears right under the box, newest first, with its headline
// figure, the points, the chart (line, bars, columns, donut or table, as the figures allow), notes, its source and
// every figure. A question it cannot place shows the closest survey questions instead of a guess.
import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { send, useMe } from "../api";
import type { Answer, AskChart } from "../api";
import EChart, { downloadPng } from "../components/EChart";
import type { Chart } from "../components/EChart";
import { ExportButtons } from "../components/bits";
import { downloadTable } from "../csv";
import { useWeighted } from "../weight";
import { ArrowRight, MessageSquare } from "lucide-react";

const EXAMPLES = ["What share bought from Amazon in all waves?", "GenAI use for shopping, monthly", "Holiday shopping progress by generation",
                  "Economy better or worse, every 4 weeks", "Compare the first and latest wave of holiday shopping progress",
                  "Top beauty retailers", "How worried are people about tariffs?", "Top food retailers, last 8 weeks"];
const FIGURE = /([+−-]?\d[\d,]*(?:\.\d+)?%|[+−-]\d+(?:\.\d+)? pts|\d[\d,]* of [\d,]+ respondents)/g;

/** A sentence with its figures in bold, the way an analyst scans it. */
const Bold = ({ text }: { text: string }) =>
  <>{text.split(FIGURE).map((part, i) => i % 2 ? <b key={i}>{part}</b> : <Fragment key={i}>{part}</Fragment>)}</>;

type View = "line" | "bar" | "column" | "donut" | "table";
const VIEW_NAMES: Record<View, string> = { line: "Line", bar: "Bars", column: "Columns", donut: "Donut", table: "Table" };

/** The ways an answer's figures can be drawn: over time a line or columns; one period bars or columns, and a donut
 *  when its answers add up to 100% (a single choice); always a table. The server's choice first. */
function views(chart: AskChart): View[] {
  if (chart.type === "line") return ["line", "column", "table"];
  const total = chart.series.length === 1 ? chart.series[0].data.reduce<number>((t, v) => t + (v ?? 0), 0) : 0;
  return [...(chart.type === "donut" ? ["donut"] as View[] : []), "bar", "column", ...(chart.type !== "donut" && Math.abs(total - 100) <= 1.5 ? ["donut"] as View[] : []), "table"];
}

/** The ECharts option for an Ask chart drawn as `view`: lines over time, horizontal bars (long answer names stay
 *  readable), columns, or a donut for a single choice that adds up to 100%. */
function option(chart: AskChart, view: View) {
  const pct = { valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) };
  if (view === "column")
    return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
             grid: { left: 8, right: 16, top: 24, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
             xAxis: { type: "category", data: chart.categories, axisLabel: { interval: 0, rotate: chart.categories.length > 6 ? 35 : 0, width: 110, overflow: "truncate" } },
             yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
             series: chart.series.map(s => ({ name: s.name, type: "bar", data: s.data, barMaxWidth: 28,
                                              label: { show: chart.series.length === 1 && chart.categories.length <= 16, position: "top", formatter: "{c}%" } })) };
  if (view === "donut")
    return { tooltip: { trigger: "item", ...pct }, legend: { bottom: 0, type: "scroll" },
             series: [{ type: "pie", radius: ["45%", "72%"], label: { formatter: "{d}%" },
                        data: chart.categories.map((name, i) => ({ name, value: chart.series[0].data[i] })) }] };
  if (view === "line")
    return { tooltip: { trigger: "axis", ...pct }, legend: { bottom: 0, type: "scroll" }, grid: { left: 48, right: 24, top: 16, bottom: 56 },
             xAxis: { type: "category", data: chart.categories }, yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
             series: chart.series.map(s => ({ name: s.name, type: "line", data: s.data, connectNulls: false, symbolSize: 6 })) };
  const names = [...chart.categories].reverse();   // biggest at the top of a horizontal bar chart
  return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
           grid: { left: 8, right: 48, top: 8, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
           xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
           yAxis: { type: "category", data: names, axisLabel: { width: 260, overflow: "truncate" } },
           series: chart.series.map(s => ({ name: s.name, type: "bar", data: [...s.data].reverse(), barMaxWidth: 18,
                                            label: { show: chart.series.length === 1, position: "right", formatter: "{c}%" } })) };
}

/** Every figure: answers down the side, periods across; a long series turns round (periods down the side). */
function Figures({ table }: { table: NonNullable<Answer["table"]> }) {
  const cell = (v: string | number | null) => (v == null ? "—" : `${v}%`);
  const across = table.head.length - 1;
  if (across <= 8)
    return <table className="data">
      <thead><tr>{table.head.map((h, i) => <th key={i} className={i ? "num" : undefined}>{h}</th>)}</tr></thead>
      <tbody>{table.rows.map(r => <tr key={String(r[0])}><th scope="row">{r[0]}</th>{r.slice(1).map((v, i) => <td key={i} className="num">{cell(v)}</td>)}</tr>)}</tbody>
      <tfoot><tr><th scope="row">Base (n)</th>{table.bases.map((b, i) => <td key={i} className="num">{b ? b.toLocaleString("en-US") : "—"}</td>)}</tr></tfoot>
    </table>;
  return <table className="data">
    <thead><tr><th>Period</th>{table.rows.map(r => <th key={String(r[0])} className="num">{r[0]}</th>)}<th className="num">Base (n)</th></tr></thead>
    <tbody>{table.head.slice(1).map((period, p) => <tr key={p}><th scope="row">{period}</th>
      {table.rows.map(r => <td key={String(r[0])} className="num">{cell(r[p + 1])}</td>)}
      <td className="num">{table.bases[p] ? table.bases[p].toLocaleString("en-US") : "—"}</td></tr>)}</tbody>
  </table>;
}

function Reply({ question, answer, weighted, checking, checked, onAsk }: { question: string; answer: Answer; weighted: boolean; checking: boolean; checked: boolean; onAsk: (q: string) => void }) {
  const chart = answer.chart;
  const offered = chart ? views(chart) : [];
  const [picked, setView] = useState<View | null>(null);
  const view = picked && offered.includes(picked) ? picked : offered[0];   // the checked answer may draw differently
  const height = chart ? (view !== "bar" ? 340 : Math.max(180, chart.categories.length * (chart.series.length > 1 ? 34 : 26) + 40)) : 0;
  const source = answer.sources[0];
  const isAdmin = !!useMe().data?.permissions?.includes("admin_pages");
  const [verified, setVerified] = useState("");
  const saveVerified = async () => {
    try { await send("POST", "/api/v1/admin/ask/verified", answer.verify); setVerified("Saved: questions like this now use this answer."); }
    catch (e) { setVerified(e instanceof Error ? e.message : String(e)); }
  };
  const how = { verified: "Verified answer", model: "Understood by AI, figures computed", meaning: "Found by meaning, figures computed",
                rules: "Matched by words, figures computed" }[answer.understood ?? ""];
  const drawn = useRef<Chart | null>(null);
  const file = `ask-${(source?.qcode ?? "answer").toLowerCase()}`;
  const notes = [question, answer.source_line ?? "", "Unweighted figures, from Coresight's surveys (Ask Coresight)."];
  return <article className="card ask-reply">
    <div className="ask-head">
      <p className="ask-q"><MessageSquare size={15} strokeWidth={1.8} aria-hidden="true" /> {question}</p>
      {answer.table && <ExportButtons onExport={format => downloadTable(format, file, answer.table!.head, answer.table!.rows, notes)}
        png={chart ? () => drawn.current && downloadPng(drawn.current, answer.headline || question, answer.source_line ?? "", file) : undefined} />}
    </div>
    {answer.no_source
      ? <p className="ask-headline">{answer.answer}</p>
      : <>
        <p className="ask-headline"><Bold text={answer.headline || answer.answer.split("\n")[1] || ""} /></p>
        {!!answer.points?.length && <ul className="ask-points">{answer.points.map((p, i) => <li key={i}><Bold text={p} /></li>)}</ul>}
        {chart && offered.length > 1 && <span className="seg ask-views" role="group" aria-label="Chart type">
          {offered.map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{VIEW_NAMES[v]}</button>)}</span>}
        {chart && view !== "table" && <EChart key={view} option={option(chart, view)} height={height} label={answer.headline || question} onReady={c => { drawn.current = c; }} />}
        {chart && view === "table" && answer.table && <div className="table-wrap"><Figures table={answer.table} /></div>}
        {(!!answer.notes?.length || weighted) && <ul className="ask-notes small muted">
          {answer.notes?.map((n, i) => <li key={i}>{n}</li>)}
          {weighted && <li>Your Weighted switch is on, but Ask Coresight answers with unweighted figures (as Forsta shows them).</li>}
        </ul>}
        {source && <p className="small muted ask-source">{answer.source_line}{" "}
          <Link to={source.link}>Open {source.link.includes("/trends/") ? "in Trends" : "in Question explorer"} →</Link></p>}
        <p className="small muted ask-how">{how}{checking && " · checking with AI…"}{checked && " · checked by AI"}{answer.changed && ` · updated by AI (first shown: ${answer.changed})`}{isAdmin && answer.verify && answer.understood !== "verified" && <>{" · "}
          {verified ? <span role="status">{verified}</span> : <button type="button" className="linklike" onClick={() => void saveVerified()}>Save as verified</button>}</>}</p>
        {answer.table && <details className="ask-figures"><summary>Every figure and its base</summary>
          <div className="table-wrap"><Figures table={answer.table} /></div></details>}
      </>}
    {answer.suggestions.length > 0 && <div className="ask-more">
      <p className="small muted">{answer.no_source ? "Closest questions" : answer.suggestions[0]?.alt ? "Did you mean" : "Other questions that match"}</p>
      <div className="tagrow">{answer.suggestions.map(s => <button key={s.key} type="button" className={s.alt ? "tag sig" : "tag"} title={s.text}
        onClick={() => onAsk(s.text)}>{s.qcode}: {s.text.length > 70 ? s.text.slice(0, 69) + "…" : s.text}</button>)}</div>
    </div>}
  </article>;
}

export default function Ask() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [replies, setReplies] = useState<{ question: string; answer: Answer; checking?: boolean; checked?: boolean }[]>([]);   // this visit's conversation, newest first
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const weighted = useWeighted();
  const ask = async (question: string) => {
    question = question.trim();
    if (question.length < 3) return;
    setText(question);
    setParams({ q: question }, { replace: true });
    setBusy(true); setError("");
    try {
      const answer = await send<Answer>("POST", "/api/v1/ask", { question, quick: true });
      setReplies(r => [{ question, answer, checking: !!answer.check }, ...r].slice(0, 20));
      if (answer.check) {   // the model's reading, after the quick answer is on screen: replaces it only for another question
        const settle = (better: Answer | null) => setReplies(r => r.map(x => x.answer !== answer ? x : !better
          || (better.mode === answer.mode && better.sources[0]?.question === answer.sources[0]?.question) ? { ...x, checking: false, checked: !!better }
          : { question, answer: { ...better, changed: answer.sources[0]?.qcode } }));
        send<Answer>("POST", "/api/v1/ask", { question, check: true }).then(settle, () => settle(null));
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  // a question in the address (the Home page's box, a shared link) is answered on arrival
  useEffect(() => { const q = params.get("q"); if (q) void ask(q); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  return <>
    <div className="page-head"><div>
      <h1>Ask Coresight</h1>
      <p className="lede">Ask anything about the surveys in plain words: a share, how many people, the top answers, a trend by week, two weeks, four weeks, month, quarter or year, a comparison, or a cut such as generation. Every figure is exact, from the surveys only.</p>
    </div></div>
    <div className="stack">
      <section className="card ask-panel">
        <form className="ask-box" onSubmit={e => { e.preventDefault(); void ask(text); }}>
          <MessageSquare size={17} strokeWidth={1.8} aria-hidden="true" />
          <label className="sr-only" htmlFor="ask">Your question</label>
          <input id="ask" value={text} onChange={e => {   // the box emptied: the answers go with it
            setText(e.target.value);
            if (!e.target.value.trim()) { setReplies([]); setError(""); setParams({}, { replace: true }); }
          }} placeholder="e.g. What share bought from Amazon in all waves?" autoFocus />
          <button className="btn primary" disabled={busy || text.trim().length < 3}><ArrowRight size={15} aria-hidden="true" />{busy ? "Finding…" : "Ask"}</button>
        </form>
        {error && <p className="state error" role="alert">Could not answer: {error}</p>}
        {!replies.length && <div className="tagrow ask-examples" aria-label="Example questions">
          {EXAMPLES.map(q => <button key={q} type="button" className="tag" onClick={() => void ask(q)}>{q}</button>)}
        </div>}
      </section>
      {replies.map((r, i) => <Reply key={replies.length - i} question={r.question} answer={r.answer} weighted={weighted} checking={!!r.checking} checked={!!r.checked} onAsk={q => void ask(q)} />)}
    </div>
  </>;
}
