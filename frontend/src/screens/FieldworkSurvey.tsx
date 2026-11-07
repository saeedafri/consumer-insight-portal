// One survey's fieldwork (/app/fieldwork/<Forsta path>), opened from a row of the Fieldwork list (Fieldwork.tsx): its
// name and dates, the funnel with what each number means, why respondents dropped out (the reason, where in the survey,
// and the cause Forsta recorded: the screen-out rule, the full quota cell, or the page people left on), the quota
// cells, finished interviews hour by hour, and Forsta's audit log. Everything comes from the same published file as the
// list (etl/fieldwork.py: summary and explain); this screen only draws. Every table scrolls inside its card.
import { Link, useParams } from "react-router";
import type { FieldworkSurvey as Survey } from "../api";
import { Card, count, day, Empty, ExportButtons, ist } from "../components/bits";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { downloadTable } from "../csv";
import { C } from "../theme";
import { SOURCE, useRecord } from "./Fieldwork";

const REASON: Record<string, string> = { Terminated: "Terminated", Overquota: "Over quota", Dropped: "Dropped out" };
const share = (part: number | null | undefined, whole: number | null | undefined) =>
  part == null || !whole ? "–" : `${(100 * part / whole).toFixed(1)}%`;

export default function FieldworkSurvey() {
  const { survey: path = "" } = useParams();
  const { data, full, problem } = useRecord();
  if (problem || !data) return problem;
  const survey = data.surveys.find(s => s.path === path);
  if (!survey) return <Empty>No fieldwork record for {path}. <Link to="/fieldwork">Back to every survey</Link></Empty>;
  return <div className="stack">
    <div className="page-head"><div>
      <p className="eyebrow"><Link to="/fieldwork">Fieldwork</Link> · {survey.path}</p>
      <h1>{survey.title ?? survey.path}</h1>
      <p className="lede">Launched {day(survey.launched)}{survey.closed ? `, closed ${day(survey.closed)}` : survey.state === "live" ? ", still in the field" : ""}
        {survey.wave_date ? ` · wave of ${day(survey.wave_date)}` : ""}{survey.survey_id ? <> · <Link to={`/w/${survey.survey_id}`}>open the wave</Link></> : null}
        {survey.hibernated && <> · <span className="chip warn">hibernated in Forsta</span></>}</p>
    </div></div>
    <Funnel survey={survey} />
    <Reasons survey={survey} />
    <div className="grid g2">
      <QuotaCells survey={survey} />
      <Hours survey={survey} />
    </div>
    <Pages survey={survey} />
    <Timeline survey={survey} full={full} />
    <Details survey={survey} />
  </div>;
}

/** The five numbers, each with what it counts and its share of everyone who opened the survey. */
function Funnel({ survey: s }: { survey: Survey }) {
  const parts: [string, number | null, string][] = [
    ["Opened", s.opened, "Opened the first page (Forsta: click-through). Every one ends in exactly one of the four below."],
    ["Qualified", s.qualified, "Finished the whole interview and fit the sample: these are the answers CIP shows."],
    ["Terminated", s.terminated, "Screened out by a rule in the questionnaire, e.g. answering too fast (a speeder)."],
    ["Over quota", s.overquota, "Fit the survey, but their group (a gender, a region, an income band) was already full."],
    ["Dropped out", s.partial, "Opened the survey and left before the end (Forsta: partial)."],
  ];
  return <div className="grid g5 funnel-kpis">{parts.map(([label, value, meaning], i) => <div key={label} className={`card kpi${i === 1 ? " lead" : ""}`}>
    <div className="k-label">{label}</div>
    <div className="k-value">{count(value)}</div>
    <div className="k-note">{i ? `${share(value, s.opened)} of opened · ` : ""}{meaning}</div>
  </div>)}</div>;
}

/** Why each person who did not qualify left: terminated and over quota from the cause Forsta wrote on each record,
 *  dropped out from the page they left on. */
