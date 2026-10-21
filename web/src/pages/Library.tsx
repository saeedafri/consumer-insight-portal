// Every survey and wave: the latest tracker wave first, then the archive grouped by year, filterable.
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useWaves } from "../api";
import { Card, Failure, Loading } from "../components/bits";
import { fmtDate } from "../stats";

const KIND: Record<string, string> = { tracker: "Weekly tracker", annual: "Annual study", adhoc: "Ad hoc study" };

export default function Library() {
  const { data: waves, isLoading, error } = useWaves();
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") ?? "all", year = params.get("year") ?? "all";
  const [text, setText] = useState(params.get("q") ?? "");
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v === "all" || !v ? p.delete(k) : p.set(k, v); setParams(p, { replace: true }); };
  const years = useMemo(() => [...new Set((waves ?? []).map(w => w.wave_date.slice(0, 4)))].sort((a, b) => b.localeCompare(a)), [waves]);
  const shown = useMemo(() => {
    const words = text.toLowerCase().split(/\s+/).filter(Boolean);
    return (waves ?? []).filter(w => (kind === "all" || w.study_type === kind) && (year === "all" || w.wave_date.startsWith(year)) &&
      words.every(t => `${w.title} ${w.survey_family} ${(w.modules ?? []).join(" ")} ${w.wave_date}`.toLowerCase().includes(t)));
  }, [waves, kind, year, text]);
  if (isLoading) return <Loading what="surveys" />;
  if (error) return <Failure error={error} />;
  const all = waves!;
  const latest = all.find(w => w.study_type === "tracker" && w.rows_built !== 0) ?? all[0];
  const byYear = new Map<string, typeof shown>();
  for (const w of shown) byYear.set(w.wave_date.slice(0, 4), [...(byYear.get(w.wave_date.slice(0, 4)) ?? []), w]);
  const trackers = all.filter(w => w.study_type === "tracker");
  return <>
    <div className="page-head"><div>
      <h1>Every Coresight consumer survey, one place</h1>
      <p className="lede">{all.length.toLocaleString("en-US")} surveys and waves from {all.at(-1)!.wave_date.slice(0, 4)} to {all[0].wave_date.slice(0, 4)}: the weekly US consumer tracker plus annual and ad hoc studies. Open any wave for its overview, every question, cross-tabs and trends.</p>
    </div></div>
    <div className="hero">
      <Card className="latest" title={<>Latest tracker wave · {fmtDate(latest.wave_date)}</>} sub={`${latest.qualified_n.toLocaleString("en-US")} qualified US adults`}>
        <div className="hero-wave-title">{latest.title}</div>
        <div>{(latest.modules ?? []).map(m => <span key={m} className="tag">{m}</span>)}</div>
        <p style={{ marginTop: 14 }}><Link className="btn primary" to={`/w/${latest.survey_id}`}>Open this wave</Link>{" "}
          <Link className="btn" to={`/w/${latest.survey_id}/changes`}>What changed this week</Link></p>
      </Card>
      <div className="grid g2">
        <div className="card kpi lead"><div className="k-label">Weekly tracker waves</div><div className="k-value">{trackers.length}</div><div className="k-note">since {fmtDate(trackers.at(-1)!.wave_date)}</div></div>
        <div className="card kpi"><div className="k-label">Annual and ad hoc studies</div><div className="k-value">{all.length - trackers.length}</div><div className="k-note">{years.length} years of archive</div></div>
        <div className="card kpi"><div className="k-label">Respondents, all waves</div><div className="k-value">{(all.reduce((a, w) => a + w.qualified_n, 0) / 1000).toFixed(0)}k</div><div className="k-note">qualified</div></div>
        <Link className="card kpi" to="/search"><div className="k-label">Find any question</div><div className="k-value" style={{ fontSize: 22 }}>Search →</div><div className="k-note">across every wave</div></Link>
      </div>
    </div>
    <Card>
      <div className="toolbar">
        <div className="seg" role="group" aria-label="Study type">
          {["all", "tracker", "annual", "adhoc"].map(k => <button key={k} aria-pressed={kind === k} onClick={() => set("kind", k)}>{k === "all" ? "All" : KIND[k]}</button>)}
        </div>
        <label className="sr-only" htmlFor="year">Year</label>
        <select id="year" value={year} onChange={e => set("year", e.target.value)}>
          <option value="all">All years</option>{years.map(y => <option key={y}>{y}</option>)}
        </select>
        <label className="sr-only" htmlFor="lib-filter">Filter surveys</label>
        <div style={{ position: "relative", flex: 1, minWidth: 220, display: "flex", alignItems: "center" }}>
          <input
            id="lib-filter"
            className="field"
            style={{ width: "100%", paddingRight: text ? 28 : 10 }}
            value={text}
            placeholder="Filter by title, module or date…"
            onChange={e => { setText(e.target.value); set("q", e.target.value); }}
          />
          {text && (
            <button
              type="button"
              onClick={() => { setText(""); set("q", ""); }}
              aria-label="Clear filter"
              style={{
                position: "absolute",
                right: 6,
                background: "transparent",
                border: 0,
                color: "var(--ink-2)",
                cursor: "pointer",
                padding: "4px 6px",
                fontSize: 13,
                lineHeight: 1
              }}
            >
              ✕
            </button>
          )}
        </div>
        <span className="muted">{shown.length} shown</span>
      </div>
      <div className="wave-list">
        {[...byYear].map(([y, ws]) => <div key={y}>
          <h2 className="year-head">{y} · {ws.length} {ws.length === 1 ? "wave" : "waves"}</h2>
          {ws.map(w => w.rows_built === 0 ? <div key={w.survey_id} className="wave-row empty" title="Registered, but no results are built for this wave yet">
            <span className="date">{fmtDate(w.wave_date)}</span><span className="title"><span>{w.title}</span></span>
            <span className="muted">No results loaded</span><span className="n">n={w.qualified_n.toLocaleString("en-US")}</span><span /></div>
          : <div key={w.survey_id} className="wave-row">
            <span className="date">{fmtDate(w.wave_date)}</span>
            <span className="title">
              <Link to={`/w/${w.survey_id}`} className="wave-title-link">{w.title}</Link>
              <small className="tags">{(w.modules ?? []).slice(0, 4).map(m => <span key={m} className="tag">{m}</span>)}</small>
            </span>
            <span className="muted">{KIND[w.study_type] ?? w.study_type}</span>
            <span className="n">n={w.qualified_n.toLocaleString("en-US")}</span>
            <span className="wave-actions">
              <Link to={`/w/${w.survey_id}`} className="btn-chip" title="Wave overview">Overview</Link>
              <Link to={`/w/${w.survey_id}/changes`} className="btn-chip" title="What changed this wave">Changes</Link>
              <Link to={`/w/${w.survey_id}/questions`} className="btn-chip" title="Question explorer">Questions</Link>
            </span>
          </div>)}
        </div>)}
        {!shown.length && (
          <div style={{ textAlign: "center", padding: "36px 16px" }}>
            <p className="muted" style={{ margin: "0 0 12px" }}>No survey matches these filters.</p>
            <button className="btn" onClick={() => { setText(""); setParams({}); }}>Reset all filters</button>
          </div>
        )}
      </div>
    </Card>
  </>;
}
