// Fieldwork (/app/fieldwork, admins only): how each survey's fieldwork went, as Forsta recorded it, and when Forsta
// will delete the archived ones. Built by the ETL from read-only Forsta calls (etl/fieldwork.py → GET
// /api/v1/admin/fieldwork): the funnel (opened, terminated, over quota, dropped out, qualified), the interview length,
// the warnings, and page by page where respondents dropped out. This screen only draws.
// Opened from the left menu ("Fieldwork", shown to admins next to Logs); the chosen survey is kept in the address.
import { useSearchParams } from "react-router";
import { useFieldwork } from "../api";
import type { FieldworkRecord, FieldworkSurvey } from "../api";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import { fmtDate } from "../stats";

const n = (v: number | null | undefined) => v == null ? "–" : v.toLocaleString("en-US");
const day = (iso: string | null | undefined) => iso ? fmtDate(iso.slice(0, 10)) : "–";
const SOURCE = "Source: Forsta (read-only), kept by CIP";

export default function Fieldwork() {
  const { data, isLoading, error } = useFieldwork();
  const [params, setParams] = useSearchParams();
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404)
    return <Empty>No fieldwork record yet. The next Forsta run collects it, for the surveys it loads and a few older ones each time.</Empty>;
  if ((error as { status?: number } | null)?.status === 403)
    return <Empty>{String((error as Error).message)}. While sign-in is the demo, enter the admin token on the Logs page first; it is kept for this browser.</Empty>;
  if (error || !data) return <Failure error={error} />;
  const shown = data.surveys.find(s => s.path === params.get("survey")) ?? data.surveys[0];
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Fieldwork</h1>
      <p className="lede">How each survey's fieldwork went, as Forsta recorded it: who opened it, who was screened out or over quota,
        where people dropped out, and how long the interview took. Read from Forsta without changing anything, and kept by CIP, because
        Forsta deletes an archived survey a year after archiving it.</p>
    </div></div>
    <Archive record={data} />
    <Surveys surveys={data.surveys} shown={shown} pick={path => setParams({ survey: path }, { replace: true })} />
    {shown && <Dropouts survey={shown} />}
  </div>;
}

