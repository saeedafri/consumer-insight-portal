// The Forsta admin screens (/app/forsta/<section>, admins only): everything Forsta gives CIP that is not a survey's
// answers, grouped the way a research team looks for it. Each section is a link in the left menu's "Forsta" group
// (components/Shell.tsx, from forstaSections.ts):
//   reports    the team's saved Forsta reports, run by Forsta (a read-only POST) with the Excel, PDF and PowerPoint
//              files Forsta exported, or Forsta's reason it could not
//   check      Forsta's own cross-tab of every question against CIP's figures, cell by cell
//   crosstab   the team's cross-tab banners and the company's cross-tab defaults
//   samples    the funnel by sample source, operating system, browser and mobile device
//   warnings   every survey's warnings, one survey's warning events, and its launch checks
//   files      each survey's files in Forsta
//   deletion   Forsta's deletion report, scheduled and deleted archives, the retention rule
//   account    Forsta's categories, its full list of API endpoints, and the surveys in Forsta that CIP has not loaded
// Data: GET /api/v1/admin/forsta (the company and one line per survey) and /api/v1/admin/forsta/<key> (one survey),
// both built by etl/fieldwork.py publish_forsta. This screen only draws; the chosen survey is kept in the address.
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { downloadForstaReport, useForsta, useForstaSurvey } from "../api";
import type { ForstaLine, ForstaOverview, ForstaReport, ForstaSurvey } from "../api";
import { Card, Empty, Failure, ist, SkeletonScreen } from "../components/bits";
import { fmtDate } from "../stats";
import { SECTIONS } from "../forstaSections";

const n = (v: number | null | undefined) => v == null ? "–" : v.toLocaleString("en-US");
const day = (iso: string | null | undefined) => iso ? fmtDate(iso.slice(0, 10)) : "–";
const size = (bytes: number) => bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;

export default function Forsta() {
  const { section = "reports" } = useParams();
  const { data, isLoading, error } = useForsta();
  const about = SECTIONS.find(s => s[0] === section) ?? SECTIONS[0];
  if (isLoading) return <SkeletonScreen kind="page" />;
  if (error || !data) return <Failure error={error} />;
  return <div className="stack">
    <div className="page-head"><div>
      <p className="eyebrow">Forsta · read without changing anything{data.collected ? ` · collected ${day(data.collected)}` : ""}</p>
      <h1>{about[1]}</h1>
      <p className="lede">{about[2]}</p>
    </div></div>
    {about[0] === "reports" && <WithSurvey data={data} has={l => l.reports > 0} render={s => <Reports survey={s} />} />}
    {about[0] === "check" && <><CheckSummary data={data} /><WithSurvey data={data} has={l => !!l.check} render={s => <Check survey={s} />} /></>}
    {about[0] === "crosstab" && <><WithSurvey data={data} has={l => l.banners > 0} render={s => <Banners survey={s} />} /><Defaults data={data} /></>}
    {about[0] === "samples" && <WithSurvey data={data} has={l => l.splits.length > 0} render={s => <Samples survey={s} />} />}
    {about[0] === "warnings" && <><CompanyWarnings data={data} /><WithSurvey data={data} has={() => true} render={s => <SurveyWarnings survey={s} />} /></>}
    {about[0] === "files" && <WithSurvey data={data} has={l => l.files > 0} render={s => <Files survey={s} />} />}
    {about[0] === "deletion" && <Deletion data={data} />}
    {about[0] === "account" && <Account data={data} />}
  </div>;
}

