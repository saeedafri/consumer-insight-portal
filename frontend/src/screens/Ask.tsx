// Ask CIP (/app/ask): a question in plain words, answered from the portal's own published survey figures with
// the chart that fits (api/assistant.py, no database). Quick results appear first. An optional AI check can refine
// the selected question, period or cut. A conversation:
// each answer appears right under the box, newest first. Both views lead with the answer in one sentence and the
// figures that matter (stat tiles), then the chart the dataviz forms pick (a line, ranked bars, one segmented bar, 100% stacked bars, a heatmap, a dumbbell),
// what the figures tell, and questions to continue with; Analyst view adds the exact sentences, notes, how the question
// was understood and every figure with its base. A question it cannot place shows the closest survey questions.
import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { send, suggestAsk, useAskHistory, useMe } from "../api";
import type { Answer, AskChart, AskOffer, AskTile } from "../api";
import EChart, { downloadPng } from "../components/EChart";
import type { Chart } from "../components/EChart";
import { ExportButtons, Menu } from "../components/bits";
import { downloadTable } from "../csv";
import { blues, C, heatStep, labelOn, scaleColours, useTheme } from "../theme";
import { useWeighted } from "../weight";
import { ArrowRight, ArrowUpRight, MessageSquare } from "lucide-react";
import MicButton from "../components/MicButton";

const EXAMPLES = ["How are higher gasoline prices affecting consumer spending?", "What share bought from Amazon in all waves?",
                  "Holiday shopping progress by generation", "Economy better or worse, every 4 weeks",
                  "Compare the first and latest wave of holiday shopping progress", "Top beauty retailers",
                  "How worried are people about tariffs?", "Top food retailers, last 8 weeks"];
const FIGURE = /([+−-]?\d[\d,]*(?:\.\d+)?%|[+−-]\d+(?:\.\d+)? percentage points|\d[\d,]* of [\d,]+ respondents)/g;
const AUDIENCE = "cip_ask_view";   // this viewer's choice of view, kept in their browser
type Audience = "client" | "analyst";
const savedAudience = (): Audience => { try { return localStorage.getItem(AUDIENCE) === "analyst" ? "analyst" : "client"; } catch { return "client"; } };

/** A sentence with its figures in bold, the way an analyst scans it. */
const Bold = ({ text }: { text: string }) =>
  <>{text.replace(/\bpts\b/g, "percentage points").replace(/\bGenZ\b/g, "Gen Z").replace(/\bn=([\d,]+)/g, "$1 responses")
    .split(FIGURE).map((part, i) => i % 2 ? <b key={i}>{part}</b> : <Fragment key={i}>{part}</Fragment>)}</>;

type View = "line" | "bar" | "column" | "donut" | "table" | "split" | "stacked" | "heatmap" | "dumbbell";
const VIEW_NAMES: Record<View, string> = { line: "Line", bar: "Bars", column: "Columns", donut: "Donut", table: "Table",
                                           split: "Split", stacked: "Stacked", heatmap: "Heatmap", dumbbell: "Before → after" };

/** The ways an answer's figures can be drawn, the server's choice first (api/assistant.py chart): over time a line or
 *  columns; two periods compared a dumbbell or bars; a single choice one segmented bar, bars or a donut; by a cut 100%
 *  stacked bars or a heatmap, or grouped bars; one period bars or columns; always a table. */
function views(chart: AskChart): View[] {
  switch (chart.type) {
    case "line": return ["line", "column", "table"];
    case "dumbbell": return ["dumbbell", "bar", "table"];
    case "split": return ["split", "bar", "donut", "table"];
    case "stacked": return ["stacked", "bar", "table"];
    case "heatmap": return ["heatmap", "bar", "table"];
  }
  return ["bar", "column", "table"];   // grouped, or ranked bars: a donut of 7+ parts is the dataviz anti-pattern
}

/** The ECharts option for an Ask chart drawn as `view`: lines over time, horizontal bars (long answer names stay
 *  readable), columns, 100% stacked bars by group, or a donut for a single choice that adds up to 100%. */
