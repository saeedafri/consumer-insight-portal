// Ask CIP (/app/ask): a question in plain words, answered from the portal's own published survey figures with the
// chart that fits (api/assistant.py: no AI model, no database, milliseconds). Every figure is exact and listed in the
// table under the chart; a question it cannot place shows the closest survey questions instead of a guess.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { send } from "../api";
import type { Answer, AskChart } from "../api";
import { Card } from "../components/bits";
import EChart from "../components/EChart";
import { ArrowRight, MessageSquare, MessageSquareText } from "lucide-react";
import { fmtDate } from "../stats";

const EXAMPLES = [["Retailers", "What share bought from Amazon in the latest wave?"], ["Technology", "GenAI use for shopping, monthly"],
                  ["Holidays", "Holiday shopping progress by generation"], ["Sentiment", "Economy better or worse, every 4 weeks"],
                  ["Compare", "Compare the first and latest wave of holiday shopping progress"], ["Sectors", "Top beauty retailers"]];

/** The ECharts option for an Ask CIP chart: lines over time, horizontal bars (long answer names stay readable),
 *  grouped bars by a cut, or a donut for a single choice that adds up to 100%. */
function option(chart: AskChart) {
  const pct = { valueFormatter: (v: unknown) => (v == null ? "—" : `${v}%`) };
  if (chart.type === "donut")
    return { tooltip: { trigger: "item", ...pct }, legend: { bottom: 0, type: "scroll" },
             series: [{ type: "pie", radius: ["45%", "72%"], label: { formatter: "{d}%" },
                        data: chart.categories.map((name, i) => ({ name, value: chart.series[0].data[i] })) }] };
  if (chart.type === "line")
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

export default function Ask() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ask = async (question: string) => {
    if (question.trim().length < 3) return;
    setParams({ q: question.trim() }, { replace: true });
    setBusy(true); setError("");
    try { setAnswer(await send<Answer>("POST", "/api/v1/ask", { question })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  // a question in the address (the Home page's box, a shared link) is answered on arrival
  useEffect(() => { const q = params.get("q"); if (q) void ask(q); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const chart = answer?.chart;
  const height = chart ? (chart.type === "line" || chart.type === "donut" ? 340 : Math.max(180, chart.categories.length * (chart.series.length > 1 ? 34 : 26) + 40)) : 0;
  return <>
    <div className="page-head"><div>
      <h1>Ask Coresight</h1>
      <p className="lede">Ask in plain words about any survey: a share, how many people, the top answers, a trend by week, two weeks, four weeks, month, quarter or year, a comparison, or a cut such as generation. Every figure is exact, from the surveys only.</p>
    </div></div>
    <div className="stack">
      <div className="ask-grid">
        <section className="card ask-panel">
          <div className="tagrow"><span className="chip sig">Answers from survey figures</span><span className="tag">Every figure exact</span></div>
          {!answer && !busy && <div className="empty-hero">
            <span className="empty-icon" aria-hidden="true"><MessageSquareText size={26} strokeWidth={1.8} /></span>
            <h2>What would you like to know?</h2>
            <p>Name what you want, and when: "latest wave", "last 8 weeks", "October 2026", "2025 vs 2026", "monthly", "by gender".</p>
          </div>}
          <form className="ask-box" onSubmit={e => { e.preventDefault(); void ask(text); }}>
            <MessageSquare size={17} strokeWidth={1.8} aria-hidden="true" />
            <label className="sr-only" htmlFor="ask">Your question</label>
            <input id="ask" value={text} onChange={e => setText(e.target.value)} placeholder="e.g. What share bought from Amazon in the latest wave?" autoFocus />
            <button className="btn primary" disabled={busy || text.trim().length < 3}><ArrowRight size={15} aria-hidden="true" />{busy ? "Finding…" : "Ask"}</button>
          </form>
          {error && <p className="state error" role="alert">Could not answer: {error}</p>}
        </section>
        <section className="card">
          <div className="card-head"><div><h2>Example questions</h2><p className="sub">Choose one to ask it</p></div></div>
          <div className="stack">
            {EXAMPLES.map(([topic, q]) => <button key={q} type="button" className="story" onClick={() => { setText(q); void ask(q); }}>
              <small>{topic}</small><b>{q}</b>
            </button>)}
          </div>
        </section>
      </div>
      {answer && <Card title={answer.no_source ? "No survey question matches this" : "Answer"}
                       sub={answer.sources[0] ? <>Source: <Link to={answer.sources[0].link}>{answer.sources[0].qcode}</Link> · newest wave {fmtDate(answer.sources[0].wave_date)} · unweighted</> : undefined}>
        <p style={{ whiteSpace: "pre-line", margin: 0, fontSize: 15 }}>{answer.answer}</p>
        {chart && <div style={{ marginTop: 14 }}><EChart option={option(chart)} height={height} label={answer.answer.split("\n")[0]} /></div>}
        {answer.table && <details style={{ marginTop: 12 }}><summary>Every figure ({answer.table.rows.length} answers)</summary>
          <div className="table-wrap"><table className="data">
            <thead><tr>{answer.table.head.map((h, i) => <th key={i} className={i ? "num" : undefined}>{h}</th>)}</tr></thead>
            <tbody>{answer.table.rows.map(r => <tr key={String(r[0])}>{r.map((v, i) => i ? <td key={i} className="num">{v == null ? "—" : `${v}%`}</td> : <th key={i} scope="row">{v}</th>)}</tr>)}</tbody>
            <tfoot><tr><th scope="row">Base (n)</th>{answer.table.bases.map((b, i) => <td key={i} className="num">{b.toLocaleString("en-US")}</td>)}</tr></tfoot>
          </table></div></details>}
        {answer.suggestions.length > 0 && <div style={{ marginTop: 12 }}><p className="small muted" style={{ margin: "0 0 6px" }}>{answer.no_source ? "Closest questions" : "Did you mean another question?"}</p>
          <div className="tagrow">{answer.suggestions.map(s => <button key={s.key} type="button" className="tag" title={s.text}
            onClick={() => { setText(s.text); void ask(s.text); }}>
            {s.qcode}: {s.text.length > 70 ? s.text.slice(0, 69) + "…" : s.text}</button>)}</div></div>}
      </Card>}
    </div>
  </>;
}