/** The survey picker above a section, and the chosen survey's record once it arrives. */
function WithSurvey({ data, has, render }: { data: ForstaOverview; has: (line: ForstaLine) => boolean; render: (s: ForstaSurvey) => ReactNode }) {
  const [params, setParams] = useSearchParams();
  const offered = data.surveys.filter(has);
  const line = offered.find(l => l.key === params.get("survey")) ?? offered[0];
  const { data: survey, isLoading, error } = useForstaSurvey(line?.key ?? "");
  if (!line) return <Empty>No survey has this in Forsta yet.</Empty>;
  return <>
    <div className="forsta-pick card">
      <label htmlFor="forsta-survey">Survey</label>
      <select id="forsta-survey" value={line.key} onChange={e => setParams({ survey: e.target.value }, { replace: true })}>
        {offered.map(l => <option key={l.key} value={l.key}>{day(l.launched)} · {l.title ?? l.path}</option>)}
      </select>
      <span className="muted">{offered.length} of {data.surveys.length} surveys · {line.path}
        {line.survey_id ? <> · <Link to={`/w/${line.survey_id}`}>open the wave</Link> · <Link to={`/fieldwork/${encodeURIComponent(line.path)}`}>fieldwork</Link></> : null}</span>
    </div>
    {isLoading ? <SkeletonScreen kind="question" /> : error || !survey ? <Failure error={error} />
      : survey.hibernated ? <Empty>Hibernated in Forsta: nothing more can be read until it is woken, and CIP never wakes a survey.</Empty> : render(survey)}
  </>;
}

/** One saved report: its tables listed on the left (searchable), the chosen one drawn on the right, % with counts. */
function Reports({ survey }: { survey: ForstaSurvey }) {
  const [picked, setPicked] = useState(0);
  const report = survey.reports[Math.min(picked, survey.reports.length - 1)];
  return <>
    <div className="seg" role="group" aria-label="Saved report">
      {survey.reports.map((r, i) => <button key={r.id} type="button" aria-pressed={r === report} onClick={() => setPicked(i)}>{r.title || "Untitled"}</button>)}
    </div>
    <Report key={`${survey.path}-${report.id}`} survey={survey} report={report} />
  </>;
}

function Report({ survey, report }: { survey: ForstaSurvey; report: ForstaReport }) {
  const [find, setFind] = useState("");
  const [table, setTable] = useState(() => Math.max(0, report.tables.findIndex(t => t.title)));   // skip Forsta's internal, untitled tables
  const [note, setNote] = useState("");
  const shown = useMemo(() => report.tables.map((t, i) => [t, i] as const)
    .filter(([t]) => !find || `${t.label} ${t.title ?? ""}`.toLowerCase().includes(find.toLowerCase())), [report, find]);
  const current = report.tables[table];
  const download = (format: ForstaReport["exports"][number]) => downloadForstaReport(survey.path.replace(/\//g, "."), report.id,
    `${survey.path.split("/").pop()} - ${report.title}`, format).then(() => setNote(""), e => setNote((e as Error).message));
  const missing = Object.entries(report.export_errors).map(([format, why]) => `${FORMAT[format]}: ${forstaReason(why)}`);
  return <Card title={report.title || "Untitled report"}
               sub={[report.description, report.access && `${report.access} in Forsta`, report.updated && `updated ${day(new Date(report.updated).toISOString())}`,
                     report.banner ? `columns: the "${report.banner}" banner` : null, `${report.tables.length} tables`].filter(Boolean).join(" · ")}
               aside={report.exports.length ? <div className="downloads">{report.exports.map(f =>
                 <button key={f} className="btn" type="button" onClick={() => download(f)}>{FORMAT[f]}</button>)}</div> : undefined}>
    {note && <p className="muted" role="status">{note}</p>}
    {missing.length > 0 && <p className="muted small">Forsta could not export: {missing.join(" · ")}</p>}
    {!report.ran ? <Empty>{report.error ? <>Forsta could not run this report: {forstaReason(report.error)}</> : "Forsta did not run this report on the last collection."}</Empty> : <div className="report-split">
      <div className="report-list">
        <input type="search" placeholder="Find a question" value={find} onChange={e => setFind(e.target.value)} aria-label="Find a question in this report" />
        <ul>{shown.map(([t, i]) => <li key={t.label}>
          <button type="button" aria-pressed={i === table} onClick={() => setTable(i)}><b>{t.label}</b> <span>{t.title ?? ""}</span></button>
        </li>)}</ul>
      </div>
      {current && <div className="report-table-pane">
        <h3>{current.label}{current.title ? `: ${current.title}` : ""}</h3>
        <div className="table-wrap fieldwork-scroll tall"><table className="data report-table forsta-xtab">
          <thead><tr><th>Answer</th>{report.columns.map((c, i) => <th key={i} className="num">{c}</th>)}</tr></thead>
          <tbody>{current.rows.map((row, r) => <tr key={r} className={r === 0 ? "base" : undefined}>
            <th scope="row">{row[0]}</th>
            {report.columns.map((_, c) => <td key={c} className="num">{r === 0 ? n(row[2 + 2 * c] as number)
              : <>{typeof row[1 + 2 * c] === "number" ? `${(row[1 + 2 * c] as number).toFixed(0)}%` : "–"}<small>{n(row[2 + 2 * c] as number)}</small></>}</td>)}
          </tr>)}</tbody>
        </table></div>
        <p className="muted small">First row: how many people the column has. Below: the share of them giving each answer, and how many. As Forsta computed it.</p>
      </div>}
    </div>}
  </Card>;
}

const FORMAT: Record<string, string> = { excel: "Excel", pdf: "PDF", pptx: "PowerPoint" };

/** Forsta's own words for why it refused, without the address and codes around them ("Unknown question 'CS3'"). */
function forstaReason(error: string) {
  const said = error.match(/"(?:error|\$error)":\s*"([^"]+)/)?.[1] ?? error;
  return said.replace(/^Internal error /, "").replace(/^CompileError: /, "").slice(0, 160);
}