function option(chart: AskChart, view: View) {
  const pct = { valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) };
  const named = (name: string) => (chart.bases?.[name] ? `${name} (n=${chart.bases[name].toLocaleString("en-US")})` : name);   // a group with its base
  if (view === "split")   // one whole in its parts: one stacked bar (dataviz: the tall segmented bar), exported as PNG like the rest
    return option({ ...chart, categories: [""], series: chart.categories.map((name, i) => ({ name, data: [chart.series[0].data[i]] })) }, "stacked");
  if (view === "stacked") {   // one bar per group, each answer its share of the group; a share too thin for its label shows none
    const colours = scaleColours(chart.series.map(s => s.name)) ?? blues(chart.series.length);
    return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: { bottom: 0, type: "scroll" },
             grid: { left: 8, right: 16, top: 8, bottom: 40, containLabel: true },
             xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
             yAxis: { type: "category", data: [...chart.categories].reverse(), axisLabel: { width: 200, overflow: "truncate", formatter: named } },
             series: chart.series.map((s, i) => ({ name: s.name, type: "bar", stack: "all", data: [...s.data].reverse(), barMaxWidth: 24,
               itemStyle: { color: colours[i], borderColor: C.surface, borderWidth: 1 },
               label: { show: true, position: "inside", color: labelOn(colours[i]),
                        formatter: (p: { value: number | null }) => (p.value != null && p.value >= 8 ? `${Math.round(p.value)}%` : "") } })) };
  }
  if (view === "column")
    return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll", formatter: named } : undefined,
             grid: { left: 8, right: 16, top: 24, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
             xAxis: { type: "category", data: chart.categories, axisLabel: { interval: 0, rotate: chart.categories.length > 6 ? 35 : 0, width: 110, overflow: "truncate", formatter: named } },
             yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
             series: chart.series.map(s => ({ name: s.name, type: "bar", data: s.data, barMaxWidth: 24,
                                              label: { show: chart.series.length === 1 && chart.categories.length <= 16, position: "top", formatter: "{c}%" } })) };
  if (view === "donut")
    return { tooltip: { trigger: "item", ...pct }, legend: { bottom: 0, type: "scroll" },
             series: [{ type: "pie", radius: ["45%", "72%"], label: { formatter: "{d}%" },
                        data: chart.categories.map((name, i) => ({ name, value: chart.series[0].data[i] })) }] };
  if (view === "line")
    return { tooltip: { trigger: "axis", ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll" } : undefined,
             grid: { left: 48, right: 24, top: 16, bottom: chart.series.length > 1 ? 56 : 24 },
             xAxis: { type: "category", data: chart.categories }, yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
             series: chart.series.map(s => ({ name: s.name, type: "line", data: s.data, connectNulls: false, symbolSize: 8, lineStyle: { width: 2 },
               endLabel: { show: chart.series.length === 1, formatter: "{c}%" } })) };
  const names = [...chart.categories].reverse();   // biggest at the top of a horizontal bar chart
  return { tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...pct }, legend: chart.series.length > 1 ? { bottom: 0, type: "scroll", formatter: named } : undefined,
           grid: { left: 8, right: 48, top: 8, bottom: chart.series.length > 1 ? 40 : 8, containLabel: true },
           xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
           yAxis: { type: "category", data: names, axisLabel: { width: 260, overflow: "truncate", formatter: named } },
           series: chart.series.map(s => ({ name: s.name, type: "bar", data: [...s.data].reverse(), barMaxWidth: 18,
                                            label: { show: chart.series.length === 1, position: "right", formatter: "{c}%" } })) };
}

/** Many answers by many groups: answers down the side, groups across, each cell shaded by its share of the largest
 *  (the cross-tabs' readable steps), every figure printed, each group's base at the foot as in the cross-tabs. */