function Reasons({ survey: s }: { survey: Survey }) {
  const rows: [string, string, string, number, number | null][] = [
    ...(s.causes ?? []).map(([status, cause, where, people, minutes]) => [status, cause, where, people, minutes] as [string, string, string, number, number | null]),
    ...s.pages.filter(p => p[4] > 0).map(([code, text, , , dropped, seconds]) =>
      ["Dropped", "Closed the survey or stopped answering on this page", `${code}: ${text}`, dropped, seconds == null ? null : +(seconds / 60).toFixed(1)] as [string, string, string, number, number | null]),
  ].sort((a, b) => b[3] - a[3]);
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `Why respondents dropped out - ${s.path}`,
    ["Reason", "Cause", "Where in the survey", "People", "Share of opened %", "Average minutes"],
    rows.map(([status, cause, where, people, minutes]) => [REASON[status] ?? status, cause, where, people, s.opened ? +(100 * people / s.opened).toFixed(1) : null, minutes]),
    [`Why respondents dropped out: ${s.title ?? s.path}`, SOURCE]);
  const counted = rows.reduce((t, r) => t + r[3], 0);
  return <Card title="Why respondents dropped out"
               sub={`Everyone who opened the survey and did not qualify: ${count(counted)} people here; Forsta's funnel counts ${count((s.opened ?? 0) - (s.qualified ?? 0))} ` +
                 "(the two can differ by a few when Forsta's summary and its data export disagree). " +
                 "Terminated and over quota come from the rule or quota cell Forsta recorded on each person; dropped out from the page they left on (average minutes there)."}
               aside={rows.length ? <ExportButtons onExport={exportTable} /> : undefined}>
    {rows.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Reason</th><th>Cause</th><th>Where in the survey</th><th className="num">People</th><th className="num">Of opened</th><th className="num">Avg. minutes</th></tr></thead>
      <tbody>{rows.map(([status, cause, where, people, minutes], i) => <tr key={i}>
        <td><span className={`chip ${status === "Terminated" ? "sig" : status === "Overquota" ? "flat" : "warn"}`}>{REASON[status] ?? status}</span></td>
        <th scope="row">{cause}</th><td title={where}>{where.length > 80 ? where.slice(0, 80) + "…" : where}</td>
        <td className="num">{count(people)}</td><td className="num">{share(people, s.opened)}</td><td className="num">{minutes ?? "–"}</td>
      </tr>)}</tbody>
    </table></div> : <Empty>{s.hibernated ? "Hibernated in Forsta: its records cannot be read until it is woken." : "No reasons recorded for this survey."}</Empty>}
  </Card>;
}

/** Each quota cell: its limit, the completes it took, and how many it turned away once full. */
function QuotaCells({ survey: s }: { survey: Survey }) {
  const cells = s.quota_cells ?? [];
  return <Card title="Quota cells" sub="A full cell turns the next people in that group away: they count as over quota.">
    {cells.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Quota</th><th>Cell</th><th className="num">Limit</th><th className="num">Completes</th><th className="num">Turned away</th></tr></thead>
      <tbody>{cells.map(([sheet, cell, limit, done, away], i) => <tr key={i} className={away ? undefined : "past"}>
        <td>{sheet}</td><th scope="row">{cell}</th><td className="num">{count(limit)}</td><td className="num">{count(done)}</td><td className="num">{count(away)}</td>
      </tr>)}</tbody>
    </table></div> : <Empty>No quotas defined in Forsta for this survey.</Empty>}
  </Card>;
}

/** Finished interviews hour by hour, stacked by outcome (drop-outs are not in Forsta's export, so not here). */
function Hours({ survey: s }: { survey: Survey }) {
  const hours = s.hours ?? [];
  if (!hours.length) return <Card title="Fieldwork hour by hour"><Empty>No interviews loaded for this survey.</Empty></Card>;
  const build = () => ({
    tooltip: { ...tooltip(), trigger: "axis" }, legend: { bottom: 0, textStyle: axisText() },
    grid: { left: 44, right: 12, top: 12, bottom: 56 },
    xAxis: { type: "category", data: hours.map(h => h[0].slice(5, 13).replace("T", " ") + "h"), axisLabel: axisText() },
    yAxis: { type: "value", axisLabel: valueText() },
    series: [["Qualified", 1, C.green], ["Terminated", 2, C.red], ["Over quota", 3, C.ink3]].map(([name, i, color]) =>
      ({ name, type: "bar", stack: "all", data: hours.map(h => h[i as number]), itemStyle: { color } })),
  });
  return <Card title="Fieldwork hour by hour" sub="Finished interviews per hour by Forsta's clock, by outcome. Drop-outs are not in Forsta's data export, so they are not counted here.">
    <EChart option={build()} build={build} height={280} label="Finished interviews per hour by outcome" />
  </Card>;
}

