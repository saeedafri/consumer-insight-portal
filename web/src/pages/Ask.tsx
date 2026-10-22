// Ask CIP: a question in plain words, answered only from the portal's published figures, every figure cited
// (api/assistant.py). With nothing to cite it says so instead of guessing.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { send } from "../api";
import type { Answer } from "../api";
import { Card } from "../components/bits";
import { fmtDate } from "../stats";

const EXAMPLES = ["How many people shopped on Cyber Monday?", "Are consumers using GenAI to shop?", "How worried are people about tariffs?",
                  "What share started holiday shopping?"];

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
  return <>
    <div className="page-head"><div>
      <h1>Ask CIP</h1>
      <p className="lede">Ask in plain words. Answers come only from the portal's own survey figures, and every figure names its survey, wave, question and number of respondents. If no survey answers it, you are told so.</p>
    </div></div>
    <div className="stack">
      <Card>
        <form className="toolbar" onSubmit={e => { e.preventDefault(); void ask(text); }}>
          <label className="sr-only" htmlFor="ask">Your question</label>
          <input id="ask" className="field" style={{ flex: 1, minWidth: 220 }} value={text} onChange={e => setText(e.target.value)}
                 placeholder="e.g. How many people shopped on Cyber Monday?" autoFocus />
          <button className="btn primary" disabled={busy || text.trim().length < 3}>{busy ? "Finding sources…" : "Ask"}</button>
        </form>
        {!answer && !busy && <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {EXAMPLES.map(q => <button key={q} type="button" className="chip flat" style={{ cursor: "pointer", padding: "6px 12px", border: "1px solid var(--silver)" }}
                                     onClick={() => { setText(q); void ask(q); }}>{q}</button>)}
        </div>}
        {error && <p className="state error" role="alert">Could not answer: {error}</p>}
      </Card>
      {answer && <Card title={answer.no_source ? "No source answers this" : "Answer"}
                       sub={answer.mode === "claude" ? "Written by Claude from the sources below only" : answer.mode === "figures"
                         ? "The matching survey figures, cited (written answers turn on once the assistant is connected to Claude)" : undefined}>
        <p style={{ whiteSpace: "pre-line", margin: 0, fontSize: 15 }}>{answer.answer}</p>
        {answer.sources.length > 0 && <div className="table-wrap" style={{ marginTop: 14 }}><table className="data">
          <thead><tr><th>Source</th><th>Question</th><th>Wave</th><th className="num">Base</th><th>Top answers</th></tr></thead>
          <tbody>{answer.sources.map(s => <tr key={s.id}>
            <td><b>{s.id}</b></td>
            <td><Link to={s.link}><code style={{ color: "var(--ink)", fontWeight: 700 }}>{s.qcode}</code> {s.question}</Link><br /><small className="muted">{s.title}</small></td>
            <td className="nowrap">{fmtDate(s.wave_date)}</td>
            <td className="num">{s.base.toLocaleString("en-US")}</td>
            <td>{s.answers.slice(0, 3).map(([label, value]) => <div key={label}>{label}: <b>{value}%</b></div>)}</td>
          </tr>)}</tbody>
        </table></div>}
      </Card>}
    </div>
  </>;
}
