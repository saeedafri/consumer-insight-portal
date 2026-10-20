// One question at a time: wording, base, top answer, any chart type that suits it, by Total or a cut.
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { COLUMNS, isFiller, useBook } from "../api";
import type { Column } from "../api";
import { BaseNote, Card, Change, Empty, Failure, Loading } from "../components/bits";
import QuestionChart, { VIEWS, viewsFor } from "../components/QuestionChart";
import type { View } from "../components/QuestionChart";
import QuestionNav from "../components/QuestionNav";
import { downloadCsv } from "../csv";
import { fmtDate, pct, SMALL_BASE } from "../stats";

const CUTS: { key: string; label: string; cols: Column[] }[] = [
  { key: "total", label: "Total", cols: ["Total"] },
  { key: "gender", label: "By gender", cols: ["Total", "Male", "Female"] },
  { key: "generation", label: "By generation", cols: ["Total", "Gen Z", "Millennial", "Gen X", "Boomer"] },
  { key: "all", label: "All columns", cols: COLUMNS },
];

export default function Explorer() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: book, isLoading, error } = useBook(id);
  const [sort, setSort] = useState(true);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  if (isLoading) return <Loading what="questions" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const allowed = viewsFor(question);
  const view = (allowed.includes(params.get("view") as View) ? params.get("view") : allowed[0]) as View;
  const cut = CUTS.find(c => c.key === params.get("cut")) ?? CUTS[0];
  const group = Math.min(Number(params.get("row") ?? 0), question.groups.length - 1);
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); p.set(k, v); setParams(p, { replace: true }); };
  const g = question.groups[group];
  const top = [...g.rows].filter(r => !isFiller(r.label)).sort((a, b) => (b.Total ?? 0) - (a.Total ?? 0))[0];
  const small = cut.cols.filter(c => (g.bases[c] ?? 0) < SMALL_BASE);
  const wave = fmtDate(book.wave.wave_date);
  const exportCsv = () => downloadCsv(`${question.id}-${book.wave.wave_date}`, ["Answer", ...cut.cols.map(c => `${c} %`), "Last week %"],
    g.rows.map(r => [r.label, ...cut.cols.map(c => r[c]), r.prior]),
    [`${question.id}: ${question.text}`, `${book.wave.title}, wave of ${wave}`, `Base: ${cut.cols.map(c => `${c} n=${g.bases[c]}`).join(", ")}`, "Source: Coresight Research US Consumer Survey"]);
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/questions/${encodeURIComponent(q.id)}?${params}`)} />
    <div className="stack">
      <Card>
        <div className="qhead"><code>{question.id}</code><span>{question.section}</span><span>· {question.type.replace("_", " ")}</span><BaseNote base={g.base} /></div>
        <p className="qtext">{question.text}</p>
        {question.base_desc && <p className="muted" style={{ margin: "0 0 6px" }}>Asked of: {question.base_desc}</p>}
        {top && <p className="top-answer">Top answer{g.label ? ` for ${g.label}` : ""}: <b>{top.label}</b> at <em>{pct(top.Total)}</em>{" "}
          <Change now={top.Total} base={g.base} before={top.prior} beforeBase={top.prior_base} label="vs last week" routing={top.flags.includes("base_changed_prior")} /></p>}
      </Card>
      <Card>
        <div className="toolbar">
          <div className="seg" role="group" aria-label="Chart type">
            {VIEWS.filter(v => allowed.includes(v.key)).map(v => <button key={v.key} aria-pressed={view === v.key} onClick={() => set("view", v.key)}>{v.label}</button>)}
          </div>
          {view !== "donut" && view !== "stacked" && <div className="seg" role="group" aria-label="Columns">
            {CUTS.map(c => <button key={c.key} aria-pressed={cut.key === c.key} onClick={() => set("cut", c.key)}>{c.label}</button>)}
          </div>}
          {question.groups.length > 1 && view !== "stacked" && <select aria-label="Grid row" value={group} onChange={e => set("row", e.target.value)}>
            {question.groups.map((x, i) => <option key={x.label} value={i}>{x.label}</option>)}
          </select>}
          <label className="check"><input type="checkbox" checked={sort} onChange={e => setSort(e.target.checked)} /> Sort by value</label>
          <span style={{ flex: 1 }} />
          <button className="btn" onClick={exportCsv}>Download CSV</button>
          <Link className="btn" to={`/w/${id}/crosstab/${encodeURIComponent(question.id)}`}>Cross-tab</Link>
          <Link className="btn" to={`/w/${id}/trends/${encodeURIComponent(question.id)}`}>Trend</Link>
        </div>
        <QuestionChart question={question} group={group} view={view} columns={view === "donut" || view === "stacked" ? ["Total"] : cut.cols} sort={sort} wave={wave} />
        <div className="legend-line">
          {(view === "bars" || view === "columns") && cut.cols.length === 1 && <>
            <span><i style={{ background: "var(--red)" }} />Top answer</span><span><i style={{ background: "var(--sky)" }} />Other answers</span></>}
          <span>Hover any bar for n, base, margin of error and the change vs last week.</span>
          {small.length > 0 && <span style={{ color: "var(--warn)" }}>Small base (n&lt;{SMALL_BASE}): {small.join(", ")}, shown faded</span>}
        </div>
      </Card>
    </div>
  </div>;
}
