// Ask CIP (/app/ask): a question in plain words, answered from the portal's own published survey figures (api/assistant.py,
// no database, no AI writing). One view, in the manager's layout (27 Nov 2026): the survey the answer comes from, a direct
// answer in one sentence with its key figure in red, three summary cards, the chart that fits the question (a line over
// time, vertical columns to compare answers or groups), then the evidence (the question asked, the source, every survey
// result) and questions to dig deeper. The words, cards and chart come from api/ask_layout.py; an answer it does not lay
// out yet (a combined question, an "among" group) shows its headline, tiles and chart as before. A question it cannot place
// shows the closest survey questions.
import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { send, suggestAsk, useAskHistory, useMe } from "../api";
import type { Answer, AskChart, AskLayout, AskOffer } from "../api";
import EChart, { downloadPng } from "../components/EChart";
import type { Chart } from "../components/EChart";
import { ExportButtons } from "../components/bits";
import { downloadBook, downloadTable } from "../csv";
import { blues, C, heatStep, labelOn, scaleColours, useTheme } from "../theme";
import { useWeighted } from "../weight";
import { ArrowRight, ArrowUpRight, Copy, History, MessageSquare, Plus } from "lucide-react";
import MicButton from "../components/MicButton";

const EXAMPLES = ["How have beauty purchases changed over time?", "What share bought from Amazon in all waves?",
                  "Holiday shopping progress by generation", "Economy better or worse, every 4 weeks",
                  "Compare the first and latest wave of holiday shopping progress", "Top beauty retailers",
                  "How worried are people about tariffs?", "Top food retailers, last 8 weeks"];
const FIGURE = /([+−-]?\d[\d,]*(?:\.\d+)?%|[+−-]\d+(?:\.\d+)? percentage points)/g;
const GAP_DAYS = 120;   // readings further apart than this are joined by a dashed line (01-template-spec.md 4.3)
const LABELLED = 12;    // a line with this many readings or fewer shows a value on each
const GRAIN_WORDS: Record<string, string> = { "Each survey": "each survey", Monthly: "monthly", Quarterly: "by quarter", Yearly: "by year" };   // api/ask_reader.py reads them
const PERIOD_WORDS = /\s*,?\s*\b(every \d+ weeks?|each (survey|wave|week)|wave by wave|week by week|monthly|quarterly|yearly|weekly|by (month|quarter|year)|over time|in (all|every) (waves?|surveys?)|all waves|in the last \d+ (months?|weeks?|years?)|since \d{4})\b/gi;
/** A period button's question: the one asked, its own period words replaced by the button's ("by quarter", "since 2022"). */
const withPeriod = (question: string, words: string) => `${question.replace(PERIOD_WORDS, "").replace(/[?\s]+$/, "")} ${words}`;
const MARKET = "cip_ask_market";   // this viewer's market, kept in their browser
type Market = "US" | "CN" | "both";
const MARKETS: [Market, string][] = [["US", "US"], ["CN", "China"], ["both", "Both"]];
const savedMarket = (): Market => { try { const m = localStorage.getItem(MARKET); return m === "US" || m === "CN" ? m : "both"; } catch { return "both"; } };

/** A sentence with its key figure (the first) in red and the other figures in bold, the way an analyst scans it. */
const Lead = ({ text }: { text: string }) =>
  <>{text.split(FIGURE).map((part, i) => !(i % 2) ? <Fragment key={i}>{part}</Fragment>
    : <b key={i} className={i === 1 ? "ask-key" : undefined}>{part}</b>)}</>;   // the split puts the first figure at 1

/** The layout's chart as an ECharts option: a line on a real time axis (dashed across long gaps, a value on each reading
 *  when few, the latest labelled), vertical columns (a scale's sides shaded, small groups faded), or paired columns. */
