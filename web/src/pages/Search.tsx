// Every question in every wave: type words or a question code; open it in its latest wave or as a trend.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useSearch } from "../api";
import { Card, Failure, Loading } from "../components/bits";
import { fmtDate } from "../stats";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const query = params.get("q") ?? "";
  const { data, isFetching, error } = useSearch(query);
  return <>
    <div className="page-head"><div>
      <h1>Find any question asked since 2018</h1>
      <p className="lede">Search by words in the question, its code (XM3, D28) or the survey title. Each result is one question wording, with how many waves asked it.</p>
    </div></div>
    <Card>
      <form className="toolbar" onSubmit={e => { e.preventDefault(); setParams(text.trim() ? { q: text.trim() } : {}); }}>
        <label className="sr-only" htmlFor="q">Search questions</label>
        <div style={{ position: "relative", flex: 1, display: "flex", alignItems: "center" }}>
          <input
            id="q"
            className="field"
            style={{ width: "100%", paddingRight: text ? "36px" : "10px" }}
            autoFocus
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. holiday shopping status, Amazon Prime, GLP-1…"
          />
          {text && (
            <button
              type="button"
              onClick={() => { setText(""); setParams({}); }}
              aria-label="Clear search"
              style={{
                position: "absolute",
                right: 8,
                background: "transparent",
                border: 0,
                color: "var(--ink-2)",
                cursor: "pointer",
                padding: "4px 8px",
                fontSize: 14,
                lineHeight: 1
              }}
            >
              ✕
            </button>
          )}
        </div>
        <button className="btn primary">Search</button>
      </form>
      {!query ? (
        <div style={{ padding: "32px 16px", textAlign: "center" }}>
          <p style={{ color: "var(--ink-2)", fontSize: "14px", margin: "0 0 16px" }}>Type to search across all tracker waves, or pick a popular topic:</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", maxWidth: 640, margin: "0 auto" }}>
            {["Amazon Prime", "Holiday shopping", "GLP-1", "Grocery prices", "Walmart", "Shein", "Temu", "Inflation impact", "Beauty products"].map(topic => (
              <button
                key={topic}
                type="button"
                className="chip flat"
                style={{ cursor: "pointer", padding: "6px 14px", fontSize: "13px", border: "1px solid var(--silver)" }}
                onClick={() => { setText(topic); setParams({ q: topic }); }}
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      ) : error ? <Failure error={error} /> : isFetching && !data ? <Loading what="results" />
        : !data?.results.length ? (
          <div style={{ textAlign: "center", padding: "36px 16px" }}>
            <p className="muted" style={{ margin: "0 0 12px" }}>No question matches “{query}”. Try fewer words or a broader term.</p>
            <button className="btn" onClick={() => { setText(""); setParams({}); }}>Clear search</button>
          </div>
        )
        : <><Understood u={data.understood} count={data.results.length} />
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Code</th><th>Question</th><th className="num">Waves</th><th>Asked</th><th aria-label="Action" style={{ width: 84 }} /></tr></thead>
          <tbody>{data.results.map(h => <tr key={h.qcode + h.text}>
            <td><code style={{ color: "var(--red)", fontWeight: 700 }}>{h.qcode}</code></td>
            <td><Link to={`/w/${h.survey_id}/questions/${encodeURIComponent(h.qcode)}`}>{h.text}</Link><br /><small className="muted">{h.title}</small></td>
            <td className="num">{h.waves}</td>
            <td className="muted">{h.first === h.last ? fmtDate(h.last) : `${fmtDate(h.first)} – ${fmtDate(h.last)}`}</td>
            <td><Link className="btn" to={h.waves > 1 ? `/w/${h.survey_id}/trends/${encodeURIComponent(h.qcode)}` : `/w/${h.survey_id}/questions/${encodeURIComponent(h.qcode)}`}>{h.waves > 1 ? "Trends" : "Explore"}</Link></td>
          </tr>)}</tbody>
        </table></div></>}
    </Card>
  </>;
}

/** What the search did with the words, so a corrected or widened search is never a surprise. */
function Understood({ u, count }: { u?: { corrected: string[]; expanded: string[]; matched_by: string }; count: number }) {
  if (!u) return null;
  return <p className="muted" style={{ margin: "0 0 10px" }}>
    {count} {count === 1 ? "question" : "questions"}
    {u.corrected.length > 0 && <> · spelling corrected: <b>{u.corrected.join(", ")}</b></>}
    {u.expanded.length > 0 && <> · also searched: {u.expanded.join("; ")}</>}
    {u.matched_by === "fragments" && <> · matched on parts of words</>}
    {u.matched_by === "any word" && <> · no question has every word, so these match some of them</>}
  </p>;
}