function Heatmap({ chart }: { chart: AskChart }) {
  useTheme();
  const top = Math.max(1, ...chart.series.flatMap(s => s.data.filter((v): v is number => v != null)));
  return <div className="table-wrap"><table className="data ask-heat">
    <thead><tr><th>Answer</th>{chart.series.map(s => <th key={s.name} className="num">{s.name}</th>)}</tr></thead>
    <tbody>{chart.categories.map((name, i) => <tr key={name}><th scope="row">{name}</th>
      {chart.series.map(s => { const v = s.data[i]; return <td key={s.name} className="num" style={v == null ? undefined : heatStep(v / top)}>{v == null ? "—" : `${v}%`}</td>; })}</tr>)}</tbody>
    {chart.bases && <tfoot><tr><th scope="row">Base (n)</th>{chart.series.map(s => <td key={s.name} className="num">{chart.bases?.[s.name]?.toLocaleString("en-US") ?? "—"}</td>)}</tr></tfoot>}
  </table></div>;
}

/** Two periods compared, answer by answer: a dot for each joined by a line (one hue, the latest stronger), and the
 *  figures with their change in points beside it (dataviz: the dumbbell). */
function Dumbbell({ chart }: { chart: AskChart }) {
  useTheme();
  const [before, after] = chart.series;
  const shade = { before: { background: C.s3 }, after: { background: C.s1 } };   // the series ramp: sky and blue are one colour in dark
  const top = Math.max(10, Math.ceil(Math.max(...[...before.data, ...after.data].filter((v): v is number => v != null)) / 10) * 10);
  const place = (share: number) => `${(share / top) * 100}%`;
  return <figure className="ask-dumbbell">
    <figcaption className="ask-legend"><span><i className="dumbbell-key" style={shade.before} />{before.name}</span><span><i className="dumbbell-key" style={shade.after} />{after.name}</span></figcaption>
    {chart.categories.map((name, i) => {
      const was = before.data[i], now = after.data[i];
      if (was == null || now == null) return null;
      return <div key={name} className="dumbbell-row" title={`${name}: ${was}% → ${now}%`}>
        <span className="dumbbell-name">{name}</span>
        <span className="dumbbell-track" aria-hidden="true">
          <span className="dumbbell-line" style={{ left: place(Math.min(was, now)), width: `${(Math.abs(now - was) / top) * 100}%` }} />
          <span className="dumbbell-dot" style={{ left: place(was), ...shade.before }} /><span className="dumbbell-dot" style={{ left: place(now), ...shade.after }} />
        </span>
        <span className="dumbbell-figures">{was}% → <b>{now}%</b> <span className="muted">{now - was >= 0 ? "+" : "−"}{Math.abs(now - was).toFixed(1)} pts</span></span>
      </div>;
    })}
  </figure>;
}

/** An answer as text to paste: an email (the finding, the key figures, the source) or a slide (a title, three bullets,
 *  a source line), written from the answer's own sentences and figures, no AI model (21 Nov 2026). */
function writeUp(question: string, answer: Answer, form: "email" | "slide"): string {
  const figures = answer.overview?.length ? answer.overview.map(o => `${o.name}: ${o.text}`)
    : (answer.tiles ?? []).map(t => `${t.label}: ${t.value}${t.note ? ` (${t.note})` : ""}`);
  const scope = answer.scope ? `${answer.scope.period}, ${answer.scope.waves} survey ${answer.scope.waves === 1 ? "wave" : "waves"}` +
    `${answer.scope.base ? `, ${answer.scope.base.toLocaleString("en-US")} respondents` : ""}` : "";
  const source = `Source: Coresight Research consumer survey${answer.sources[0] ? `, question ${answer.sources[0].qcode} “${answer.sources[0].question}”` : ""}` +
    `${scope ? `; ${scope}` : ""}; ${answer.weighting === "weighted" ? "Census-weighted" : "unweighted"}.`
  const notes = (answer.notes ?? []).filter(n => !n.startsWith("Asked under"));
  const lead = answer.headline || answer.takeaway || "";
  return form === "slide"
    ? [lead, "", ...figures.slice(0, 3).map(f => `• ${f}`), ...(answer.takeaway && answer.takeaway !== lead ? [`• ${answer.takeaway}`] : []), "", source].join("\n")
    : [`On “${question}”: ${lead}`, "", ...(figures.length ? ["Key figures:", ...figures.map(f => `- ${f}`), ""] : []),
       ...(answer.takeaway && answer.takeaway !== lead ? [answer.takeaway, ""] : []), ...notes.map(n => `Note: ${n}`), source].join("\n");
}

