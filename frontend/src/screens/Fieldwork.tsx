// Fieldwork (/app/fieldwork): every survey's funnel as Forsta recorded it, and when Forsta will delete the archived ones.
// Built by the ETL from read-only Forsta calls (etl/fieldwork.py): admins read GET /api/v1/admin/fieldwork (everything);
// a role the super admin turned "fieldwork" on for (the Access page) reads GET /api/v1/fieldwork (no deletion schedule,
// no Forsta user emails). A survey's row opens its own page (FieldworkSurvey.tsx): why people dropped out, the quota
// cells, the timelines. Opened from the left menu ("Fieldwork"). This screen only draws.
import { Link, useNavigate } from "react-router";
import { useFieldwork, useMe } from "../api";
import type { FieldworkRecord, FieldworkSurvey } from "../api";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import { fmtDate } from "../stats";

export const n = (v: number | null | undefined) => v == null ? "–" : v.toLocaleString("en-US");
export const day = (iso: string | null | undefined) => iso ? fmtDate(iso.slice(0, 10)) : "–";
export const SOURCE = "Source: Forsta (read-only), kept by CIP";

/** The record for this person (admins: everything), or what to say when it is not there or not theirs. */
export function useRecord() {
  const { data: me } = useMe();
  const full = !!me?.permissions?.includes("admin_pages");
  const { data, isLoading, error } = useFieldwork(full);
  const status = (error as { status?: number } | null)?.status;
  const problem = isLoading || !me ? <SkeletonScreen kind="page" />
    : status === 404 || (error as Error | null)?.message?.includes("No fieldwork") ? <Empty>No fieldwork record yet. The next Forsta run collects it.</Empty>
    : status === 403 || (error as Error | null)?.message?.includes("subscription") ? <Empty>{String((error as Error).message)}. Fieldwork is shown to admins, and to the roles the super admin turns it on for (the Access page). With the demo sign-in, an admin enters the admin token on the Logs page first.</Empty>
    : error || !data ? <Failure error={error} /> : null;
  return { data, full, problem };
}
const PLANNED: Record<string, string> = { autoclose_planned: "automatic closes", archives_planned: "planned archive actions",
  archives_scheduled: "surveys scheduled for archiving", archives_deleted: "surveys already deleted" };

export default function Fieldwork() {
  const { data, problem } = useRecord();
  if (problem || !data) return problem;
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Fieldwork</h1>
      <p className="lede">How each survey's fieldwork went, as Forsta recorded it: who opened it, who was screened out or over quota,
        where people dropped out, and how long the interview took. Read from Forsta without changing anything, and kept by CIP, because
        Forsta deletes an archived survey a year after archiving it. What each number means: <Link to="/methodology#fieldwork-terms">Methodology</Link>.</p>
    </div></div>
    <Surveys surveys={data.surveys} />
    <Archive record={data} />
    <NotLoaded record={data} />
  </div>;
}