function layoutOption(chart: AskLayout["chart"]) {
  const pct = { valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) };
  const colours = chart.series.length === 1 ? [C.red] : chart.kind === "paired" ? [C.s3, C.red] : [C.red, ...blues(chart.series.length - 1)];
  if (chart.kind === "line") {
    const dates = chart.dates ?? chart.categories;
    const days = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / 864e5;
    const lines = chart.series.flatMap((s, n) => {
      const points = dates.map((d, i) => [d, s.data[i]] as [string, number | null]).filter(([, v]) => v != null);
      const solid: [string, number | null][] = [];
      const dashed: [string, number | null][] = [];
      points.forEach((p, i) => {
        if (i && days(points[i - 1][0], p[0]) > GAP_DAYS) { solid.push([p[0], null]); dashed.push(points[i - 1], p, [p[0], null]); }
        solid.push(p);
      });
      const few = points.length <= LABELLED && chart.series.length === 1;
      return [{ name: s.name, type: "line", data: solid, connectNulls: false, symbolSize: 7, lineStyle: { width: 2.5, color: colours[n] },
                itemStyle: { color: colours[n] }, label: { show: few, position: "top", formatter: (p: { value: [string, number] }) => `${p.value[1]}%` },
                endLabel: { show: true, formatter: (p: { value: [string, number] }) => `${p.value[1]}%`, fontWeight: 700, color: colours[n] } },
              ...(dashed.length ? [{ name: `${s.name} (gap)`, type: "line", data: dashed, symbol: "none", silent: true, tooltip: { show: false },
                                     lineStyle: { type: "dashed", width: 1.5, color: C.lineStrong } }] : [])];
    });
    return { tooltip: { trigger: "axis", ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll", data: chart.series.map(s => s.name) } : undefined,
             grid: { left: 44, right: 56, top: 24, bottom: chart.series.length > 1 ? 48 : 28 },
             xAxis: { type: "time" }, yAxis: { type: "value", min: 0, max: 100, interval: 25, axisLabel: { formatter: "{value}%" } }, series: lines };
  }
  const shade = (i: number, n: number) => chart.small?.[i] ? { color: colours[n], opacity: 0.4 }
    : chart.sides?.[i] === "positive" ? { color: C.s1 } : chart.sides?.[i] === "negative" ? { color: C.red } : chart.sides ? { color: C.grey } : { color: colours[n] };
  return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct },
           legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
           grid: { left: 8, right: 16, top: 28, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
           xAxis: { type: "category", data: chart.categories, axisLabel: { interval: 0, rotate: chart.categories.length > 6 ? 35 : 0, width: 120, overflow: "truncate" } },
           yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
           series: chart.series.map((s, n) => ({ name: s.name, type: "bar", barMaxWidth: 48,
             data: s.data.map((v, i) => ({ value: v, itemStyle: shade(i, n) })),
             label: { show: chart.categories.length <= 16, position: "top", formatter: (p: { value: number | null }) => (p.value == null ? "" : `${p.value}%`) } })) };
}

/** An answer not laid out yet (a combined question, an "among" group): its chart as the server drew it, one view. */
function option(chart: AskChart) {
  const pct = { valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) };
  if (chart.type === "line")
    return { tooltip: { trigger: "axis", ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
             grid: { left: 48, right: 24, top: 16, bottom: chart.series.length > 1 ? 56 : 24 },
             xAxis: { type: "category", data: chart.categories }, yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
             series: chart.series.map(s => ({ name: s.name, type: "line", data: s.data, connectNulls: false, symbolSize: 8, lineStyle: { width: 2 } })) };
  if (chart.type === "stacked" || chart.type === "split") {
    const series = chart.type === "split" ? chart.categories.map((name, i) => ({ name, data: [chart.series[0].data[i]] })) : chart.series;
    const colours = scaleColours(series.map(s => s.name)) ?? blues(series.length);
    return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: { bottom: 0, type: "scroll" },
             grid: { left: 8, right: 16, top: 8, bottom: 40, containLabel: true }, xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
             yAxis: { type: "category", data: chart.type === "split" ? [""] : [...chart.categories].reverse() },
             series: series.map((s, i) => ({ name: s.name, type: "bar", stack: "all", data: chart.type === "split" ? s.data : [...s.data].reverse(), barMaxWidth: 24,
               itemStyle: { color: colours[i] }, label: { show: true, position: "inside", color: labelOn(colours[i]),
                 formatter: (p: { value: number | null }) => (p.value != null && p.value >= 8 ? `${Math.round(p.value)}%` : "") } })) };
  }
  return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
           grid: { left: 8, right: 16, top: 24, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
           xAxis: { type: "category", data: chart.categories, axisLabel: { interval: 0, rotate: chart.categories.length > 6 ? 35 : 0, width: 110, overflow: "truncate" } },
           yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
           series: chart.series.map(s => ({ name: s.name, type: "bar", data: s.data, barMaxWidth: 32,
                                            label: { show: chart.series.length === 1, position: "top", formatter: "{c}%" } })) };
}

