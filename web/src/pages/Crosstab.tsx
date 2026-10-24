// Cross-tab matrix: answers × banner columns with the base row first, a blue heat ombre, significance letters
// (Qualtrics style) or arrows against a reference column, and a second mode that crosses two cuts.
import { useMemo, useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { CUT_NAMES, CUT_OF, present, useBook, useCrosstab } from "../api";
import type { Column, Group, Question, Wave } from "../api";
import { BaseNote, Card, Empty, Failure, Loading, SkeletonScreen, SourceLine, sourceText, ExportButtons } from "../components/bits";
import QuestionNav from "../components/QuestionNav";
import QuestionTabs from "../components/QuestionTabs";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { C, heatStep, useTheme } from "../theme";
import { count, fmtDate, HIDDEN_BASE, HIDDEN_NOTE, moe, pct, significant, SMALL_BASE, versusRest } from "../stats";
import { perf } from "../perf";
import Profiled from "../components/Profiled";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ChevronLeft, ChevronRight } from "lucide-react";

const LETTERS = "ABCDEFG";
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
  const place = (e: MouseEvent, body: ReactNode) => ({ x: Math.max(8, Math.min(e.clientX + 14, innerWidth - 340)), y: e.clientY + 14, body });
  const on = (body: ReactNode) => ({
    onMouseMove: (e: MouseEvent) => setCard(place(e, body)),
    onMouseLeave: () => setCard(null),
    onClick: (e: MouseEvent) => setCard(c => (c ? null : place(e, body))),   // a tap shows it on touch screens; a second tap hides it
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
  useTheme();   // the heat cells take the new theme's steps on a switch
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  if (isLoading) return <SkeletonScreen kind="question" />;
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
        <div className="qcrumbs" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div className="breadcrumb">
            <Link to={`/w/${id}`}>Overview</Link>
            <span className="sep">›</span>
            <span>{question.section}</span>
            <span className="sep">›</span>
            <code>{question.id}</code>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={!prevQ}
                    onClick={() => prevQ && navigate(`/w/${id}/crosstab/${encodeURIComponent(prevQ.id)}?${params}`)}
                    aria-label="Previous question"
                  >
                    <ChevronLeft size={14} />
                  </Button>
                }
              />
              <TooltipContent side="top">
                {prevQ ? `Previous: ${prevQ.id} (${prevQ.short || prevQ.text})` : "First question"}
              </TooltipContent>
            </Tooltip>
            <span style={{ fontSize: 11.5, color: "var(--ink-2)", fontWeight: 600 }}>{qIndex + 1} of {book.questions.length}</span>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={!nextQ}
                    onClick={() => nextQ && navigate(`/w/${id}/crosstab/${encodeURIComponent(nextQ.id)}?${params}`)}
                    aria-label="Next question"
                  >
                    <ChevronRight size={14} />
                  </Button>
                }
              />
              <TooltipContent side="top">
                {nextQ ? `Next: ${nextQ.id} (${nextQ.short || nextQ.text})` : "Last question"}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
        <div className="qhead"><code>{question.id}</code><span>{question.section}</span><BaseNote base={question.groups[0].base} /></div>
        <h1 className="qtext">{question.text}</h1>
        <div style={{ marginTop: 10 }}>
          <Tabs value={mode} onValueChange={m => set("mode", m)}>
            <TabsList>
              <TabsTrigger value="banner">Banner: gender and generation</TabsTrigger>
              <TabsTrigger value="two" disabled={!profiled} title={profiled ? undefined : "This survey has no respondent profile to cut by"}>
                Combine two cuts
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <QuestionTabs id={id} q={question.id} />
      </Card>
      {!profiled && <p className="muted">This survey has no respondent profile (gender, age, generation…), so only the Total column is available.</p>}
      {mode === "banner" ? (
        <Profiled id="Crosstab:Banner">
          <Banner question={question} n={book.n} wave={fmtDate(book.wave.wave_date)} cols={cols} from={book.wave} />
        </Profiled>
      ) : (
        <Profiled id="Crosstab:TwoCuts">
          <TwoCuts id={id} question={question} />
        </Profiled>
      )}
    </div>
  </div>;
}

