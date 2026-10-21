// Cross-tab matrix: answers × banner columns with the base row first, a blue heat ombre, significance letters
// (Qualtrics style) or arrows against a reference column, and a second mode that crosses two cuts.
import { useMemo, useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { present, useBook, useCrosstab } from "../api";
import type { Column, Group, Question } from "../api";
import { BaseNote, Card, Empty, Failure, IconDownload, Loading, SourceLine } from "../components/bits";
import QuestionNav from "../components/QuestionNav";
import { downloadCsv } from "../csv";
import { heat, heatAlpha, inkOn } from "../theme";
import { count, fmtDate, moe, pct, significant, SMALL_BASE, versusRest } from "../stats";
import { perf } from "../perf";
import Profiled from "../components/Profiled";

const LETTERS = "ABCDEFG";
const CUT_NAMES: Record<string, string> = { gender: "Gender", age_band: "Age band", generation: "Generation", income_band: "Household income",
                                             census_region: "Census region", urbanicity: "Urbanicity" };
const SORTED_CUTS = Object.entries(CUT_NAMES).sort(([, a], [, b]) => a.localeCompare(b));

const GENERATIONS = ["GenZ", "Millennial", "GenX", "Boomer", "Silent"];
/** Cut values in reading order: generations young to old, numbers (age, income) ascending, the rest A–Z. */
function natural(values: string[]): string[] {
  const num = (v: string) => { const m = v.replace(/,/g, "").match(/\d+(\.\d+)?/); return m ? Number(m[0]) * (/k\b/i.test(v) ? 1000 : 1) : NaN; };
  return [...values].sort((a, b) => {
    const ga = GENERATIONS.indexOf(a), gb = GENERATIONS.indexOf(b);
    if (ga >= 0 || gb >= 0) return (ga < 0 ? 99 : ga) - (gb < 0 ? 99 : gb);
    const na = num(a), nb = num(b);
    if (!isNaN(na) && !isNaN(nb)) return /under|less/i.test(a) ? -1 : /under|less/i.test(b) ? 1 : na - nb;
    return a.localeCompare(b);
  });
}

function useHover() {
  const [card, setCard] = useState<{ x: number; y: number; body: ReactNode } | null>(null);
  const on = (body: ReactNode) => ({
    onMouseMove: (e: MouseEvent) => setCard({ x: Math.min(e.clientX + 14, innerWidth - 340), y: e.clientY + 14, body }),
    onMouseLeave: () => setCard(null),
  });
  const view = card && <div className="hovercard" style={{ left: card.x, top: card.y }} role="tooltip">{card.body}</div>;
  return { on, view };
}

export default function Crosstab() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  if (isLoading) return <Loading what="cross-tabs" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const cols = present(book.n);
  const profiled = cols.length > 1;   // ad hoc and archive surveys without age/gender profiles have nothing to cut by
  const mode = params.get("mode") === "two" && profiled ? "two" : "banner";
  const qIndex = book.questions.findIndex(x => x.id === question.id);
  const prevQ = qIndex > 0 ? book.questions[qIndex - 1] : null;
  const nextQ = qIndex >= 0 && qIndex < book.questions.length - 1 ? book.questions[qIndex + 1] : null;
  const set = (k: string, v: string) => {
    perf.startFilterChange(k, v);
    const p = new URLSearchParams(params);
    p.set(k, v);
    setParams(p, { replace: true });
  };
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/crosstab/${encodeURIComponent(q.id)}?${params}`)} />
    <div className="stack">
      <Card>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div className="breadcrumb">
            <Link to={`/w/${id}`}>Overview</Link>
            <span className="sep">›</span>
            <span>{question.section}</span>
            <span className="sep">›</span>
            <code>{question.id}</code>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              className="icon-btn"
              style={{ width: 28, height: 28, borderRadius: 6, fontSize: 13 }}
              disabled={!prevQ}
              onClick={() => prevQ && navigate(`/w/${id}/crosstab/${encodeURIComponent(prevQ.id)}?${params}`)}
              title={prevQ ? `Previous: ${prevQ.id} (${prevQ.short || prevQ.text})` : "First question"}
              aria-label="Previous question"
            >
              ‹
            </button>
            <span style={{ fontSize: 11.5, color: "var(--ink-2)", fontWeight: 600 }}>{qIndex + 1} of {book.questions.length}</span>
            <button
              className="icon-btn"
              style={{ width: 28, height: 28, borderRadius: 6, fontSize: 13 }}
              disabled={!nextQ}
              onClick={() => nextQ && navigate(`/w/${id}/crosstab/${encodeURIComponent(nextQ.id)}?${params}`)}
              title={nextQ ? `Next: ${nextQ.id} (${nextQ.short || nextQ.text})` : "Last question"}
              aria-label="Next question"
            >
              ›
            </button>
          </div>
        </div>
        <div className="qhead"><code>{question.id}</code><span>{question.section}</span><BaseNote base={question.groups[0].base} /></div>
        <p className="qtext">{question.text}</p>
        <div className="seg" role="group" aria-label="Cross-tab mode">
          <button aria-pressed={mode === "banner"} onClick={() => set("mode", "banner")}>Banner: gender and generation</button>
          <button aria-pressed={mode === "two"} onClick={() => set("mode", "two")} disabled={!profiled}
                  title={profiled ? undefined : "This survey has no respondent profile (gender, age, generation…) to cut by"}>Combine two cuts</button>
        </div>
      </Card>
      {!profiled && <p className="muted">This survey has no respondent profile (gender, age, generation…), so only the Total column is available.</p>}
      {mode === "banner" ? (
        <Profiled id="Crosstab:Banner">
          <Banner question={question} n={book.n} wave={fmtDate(book.wave.wave_date)} cols={cols} />
        </Profiled>
      ) : (
        <Profiled id="Crosstab:TwoCuts">
          <TwoCuts id={id} question={question} />
        </Profiled>
      )}
    </div>
  </div>;
}

function Banner({ question, n, wave, cols }: { question: Question; n: Record<Column, number>; wave: string; cols: Column[] }) {
  const [params, setParams] = useSearchParams();
  const ref = (cols.includes(params.get("ref") as Column) ? params.get("ref") : "Total") as Column;
  const marks = params.get("marks") === "arrows" ? "arrows" : "letters";
  const set = (k: string, v: string) => {
    perf.startFilterChange(k, v);
    const p = new URLSearchParams(params);
    p.set(k, v);
    setParams(p, { replace: true });
  };
  const { on, view } = useHover();
  const exportCsv = () => downloadCsv(`${question.id}-crosstab`, ["Group", "Answer", ...cols],
    question.groups.flatMap(g => g.rows.map(r => [g.label, r.label, ...cols.map(c => r[c])])),
    [`${question.id}: ${question.text}`, `Wave of ${wave}`, `Bases: ${cols.map(c => `${c} n=${question.groups[0].bases[c]}`).join(", ")}`]);
  return <Card title="Column percentages" sub={marks === "letters"
      ? "A letter means the figure is significantly higher than that column's (95 %). Click a column to compare everything against it."
      : `▲▼ = significantly higher or lower than ${ref === "Total" ? "everyone else" : ref} (95 %). Click a column to change the reference.`}
    aside={<div className="toolbar" style={{ margin: 0 }}>
      <div className="seg" role="group" aria-label="Significance marks">
        <button aria-pressed={marks === "letters"} onClick={() => set("marks", "letters")}>Letters</button>
        <button aria-pressed={marks === "arrows"} onClick={() => set("marks", "arrows")}>Arrows</button>
      </div>
      <button className="btn" onClick={exportCsv}><IconDownload /> Download CSV</button></div>}>
    {question.groups.map(g => <Matrix key={g.label} g={g} q={question} n={n} cols={cols} refCol={ref} marks={marks} hover={on} onRef={c => set("ref", c)} />)}
    <div className="legend-line">
      <span><i style={{ background: heat(0.15) }} />low</span><span><i style={{ background: heat(0.9) }} />high share</span>
      <span style={{ color: "var(--warn)" }}>Amber base = fewer than {SMALL_BASE} respondents: read with caution</span>
    </div>
    <SourceLine wave={wave} base={`Total n=${question.groups[0].base}`} asked={question.base_desc} extra="letters: column-vs-column z-tests" />
    {view}
  </Card>;
}

function Matrix({ g, q, n, cols, refCol, marks, hover, onRef }: { g: Group; q: Question; n: Record<Column, number>; cols: Column[]; refCol: Column; marks: string;
  hover: (body: ReactNode) => object; onRef: (c: Column) => void }) {
  const max = Math.max(1, ...g.rows.flatMap(r => cols.map(c => r[c] ?? 0)));
  const base = (c: Column) => g.bases[c] ?? 0;
  const mark = (v: number, c: Column, r: (typeof g.rows)[number]) => {
    if (base(c) < SMALL_BASE) return "";
    if (marks === "letters")
      return cols.map((o, i) => o !== c && base(o) >= SMALL_BASE && (r[o] ?? 0) < v && significant(v, base(c), r[o] ?? 0, base(o)) ? LETTERS[i] : "").join("");
    if (c === refCol) return "";
    const s = refCol === "Total" ? versusRest(v, base(c), r.Total ?? 0, base("Total"))
      : significant(v, base(c), r[refCol] ?? 0, base(refCol)) ? (v > (r[refCol] ?? 0) ? 1 : -1) : 0;
    return s > 0 ? "▲" : s < 0 ? "▼" : "";
  };
  return <div className="table-wrap" style={{ marginBottom: 14 }}>
    {g.label && <h3 style={{ margin: "10px 0 6px", fontSize: "14.5px", fontWeight: 700 }}>{g.label}</h3>}
    <table className="data xt">
      <thead><tr><th>Answer</th>{cols.map((c, i) =>
        <th key={c} className={`num ${c === refCol && marks === "arrows" ? "ref" : ""}`}>
          <button onClick={() => onRef(c)} title={`Compare against ${c}`}>{c}<small>{LETTERS[i]} · n={n[c] ?? base(c)}</small></button></th>)}</tr></thead>
      <tbody>
        <tr className="base-row"><th scope="row">Base (answered)</th>{cols.map(c =>
          <td key={c} className="num" style={base(c) < SMALL_BASE ? { color: "var(--warn)" } : undefined}>{base(c)}{base(c) < SMALL_BASE ? " ⚠" : ""}</td>)}</tr>
        {g.rows.map(r => <tr key={r.label}><th scope="row">{r.label}</th>{cols.map(c => {
          const v = r[c];
          if (v == null) return <td key={c} className="cell hidden">–</td>;
          const alpha = heatAlpha(v / max);
          const m = mark(v, c, r);
          return <td key={c} className={`cell ${base(c) < SMALL_BASE ? "small-col" : ""}`}
                     style={{ background: heat(alpha), color: inkOn(alpha) }}
                     {...hover(<><b>{r.label}</b><b className="v">{pct(v)} <small style={{ fontSize: 12, color: "var(--ink-2)" }}>±{moe(v, base(c)).toFixed(1)}</small></b>
                       {c} · ≈{count(v, base(c))} of {base(c)} respondents
                       {m && <div style={{ marginTop: 4 }}>{marks === "letters" ? `Significantly higher than ${m.split("").map(l => cols[LETTERS.indexOf(l)]).join(", ")}`
                         : `Significantly ${m === "▲" ? "higher" : "lower"} than ${refCol === "Total" ? "everyone else" : refCol}`} (95 %)</div>}
                       {base(c) < SMALL_BASE && <div style={{ color: "var(--warn)" }}>Small base: read with caution</div>}
                       <div className="muted" style={{ marginTop: 4 }}>{q.id}</div></>)}>
            {v.toFixed(0)}{m && <sup>{m}</sup>}</td>;
        })}</tr>)}
      </tbody>
    </table>
  </div>;
}

function TwoCuts({ id, question }: { id: number; question: Question }) {
  const [params, setParams] = useSearchParams();
  const a = params.get("a") ?? "gender", b = params.get("b") ?? "generation";
  const weeks = Number(params.get("weeks") ?? 1);
  const set = (k: string, v: string) => {
    perf.startFilterChange(k, v);
    const p = new URLSearchParams(params);
    p.set(k, v);
    setParams(p, { replace: true });
  };
  const { data, isFetching, error } = useCrosstab(id, question.id, [a, b], weeks, a !== b);
  const { on, view } = useHover();
  const answers = useMemo(() => [...new Map((data?.rows ?? []).map(r =>
    [`${r[2]}|${r[3]}`, [r[2], r[4]].filter(Boolean).join(": ")])).entries()], [data]);
  const pick = params.get("answer") ?? answers[0]?.[0];
  const rows = (data?.rows ?? []).filter(r => `${r[2]}|${r[3]}` === pick);
  const v1s = natural([...new Set(rows.map(r => r[0] as string))]), v2s = natural([...new Set(rows.map(r => r[1] as string))]);
  const cell = (x: string, y: string) => rows.find(r => r[0] === x && r[1] === y);
  return <Card title="Two cuts combined" sub="One answer at a time. Cells under 30 respondents are hidden; under 50 are flagged. Pool four weeks to grow small cells.">
    <div className="toolbar">
      {(["a", "b"] as const).map(k => <select key={k} aria-label={k === "a" ? "Rows" : "Columns"} value={k === "a" ? a : b} onChange={e => set(k, e.target.value)}>
        {SORTED_CUTS.map(([v, l]) => <option key={v} value={v}>{k === "a" ? "Rows: " : "Columns: "}{l}</option>)}</select>)}
      <div className="seg" role="group" aria-label="Weeks pooled">
        {[1, 2, 4].map(w => <button key={w} aria-pressed={weeks === w} onClick={() => set("weeks", String(w))}>{w === 1 ? "This week" : `Last ${w} weeks`}</button>)}
      </div>
      {answers.length > 0 && <select aria-label="Answer" value={pick} onChange={e => set("answer", e.target.value)} style={{ maxWidth: 360 }}>
        {answers.map(([k, l]) => <option key={k} value={k}>{String(l)}</option>)}</select>}
    </div>
    {a === b ? <Empty>Pick two different cuts.</Empty> : error ? <Failure error={error} /> : !data ? <Loading what="cells" /> : <>
      {data.warnings.includes("base_changed_within_pool") && <p className="chip warn" style={{ whiteSpace: "normal", borderRadius: 8, padding: "8px 12px" }}>
        Who was asked this question changed within the pooled weeks, so pooling mixes two different groups. Use “This week”.</p>}
      <p className="muted">{data.weeks > 1 ? `Pooled ${data.weeks} waves: ${data.waves.map(w => fmtDate(w.wave_date)).join(", ")}` : `Wave of ${fmtDate(data.waves[0]?.wave_date)}`}{isFetching ? " · updating…" : ""}</p>
      <div className="table-wrap"><table className="data xt">
        <thead><tr><th>{CUT_NAMES[a]} \ {CUT_NAMES[b]}</th>{v2s.map(y => <th key={y} className="num">{y}</th>)}</tr></thead>
        <tbody>{v1s.map(x => <tr key={x}><th scope="row">{x}</th>{v2s.map(y => {
          const r = cell(x, y);
          if (!r) return <td key={y} className="cell hidden">–</td>;
          const [, , , , , nn, base, p, flags] = r as [string, string, string, number, string, number | null, number, number | null, string];
          if (flags === "suppressed") return <td key={y} className="cell hidden" {...on(<>{x} × {y}<br />Only {base} respondents: hidden</>)}>n&lt;30</td>;
          const alpha = heatAlpha((p ?? 0) / 100);
          return <td key={y} className={`cell ${flags === "small_base" ? "small-col" : ""}`} style={{ background: heat(alpha), color: inkOn(alpha) }}
                     {...on(<><b>{x} × {y}</b><b className="v">{pct(p)} <small style={{ fontSize: 12 }}>±{moe(p ?? 0, base).toFixed(1)}</small></b>{nn} of {base} respondents
                       {flags === "small_base" && <div style={{ color: "var(--warn)" }}>Small base: read with caution</div>}</>)}>
            {(p ?? 0).toFixed(0)}<small style={{ display: "block", fontWeight: 400, fontSize: 10 }}>n={base}</small></td>;
        })}</tr>)}</tbody>
      </table></div>
    </>}
    {view}
  </Card>;
}