/** Many answers by many groups (the server's heatmap): answers down the side, groups across, each cell shaded. */
function Heatmap({ chart }: { chart: AskChart }) {
  useTheme();
  const top = Math.max(1, ...chart.series.flatMap(s => s.data.filter((v): v is number => v != null)));
  return <div className="table-wrap"><table className="data ask-heat">
    <thead><tr><th>Answer</th>{chart.series.map(s => <th key={s.name} className="num">{s.name}</th>)}</tr></thead>
    <tbody>{chart.categories.map((name, i) => <tr key={name}><th scope="row">{name}</th>
      {chart.series.map(s => { const v = s.data[i]; return <td key={s.name} className="num" style={v == null ? undefined : heatStep(v / top)}>{v == null ? "—" : `${v}%`}</td>; })}</tr>)}</tbody>
  </table></div>;
}

/** The full answer as plain text: the question, the direct answer, the three cards, the question asked and the source. */
function answerText(question: string, answer: Answer): string {
  const layout = answer.layout;
  const cards = layout ? layout.cards : answer.tiles ?? [];
  return [`Q: ${question}`, layout?.lead || answer.headline || answer.takeaway || "",
          ...cards.map(c => `${c.label}: ${c.value}${c.note ? ` (${c.note})` : ""}`),
          ...(answer.sources[0] ? [`Question asked: “${answer.sources[0].question}”`] : []),
          ...(layout ? [`Source: ${layout.source}.`] : []), ...(layout?.notes ?? [])].join("\n");
}

async function copyText(button: HTMLButtonElement, text: string) {
  const label = button.lastChild as Text | null;
  const original = label?.textContent ?? "";
  try { await navigator.clipboard.writeText(text); if (label) label.textContent = "Copied"; }
  catch { if (label) label.textContent = "The browser blocked copying"; }
  setTimeout(() => { if (label) label.textContent = original; }, 1800);
}

/** Every survey's figures, as the evidence shows them: no bases (the meeting of 27 Nov 2026). */
function Figures({ table }: { table: NonNullable<Answer["table"]> }) {
  const cell = (row: number, col: number) => { const share = table.rows[row][col + 1]; return share == null ? "—" : `${share}%`; };
  if (table.head.length <= 9)
    return <table className="data">
      <thead><tr>{table.head.map((h, i) => <th key={i} className={i ? "num" : undefined}>{h}</th>)}</tr></thead>
      <tbody>{table.rows.map((r, row) => <tr key={row}><th scope="row">{r[0]}</th>{r.slice(1).map((_, col) => <td key={col} className="num">{cell(row, col)}</td>)}</tr>)}</tbody>
    </table>;
  return <table className="data">
    <thead><tr><th>Survey</th>{table.rows.map((r, row) => <th key={row} className="num">{r[0]}</th>)}</tr></thead>
    <tbody>{[...table.head.slice(1).keys()].reverse().map(col => <tr key={col}><th scope="row">{table.head[col + 1]}</th>
      {table.rows.map((_, row) => <td key={row} className="num">{cell(row, col)}</td>)}</tr>)}</tbody>
  </table>;
}