/** Every survey's check in one table: questions compared, cells, and how many differ. */
function CheckSummary({ data }: { data: ForstaOverview }) {
  const checked = data.surveys.filter(l => l.check);
  const cells = checked.reduce((t, l) => t + l.check!.cells, 0), equal = checked.reduce((t, l) => t + l.check!.equal, 0);
  return <>
    <div className="grid g3">
      <div className="card kpi lead"><div className="k-label">Cells that match Forsta</div><div className="k-value">{cells ? `${(100 * equal / cells).toFixed(2)}%` : "–"}</div>
        <div className="k-note">{n(equal)} of {n(cells)} answer counts and bases</div></div>
      <div className="card kpi"><div className="k-label">Surveys checked</div><div className="k-value">{n(checked.length)}</div><div className="k-note">of {n(data.surveys.length)} kept from Forsta</div></div>
      <div className="card kpi"><div className="k-label">Surveys with a difference</div><div className="k-value">{n(checked.filter(l => l.check!.differs).length)}</div>
        <div className="k-note">each difference is listed below, per survey</div></div>
    </div>
    <Card title="Every survey" sub="Forsta's cross-tab of every question for everyone qualified, against CIP's own count from Forsta's raw data.">
      <div className="table-wrap fieldwork-scroll"><table className="data report-table">
        <thead><tr><th>Survey</th><th className="num">Questions</th><th className="num">Cells</th><th className="num">Match</th><th className="num">Differ</th></tr></thead>
        <tbody>{checked.map(l => <tr key={l.key} className={l.check!.differs ? undefined : "past"}>
          <th scope="row">{l.title ?? l.path}<br /><small className="muted">{day(l.launched)} · {l.path}</small></th>
          <td className="num">{n(l.check!.tables)}</td><td className="num">{n(l.check!.cells)}</td><td className="num">{n(l.check!.equal)}</td>
          <td className="num">{l.check!.differs ? <span className="chip sig">{n(l.check!.differs)}</span> : "0"}</td>
        </tr>)}</tbody>
      </table></div>
    </Card>
  </>;
}