async function copyText(button: HTMLButtonElement, text: string) {
  const original = button.textContent;
  try { await navigator.clipboard.writeText(text); button.textContent = "Copied"; }
  catch { button.textContent = "The browser blocked copying"; }
  setTimeout(() => { button.textContent = original; }, 1800);
}

/** The figures that matter, as stat tiles: the main one first (api/assistant.py brief). */
const Tiles = ({ tiles }: { tiles: AskTile[] }) =>
  <div className="grid g3 ask-tiles">{tiles.map((t, i) => <div key={t.label} className={`kpi ask-tile${i ? "" : " lead"}`}>
    <div className="k-label">{t.label}</div><div className="k-value">{t.value}</div><div className="k-note">{t.note}</div></div>)}</div>;

/** The exact base follows its figure, including in tables turned sideways for long series. */
function Figures({ table }: { table: NonNullable<Answer["table"]> }) {
  const cell = (row: number, col: number) => {
    const share = table.rows[row][col + 1];
    const base = table.cell_bases?.[row][col];
    return share == null ? "—" : <>{share}%{base != null && <small className="muted"> (n={base.toLocaleString("en-US")})</small>}</>;
  };
  if (table.head.length <= 9)
    return <table className="data">
      <thead><tr>{table.head.map((h, i) => <th key={i} className={i ? "num" : undefined}>{h}</th>)}</tr></thead>
      <tbody>{table.rows.map((r, row) => <tr key={row}><th scope="row">{r[0]}</th>{r.slice(1).map((_, col) => <td key={col} className="num">{cell(row, col)}</td>)}</tr>)}</tbody>
    </table>;
  return <table className="data">
    <thead><tr><th>Period or group</th>{table.rows.map((r, row) => <th key={row} className="num">{r[0]}</th>)}</tr></thead>
    <tbody>{table.head.slice(1).map((period, col) => <tr key={col}><th scope="row">{period}</th>
      {table.rows.map((_, row) => <td key={row} className="num">{cell(row, col)}</td>)}</tr>)}</tbody>
  </table>;
}