function Reply({ question, answer, checking, folded, onAsk, onMarket }: { question: string; answer: Answer; checking: boolean; folded: boolean;
                                                             onAsk: (q: string, key?: string) => void; onMarket: (m: Market) => void }) {
  useTheme();
  const [opened, open] = useState(false);
  const layout = answer.layout ?? null;
  const chart = answer.chart;
  const source = answer.sources[0];
  const isAdmin = !!useMe().data?.permissions?.includes("admin_pages");
  const [verified, setVerified] = useState("");
  const [others, showOthers] = useState(false);
  const saveVerified = async () => {
    try { await send("POST", "/api/v1/admin/ask/verified", answer.verify); setVerified("Saved: questions like this now use this answer."); }
    catch (e) { setVerified(e instanceof Error ? e.message : String(e)); }
  };
  const [drawn, setDrawn] = useState<Chart | null>(null);   // state, so the PNG export appears once the chart is drawn
  if (folded && !opened)   // (after every hook) an earlier answer in the conversation: its direct answer in one line, opened on request
    return <article className="card ask-folded">
      <p className="ask-q"><MessageSquare size={15} strokeWidth={1.8} aria-hidden="true" /> {answer.asked_as ?? question}</p>
      <p className="small"><Lead text={answer.layout?.lead || answer.headline || answer.answer || ""} /></p>
      <button type="button" className="linklike small" aria-expanded={false} onClick={() => open(true)}>Show full answer</button>
    </article>;
  const file = `ask-${(source?.qcode ?? "answer").toLowerCase()}`;
  const table = answer.table;
  const height = layout ? (layout.chart.kind === "line" ? 300 : 280) : chart ? (chart.type === "stacked" ? Math.max(160, chart.categories.length * 40 + 60) : chart.type === "split" ? 120 : 300) : 0;
  const notes = [question, layout?.source ?? "", "Figures are the share of people surveyed who gave each answer (Coresight's surveys, Ask CIP)."];
  /** Excel: the answer (its sentence, cards and the chart's numbers with a native chart) and every survey result; the other
   *  formats: every survey result as a table, as before. */
  const exportFigures = (format: Parameters<typeof downloadTable>[0]) => {
    if (format === "xlsx" && layout) {
      const lines = layout.chart.kind === "line";
      const answerRows = layout.chart.categories.map((c, i) => [c, ...layout.chart.series.map(s => s.data[i])]);
      return downloadBook("xlsx", file, [
        { title: "Answer", header: [lines ? "Survey" : "Answer", ...layout.chart.series.map(s => s.name)], rows: answerRows, unit: "%",
          chart: lines ? "line" : "column", notes: [question, layout.lead, ...layout.cards.map(c => `${c.label}: ${c.value} (${c.note})`),
                                                    `Question asked: “${source?.question ?? ""}”`, `Source: ${layout.source}`, ...layout.notes] },
        ...(table ? [{ title: "Every survey result", header: table.head, rows: table.rows, unit: "%" as const, notes }] : [])]);
    }
    return table && downloadTable(format, file, table.head, table.rows, notes);
  };
  return <article className="card ask-reply">
    <div className="ask-head">
      <p className="ask-by"><span className="ask-mark" aria-hidden="true"><MessageSquare size={14} strokeWidth={2.2} /></span>
        <b>Ask CIP</b>{layout && <span className="muted">{layout.survey}</span>}</p>
      {!answer.no_source && !checking && <div className="ask-tools">
        <button type="button" className="btn" onClick={e => void copyText(e.currentTarget, answerText(question, answer))}><Copy size={14} aria-hidden="true" />Copy</button>
        {table && <ExportButtons pin={false} onExport={exportFigures}
          png={drawn ? () => downloadPng(drawn, layout?.lead || answer.headline || question, layout?.source ?? "", file) : undefined} />}
      </div>}
    </div>
    <p className="ask-q"><MessageSquare size={15} strokeWidth={1.8} aria-hidden="true" /> {question}
      {answer.corrected && <span className="small muted ask-corrected"> · answered as “{answer.corrected}”, the spelling put right</span>}
      {answer.asked_as && <span className="small muted ask-corrected"> · read as: “{answer.asked_as}”</span>}</p>
    {answer.notice && <p className="small ask-notice">{answer.notice}</p>}
    {answer.no_source
      ? <><p className="ask-headline">{answer.answer}</p>
        {!!answer.markets?.length && <div className="ask-chips" role="group" aria-label="Choose a market">{answer.markets.map(m =>
          <button key={m.market} type="button" onClick={() => onMarket(m.market)}>{m.label}</button>)}</div>}</>
      : <>
        <p className="ask-headline"><Lead text={layout?.lead || answer.headline || answer.takeaway || answer.answer.split("\n")[1] || ""} /></p>
        {checking && <p className="small muted">Checking the survey match…</p>}
        {!!answer.read_as?.length && <div className="ask-more"><p className="small muted">Read as</p>
          <div className="tagrow">{answer.read_as.map(r => <span key={r.label} className="tag" title={r.value}>{r.label}: {r.value.length > 70 ? r.value.slice(0, 69) + "…" : r.value}</span>)}</div></div>}
        {layout
          ? <ul className="ask-cards" aria-label="Key figures">{layout.cards.map(c => <li key={c.label} className={c.tone === "main" ? "main" : undefined}>
              <span className="k-label">{c.label}</span>
              <span className="k-value">{c.tone === "up" ? "↑ " : c.tone === "down" ? "↓ " : ""}{c.value}</span>
              <span className="k-note">{c.note}</span></li>)}</ul>
          : !!answer.tiles?.length && <ul className="ask-cards" aria-label="Key figures">{answer.tiles.map((t, i) => <li key={t.label} className={i ? undefined : "main"}>
              <span className="k-label">{t.label}</span><span className="k-value">{t.value}</span><span className="k-note">{t.note}</span></li>)}</ul>}
        {!!answer.overview?.length && <ul className="ask-points">{answer.overview.map(o => <li key={o.qcode}><b>{o.name}</b>: <Lead text={o.text} /></li>)}</ul>}
        {(layout || chart) && <div className="ask-chart">
          <div className="ask-chart-top"><div><h3>{layout?.title || source?.name || question}</h3><p className="small muted">% of people asked{layout?.chart.kind === "line" ? ", in each survey" : ""}</p></div>
            {layout?.chart.kind === "line" && source && <div className="ask-periods">
              {!!layout.chart.ranges?.length && <span className="seg" role="group" aria-label="Time range">{layout.chart.ranges.map(r =>
                <button key={r} type="button" onClick={() => onAsk(withPeriod(question, r === "Last 12 months" ? "in the last 12 months, each survey" : r.toLowerCase()), source.key)}>{r}</button>)}</span>}
              {!!layout.chart.grains?.length && <span className="seg" role="group" aria-label="Period">{layout.chart.grains.map(g =>
                <button key={g} type="button" aria-pressed={layout.chart.grain === g} onClick={() => onAsk(withPeriod(question, GRAIN_WORDS[g] ?? ""), source.key)}>{g}</button>)}</span>}
            </div>}</div>
          {layout ? <EChart option={layoutOption(layout.chart)} height={height} label={layout.lead} onReady={setDrawn} />
            : chart?.type === "heatmap" ? <Heatmap chart={chart} />
            : chart && <EChart option={option(chart)} height={height} label={answer.headline || question} onReady={setDrawn} />}
          {(!!layout?.notes.length || !!answer.notes?.length) && <p className="small muted ask-foot">{[...(layout?.notes ?? []), ...(layout ? [] : answer.notes ?? [])].join(" ")}</p>}
        </div>}
        {source && <div className="ask-evidence">
          <p><span className="t-lbl">Question asked</span><q>{source.question}</q></p>
          {layout && <p><span className="t-lbl">Source</span>{layout.source}</p>}
          {table && <details className="ask-figures"><summary>See every survey result</summary><div className="table-wrap"><Figures table={table} /></div></details>}
          {answer.suggestions.length > 0 && <p className="small muted">Not what you meant? <button type="button" className="linklike" aria-expanded={others}
            onClick={() => showOthers(!others)}>Pick a different survey question</button></p>}
          {others && <div className="tagrow">{answer.suggestions.slice(0, 4).map(s => <button key={s.key} type="button" className="tag" title={s.text}
            onClick={() => onAsk(question, s.key)}>{s.label ?? (s.text.length > 90 ? s.text.slice(0, 89) + "…" : s.text)}</button>)}</div>}
          {isAdmin && answer.verify && !checking && answer.understood !== "verified" && <p className="small muted">
            {verified ? <span role="status">{verified}</span> : <button type="button" className="linklike" onClick={() => void saveVerified()}>Save as verified</button>}</p>}
        </div>}
      </>}
    {answer.no_source && answer.suggestions.length > 0 && <div className="ask-more">
      <p className="small muted">{answer.mode === "choose" ? "Choose one" : "These are the closest questions we have"}</p>
      <div className="tagrow">{answer.suggestions.map(s => <button key={s.key} type="button" className="tag" title={s.text}
        onClick={() => onAsk(question, s.key)}>{s.label ?? (s.text.length > 90 ? s.text.slice(0, 89) + "…" : s.text)}</button>)}</div>
    </div>}
    {!!answer.next?.length && <div className="ask-more">
      <h3 className="ask-dig">Dig deeper</h3>
      <div className="ask-chips">{answer.next.map(n => <button key={n.label ?? n.question} type="button" title={n.question} onClick={() => n.market ? onMarket(n.market) : onAsk(n.question, n.key)}>
        {n.label ?? n.question}<ArrowUpRight size={14} aria-hidden="true" /></button>)}</div>
    </div>}
    {source && !answer.no_source && <p className="small muted"><Link to={source.link}>Open this survey question →</Link></p>}
  </article>;
}