/** Forsta's deletion schedule: every archived survey, when it goes, and whether CIP holds its respondents. */
function Archive({ record }: { record: FieldworkRecord }) {
  const list = record.archive;
  if (!list.length) return null;
  const missing = list.filter(a => !a.held);
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Forsta deletion schedule",
    ["Survey", "Forsta path", "Archived", "Deleted by Forsta", "Respondents held in CIP"],
    list.map(a => [a.name, a.path, a.archived_at?.slice(0, 10), a.delete_at?.slice(0, 10), a.held ? "yes" : "no"]), ["Forsta's archived surveys", SOURCE]);
  return <Card title="Forsta's deletion schedule"
               sub={`${list.length} archived surveys, deleted by Forsta between ${day(list[0].delete_at)} and ${day(list.at(-1)!.delete_at)}. ` +
                 (missing.length ? `${list.length - missing.length} are held in CIP; ${missing.length} are not (listed first).` : "Every one is held in CIP.")}
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Survey</th><th>Forsta path</th><th className="num">Archived</th><th className="num">Deleted by Forsta</th><th>In CIP</th></tr></thead>
      <tbody>{[...missing, ...list.filter(a => a.held)].map(a => <tr key={a.path}>
        <th scope="row">{a.name ?? a.path}</th><td>{a.path}</td><td className="num">{day(a.archived_at)}</td><td className="num">{day(a.delete_at)}</td>
        <td>{a.held ? <span className="chip flat">held</span> : <span className="chip warn">not held</span>}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** Every survey with a kept record, newest first: its funnel in one row. A row opens its drop-out funnel below. */
function Surveys({ surveys, shown, pick }: { surveys: FieldworkSurvey[]; shown?: FieldworkSurvey; pick: (path: string) => void }) {
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Fieldwork by survey",
    ["Survey", "Forsta path", "Launched", "Opened", "Qualified", "Terminated", "Over quota", "Dropped out", "Incidence %", "Median minutes", "Blocked sessions", "Server errors"],
    surveys.map(s => [s.title, s.path, s.launched?.slice(0, 10), s.opened, s.qualified, s.terminated, s.overquota, s.partial, s.incidence, s.median_minutes,
      s.warnings.blocks ?? null, s.warnings.server_errors ?? null]), ["Fieldwork by survey", "Incidence = qualified / opened the survey", SOURCE]);
  return <Card title="Every survey's fieldwork" sub="Incidence = qualified ÷ opened the survey. Choose a survey to see where its respondents dropped out."
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="table-wrap"><table className="data report-table fieldwork-table">
      <thead><tr><th>Survey</th><th className="num">Launched</th><th className="num">Opened</th><th className="num">Qualified</th><th className="num">Terminated</th>
        <th className="num">Over quota</th><th className="num">Dropped out</th><th className="num">Incidence</th><th className="num">Median length</th><th className="num">Warnings</th></tr></thead>
      <tbody>{surveys.map(s => <tr key={s.path} className={s === shown ? "picked" : undefined}>
        <th scope="row"><button className="link-button" onClick={() => pick(s.path)} aria-pressed={s === shown}>{s.title ?? s.path}</button>
          {s.hibernated && <span className="chip warn">hibernated</span>}{s.state === "live" && <span className="chip sig">in the field</span>}</th>
        <td className="num">{day(s.launched)}</td><td className="num">{n(s.opened)}</td><td className="num">{n(s.qualified)}</td><td className="num">{n(s.terminated)}</td>
        <td className="num">{n(s.overquota)}</td><td className="num">{n(s.partial)}</td><td className="num">{s.incidence == null ? "–" : `${s.incidence}%`}</td>
        <td className="num">{s.median_minutes == null ? "–" : `${s.median_minutes} min`}</td>
        <td className="num" title="Blocked sessions, server errors and exceptions Forsta logged">{n((s.warnings.blocks ?? 0) + (s.warnings.server_errors ?? 0) + (s.warnings.exceptions ?? 0))}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** One survey's pages in order: how many reached each, how many left there, and the seconds spent on it. */
function Dropouts({ survey }: { survey: FieldworkSurvey }) {
  if (!survey.pages.length) return <Card title={`Where respondents dropped out: ${survey.title ?? survey.path}`}>
    <Empty>{survey.hibernated ? "This survey is hibernated in Forsta: its page record cannot be read until it is woken." : "Forsta has no page record for this survey."}</Empty>
  </Card>;
  const most = Math.max(...survey.pages.map(p => p[4]));
  const top = [...survey.pages].sort((a, b) => b[4] - a[4]).slice(0, 3).map(p => p[0]);
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `Drop-outs - ${survey.path}`,
    ["Question", "Wording", "Reached the page", "Went on", "Dropped out", "Dropped %", "Average seconds"],
    survey.pages.map(([code, text, started, submitted, dropped, seconds]) => [code, text, started, submitted, dropped, started ? +(100 * dropped / started).toFixed(1) : null, seconds && +seconds.toFixed(1)]),
    [`Where respondents dropped out: ${survey.title ?? survey.path}`, SOURCE]);
  return <Card title={`Where respondents dropped out: ${survey.title ?? survey.path}`}
               sub={`${n(survey.partial)} dropped out after opening the survey. The three pages that lost the most are marked.`}
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="table-wrap"><table className="data report-table">
      <thead><tr><th>Question</th><th className="num">Reached</th><th className="num">Dropped out</th><th className="num">Dropped %</th><th className="num">Average time</th></tr></thead>
      <tbody>{survey.pages.map(([code, text, started, , dropped, seconds], i) => <tr key={i} className={top.includes(code) && dropped ? "picked" : undefined}>
        <th scope="row" title={text}><b>{code}</b> <span className="muted">{text.length > 70 ? text.slice(0, 70) + "…" : text}</span></th>
        <td className="num">{n(started)}</td>
        <td className="num"><span className="vs-bar actual" style={{ width: most ? 80 * dropped / most : 0 }} />{n(dropped)}</td>
        <td className="num">{started ? `${(100 * dropped / started).toFixed(1)}%` : "–"}</td>
        <td className="num">{seconds == null ? "–" : `${seconds.toFixed(0)} s`}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}