/** One survey's check: every difference, and the tables only Forsta has (its own quota and routing variables). */
function Check({ survey }: { survey: ForstaSurvey }) {
  const c = survey.check;
  if (!c) return <Empty>{survey.check_error ? `Forsta could not run its cross-tab: ${forstaReason(survey.check_error)}` : "Not checked: this survey is not loaded in CIP."}</Empty>;
  return <div className="grid g2">
    <Card title={c.differs.length ? `${n(c.differs.length)} cells differ` : "Every cell matches"} sub={`${n(c.equal)} of ${n(c.cells)} cells across ${n(c.tables)} questions are the same in Forsta and CIP.`}>
      {c.differs.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
        <thead><tr><th>Question</th><th>Answer</th><th className="num">Forsta</th><th className="num">CIP</th></tr></thead>
        <tbody>{c.differs.map(([q, answer, forsta, cip], i) => <tr key={i}><th scope="row">{q}</th><td>{answer}</td><td className="num">{n(forsta)}</td><td className="num">{cip == null ? "not in CIP" : n(cip)}</td></tr>)}</tbody>
      </table></div> : <p className="muted">Forsta and CIP agree on every answer count and every base.</p>}
    </Card>
    <Card title="Not compared" sub="Tables only Forsta has: its own quota, routing and timing variables (v…, status, qtime), and number questions, where Forsta gives a mean and median instead of counts.">
      <p className="chips">{c.not_compared.map(t => <span key={t} className="tag">{t}</span>)}</p>
      {c.cip_only.length > 0 && <p className="muted small">In CIP but not in Forsta's cross-tab: {c.cip_only.join(", ")}</p>}
    </Card>
  </div>;
}

/** Every banner the team built: its columns and the condition behind each. */
function Banners({ survey }: { survey: ForstaSurvey }) {
  return <div className="grid g2">{survey.banners.map((b, i) => <Card key={i} title={b.title || `Banner ${i + 1}`} sub={`${b.segments.length} columns`}>
    <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Column</th><th>Who is in it (Forsta condition)</th></tr></thead>
      <tbody>{b.segments.map(([title, cond], j) => <tr key={j}><th scope="row">{title}</th><td><code className="cond">{cond}</code></td></tr>)}</tbody>
    </table></div>
  </Card>)}</div>;
}

function Defaults({ data }: { data: ForstaOverview }) {
  const set = Object.entries(data.crosstab_defaults ?? {});
  return <Card title="Company cross-tab defaults" sub="The defaults every new cross-tab in Forsta starts from.">
    {set.length ? <dl className="details">{set.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{JSON.stringify(v)}</dd></div>)}</dl>
      : <p className="muted">None set: Forsta's own defaults apply.</p>}
  </Card>;
}

const FUNNEL: [string, string][] = [["clickthrough", "Opened"], ["qualified", "Qualified"], ["terminates", "Terminated"], ["overquota", "Over quota"], ["partial", "Dropped out"]];

/** The funnel for each way Forsta splits the respondents, one table per split, segments nobody opened left out. */
const SPLIT_NAMES: Record<string, string> = { list: "Sample source", OS: "Operating system", browser: "Browser", "Mobile OS": "Mobile operating system",
  "Mobile Category": "Device type" };

function Samples({ survey }: { survey: ForstaSurvey }) {
  return <div className="stack">{Object.entries(survey.splits).map(([name, split]) => {
    const rows = split.segments.map((segment, i) => [segment, ...FUNNEL.map(([f]) => split.rows[f]?.[i] ?? null)] as [string, ...(number | null)[]])
      .filter(r => r[1]);
    return <Card key={name} title={SPLIT_NAMES[name] ?? name} sub="Incidence = qualified ÷ opened. Segments nobody opened the survey from are left out.">
      <div className="table-wrap fieldwork-scroll"><table className="data report-table">
        <thead><tr><th>{name === "list" ? "Source" : "Segment"}</th>{FUNNEL.map(([, label]) => <th key={label} className="num">{label}</th>)}<th className="num">Incidence</th></tr></thead>
        <tbody>{rows.map(([segment, ...v]) => <tr key={segment} className={segment === "Total" ? "base" : undefined}>
          <th scope="row">{segment}</th>{v.map((x, i) => <td key={i} className="num">{n(x)}</td>)}
          <td className="num">{v[0] ? `${(100 * (v[1] ?? 0) / v[0]).toFixed(1)}%` : "–"}</td>
        </tr>)}</tbody>
      </table></div>
    </Card>;
  })}</div>;
}

const WARNING_KINDS: [string, string][] = [["blocks", "Blocked sessions"], ["server_errors", "Server errors"], ["exceptions", "Exceptions"],
  ["quota_misses", "Quota misses"], ["missing_resources", "Missing resources"]];

function CompanyWarnings({ data }: { data: ForstaOverview }) {
  return <Card title="Every survey's warnings" sub="Forsta's company-wide warning summary: what it logged against each survey with warnings.">
    {data.warnings_summary.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
      <thead><tr><th>Survey</th>{WARNING_KINDS.map(([, label]) => <th key={label} className="num">{label}</th>)}<th>Last edited by</th></tr></thead>
      <tbody>{data.warnings_summary.map((w, i) => <tr key={i}><th scope="row">{w.name ?? w.path}</th>
        {WARNING_KINDS.map(([k]) => <td key={k} className="num">{n(w[k] as number)}</td>)}<td>{w.lastEditBy ?? "–"}</td></tr>)}</tbody>
    </table></div> : <p className="muted">No warnings on any survey.</p>}
  </Card>;
}

function SurveyWarnings({ survey }: { survey: ForstaSurvey }) {
  const checks = Object.entries(survey.launch_warnings);
  return <div className="grid g2">
    <Card title="Warning events" sub={WARNING_KINDS.map(([k, label]) => `${label} ${n(survey.warnings.counts[k] ?? 0)}`).join(" · ")}>
      {survey.warnings.events.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
        <thead><tr><th>When (IST)</th><th>Kind</th><th>What Forsta said</th></tr></thead>
        <tbody>{survey.warnings.events.map(([when, kind, reason, message], i) => <tr key={i}>
          <td className="num">{ist(when)}</td><td>{kind}{reason ? ` · ${reason}` : ""}</td><td>{message}</td></tr>)}</tbody>
      </table></div> : <p className="muted">No warning events.</p>}
    </Card>
    <Card title="Launch checks" sub="What Forsta checks before a survey goes live: tasks, imports, translations, offline mode and more.">
      {checks.length ? <ul className="terms">{checks.map(([k, items]) => <li key={k}><b>{k}</b> {items.map(x => typeof x === "string" ? x : JSON.stringify(x)).join("; ")}</li>)}</ul>
        : <p className="muted">Every launch check passed: nothing flagged.</p>}
    </Card>
  </div>;
}

function Files({ survey }: { survey: ForstaSurvey }) {
  const files = [...survey.files].sort((a, b) => b.modified.localeCompare(a.modified));
  return <Card title="Files in Forsta" sub={`${files.length} files, ${size(files.reduce((t, f) => t + f.size, 0))} in all, newest first. CIP keeps survey.xml (the questionnaire's logic).`}>
    <div className="table-wrap fieldwork-scroll tall"><table className="data report-table">
      <thead><tr><th>File</th><th className="num">Size</th><th className="num">Changed (IST)</th></tr></thead>
      <tbody>{files.map(f => <tr key={f.filename}><th scope="row">{f.filename}</th><td className="num">{size(f.size)}</td>
        <td className="num">{ist(f.modified)}</td></tr>)}</tbody>
    </table></div>
  </Card>;
}

function Deletion({ data }: { data: ForstaOverview }) {
  const rule = data.retention?.server_delete_days;
  return <>
    <div className="grid g4">
      <div className="card kpi lead"><div className="k-label">Deleted by Forsta next</div><div className="k-value">{data.deletion[0] ? `${data.deletion[0].days_until_deletion} days` : "–"}</div>
        <div className="k-note">{data.deletion[0] ? `${data.deletion[0].title}, ${day(data.deletion[0].date_of_deletion)}` : "nothing due"}</div></div>
      <div className="card kpi"><div className="k-label">Surveys in the deletion report</div><div className="k-value">{n(data.deletion.length)}</div><div className="k-note">archived, waiting to be deleted</div></div>
      <div className="card kpi"><div className="k-label">Retention rule</div><div className="k-value">{rule ? `${rule} days` : "–"}</div><div className="k-note">from archiving to deletion, set for the company in Forsta</div></div>
      <div className="card kpi"><div className="k-label">Scheduled · deleted · data deletions</div><div className="k-value">{n(data.scheduled.length)} · {n(data.deleted.length)} · {n(data.deletion_data.length)}</div>
        <div className="k-note">planned closes {n(data.planned.autoclose.length)}, planned archives {n(data.planned.archives.length)}</div></div>
    </div>
    <Card title="Forsta's deletion report" sub="Every archived survey Forsta will delete, soonest first, with its risk level and when someone last opened it.">
      <div className="table-wrap fieldwork-scroll tall"><table className="data report-table">
        <thead><tr><th>Survey</th><th className="num">Deleted on</th><th className="num">Days left</th><th>Risk</th><th className="num">Last opened</th><th>Created by</th></tr></thead>
        <tbody>{[...data.deletion].sort((a, b) => a.days_until_deletion - b.days_until_deletion).map(d => <tr key={d.path}>
          <th scope="row">{d.title}<br /><small className="muted">{d.path}</small></th><td className="num">{day(d.date_of_deletion)}</td><td className="num">{n(d.days_until_deletion)}</td>
          <td><span className={`chip ${d.risk_level === "HIGH" ? "sig" : d.risk_level === "MEDIUM" ? "warn" : "flat"}`}>{(d.risk_level ?? "–").toLowerCase()}</span></td>
          <td className="num">{day(d.last_access)}</td><td>{d.created_by}</td>
        </tr>)}</tbody>
      </table></div>
    </Card>
  </>;
}

function Account({ data }: { data: ForstaOverview }) {
  const [find, setFind] = useState("");
  const endpoints = data.endpoints.filter(([method, endpoint, title]) => !find || `${method} ${endpoint} ${title ?? ""}`.toLowerCase().includes(find.toLowerCase()));
  const methods = Object.entries(data.endpoints.reduce<Record<string, number>>((t, [m]) => ({ ...t, [m]: (t[m] ?? 0) + 1 }), {}));
  return <>
    <div className="grid g2">
      <Card title="In Forsta, not in CIP" sub="Surveys in Forsta's history that CIP has not loaded: usually test copies.">
        {data.not_loaded.length ? <div className="table-wrap fieldwork-scroll"><table className="data report-table">
          <thead><tr><th>Survey</th><th>Forsta path</th><th>State</th></tr></thead>
          <tbody>{data.not_loaded.map(s => <tr key={s.path}><th scope="row">{s.title ?? "–"}</th><td>{s.path}</td><td>{s.state ?? "not in the register"}</td></tr>)}</tbody>
        </table></div> : <p className="muted">Every survey in Forsta is in CIP.</p>}
      </Card>
      <Card title="Survey categories" sub="The categories Forsta offers for a survey.">
        <p className="chips">{data.categories.filter(c => c.key).map(c => <span key={c.key} className="tag">{c.text}</span>)}</p>
      </Card>
    </div>
    <Card title="Every Forsta API endpoint" sub={`Forsta's own list (${methods.map(([m, c]) => `${c} ${m}`).join(", ")}). CIP reads with GET and the three read-only POSTs only; see docs/FORSTA_API_REVIEW.md.`}
          aside={<input type="search" placeholder="Find an endpoint" value={find} onChange={e => setFind(e.target.value)} aria-label="Find an endpoint" />}>
      <div className="table-wrap fieldwork-scroll tall"><table className="data report-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>What it is</th></tr></thead>
        <tbody>{endpoints.map(([method, endpoint, title], i) => <tr key={i}><td><span className={`chip ${method === "GET" ? "flat" : "warn"}`}>{method}</span></td>
          <th scope="row"><code>{endpoint}</code></th><td>{title ?? ""}</td></tr>)}</tbody>
      </table></div>
    </Card>
  </>;
}