function Reply({ question, answer, audience, checking, onAsk }: { question: string; answer: Answer; audience: Audience;
                                                                                    checking: boolean; onAsk: (q: string, key?: string) => void }) {
  const chart = answer.chart;
  const offered = chart ? views(chart) : [];
  const [picked, setView] = useState<View | null>(null);
  const view = picked && offered.includes(picked) ? picked : offered[0];   // the checked answer may draw differently
  const drawnByHand = view === "heatmap" || view === "dumbbell" || view === "table";
  const height = chart ? (view === "bar" ? Math.max(180, chart.categories.length * (chart.series.length > 1 ? 34 : 26) + 40)
                          : view === "stacked" ? Math.max(160, chart.categories.length * 40 + 60) : view === "split" ? 120 : 320) : 0;
  const source = answer.sources[0];
  const scope = answer.scope;
  const analyst = audience === "analyst";
  const isAdmin = !!useMe().data?.permissions?.includes("admin_pages");
  const [verified, setVerified] = useState("");
  const saveVerified = async () => {
    try { await send("POST", "/api/v1/admin/ask/verified", answer.verify); setVerified("Saved: questions like this now use this answer."); }
    catch (e) { setVerified(e instanceof Error ? e.message : String(e)); }
  };
  // verified and named: right 99%+ in the per-survey checks (etl/ask_quality.py); the rest are best matches to check
  // unsure of its pick, and not about to be checked by the AI: the alternatives under the answer's first line, not the foot
  const unsure = !!answer.unsure && !answer.no_source && !checking && answer.suggestions.length > 0;
  const how = { verified: "Verified answer", named: "Matched survey question",
                learned: "Answered as a question settled earlier by the AI check, figures computed",
                name: "Best match by name: other survey questions share this name (below)",
                model: "Best match, understood by AI: check the question below", reader: "Best match, read by Ask's own model: check the question below",
                meaning: "Best match by meaning: check the question below",
                rules: "Best match by words: check the question below",
                topic: "From the topic's dashboard: its headline figure's trend, then its key figures" }[answer.understood ?? ""];
  const drawn = useRef<Chart | null>(null);
  const file = `ask-${(source?.qcode ?? "answer").toLowerCase()}`;
  const weightedAnswer = answer.weighting === "weighted";
  const notes = [question, answer.source_line ?? "", `${weightedAnswer ? "Census-weighted" : "Unweighted"} figures, from Coresight's surveys (Ask CIP).`];
  if (scope) notes.splice(1, 0, `Data used: ${scope.period} · ${scope.waves} ${scope.waves === 1 ? "wave" : "waves"} · ${scope.country}`);
  const tiles = answer.tiles ?? [];
  const table = answer.table;
  /** Include denominators in data downloads without treating them as percentages in PowerPoint charts. */
  const exportFigures = (format: Parameters<typeof downloadTable>[0]) => {
    if (!table) return;
    const cellBases = table.cell_bases;
    const rows = cellBases && (format === "csv" || format === "xlsx")
      ? table.rows.flatMap((row, i) => [row, [`${row[0]} · Base (n)`, ...cellBases[i]]])
      : table.rows;
    return downloadTable(format, file, table.head, rows, notes);
  };
  return <article className="card ask-reply">
    <div className="ask-head">
      <p className="ask-q"><MessageSquare size={15} strokeWidth={1.8} aria-hidden="true" /> {question}
        {answer.corrected && <span className="small muted ask-corrected"> · answered as “{answer.corrected}”, the spelling put right</span>}
        {answer.asked_as && <span className="small muted ask-corrected"> · read with your last question: “{answer.asked_as}”</span>}</p>
      {!answer.no_source && !checking && <Menu label="Copy" name="Copy the answer as text" keep>
        <button type="button" onClick={e => void copyText(e.currentTarget, writeUp(question, answer, "email"))}>For an email</button>
        <button type="button" onClick={e => void copyText(e.currentTarget, writeUp(question, answer, "slide"))}>For a slide</button>
      </Menu>}
      {table && !checking && <ExportButtons pin={false} onExport={exportFigures}
        png={chart && !drawnByHand ? () => drawn.current && downloadPng(drawn.current, answer.headline || question, answer.source_line ?? "", file) : undefined} />}
    </div>
    {answer.no_source
      ? <p className="ask-headline">{answer.answer}</p>
      : <>
        <p className="ask-headline"><Bold text={answer.headline || answer.takeaway || answer.answer.split("\n")[1] || ""} /></p>
        {source && <p className="small muted ask-source">
          {scope && <>{scope.country === "US" ? "United States" : scope.country === "CN" ? "China" : scope.country}
            {" · "}{scope.period}{" · "}{scope.waves} {scope.waves === 1 ? "survey wave" : "survey waves"}
            {!!scope.base && <>{" · "}{scope.base.toLocaleString("en-US")} respondents</>}{weightedAnswer ? " · Census-weighted · " : " · Unweighted · "}</>}
          <Link to={source.link} title={source.question}>Source {source.qcode}{source.name ? `: ${source.name}` : ""} →</Link>
        </p>}
        {(how || checking) && <p className="small muted ask-how">{checking ? "Checking the survey match…" : analyst ? how :
          answer.understood === "verified" ? "Verified survey match" : answer.understood === "named" ? "Matched survey question" :
          answer.understood === "topic" ? "From the topic's dashboard" : "Closest survey match"}
          {analyst && isAdmin && answer.verify && !checking && answer.understood !== "verified" && <>{" · "}
          {verified ? <span role="status">{verified}</span> : <button type="button" className="linklike" onClick={() => void saveVerified()}>Save as verified</button>}</>}</p>}
        {unsure && <div className="ask-more ask-alt"><p className="small muted">Not what you meant?</p>
          <div className="tagrow">{answer.suggestions.slice(0, 3).map(s => <button key={s.key} type="button" className="tag" title={s.text}
            onClick={() => onAsk(question, s.key)}>{s.qcode}: {s.text.length > 70 ? s.text.slice(0, 69) + "…" : s.text}</button>)}</div></div>}
        {tiles.length > 0 && <Tiles tiles={tiles} />}
        {!!answer.overview?.length && <ul className="ask-points">{answer.overview.map(o => <li key={o.qcode}><b>{o.name}</b>: <Bold text={o.text} /> <Link to={o.link} className="small">{o.qcode} →</Link></li>)}</ul>}
        {analyst && !!answer.points?.length && <ul className="ask-points">{answer.points.map((p, i) => <li key={i}><Bold text={p} /></li>)}</ul>}
        {chart && offered.length > 1 && <span className="seg ask-views" role="group" aria-label="Chart type">
          {offered.map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{VIEW_NAMES[v]}</button>)}</span>}
        {chart && view === "heatmap" && <Heatmap chart={chart} />}
        {chart && view === "dumbbell" && <Dumbbell chart={chart} />}
        {chart && !drawnByHand && <EChart key={view} option={option(chart, view)} height={height} label={answer.headline || question} onReady={c => { drawn.current = c; }} />}
        {chart && view === "table" && answer.table && <div className="table-wrap"><Figures table={answer.table} /></div>}
        {answer.takeaway && answer.takeaway !== answer.headline && <div className="ask-takeaway"><b>What this tells us</b><p><Bold text={answer.takeaway} /></p></div>}
        {!!answer.notes?.length && <ul className="ask-notes small muted">
          {answer.notes?.map((n, i) => <li key={i}>{n}</li>)}
        </ul>}
        {table && view !== "table" && <details className="ask-figures" open={analyst}><summary>Figures and sample sizes</summary>
          {source && <p className="small muted">{answer.source_line}</p>}
          <div className="table-wrap"><Figures table={table} /></div></details>}
      </>}
    {!!answer.next?.length && <div className="ask-more">
      <p className="small muted">Continue the analysis</p>
      <div className="ask-next">{answer.next.map(n => <button key={n.question} type="button" onClick={() => onAsk(n.question, n.key)}>
        {n.question}<ArrowUpRight size={14} aria-hidden="true" /></button>)}</div>
    </div>}
    {answer.suggestions.length > (unsure ? 3 : 0) && <div className="ask-more">
      <p className="small muted">{answer.mode === "choose" ? "Choose one" : answer.no_source ? "Closest questions" : answer.suggestions[0]?.alt ? "Did you mean" : "Other questions that match"}</p>
      <div className="tagrow">{answer.suggestions.slice(unsure ? 3 : 0).map(s => <button key={s.key} type="button" className={s.alt ? "tag sig" : "tag"} title={s.text}
        onClick={() => onAsk(question, s.key)}>{s.qcode}: {s.text.length > 70 ? s.text.slice(0, 69) + "…" : s.text}</button>)}</div>
    </div>}
  </article>;
}

