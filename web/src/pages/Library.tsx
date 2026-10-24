// Every survey and wave: the latest tracker wave first, then the archive grouped by year, filterable.
import CountUp from "../components/CountUp";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { bookOf, queries, send, useAlerts, useTeamViews, useWaves } from "../api";
import type { Alert, TeamView } from "../api";
import { Card, deleteLater, Empty, Failure, population, SkeletonScreen } from "../components/bits";
import { removeView, savedViews } from "../saved";
import { fmtDate } from "../stats";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { X } from "lucide-react";

const KIND: Record<string, string> = { tracker: "Weekly tracker", annual: "Annual study", adhoc: "Ad hoc study" };
const PLATFORM: Record<string, string> = { forsta: "Forsta", qualtrics: "Qualtrics", surveymonkey: "SurveyMonkey" };

export default function Library() {
  const { data: waves, isLoading, error } = useWaves();
  const [params, setParams] = useSearchParams();
  const kind = KIND[params.get("kind") ?? ""] ? params.get("kind")! : "all", year = params.get("year") ?? "all", event = params.get("event") ?? "all";
  const [text, setText] = useState(params.get("q") ?? "");
  const [saved, setSaved] = useState(savedViews);
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v === "all" || !v ? p.delete(k) : p.set(k, v); setParams(p, { replace: true }); };
  const years = useMemo(() => [...new Set((waves ?? []).map(w => w.wave_date.slice(0, 4)))].sort((a, b) => b.localeCompare(a)), [waves]);
  const events = useMemo(() => [...new Set((waves ?? []).flatMap(w => w.events ?? []))].sort(), [waves]);
  const shown = useMemo(() => {
    const words = text.toLowerCase().split(/\s+/).filter(Boolean);
    return (waves ?? []).filter(w => (kind === "all" || w.study_type === kind) && (year === "all" || w.wave_date.startsWith(year)) &&
      (event === "all" || (w.events ?? []).includes(event)) &&
      words.every(t => `${w.title} ${w.survey_family} ${(w.modules ?? []).join(" ")} ${(w.events ?? []).join(" ")} ${w.wave_date}`.toLowerCase().includes(t)));
  }, [waves, kind, year, event, text]);
  const latest = waves?.find(w => w.study_type === "tracker" && w.rows_built !== 0) ?? waves?.[0];
  // the wave most people open next: its book is fetched while this screen is idle (≈ 20 KB, cached 5 min)
  useEffect(() => { if (latest) void queries.prefetchQuery({ queryKey: ["book", latest.survey_id, false], queryFn: () => bookOf(latest.survey_id), staleTime: 5 * 60_000 }); }, [latest]);
  if (isLoading) return <SkeletonScreen kind="library" />;
  if (error) return <Failure error={error} />;
  const all = waves!;
  if (!latest) return <><div className="page-head"><div><h1>Survey library</h1></div></div>
    <Empty>No surveys are available to you yet. When a survey is published for your account it appears here.</Empty></>;
  const byYear = new Map<string, typeof shown>();
  for (const w of shown) byYear.set(w.wave_date.slice(0, 4), [...(byYear.get(w.wave_date.slice(0, 4)) ?? []), w]);
  const trackers = all.filter(w => w.study_type === "tracker");
  return <>
    <div className="page-head"><div>
      <h1>Every Coresight consumer survey, one place</h1>
      <p className="lede">{all.length.toLocaleString("en-US")} surveys and waves{all.length ? ` from ${all.at(-1)!.wave_date.slice(0, 4)} to ${all[0].wave_date.slice(0, 4)}` : ""}: the weekly US consumer tracker plus annual and ad hoc studies. Open any wave for its overview, every question, cross-tabs and trends.</p>
    </div></div>
    <div className="hero">
      <Card className="latest" title={<>Latest {latest.study_type === "tracker" ? "tracker " : ""}wave · {fmtDate(latest.wave_date)}</>} sub={`${latest.qualified_n.toLocaleString("en-US")} qualified · ${population(latest)}`}>
        <div className="hero-wave-title">{latest.title}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "6px 0" }}>
          {(latest.modules ?? []).map(m => (
            <span key={m} className="tag">{m}</span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          <Link className={buttonVariants({ variant: "default" })} to={`/w/${latest.survey_id}`}>
            Open this wave
          </Link>
          <Link className={buttonVariants({ variant: "outline" })} to={`/w/${latest.survey_id}/changes`}>
            {latest.study_type === "tracker" ? "What changed this week" : "What changed"}
          </Link>
        </div>
      </Card>
      <div className="grid g2">
        <div className="card kpi lead"><div className="k-label">Weekly tracker waves</div><div className="k-value"><CountUp text={String(trackers.length)} /></div><div className="k-note">{trackers.length ? `since ${fmtDate(trackers.at(-1)!.wave_date)}` : "none yet"}</div></div>
        <div className="card kpi"><div className="k-label">Annual and ad hoc studies</div><div className="k-value"><CountUp text={String(all.length - trackers.length)} /></div><div className="k-note">{years.length} years of archive</div></div>
        <div className="card kpi"><div className="k-label">Respondents, all waves</div><div className="k-value"><CountUp text={`${(all.reduce((a, w) => a + w.qualified_n, 0) / 1000).toFixed(0)}k`} /></div><div className="k-note">qualified</div></div>
        <Link className="card kpi" to="/search"><div className="k-label">Find any question</div><div className="k-value" style={{ fontSize: 22 }}>Search →</div><div className="k-note">across every wave</div></Link>
      </div>
    </div>
    <TeamSaved />
    <TeamAlerts />
    {saved.length > 0 && <Card title="Your saved views" sub="Saved in this browser with the bookmark button at the top. Copy link on any screen shares one.">
      <ul className="saved-views">{saved.map(v => <li key={v.url}>
        <Link to={v.url}>{v.name}</Link><small className="muted">{fmtDate(v.saved.slice(0, 10))}</small>
        <Button variant="ghost" size="xs" onClick={() => { removeView(v.url); setSaved(savedViews()); }} aria-label={`Remove ${v.name}`}>Remove</Button>
      </li>)}</ul>
    </Card>}
    <Card>
      <div className="toolbar" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Tabs value={kind} onValueChange={k => set("kind", k)}>
          <TabsList>
            {["all", "tracker", "annual", "adhoc"].map(k => (
              <TabsTrigger key={k} value={k}>
                {k === "all" ? "All" : KIND[k]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <label className="sr-only" htmlFor="year">Year</label>
        <select id="year" value={year} onChange={e => set("year", e.target.value)}>
          <option value="all">All years</option>{years.map(y => <option key={y}>{y}</option>)}
        </select>
        <label className="sr-only" htmlFor="event">Recurring retail event named in the survey title</label>
        <select id="event" value={event} onChange={e => set("event", e.target.value)}>
          <option value="all">All events</option>{events.map(e => <option key={e}>{e}</option>)}
        </select>
        <label className="sr-only" htmlFor="lib-filter">Filter surveys</label>
        <div style={{ position: "relative", flex: 1, minWidth: 220, display: "flex", alignItems: "center" }}>
          <Input
            id="lib-filter"
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
                padding: "4px",
                display: "inline-flex",
                alignItems: "center"
              }}
            >
              <X size={14} />
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
              <small className="tags">{(w.events ?? []).map(e => <span key={e} className="tag event">{e}</span>)}{(w.modules ?? []).slice(0, 4).map(m => <span key={m} className="tag">{m}</span>)}</small>
            </span>
            <span className="muted">{KIND[w.study_type] ?? w.study_type}{w.platform ? <><br /><small>{PLATFORM[w.platform]}</small></> : null}</span>
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
            <Button variant="outline" size="sm" onClick={() => { setText(""); setParams({}); }}>Reset all filters</Button>
          </div>
        )}
      </div>
    </Card>
  </>;
}

/** What anyone on the team saved with the bookmark button: open it, or remove it. */
/** Hide a team item now; it is deleted after a few seconds unless undone (bits.tsx UndoBar). */
function removeLater<T>(key: string, what: string, url: string, keep: (x: T) => boolean) {
  queries.setQueryData<T[]>([key], list => list?.filter(keep));
  deleteLater({ what, run: () => send("DELETE", url).finally(() => queries.invalidateQueries({ queryKey: [key] })),
                undo: () => void queries.invalidateQueries({ queryKey: [key] }) });
}

function TeamSaved() {
  const { data } = useTeamViews();
  if (!data?.length) return null;
  return <Card title="Team saved views" sub="Saved by anyone on the team with the bookmark button at the top of a screen">
    <ul className="saved-views">{data.map(v => <li key={v.view_id}>
      <Link to={v.url}>{v.name}</Link><small className="muted">{v.saved_by} · {fmtDate(v.created_at.slice(0, 10))}</small>
      <Button variant="ghost" size="xs" onClick={() => removeLater<TeamView>("team-views", `Saved view “${v.name}”`, `/api/v1/team/views/${v.view_id}`, x => x.view_id !== v.view_id)} aria-label={`Remove ${v.name}`}>Remove</Button>
    </li>)}</ul>
  </Card>;
}

/** The team's metric alerts: each fires a Teams message once per new wave when its answer moves significantly. */
function TeamAlerts() {
  const { data } = useAlerts();
  if (!data?.length) return null;
  return <Card title="Team alerts" sub="Set with “Alert me” under any question. The pipeline checks each one when a new wave loads and posts to Teams when the answer moves significantly.">
    <ul className="saved-views">{data.map(a => <li key={a.alert_id}>
      <span>{a.name}{a.dim !== "total" ? ` · ${a.dim_value}` : ""} <small className="muted">vs {a.against === "ly" ? "last year" : "the previous wave"}</small></span>
      <small className="muted">{a.created_by}{a.last_fired ? ` · last fired on wave ${a.last_fired}` : ""}</small>
      <button className="btn-chip" onClick={() => removeLater<Alert>("alerts", `Alert “${a.name}”`, `/api/v1/alerts/${a.alert_id}`, x => x.alert_id !== a.alert_id)} aria-label={`Remove ${a.name}`}>Remove</button>
    </li>)}</ul>
  </Card>;
}