/** Forsta's deletion schedule: every archived survey, when it goes, and whether CIP holds its respondents. */
function Archive({ record }: { record: FieldworkRecord }) {
  const list = record.archive;
  if (!list.length) return null;
  const missing = list.filter(a => !a.held);
  const days = record.retention?.find(r => r.server_delete_days)?.server_delete_days;   // the company's rule in Forsta
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Forsta deletion schedule",
    ["Survey", "Forsta path", "Archived", "Deleted by Forsta", "Respondents held in CIP"],
    list.map(a => [a.name, a.path, a.archived_at?.slice(0, 10), a.delete_at?.slice(0, 10), a.held ? "yes" : "no"]), ["Forsta's archived surveys", SOURCE]);
  return <Card title="Forsta's deletion schedule"
               sub={`${list.length} archived surveys, deleted by Forsta between ${day(list[0].delete_at)} and ${day(list.at(-1)!.delete_at)}. ` +
                 (missing.length ? `${list.length - missing.length} are held in CIP; ${missing.length} are not (listed first).` : "Every one is held in CIP.") +
                 (days ? ` Forsta's retention rule for the company: deleted ${days} days after archiving.` : "")}
               aside={<ExportButtons onExport={exportTable} />}>
    <p className="muted" style={{ marginBottom: 12 }}>{record.planned?.length
      ? `Planned by Forsta: ${record.planned.map(p => `${p.items.length} ${PLANNED[p.kind] ?? p.kind}`).join(", ")}.`
      : "Nothing planned by Forsta: no automatic closes, archives or deletions are scheduled beyond the dates below."}</p>
    <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Survey</th><th>Forsta path</th><th className="num">Archived</th><th className="num">Deleted by Forsta</th><th>In CIP</th></tr></thead>
      <tbody>{[...missing, ...list.filter(a => a.held)].map(a => <tr key={a.path}>
        <th scope="row">{a.name ?? a.path}</th><td>{a.path}</td><td className="num">{day(a.archived_at)}</td><td className="num">{day(a.delete_at)}</td>
        <td>{a.held ? <span className="chip flat">held</span> : <span className="chip warn">not held</span>}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** Every survey with a kept record, newest first: its funnel in one row, the table scrolling inside its card. A row
 *  opens the survey's own page. */
function Surveys({ surveys }: { surveys: FieldworkSurvey[] }) {
  const navigate = useNavigate();
  const open = (path: string) => navigate(`/fieldwork/${encodeURIComponent(path)}`);
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Fieldwork by survey",
    ["Survey", "Forsta path", "Launched", "Opened", "Qualified", "Terminated", "Over quota", "Dropped out", "Incidence %", "Median minutes", "Blocked sessions", "Server errors"],
    surveys.map(s => [s.title, s.path, s.launched?.slice(0, 10), s.opened, s.qualified, s.terminated, s.overquota, s.partial, s.incidence, s.median_minutes,
      s.warnings.blocks ?? null, s.warnings.server_errors ?? null]), ["Fieldwork by survey", "Incidence = qualified / opened the survey", SOURCE]);
  return <Card title="Every survey's fieldwork" sub={`${surveys.length} surveys. Opened = qualified + terminated + over quota + dropped out. Incidence = qualified ÷ opened. Choose a survey to see why its respondents dropped out.`}
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="table-wrap fieldwork-scroll tall"><table className="data report-table fieldwork-table">
      <thead><tr><th>Survey</th><th className="num">Launched</th><th className="num">Opened</th><th className="num">Qualified</th><th className="num">Terminated</th>
        <th className="num">Over quota</th><th className="num">Dropped out</th><th className="num">Incidence</th><th className="num">Median length</th><th className="num">Warnings</th></tr></thead>
      <tbody>{surveys.map(s => <tr key={s.path} className="clickable" onClick={() => open(s.path)}>
        <th scope="row"><button className="link-button" onClick={e => { e.stopPropagation(); open(s.path); }}>{s.title ?? s.path}</button>
          {s.hibernated && <span className="chip warn">hibernated</span>}{s.state === "live" && <span className="chip sig">in the field</span>}</th>
        <td className="num">{day(s.launched)}</td><td className="num">{n(s.opened)}</td><td className="num">{n(s.qualified)}</td><td className="num">{n(s.terminated)}</td>
        <td className="num">{n(s.overquota)}</td><td className="num">{n(s.partial)}</td><td className="num">{s.incidence == null ? "–" : `${s.incidence}%`}</td>
        <td className="num">{s.median_minutes == null ? "–" : `${s.median_minutes} min`}</td>
        <td className="num" title="Blocked sessions, server errors and exceptions Forsta logged">{n((s.warnings.blocks ?? 0) + (s.warnings.server_errors ?? 0) + (s.warnings.exceptions ?? 0))}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** The surveys Forsta's history has that CIP has not loaded: test surveys, or one the load missed. */
function NotLoaded({ record }: { record: FieldworkRecord }) {
  const list = record.not_loaded ?? [];
  if (!list.length) return null;
  return <Card title="In Forsta, not in CIP" sub={`${list.length} surveys in Forsta's history that CIP has not loaded: usually test copies; anything else is worth a look.`}>
    <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Survey</th><th>Forsta path</th><th>State in Forsta</th></tr></thead>
      <tbody>{list.map(n => <tr key={n.path}><th scope="row">{n.title ?? "–"}</th><td>{n.path}</td><td>{n.state ?? "not in the register"}</td></tr>)}</tbody>
    </table></div>
  </Card>;
}