export default function Ask() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [replies, setReplies] = useState<{ id: number; question: string; answer: Answer; checking: boolean }[]>([]);   // this visit's conversation, oldest first
  const [historyOpen, showHistory] = useState(false);
  const [historyAll, showAllHistory] = useState(false);   // History lists the 4 newest, then every one on request (01 4.5)
  const historyButton = useRef<HTMLButtonElement>(null);
  const active = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offer, setOffer] = useState<AskOffer | null>(null);   // while typing: the words put right, questions by name
  const asked = useRef(params.get("q") ?? "");   // not the address: react-router 7 updates it a render after the text
  const newest = useRef<HTMLDivElement>(null);   // the latest answer, scrolled into view when it arrives
  const box = useRef<HTMLInputElement>(null);
  const [market, setMarket] = useState<Market>(savedMarket);
  const [threadMarket, setThreadMarket] = useState<Market | null>(null);   // chosen in an ask-back: kept for this conversation's follow-ups
  const chooseMarket = (m: Market) => { setMarket(m); setThreadMarket(null); try { localStorage.setItem(MARKET, m); } catch { /* private window */ } };
  const weighted = useWeighted();
  const history = useAskHistory().data?.questions ?? [];
  // this visit's questions first (the access log is written a moment later), then earlier ones, each once
  const recent = [...new Map([...replies.map(r => r.answer.asked_as ?? r.question), ...history.map(h => h.question)]
    .map(q => [q.toLowerCase(), q])).values()].slice(0, 30);
  // History closes on Escape (back to its button) and on a click outside it
  useEffect(() => {
    if (!historyOpen) return;
    const close = (e: KeyboardEvent | MouseEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !(e.target as Element).closest(".ask-history-pop, .ask-history-button")) {
        showHistory(false);
        if (e instanceof KeyboardEvent) historyButton.current?.focus();
      }
    };
    document.addEventListener("keydown", close); document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, [historyOpen]);
  /** New question: a fresh conversation; the earlier questions stay in the history below the box. */
  const startOver = () => {
    active.current?.abort();
    asked.current = "";
    setText(""); setBusy(false); setReplies([]); setError(""); setOffer(null); setThreadMarket(null); setParams({}, { replace: true });
    box.current?.focus();
  };
  /** Keep one active question so a late reply cannot overwrite a newer one or reappear after clearing. */
  /** fresh: a question from History, asked in a new conversation (no earlier answer to read it with, the selector's market). */
  const ask = async (question: string, key?: string, chosen?: Market, fresh = false) => {
    question = question.trim();
    if (question.length < 3) { setError("Type a question first."); return; }
    active.current?.abort();
    const request = new AbortController();
    active.current = request;
    const id = ++sequence.current;
    const { signal } = request;
    asked.current = question;
    setText(question);
    setParams(key ? { q: question, key } : { q: question }, { replace: true });
    setReplies(replies => replies.map(reply => reply.checking ? { ...reply, checking: false } : reply));
    setBusy(true); setError(""); setOffer(null);
    // a typed question goes with the latest answered one, so "What about Gen Z?" is read with it (api/assistant.py follow_on)
    const last = key || fresh ? undefined : [...replies].reverse().find(r => r.answer.mode === "figures" && r.answer.sources.length);
    const body = { question, market: chosen ?? (fresh ? null : threadMarket) ?? market, ...(key ? { key } : {}), ...(weighted ? { weighted: true } : {}),
                   ...(last ? { previous: last.answer.asked_as ?? last.answer.corrected ?? last.question, previous_key: last.answer.sources[0].key } : {}) };
    try {
      const answer = await send<Answer>("POST", "/api/v1/ask", { ...body, quick: true }, signal);
      if (signal.aborted) return;
      if (answer.asked_as) setParams({ q: answer.asked_as }, { replace: true });   // a shared link answers the follow-up as read
      setReplies(replies => [...replies, { id, question, answer, checking: !!answer.check }].slice(-20));
      setText(""); asked.current = "";
      requestAnimationFrame(() => {
        if (!signal.aborted) newest.current?.scrollIntoView({
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start",
        });
      });
      if (answer.check) {
        const settle = (checked: Answer | null) => {
          if (signal.aborted) return;
          setReplies(replies => replies.map(reply => reply.id !== id ? reply : {
            ...reply, checking: false,
            answer: checked?.understood === "model" ? checked : reply.answer,
          }));
        };
        void send<Answer>("POST", "/api/v1/ask", { ...body, check: true }, signal).then(settle, () => settle(null));
      }
    } catch (e) {
      if (!signal.aborted) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  };
  // after a pause in typing (250 ms), what the box offers: no model and no cost, never for the question just asked
  const typed = text.trim();
  useEffect(() => {
    if (typed.length < 3 || typed === asked.current) { setOffer(null); return; }
    let current = true;
    const wait = setTimeout(() => suggestAsk(typed).then(o => { if (current && typed !== asked.current) setOffer(o); },
      () => { if (current) setOffer(null); }), 250);
    return () => { current = false; clearTimeout(wait); };
  }, [typed]);   // eslint-disable-line react-hooks/exhaustive-deps
  // a question in the address (the Home page's box, a shared link) is answered on arrival
  useEffect(() => {
    const q = params.get("q");
    if (q) void ask(q, params.get("key") ?? undefined);
    return () => active.current?.abort();
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  return <>
    <div className="page-head"><div>
      <h1>What would you like to understand?</h1>
      <p className="lede">Ask a question in your own words.</p>
    </div>
      <div className="ask-page-tools">
        <span className="small muted" id="ask-market">Market</span>
        <span className="seg" role="group" aria-labelledby="ask-market">{MARKETS.map(([code, label]) =>
          <button key={code} type="button" aria-pressed={market === code} onClick={() => chooseMarket(code)}>{label}</button>)}</span>
        {recent.length > 0 && <button type="button" className="btn ask-history-button" ref={historyButton} aria-expanded={historyOpen}
          aria-controls="ask-history" onClick={() => showHistory(!historyOpen)}><History size={14} aria-hidden="true" />History ({recent.length})</button>}
        <button type="button" className="btn primary" onClick={startOver}><Plus size={15} aria-hidden="true" />New question</button>
        {historyOpen && <div className="ask-history-pop" id="ask-history">
          {recent.slice(0, historyAll ? recent.length : 4).map(q => <button key={q} type="button" onClick={() => { showHistory(false); startOver(); void ask(q, undefined, undefined, true); }}>{q}</button>)}
          {!historyAll && recent.length > 4 && <button type="button" className="muted" onClick={() => showAllHistory(true)}>Show all {recent.length}</button>}
        </div>}
      </div>
    </div>
    <div className="stack ask-thread" aria-live="polite">
      {!replies.length && <div className="tagrow ask-examples" aria-label="Example questions">
        {EXAMPLES.map(q => <button key={q} type="button" className="tag" onClick={() => void ask(q)}>{q}</button>)}
      </div>}
      {replies.map((r, i) => <div key={r.id} ref={i === replies.length - 1 ? newest : undefined}>
        <Reply question={r.question} answer={r.answer} checking={r.checking} folded={i < replies.length - 1}
               onAsk={(q, key) => void ask(q, key)} onMarket={m => { setThreadMarket(m); void ask(r.question, undefined, m); }} /></div>)}
      {busy && <p className="small muted" role="status">Finding the answer…</p>}
    </div>
    <div className="ask-dock">
      <section className="card ask-panel">
        {offer && (offer.corrected || offer.suggestions.length > 0) && <div className="tagrow ask-suggest" aria-label="Suggestions as you type">
          {offer.corrected && <button type="button" className="tag sig" onClick={() => void ask(offer.corrected!)}>Did you mean “{offer.corrected}”?</button>}
          {offer.suggestions.map(s => <button key={s.key} type="button" className="tag" onClick={() => void ask(s.text, s.key)}>{s.text}</button>)}
        </div>}
        <form className="ask-box" onSubmit={e => { e.preventDefault(); void ask(text); }}>
          <MessageSquare size={17} strokeWidth={1.8} aria-hidden="true" />
          <label className="sr-only" htmlFor="ask">Your question</label>
          <input id="ask" ref={box} value={text} onChange={e => { setText(e.target.value); setError(""); }}
            onKeyDown={e => { if (e.key === "Escape") setOffer(null); }} placeholder="Ask a question in your own words" autoFocus />
          <MicButton text={text} setText={setText} />
          <button className="btn primary" disabled={busy}><ArrowRight size={15} aria-hidden="true" />{busy ? "Finding…" : "Ask"}</button>
        </form>
        {error && <p className="state error" role="alert">{error === "Type a question first." ? error : `Could not answer: ${error}`}</p>}
      </section>
    </div>
  </>;
}
