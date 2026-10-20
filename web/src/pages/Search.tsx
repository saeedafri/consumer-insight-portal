// Every question in every wave: type words or a question code; open it in its latest wave or as a trend.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useSearch } from "../api";
import { Card, Empty, Failure, Loading } from "../components/bits";
import { fmtDate } from "../stats";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const query = params.get("q") ?? "";
  const { data, isFetching, error } = useSearch(query);
  return <>
    <div className="page-head"><div>
      <p className="eyebrow">Search questions</p>
      <h1>Find any question asked since 2018</h1>
      <p className="lede">Search by words in the question, its code (XM3, D28) or the survey title. Each result is one question wording, with how many waves asked it.</p>
    </div></div>
    <Card>
      <form className="toolbar" onSubmit={e => { e.preventDefault(); setParams(text.trim() ? { q: text.trim() } : {}); }}>
        <label className="sr-only" htmlFor="q">Search</label>
        <input id="q" className="field" style={{ flex: 1 }} autoFocus value={text} onChange={e => setText(e.target.value)} placeholder="e.g. holiday shopping status, Amazon Prime, GLP-1" />
        <button className="btn primary">Search</button>
      </form>
      {!query ? <Empty>Type at least two letters to search every wave.</Empty>
        : error ? <Failure error={error} /> : isFetching && !data ? <Loading what="results" />
        : !data?.results.length ? <Empty>No question matches “{query}”. Try fewer words.</Empty>
        : <div className="table-wrap"><table className="data">
          <thead><tr><th>Code</th><th>Question</th><th className="num">Waves</th><th>Asked</th><th /></tr></thead>
          <tbody>{data.results.map(h => <tr key={h.qcode + h.text}>
            <td><code style={{ color: "var(--red)", fontWeight: 700 }}>{h.qcode}</code></td>
            <td><Link to={`/w/${h.survey_id}/questions/${encodeURIComponent(h.qcode)}`}>{h.text}</Link><br /><small className="muted">{h.title}</small></td>
            <td className="num">{h.waves}</td>
            <td className="muted">{h.first === h.last ? fmtDate(h.last) : `${fmtDate(h.first)} – ${fmtDate(h.last)}`}</td>
            <td>{h.waves > 1 && <Link className="btn" to={`/w/${h.survey_id}/trends/${encodeURIComponent(h.qcode)}`}>Trend</Link>}</td>
          </tr>)}</tbody>
        </table></div>}
    </Card>
  </>;
}
