// The questionnaire as a respondent saw it, one question at a time, with the live result beside it.
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useBook } from "../api";
import { BaseNote, Card, Empty, Failure, Loading } from "../components/bits";
import QuestionChart from "../components/QuestionChart";
import { fmtDate } from "../stats";

export default function Survey() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const { data: book, isLoading, error } = useBook(id);
  const [picked, setPicked] = useState<Record<string, string[]>>({});
  const at = useMemo(() => Math.max(0, book?.questions.findIndex(x => x.id === code) ?? 0), [book, code]);
  if (isLoading) return <Loading what="questionnaire" />;
  if (error || !book) return <Failure error={error} />;
  const q = book.questions[at];
  if (!q) return <Empty>This wave has no questions to preview.</Empty>;
  const go = (i: number) => navigate(`/w/${id}/survey/${encodeURIComponent(book.questions[i].id)}`);
  const multi = q.type === "multi" || q.type === "grid_multi";
  const choose = (key: string, label: string) => setPicked(p => {
    const now = p[key] ?? [];
    return { ...p, [key]: multi ? (now.includes(label) ? now.filter(x => x !== label) : [...now, label]) : [label] };
  });
  const sections = [...new Map(book.questions.map((x, i) => [x.section, i])).entries()];
  return <>
    <div className="page-head"><div>
      <p className="eyebrow">Survey preview · wave of {fmtDate(book.wave.wave_date)}</p>
      <h1>What respondents were asked</h1>
      <p className="lede">{book.questions.length} questions in {sections.length} sections. Answer for yourself to see where you sit against {book.wave.qualified_n} respondents.</p>
    </div></div>
    <div className="grid g3">
      <div className="span2 stack">
        <Card className="respondent">
          <div className="qhead"><span style={{ color: "var(--red)", fontWeight: 700 }}>{q.section}</span><span>· Question {at + 1} of {book.questions.length}</span><code>{q.id}</code></div>
          <h2>{q.text}</h2>
          <p className="muted">{multi ? "Select all that apply." : "Select one."}{q.base_desc ? ` Asked of: ${q.base_desc}.` : ""}</p>
          {q.groups.length > 1 ? <div className="table-wrap"><table className="data">
            <thead><tr><th />{q.groups[0].rows.map(r => <th key={r.label} className="num" style={{ whiteSpace: "normal" }}>{r.label}</th>)}</tr></thead>
            <tbody>{q.groups.map(g => <tr key={g.label}><th scope="row">{g.label}</th>{g.rows.map(r => {
              const on = (picked[q.id + g.label] ?? []).includes(r.label);
              return <td key={r.label} className="num"><button className={`option ${on ? "on" : ""}`} style={{ padding: 8, justifyContent: "center" }}
                aria-pressed={on} aria-label={`${g.label}: ${r.label}`} onClick={() => choose(q.id + g.label, r.label)}><span className="box radio" /></button></td>;
            })}</tr>)}</tbody></table></div>
          : <div className="options">{q.groups[0].rows.map(r => {
              const on = (picked[q.id] ?? []).includes(r.label);
              return <button key={r.label} className={`option ${on ? "on" : ""}`} aria-pressed={on} onClick={() => choose(q.id, r.label)}>
                <span className={`box ${multi ? "" : "radio"}`} /><span style={{ textAlign: "left" }}>{r.label}</span></button>;
            })}</div>}
          <div className="toolbar" style={{ marginTop: 20 }}>
            <button className="btn" disabled={at === 0} onClick={() => go(at - 1)}>‹ Previous</button>
            <button className="btn primary" disabled={at >= book.questions.length - 1} onClick={() => go(at + 1)}>Next question ›</button>
          </div>
        </Card>
        <Card title="How everyone answered" sub={`${q.id} · Total`} aside={<BaseNote base={q.groups[0].base} />}>
          <QuestionChart question={q} view={q.groups.length > 1 ? "stacked" : "bars"} columns={["Total"]} sort={false} wave={fmtDate(book.wave.wave_date)} />
        </Card>
      </div>
      <Card title="Questionnaire flow" className="flow">
        <div style={{ maxHeight: "70vh", overflowY: "auto" }}>
          {sections.map(([section, first], k) => <button key={section} className={q.section === section ? "on" : ""} onClick={() => go(first)}>
            <span className="no">{k + 1}</span><span>{section}<br /><small className="muted">{book.questions.filter(x => x.section === section).length} questions</small></span>
          </button>)}
        </div>
      </Card>
    </div>
  </>;
}