function Banner({ question, n, wave, cols, from }: { question: Question; n: Record<Column, number>; wave: string; cols: Column[]; from: Wave }) {
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
  const exportAs = (format: Format) => downloadTable(format, `${question.id}-crosstab`, ["Group", "Answer", ...cols],
    // a grid's rows have their own bases: each group carries its base row, never the first group's
    question.groups.flatMap(g => [[g.label, "Base (answered)", ...cols.map(c => g.bases[c] ?? 0)], ...g.rows.map(r => [g.label, r.label, ...cols.map(c => r[c])])]),
    [`${question.id}: ${question.text}`, `Wave of ${wave}`, "Each group's base is its first row",
     "Letters and arrows: single 95 % comparisons between groups, not corrected for multiple tests", sourceText(from, wave, `Total n=${question.groups[0].base}`)]);
  return <Card title="Column percentages" sub={marks === "letters"
      ? "A letter means the figure is higher than that column's in a single 95 % comparison, tested within the same cut only (Male vs Female, generation vs generation): groups that share people are never tested against each other. Not corrected for the many cells compared."
      : `▲▼ = higher or lower than ${ref === "Total" ? "everyone else (the rest of the sample)" : `${ref}, within the same cut`} in a single 95 % comparison, not corrected for multiple tests. Click a column to change the reference.`}
    aside={<div className="toolbar" style={{ margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
      <Tabs value={marks} onValueChange={m => set("marks", m)}>
        <TabsList>
          <TabsTrigger value="letters">Letters</TabsTrigger>
          <TabsTrigger value="arrows">Arrows</TabsTrigger>
        </TabsList>
      </Tabs>
      <ExportButtons onExport={exportAs} /></div>}>
    {question.groups.map(g => <Matrix key={g.label} g={g} q={question} n={n} cols={cols} refCol={ref} marks={marks} hover={on} onRef={c => set("ref", c)} />)}
    <div className="legend-line">
      <span className="heat-legend" aria-label="Shade: share of the table's largest figure, in six steps">low{C.heat.map(c => <i key={c} style={{ background: c }} />)}high share</span>
      <span style={{ color: "var(--warn)" }}>Amber base = fewer than {SMALL_BASE} respondents: read with caution</span>
    </div>
    <SourceLine wave={wave} base={`Total n=${question.groups[0].base}`} asked={question.base_desc} extra="letters: z-tests between groups of the same cut; vs Total = vs the rest of the sample" from={from} />
    {view}
  </Card>;
}

function Matrix({ g, q, n, cols, refCol, marks, hover, onRef }: { g: Group; q: Question; n: Record<Column, number>; cols: Column[]; refCol: Column; marks: string;
  hover: (body: ReactNode) => object; onRef: (c: Column) => void }) {
  const max = Math.max(1, ...g.rows.flatMap(r => cols.map(c => r[c] ?? 0)));
  const base = (c: Column) => g.bases[c] ?? 0;
  // Only independent groups are tested, as standard banner testing does: columns of the same cut (Male vs Female,
  // Gen Z vs Boomer), and a group against everyone else (never against Total, which contains it). Men vs Gen Z share
  // people, so a z-test between them would be wrong: no mark.
  const dim = (c: Column) => CUT_OF[c][0];
  const mark = (v: number, c: Column, r: (typeof g.rows)[number]) => {
    if (base(c) < SMALL_BASE) return "";
    if (marks === "letters")
      return cols.map((o, i) => o !== c && c !== "Total" && dim(o) === dim(c) && base(o) >= SMALL_BASE && (r[o] ?? 0) < v
        && significant(v, base(c), r[o] ?? 0, base(o)) ? LETTERS[i] : "").join("");
    if (c === refCol || (refCol !== "Total" && dim(refCol) !== dim(c))) return "";
    const s = refCol === "Total" ? versusRest(v, base(c), r.Total ?? 0, base("Total"))
      : significant(v, base(c), r[refCol] ?? 0, base(refCol)) ? (v > (r[refCol] ?? 0) ? 1 : -1) : 0;
    return s > 0 ? "▲" : s < 0 ? "▼" : "";
  };
  return <div className="table-wrap" style={{ marginBottom: 14 }}>
    {g.label && <h3 style={{ margin: "10px 0 6px", fontSize: 14, fontWeight: 700 }}>{g.label}</h3>}
    <table className="data xt">
      <thead><tr><th>Answer</th>{cols.map((c, i) =>
        <th key={c} className={`num ${c === refCol && marks === "arrows" ? "ref" : ""}`}>
          <button onClick={() => onRef(c)} title={`Compare against ${c}`}>{c}<small>{LETTERS[i]} · n={n[c] ?? base(c)}</small></button></th>)}</tr></thead>
      <tbody>
        <tr className="base-row"><th scope="row">Base (answered)</th>{cols.map(c =>
          <td key={c} className="num" style={base(c) < SMALL_BASE ? { color: "var(--warn)" } : undefined}>{base(c)}{base(c) < SMALL_BASE ? " ⚠" : ""}</td>)}</tr>
        {g.rows.map(r => <tr key={r.label}><th scope="row">{r.label}</th>{cols.map(c => {
          const v = r[c];
          if (v == null) return <td key={c} className="cell hidden" title={base(c) ? `Only ${base(c)} respondents: hidden (under ${HIDDEN_BASE})` : "Nobody in this group answered"}>{base(c) ? HIDDEN_NOTE : "–"}</td>;
          const m = mark(v, c, r);
          return <td key={c} className={`cell ${base(c) < SMALL_BASE ? "small-col" : ""}`}
                     style={heatStep(v / max)}
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
  const cut = (k: string, fallback: string) => (CUT_NAMES[params.get(k) ?? ""] ? params.get(k)! : fallback);   // only cuts we know
  const a = cut("a", "gender"), b = cut("b", "generation");
  const weeks = [1, 2, 4].includes(Number(params.get("weeks"))) ? Number(params.get("weeks")) : 1;
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
  return <Card title="Two cuts combined" sub={`One answer at a time. Cells under ${HIDDEN_BASE} respondents are hidden; under ${SMALL_BASE} are flagged. No significance tests in this view. Pool four weeks to grow small cells.`}>
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
          if (flags === "suppressed") return <td key={y} className="cell hidden" {...on(<>{x} × {y}<br />Only {base} respondents: hidden</>)}>{HIDDEN_NOTE}</td>;
          return <td key={y} className={`cell ${flags === "small_base" ? "small-col" : ""}`} style={heatStep((p ?? 0) / 100)}
                     {...on(<><b>{x} × {y}</b><b className="v">{pct(p)} <small style={{ fontSize: 12 }}>±{moe(p ?? 0, base).toFixed(1)}</small></b>{nn} of {base} respondents
                       {flags === "small_base" && <div style={{ color: "var(--warn)" }}>Small base: read with caution</div>}</>)}>
            {(p ?? 0).toFixed(0)}<small style={{ display: "block", fontWeight: 500, fontSize: 12 }}>n={base}</small></td>;
        })}</tr>)}</tbody>
      </table></div>
    </>}
    {view}
  </Card>;
}
