// Every question in every wave: type words or a question code; open it in its latest wave or as a trend.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { SEARCH_PAGE, useSearch } from "../api";
import type { Hit } from "../api";
import { Card, Failure, Loading } from "../components/bits";
import { fmtDate } from "../stats";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search as SearchIcon, X } from "lucide-react";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const query = params.get("q") ?? "";
  const page = Math.max(1, Math.trunc(Number(params.get("page") ?? 1)) || 1);
  const { data, isFetching, error } = useSearch(query, page);
  const goPage = (n: number) => { const p = new URLSearchParams(params); if (n > 1) p.set("page", String(n)); else p.delete("page"); setParams(p); scrollTo(0, 0); };
  const byMeasure = params.get("by") === "measure";

  return <>
    <div className="page-head"><div>
      <h1>Find any question asked since 2018</h1>
      <p className="lede">Search by words in the question, its code (XM3, D28) or the survey title. Each result is one question wording, with how many waves asked it.</p>
    </div></div>
    <Card>
      <form className="toolbar" onSubmit={e => { e.preventDefault(); setParams(text.trim() ? { q: text.trim() } : {}); }}>
        <label className="sr-only" htmlFor="q">Search questions</label>
        <div style={{ position: "relative", flex: 1, display: "flex", alignItems: "center" }}>
          <Input
            id="q"
            autoFocus
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. holiday shopping status, Amazon Prime, GLP-1…"
            style={{ width: "100%", paddingRight: text ? "36px" : "10px" }}
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
                padding: "4px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
        <Button variant="default">
          <SearchIcon size={14} />
          Search
        </Button>
      </form>
      {!query ? (
        <div style={{ padding: "32px 16px", textAlign: "center" }}>
          <p style={{ color: "var(--ink-2)", fontSize: "14px", margin: "0 0 16px" }}>Type to search across all tracker waves, or pick a popular topic:</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", maxWidth: 680, margin: "0 auto" }}>
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
            <Button variant="outline" size="sm" onClick={() => { setText(""); setParams({}); }}>Clear search</Button>
          </div>
        )
        : <><div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <Understood u={data.understood} count={data.results.length} total={data.total} from={(page - 1) * SEARCH_PAGE + 1} />
          <Tabs value={byMeasure ? "measure" : "wording"} onValueChange={val => {
            const p = new URLSearchParams(params);
            if (val === "measure") p.set("by", "measure");
            else p.delete("by");
            setParams(p);
          }}>
            <TabsList>
              <TabsTrigger value="wording">Each wording</TabsTrigger>
              <TabsTrigger value="measure">Group by measure</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        {byMeasure ? <Measures hits={data.results} /> : <div className="table-wrap"><table className="data">
          <thead><tr><th>Code</th><th>Question</th><th className="num">Waves</th><th>Asked</th><th aria-label="Action" style={{ width: 92 }} /></tr></thead>
          <tbody>{data.results.map(h => <tr key={h.qcode + h.text}>
            <td><code style={{ color: "var(--ink)", fontWeight: 700 }}>{h.qcode}</code></td>
            <td><Link to={`/w/${h.survey_id}/questions/${encodeURIComponent(h.qcode)}`}>{h.text}</Link><br /><small className="muted">{h.title}</small></td>
            <td className="num">{h.waves}</td>
            <td className="muted">{h.first === h.last ? fmtDate(h.last) : `${fmtDate(h.first)} – ${fmtDate(h.last)}`}</td>
            <td>
              <Link
                className={buttonVariants({ variant: "outline", size: "sm" })}
                to={h.waves > 1 ? `/w/${h.survey_id}/trends/${encodeURIComponent(h.qcode)}` : `/w/${h.survey_id}/questions/${encodeURIComponent(h.qcode)}`}
              >
                {h.waves > 1 ? "Trends" : "Explore"}
              </Link>
            </td>
          </tr>)}</tbody>
        </table></div>}
        {data.total > SEARCH_PAGE && <nav className="pager" aria-label="Search result pages">
          <button className="btn" disabled={page <= 1} onClick={() => goPage(page - 1)}>Previous</button>
          <span className="muted">Page {page} of {Math.ceil(Math.min(data.total, 5000 + SEARCH_PAGE) / SEARCH_PAGE)}</span>
          <button className="btn" disabled={page * SEARCH_PAGE >= Math.min(data.total, 5000 + SEARCH_PAGE)} onClick={() => goPage(page + 1)}>Next</button>
        </nav>}</>}
    </Card>
  </>;
}

/** Hits grouped by harmonised measure: every wording and code of one concept together, with the waves they add up
 *  to. A wording no one has linked to a concept stands alone. */
function Measures({ hits }: { hits: Hit[] }) {
  const groups = new Map<string, Hit[]>();
  for (const h of hits) {
    const key = h.measure_id ? `m${h.measure_id}` : `${h.qcode}|${h.text}`;
    groups.set(key, [...(groups.get(key) ?? []), h]);
  }
  return <div className="table-wrap"><table className="data">
    <thead><tr><th>Measure</th><th className="num">Waves</th><th>Asked</th><th>Wordings</th></tr></thead>
    <tbody>{[...groups.values()].map(g => {
      const first = g.map(h => h.first).sort()[0], last = g.map(h => h.last).sort().at(-1)!;
      const latest = [...g].sort((a, b) => b.last.localeCompare(a.last))[0];
      return <tr key={latest.qcode + latest.text}>
        <td><b>{latest.measure ?? latest.text}</b>{!latest.measure && <><br /><small className="muted">not linked to a measure yet</small></>}</td>
        <td className="num">{g.reduce((n, h) => n + h.waves, 0)}</td>
        <td className="muted">{first === last ? fmtDate(last) : `${fmtDate(first)} – ${fmtDate(last)}`}</td>
        <td>{g.map(h => <div key={h.qcode + h.text} style={{ marginBottom: 4 }}>
          <code style={{ color: "var(--ink)", fontWeight: 700 }}>{h.qcode}</code>{" "}
          <Link to={`/w/${h.survey_id}/compare/${encodeURIComponent(h.qcode)}`}>{h.text.length > 120 ? h.text.slice(0, 119) + "…" : h.text}</Link>
          <small className="muted"> · {h.waves} wave{h.waves === 1 ? "" : "s"}</small></div>)}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}

/** What the search did with the words, so a corrected or widened search is never a surprise. */
function Understood({ u, count, total, from }: { u?: { corrected: string[]; expanded: string[]; matched_by: string }; count: number; total?: number; from: number }) {
  if (!u) return null;
  return <p className="muted" style={{ margin: "0 0 10px" }}>
    {total != null && total > count ? <>{from.toLocaleString("en-US")}–{(from + count - 1).toLocaleString("en-US")} of {total.toLocaleString("en-US")} questions, best match first</>
      : <>{count} {count === 1 ? "question" : "questions"}</>}
    {u.corrected.length > 0 && <> · spelling corrected: <b>{u.corrected.join(", ")}</b></>}
    {u.expanded.length > 0 && <> · also searched: {u.expanded.join("; ")}</>}
    {u.matched_by === "fragments" && <> · matched on parts of words</>}
    {u.matched_by === "any word" && <> · no question has every word, so these match some of them</>}
  </p>;
}