/** The survey's pages in order: how many reached each, how many left there, and the seconds spent on it. */
function Pages({ survey }: { survey: Survey }) {
  if (!survey.pages.length) return null;
  const most = Math.max(...survey.pages.map(p => p[4]));
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `Drop-outs by page - ${survey.path}`,
    ["Question", "Wording", "Reached the page", "Went on", "Dropped out", "Dropped %", "Average seconds"],
    survey.pages.map(([code, text, started, submitted, dropped, seconds]) => [code, text, started, submitted, dropped, started ? +(100 * dropped / started).toFixed(1) : null, seconds && +seconds.toFixed(1)]),
    [`Drop-outs by page: ${survey.title ?? survey.path}`, SOURCE]);
  return <Card title="Page by page" sub={`Everyone who reached each page, in questionnaire order: ${count(survey.partial)} dropped out in all. Terminated and over-quota people also stop reaching pages, so "reached" falls faster than the drop-outs alone.`}
               aside={<ExportButtons onExport={exportTable} />}>
    <div className="table-wrap fieldwork-scroll tall"><table className="data report-table">
      <thead><tr><th>Question</th><th className="num">Reached</th><th className="num">Dropped out</th><th className="num">Dropped %</th><th className="num">Average time</th></tr></thead>
      <tbody>{survey.pages.map(([code, text, started, , dropped, seconds], i) => <tr key={i}>
        <th scope="row" title={text}><b>{code}</b> <span className="muted">{text.length > 70 ? text.slice(0, 70) + "…" : text}</span></th>
        <td className="num">{count(started)}</td>
        <td className="num"><span className="vs-bar actual" style={{ width: most ? 80 * dropped / most : 0 }} />{count(dropped)}</td>
        <td className="num">{started ? `${(100 * dropped / started).toFixed(1)}%` : "–"}</td>
        <td className="num">{seconds == null ? "–" : `${seconds.toFixed(0)} s`}</td>
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** What happened to the survey, from Forsta's audit log (launched, closed, edited, permissions; not the reads), and the
 *  screen-out rules behind "terminated". Forsta user emails are shown to admins only. */
function Timeline({ survey, full }: { survey: Survey; full: boolean }) {
  const events = survey.timeline ?? [], terms = survey.terms ?? [];
  if (!events.length && !terms.length) return null;
  return <div className="grid g2">
    {events.length > 0 && <Card title="Survey timeline" sub={`From Forsta's audit log: launches, closes, edits${full ? ", permission changes and who made them" : " and permission changes"} (reads left out).`}>
      <ol className="timeline">{events.map(([when, who, what], i) => <li key={i}>
        <time dateTime={when}>{ist(when)}</time><span>{what}</span>{who && <span className="muted">{who}</span>}
      </li>)}</ol>
    </Card>}
    {terms.length > 0 && <Card title="Screen-out rules" sub="The terms in the questionnaire: a respondent who meets one is terminated.">
      <ul className="terms">{terms.map(([label, description], i) => <li key={i}><b>{label}</b> {description}</li>)}</ul>
    </Card>}
  </div>;
}

/** What else Forsta holds about the survey: its category, saved reports, archive check, tasks, layouts and sources. */
function Details({ survey }: { survey: Survey }) {
  const saved = survey.saved_reports ?? [];
  return <Card title="In Forsta" sub="Read from Forsta without changing anything.">
    <dl className="details">
      <div><dt>Category</dt><dd>{survey.category || "–"}</dd></div>
      <div><dt>Can be archived</dt><dd>{survey.can_archive || "–"}</dd></div>
      <div><dt>Open tasks</dt><dd>{count(survey.tasks)}</dd></div>
      <div><dt>Data layouts · data sources</dt><dd>{count(survey.layouts)} · {count(survey.datasources)}</dd></div>
      <div><dt>Median interview</dt><dd>{survey.median_minutes == null ? "–" : `${survey.median_minutes} minutes (qualified people)`}</dd></div>
      <div><dt>Questions shown on a condition</dt><dd>{survey.conditions == null ? "questionnaire not kept yet" : <>{survey.conditions}
        {survey.survey_id && <> · <Link to={`/w/${survey.survey_id}/survey`}>see them on the Survey preview</Link></>}</>}</dd></div>
    </dl>
    {saved.length > 0 && <>
      <h3 className="details-head">Saved reports in Forsta</h3>
      <ul className="terms">{saved.map(([title, updated, access], i) => <li key={i}><b>{title || "Untitled"}</b> <span className="muted">{[updated && `updated ${day(updated)}`, access].filter(Boolean).join(" · ")}</span></li>)}</ul>
    </>}
  </Card>;
}
