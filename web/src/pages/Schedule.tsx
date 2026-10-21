// The data team's launch plan week by week, against what Forsta fielded: status, progress to quota, and
// anything that differs from the plan (a missing topic, another lead sector).
import { useState } from "react";
import { Link } from "react-router";
import { LaunchWeek, useSchedule } from "../api";
import { Card, Failure, Loading } from "../components/bits";
import { fmtDate } from "../stats";

const STATUS: Record<LaunchWeek["status"], [string, string]> = {
  loaded: ["In the portal", "ok"], in_field: ["In field", "live"], closed: ["Closed · loading", "warn"],
  load_failed: ["Load failed", "sig"], setting_up: ["Set up in Forsta", "flat"], planned: ["Planned", "none"],
  not_found: ["No survey found", "sig"],
};
const DAY = 86_400_000;
const ist = (iso: string) => new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });

function Quota({ w }: { w: LaunchWeek }) {
  if (w.qualified == null || !["in_field", "closed", "loaded", "load_failed"].includes(w.status)) return <span className="muted">—</span>;
  const share = Math.min(100, Math.round((w.qualified / w.quota) * 100));
  return <div className={`quota ${share >= 100 ? "done" : ""}`} title={`${w.qualified} of ${w.quota} qualified completes`}>
    <span className="bar"><i style={{ width: `${share}%` }} /></span><small>{w.qualified}/{w.quota}</small>
  </div>;
}

export default function Schedule() {
  const { data, isLoading, error } = useSchedule();
  const [all, setAll] = useState(false);
  if (isLoading) return <Loading what="the launch schedule" />;
  if (error) return <Failure error={error} />;
  const today = new Date(new Date().toDateString()).getTime();
  const at = (w: LaunchWeek) => new Date(w.date + "T00:00:00").getTime();
  const weeks = data!.weeks;
  const current = [...weeks].reverse().find(w => at(w) <= today && today - at(w) < 7 * DAY);
  const next = weeks.find(w => at(w) > today);
  const past = weeks.filter(w => at(w) <= today);
  const delivered = past.filter(w => w.status === "loaded").length;
  const flagged = weeks.filter(w => at(w) >= today - 7 * DAY && w.notes.length);
  const shown = all ? weeks : weeks.filter(w => at(w) >= today - 42 * DAY);
  return <>
    <div className="page-head"><div>
      <h1>Launch schedule</h1>
      <p className="lede">The data team's 12-week sector plan, checked each week against Forsta. A wave launches Monday around 18:00 IST. The portal loads it as soon as its quota of {data!.quota} qualified completes is reached or 9 hours have passed (03:00 IST), whichever comes first, and refreshes it when Forsta closes the survey.</p>
    </div></div>
    <div className="grid g4" style={{ marginBottom: 18 }}>
      <div className="card kpi lead">
        <div className="k-label">This week{current ? ` · ${fmtDate(current.date)}` : ""}</div>
        <div className="k-value" style={{ fontSize: 22 }}>{current?.sector ?? "No launch"}</div>
        <div className="k-note">{current ? STATUS[current.status][0] : ""}{current?.qualified != null && current.status !== "planned" ? ` · ${current.qualified}/${current.quota}` : ""}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Next launch{next ? ` · ${fmtDate(next.date)}` : ""}</div>
        <div className="k-value" style={{ fontSize: 22 }}>{next?.sector ?? "—"}</div>
        <div className="k-note">{next?.topics.length ? `with ${next.topics.join(", ")}` : "no topic planned"}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Planned waves delivered</div>
        <div className="k-value">{delivered}/{past.length}</div>
        <div className="k-note">since {fmtDate(weeks[0].date)}</div>
      </div>
      <div className="card kpi">
        <div className="k-label">Plan runs until</div>
        <div className="k-value" style={{ fontSize: 22 }}>{data!.plan_ends ? fmtDate(data!.plan_ends) : "—"}</div>
        <div className="k-note">cycle {weeks.at(-1)?.cycle} · ask the data team for the next cycle</div>
      </div>
    </div>
    <div className="stack">
    {flagged.length > 0 && <Card title="Differs from the plan" sub="Surveys this week or later whose Forsta title is missing a planned topic, or has a different lead sector">
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {flagged.map(w => <li key={w.date}><b>{fmtDate(w.date)} · {w.sector}</b>: {w.notes.join("; ")} <span className="muted">({w.title})</span></li>)}
      </ul>
    </Card>}
    <Card title="Topic rotation" sub="Each topic rides with set lead sectors. When a week misses its topic, the next of those sectors carries it">
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Topic</th><th>Rides with</th><th>Last fielded</th><th>Next planned</th></tr></thead>
          <tbody>{data!.topics.map(t => <tr key={t.topic}>
            <td><span className="tag">{t.topic}</span></td>
            <td>{t.sectors.join(" · ") || <span className="muted">—</span>}</td>
            <td>{t.last ? fmtDate(t.last) : "—"}<br /><small className="muted">{t.fielded} waves since Jul 2025</small></td>
            <td>{t.next ? <>{fmtDate(t.next)}<br /><small className="muted">{t.next_sector}</small></> : <span className="muted">not in the plan</span>}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </Card>
    <Card title="Week by week" sub={`From ${data!.source}, imported ${fmtDate(data!.imported)}`}
          aside={<button className="btn" onClick={() => setAll(a => !a)}>{all ? "Recent and upcoming" : "All weeks since Jul 2025"}</button>}>
      <div className="table-wrap">
        <table className="data schedule">
          <thead><tr><th>Monday</th><th>Lead sector</th><th>Planned topics</th><th>Status</th><th>Quota</th><th>Survey in Forsta</th></tr></thead>
          <tbody>{shown.map(w => <tr key={w.date} className={w === current ? "now" : at(w) < today ? "past" : ""}>
            <td className="num" style={{ textAlign: "left" }}>{fmtDate(w.date)}<br /><small className="muted">cycle {w.cycle}</small></td>
            <td>{w.sector}</td>
            <td>{w.topics.length ? w.topics.map(t => <span key={t} className="tag">{t}</span>) : <span className="muted">—</span>}</td>
            <td><span className={`chip ${STATUS[w.status][1]}`}>{STATUS[w.status][0]}</span>
              {w.launched && <small className="muted" style={{ display: "block", marginTop: 4 }}>{ist(w.launched)}{w.closed ? ` → ${ist(w.closed)}` : ""} IST</small>}</td>
            <td><Quota w={w} /></td>
            <td className="title-cell">{w.survey_id ? <Link to={`/w/${w.survey_id}`}>{w.title}</Link> : w.title ?? <span className="muted">—</span>}
              {w.notes.map(n => <span key={n} className="note">{n}</span>)}</td>
          </tr>)}</tbody>
        </table>
      </div>
      {data!.corrected.length > 0 && <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>Corrected on import (the year was mistyped in the workbook): {data!.corrected.join(" · ")}</p>}
    </Card>
    </div>
  </>;
}