export default function Ask() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [replies, setReplies] = useState<{ id: number; question: string; answer: Answer; checking: boolean }[]>([]);   // this visit's conversation, newest first
  const active = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offer, setOffer] = useState<AskOffer | null>(null);   // while typing: the words put right, questions by name
  const asked = useRef(params.get("q") ?? "");   // not the address: react-router 7 updates it a render after the text
  const panel = useRef<HTMLElement>(null);   // the box: a new answer is prepended above the replies, so scroll back up to it
  const [audience, setAudience] = useState<Audience>(savedAudience);
  const weighted = useWeighted();
  const history = useAskHistory().data?.questions ?? [];
  // this visit's questions first (the access log is written a moment later), then earlier ones, each once
  const recent = [...new Map([...replies.map(r => r.answer.asked_as ?? r.question), ...history.map(h => h.question)]
    .map(q => [q.toLowerCase(), q])).values()].slice(0, 30);
  const choose = (a: Audience) => { setAudience(a); try { localStorage.setItem(AUDIENCE, a); } catch { /* private window */ } };
  /** Keep one active question so a late reply cannot overwrite a newer one or reappear after clearing. */
  const ask = async (question: string, key?: string) => {
    question = question.trim();
    if (question.length < 3) return;
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
    const last = key ? undefined : replies.find(r => r.answer.mode === "figures" && r.answer.sources.length);
    const body = { question, ...(key ? { key } : {}), ...(weighted ? { weighted: true } : {}),
                   ...(last ? { previous: last.answer.asked_as ?? last.answer.corrected ?? last.question, previous_key: last.answer.sources[0].key } : {}) };
    try {
      const answer = await send<Answer>("POST", "/api/v1/ask", { ...body, quick: true }, signal);
      if (signal.aborted) return;
      if (answer.asked_as) setParams({ q: answer.asked_as }, { replace: true });   // a shared link answers the follow-up as read
      setReplies(replies => [{ id, question, answer, checking: !!answer.check }, ...replies].slice(0, 20));
      requestAnimationFrame(() => {
        if (!signal.aborted) panel.current?.scrollIntoView({
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
  // (15 Nov 2026: a typo such as "subcription" found nothing, and nothing helped while typing)
  const typed = text.trim();
  useEffect(() => {
    if (typed.length < 3 || typed === asked.current) { setOffer(null); return; }
    let current = true;
    // asked again on arrival: Enter within the pause asks this same text, and the effect does not run again to cancel
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
      <h1>Ask CIP</h1>
      <p className="lede">Ask about the surveys in plain words. Get a figure, compare periods, or see how answers differ across groups. Each result links to its source.</p>
    </div></div>
    <div className="stack">
      <section className="card ask-panel" ref={panel}>
        <form className="ask-box" onSubmit={e => { e.preventDefault(); void ask(text); }}>
          <MessageSquare size={17} strokeWidth={1.8} aria-hidden="true" />
          <label className="sr-only" htmlFor="ask">Your question</label>
          <input id="ask" value={text} onChange={e => {   // the box emptied: the answers go with it
            setText(e.target.value);
            if (!e.target.value.trim()) {
              active.current?.abort();
              asked.current = "";
              setBusy(false); setReplies([]); setError(""); setParams({}, { replace: true });
            }
          }} onKeyDown={e => { if (e.key === "Escape") setOffer(null); }}
            placeholder="e.g. How are higher gasoline prices affecting consumer spending?" autoFocus />
          <MicButton text={text} setText={setText} />
          <button className="btn primary" disabled={busy || text.trim().length < 3}><ArrowRight size={15} aria-hidden="true" />{busy ? "Finding…" : "Ask"}</button>
        </form>
        <span className="seg ask-audience" role="group" aria-label="Answer view">
          <button type="button" aria-pressed={audience === "client"} onClick={() => choose("client")}>Client view</button>
          <button type="button" aria-pressed={audience === "analyst"} onClick={() => choose("analyst")}>Analyst view</button>
        </span>
        {offer && (offer.corrected || offer.suggestions.length > 0) && <div className="tagrow ask-suggest" aria-label="Suggestions as you type">
          {offer.corrected && <button type="button" className="tag sig" onClick={() => void ask(offer.corrected!)}>Did you mean “{offer.corrected}”?</button>}
          {offer.suggestions.map(s => <button key={s.key} type="button" className="tag" title={`${s.qcode}: asked in ${s.waves} ${s.waves === 1 ? "wave" : "waves"}`}
            onClick={() => void ask(s.text, s.key)}>{s.text} <span className="muted">· {s.waves} {s.waves === 1 ? "wave" : "waves"}</span></button>)}
        </div>}
        <p className="sr-only" role="status">{busy ? "Finding survey evidence." : replies.length ? "New answer available." : ""}</p>
        {error && <p className="state error" role="alert">Could not answer: {error}</p>}
        {!replies.length && <div className="tagrow ask-examples" aria-label="Example questions">
          {EXAMPLES.map(q => <button key={q} type="button" className="tag" onClick={() => void ask(q)}>{q}</button>)}
        </div>}
        {recent.length > 0 && <details className="ask-history"><summary className="small muted">Your recent questions ({recent.length})</summary>
          <div className="tagrow">{recent.map(q => <button key={q} type="button" className="tag" onClick={() => void ask(q)}>{q}</button>)}</div></details>}
      </section>
      {replies.map(r => <Reply key={r.id} question={r.question} answer={r.answer} audience={audience}
                                    checking={r.checking} onAsk={(q, key) => void ask(q, key)} />)}
    </div>
  </>;
}
