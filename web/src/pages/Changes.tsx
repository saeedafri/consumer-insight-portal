// Every answer of the wave against last week or the same week last year, most significant first.
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useBook } from "../api";
import { Card, Failure, Loading } from "../components/bits";
import { downloadCsv } from "../csv";
import { isProfile, moves } from "../moves";
import { fmtDate, pct, pts } from "../stats";

export default function Changes() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const all = useMemo(() => (book ? moves(book) : []), [book]);
  if (isLoading) return <Loading what="changes" />;
  if (error || !book) return <Failure error={error} />;
  const against = params.get("vs") === "ly" ? "ly" : "prior";
  const onlySig = params.get("all") !== "1";
  const section = params.get("section") ?? "all";
  const profile = params.get("profile") === "1";
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v ? p.set(k, v) : p.delete(k); setParams(p, { replace: true }); };
  const key = against === "ly" ? "dLy" : "d";
  const rows = all.filter(m => m[key] != null && (!onlySig || (against === "ly" ? m.sigLy : m.sig)) && (section === "all" || m.q.section === section)
                         && (profile || !isProfile(m)))
    .sort((a, b) => Math.abs(b[key]!) - Math.abs(a[key]!));
  const routing = all.filter(m => m.routing).length;
  const sections = [...new Set(book.questions.map(q => q.section))];
  const noLy = book.wave.ly_status !== "loaded";
  return <>
    <div className="page-head"><div>
      <p className="eyebrow">What changed · wave of {fmtDate(book.wave.wave_date)}</p>
      <h1>{rows.length} {onlySig ? "significant " : ""}changes against {against === "ly" ? "the same week last year" : "last week"}</h1>
      <p className="lede">Every answer of every question, tested with a two-proportion z-test and kept as significant only if it survives the Benjamini–Hochberg correction across the whole wave (5 % false discoveries), so chance moves are not reported as news. Answers whose question was asked of a different group than last week ({routing}) are left out of the test rather than shown as a false move.</p>
    </div></div>
    <Card>
      <div className="toolbar">
        <div className="seg" role="group" aria-label="Compare against">
          <button aria-pressed={against === "prior"} onClick={() => set("vs", "")}>vs last week</button>
          <button aria-pressed={against === "ly"} onClick={() => set("vs", "ly")} disabled={noLy} title={noLy ? "Last year's week is not loaded" : undefined}>vs last year{noLy ? " (not loaded)" : ""}</button>
        </div>
        <label className="check"><input type="checkbox" checked={onlySig} onChange={e => set("all", e.target.checked ? "" : "1")} /> Significant only</label>
        <label className="check" title="Age, gender, income, relationship… shift with each week's sample: context, not news">
          <input type="checkbox" checked={profile} onChange={e => set("profile", e.target.checked ? "1" : "")} /> Include who answered (demographics)</label>
        <select aria-label="Section" value={section} onChange={e => set("section", e.target.value === "all" ? "" : e.target.value)}>
          <option value="all">All sections</option>{sections.map(s => <option key={s}>{s}</option>)}
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => downloadCsv(`changes-${book.wave.wave_date}`, ["Code", "Question", "Answer", "Now %", "Then %", "Change pts", "Significant"],
          rows.map(m => [m.q.id, m.q.text, m.label, m.now, against === "ly" ? m.ly : m.prior, m[key]?.toFixed(1), (against === "ly" ? m.sigLy : m.sig) ? "yes" : "no"]),
          [`${book.wave.title}, wave of ${fmtDate(book.wave.wave_date)}`, `Compared against ${against === "ly" ? "the same week last year" : "last week"}`])}>Download CSV</button>
      </div>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Answer</th><th>Question</th><th className="num">Now</th><th className="num">{against === "ly" ? "Last year" : "Last week"}</th><th className="num">Change</th><th style={{ width: 160 }}>Size of change</th></tr></thead>
        <tbody>{rows.slice(0, 300).map(m => {
          const d = m[key]!, sig = against === "ly" ? m.sigLy : m.sig;
          return <tr key={m.q.id + m.label}>
            <th scope="row">{m.label}</th>
            <td><Link to={`/w/${id}/trends/${encodeURIComponent(m.q.id)}`}><code style={{ color: "var(--red)", fontWeight: 700 }}>{m.q.id}</code></Link> <span className="muted">{(m.q.short || m.q.text).slice(0, 90)}</span></td>
            <td className="num"><b>{pct(m.now)}</b></td>
            <td className="num muted">{pct(against === "ly" ? m.ly : m.prior)}</td>
            <td className={`num ${sig ? "sig" : "muted"}`}>{pts(d)}</td>
            <td><div className="bar-delta" aria-hidden><span style={{ [d > 0 ? "left" : "right"]: "50%", width: `${Math.min(50, Math.abs(d) * 2)}%`, background: sig ? "var(--red)" : "var(--silver)" }} /></div></td>
          </tr>;
        })}</tbody>
      </table></div>
      {rows.length > 300 && <p className="muted">Showing the 300 largest of {rows.length}. Download the CSV for all.</p>}
    </Card>
  </>;
}
