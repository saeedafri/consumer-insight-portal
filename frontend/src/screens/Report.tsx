// The weekly report (/app/w/:id/report): the "US Consumer Survey Insights" PDF report of one weekly-tracker wave, in
// the PDF's order: three data points to watch, consumer sentiment (net better, with news events and income groups),
// the 13-week tables (where consumers shop, what they buy, what they do), each with a year's chart of its biggest
// answers, retailers' shopper profiles, methodology, and the appendix of sentiment data. Every table has the portal's
// Export menu (CSV, Excel, PowerPoint, Pin to a board).
// Every number is built by the ETL when the wave is published (etl/weekly_report.py → report.json.gz), and which tables
// appear, with their titles, comes from config/weekly_report.yml: this screen only draws what it is given.
// Opened from the wave's left menu ("Weekly report", shown for the waves that have one: api/v1/reports).
import { useMemo, useState } from "react";
import { useParams } from "react-router";
import { useReport } from "../api";
import type { AppendixRow, ReportTable, WeeklyReport } from "../api";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { fmtDate } from "../stats";
import { C, useTheme } from "../theme";

const shortDate = (iso: string | null) => iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }) : "–";
const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
/** A change in percentage points, signed: +5.4, −0.8 (the PDF writes negatives in brackets). */
const points = (v: number | null) => v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`;
const time = (iso: string | null) => iso ? Date.parse(`${iso}T00:00:00Z`) : null;
const INCOME_COLOURS = ["#A3C0CE", "#D62E2F", "#005F8F"];   // <$50K, $50K–<$100K, $100K+ (as in the PDF's charts)

/** What both charts on this screen share: a % axis over time, a legend on top, a tooltip that copes with a week not asked. */
const lineChart = (series: object[]) => ({
  tooltip: { ...tooltip(), trigger: "axis", valueFormatter: (v: number | null) => pct(v) },
  legend: { top: 0, left: 0, textStyle: axisText() },
  grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
  xAxis: { type: "time", axisLabel: valueText() },
  yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
  series,
});

export default function Report() {
  const id = Number(useParams().id);
  const { data, isLoading, error } = useReport(id);
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404)
    return <Empty>This wave has no weekly report. Reports are built for every weekly tracker survey since July 2025, when the tracker's questions took their current form.</Empty>;
  if (error || !data) return <Failure error={error} />;
  const parts = [...new Set(data.tables.map(t => t.part))];   // the report's parts, in the order the settings give
  return <div className="stack">
    <div className="page-head"><div>
      <h1>US Consumer Survey Insights · week of {fmtDate(data.wave_date)}</h1>
      <p className="lede">From the survey of {fmtDate(data.wave_date)} ({data.methodology.weeks[0]?.respondents.toLocaleString("en-US")} US adults 18+).
        Figures are % of respondents, as four-week rolling averages unless marked weekly. Changes are in percentage points (PPTs);
        coloured only when statistically significant.</p>
    </div></div>
    <ThreePoints report={data} />
    <Sentiment report={data} />
    {parts.map(part => <section key={part} className="stack">
      <h2 className="report-section">{part}</h2>
      {data.tables.filter(t => t.part === part).map(t => <WeekTable key={t.question} title={t.title} table={t} events={data.events} />)}
    </section>)}
    <Profiles report={data} />
    <Methodology report={data} />
    <Appendix report={data} />
  </div>;
}

/** "Three data points to watch this week": the three biggest significant three-month moves, one per table. */
function ThreePoints({ report }: { report: WeeklyReport }) {
  if (!report.three_points.length) return null;
  return <Card title="Three data points to watch this week">
    <ol className="three-points">
      {report.three_points.map(p => <li key={`${p.section}-${p.label}`}>
        <span className="three-points-value">{points(p.change)}<small>PPTs</small></span>
        <span><b>{p.label}</b> <span className="muted">({p.section.toLowerCase()})</span>: the four-week share {p.change > 0 ? "rose" : "fell"} over three
          months, from {pct(p.from)} on {fmtDate(p.from_date)} to {pct(p.to)} on {fmtDate(p.to_date)}.</span>
      </li>)}
    </ol>
  </Card>;
}

/** Net better for personal finances and the economy over the past year, with the news events, then by income group. */
function Sentiment({ report }: { report: WeeklyReport }) {
  const theme = useTheme();
  const [weekly, setWeekly] = useState(false);
  const names = Object.keys(report.sentiment);
  const start = report.sentiment[names[0]]?.dates.find(Boolean) ?? "";
  const events = report.events.filter(e => e.kind === "economy" && e.date >= start);   // the economy events of this year
  const option = useMemo(() => lineChart(names.map((name, i) => ({
    name: `Net better: ${name.toLowerCase()}`, type: "line", showSymbol: false, color: i === 0 ? "#A3C0CE" : C.red, lineStyle: { width: 2 },
    data: report.sentiment[name].dates.map((d, k) => [time(d), report.sentiment[name].lines.Total[weekly ? "weekly" : "four_week"][k]]),
    // news events: a thin dashed line each, labelled when hovered; all are listed under the chart too
    markLine: i ? undefined : { symbol: "none", lineStyle: { color: C.lineStrong, type: [3, 3], width: 1 }, label: { show: false },
      emphasis: { label: { show: true, formatter: "{b}", color: C.ink, fontSize: 11 } },
      data: events.map(e => ({ xAxis: time(e.date), name: `${shortDate(e.date)}: ${e.label}` })) },
  }))), [report, weekly, theme]);
  if (!names.length) return null;
  return <>
    <h2 className="report-section">Consumer sentiment</h2>
    <Card title="Personal finances and the economy: net better over the next 12 months"
          sub={`% expecting better minus % expecting worse, ${weekly ? "single weeks" : "four-week rolling average"}. Dashed lines mark news events (hover for the event).`}
          aside={<div className="seg" role="group" aria-label="Averaging">
            <button aria-pressed={!weekly} onClick={() => setWeekly(false)}>Four-week average</button>
            <button aria-pressed={weekly} onClick={() => setWeekly(true)}>Weekly</button></div>}>
      <EChart option={option} height={320} label="Net better for personal finances and the economy over the past year" />
      {events.length > 0 && <ul className="event-list">{events.map(e => <li key={e.date + e.label}><b>{shortDate(e.date)}</b> {e.label}</li>)}</ul>}
    </Card>
    <div className="grid g2">{names.map(name => <IncomeChart key={name} report={report} name={name} />)}</div>
  </>;
}

/** One sentiment question's net better by income group (four-week averages), each with its change over a year. */
function IncomeChart({ report, name }: { report: WeeklyReport; name: string }) {
  const theme = useTheme();
  const data = report.sentiment[name];
  const groups = Object.keys(data.lines).filter(g => g !== "Total");
  const option = useMemo(() => lineChart(groups.map((g, i) => ({
    name: g, type: "line", showSymbol: false, color: INCOME_COLOURS[i], lineStyle: { width: 2 },
    data: data.dates.map((d, k) => [time(d), data.lines[g].four_week[k]]) }))), [data, theme]);
  return <Card title={`${name} by household income`} sub="Net better, four-week rolling average"
               aside={<span className="year-changes">{groups.map(g => <span key={g} className="chip flat" title="Change over a year">{g}: {points(data.lines[g].year_change)} y/y</span>)}</span>}>
    <EChart option={option} height={260} label={`Net better for ${name.toLowerCase()} by household income`} />
  </Card>;
}

/** A year of a table's four-week averages: its six biggest answers drawn, the rest one click away in the legend, retail
 *  events marked (the PDF's Figures 5 and 7 draw the main food and nonfood retailers this way). */
function TrendChart({ title, table, events }: { title: string; table: ReportTable; events: WeeklyReport["events"] }) {
  const theme = useTheme();
  const option = useMemo(() => {
    const labels = table.rows.map(r => r.label);   // biggest first
    const start = table.trend.dates.find(Boolean) ?? "";
    const marks = events.filter(e => e.kind === "retail" && e.date >= start);
    const base = lineChart(labels.map((label, i) => ({
      name: label, type: "line", showSymbol: false, lineStyle: { width: 2 },
      data: table.trend.dates.map((d, k) => [time(d), table.trend.lines[label]?.[k] ?? null]),
      markLine: i ? undefined : { symbol: "none", lineStyle: { color: C.lineStrong, type: [3, 3], width: 1 }, label: { show: false },
        emphasis: { label: { show: true, formatter: "{b}", color: C.ink, fontSize: 11 } },
        data: marks.map(e => ({ xAxis: time(e.date), name: `${shortDate(e.date)}: ${e.label}` })) },
    })));
    return { ...base, legend: { ...base.legend, type: "scroll", selected: Object.fromEntries(labels.map((l, i) => [l, i < 6])) } };
  }, [table, events, theme]);
  return <EChart option={option} height={300} label={`${title}: the biggest answers over the past year, four-week rolling average`} />;
}

/** A 13-week table, as in the PDF: four-week rolling averages, then the one-week and three-month changes; its chart above. */
function WeekTable({ title, table, events }: { title: string; table: ReportTable; events: WeeklyReport["events"] }) {
  const change = (v: number | null, significant: boolean) =>
    <td className={`num ${significant ? "change-sig" : ""}`} title={significant ? "Statistically significant" : undefined}>{points(v)}</td>;
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, title,
    ["Answer", ...table.dates.map(d => d ?? ""), "1-wk chg", "3-mo chg", "1-wk significant", "3-mo significant"],
    table.rows.map(r => [r.label, ...r.values, r.week_change, r.quarter_change, r.week_significant ? "yes" : "", r.quarter_significant ? "yes" : ""]),
    [title, "% of respondents, four-week rolling average. Changes in percentage points.", "Source: Coresight Research US Consumer Survey"]);
  return <Card title={title} sub="% of respondents, four-week rolling average. Coloured changes are statistically significant; biggest first. The chart shows the six biggest; click a name in its legend to add or remove a line."
               aside={<ExportButtons onExport={exportTable} />}>
    <TrendChart title={title} table={table} events={events} />
    <div className="table-wrap"><table className="data report-table">
      <thead><tr><th>Answer</th>{table.dates.map((d, i) => <th key={i} className="num">{shortDate(d)}</th>)}
        <th className="num" title="One-week change, percentage points">1-wk chg</th><th className="num" title="Three-month change, percentage points">3-mo chg</th></tr></thead>
      <tbody>{table.rows.map(row => <tr key={row.label}>
        <th scope="row">{row.label}</th>
        {row.values.map((v, i) => <td key={i} className="num">{pct(v)}</td>)}
        {change(row.week_change, row.week_significant)}{change(row.quarter_change, row.quarter_significant)}
      </tr>)}</tbody>
    </table></div>
  </Card>;
}

/** Each retailer's shoppers over the 13 weeks: average age and household income (the Databank's shopper profiles). */
function Profiles({ report }: { report: WeeklyReport }) {
  if (!report.profiles.length) return null;
  return <>
    <h2 className="report-section">Retailers' shopper profiles</h2>
    <div className="grid g2">{report.profiles.map(set => <Card key={set.title} title={set.title}
        sub="Average age and household income of respondents who bought from each retailer in the 13 weeks, from age and income band midpoints."
        aside={<ExportButtons onExport={format => downloadTable(format, set.title, ["Retailer", "Average age", "Household income ($K)", "Shoppers"],
          set.rows.map(p => [p.label, p.age, p.income_k, p.shoppers]), [set.title, "13 weeks to " + report.wave_date, "Source: Coresight Research US Consumer Survey"])} />}>
      <div className="table-wrap"><table className="data report-table">
        <thead><tr><th>Retailer</th><th className="num">Avg age</th><th className="num" title="Average household income, $ thousands">Income ($K)</th>
          <th className="num" title="Respondents who bought there in the 13 weeks">Shoppers</th></tr></thead>
        <tbody>{set.rows.map(p => <tr key={p.label}><th scope="row">{p.label}</th><td className="num">{p.age}</td>
          <td className="num">{p.income_k}</td><td className="num">{p.shoppers.toLocaleString("en-US")}</td></tr>)}</tbody>
      </table></div>
    </Card>)}</div>
  </>;
}

/** Respondents per week and the margins of error, as the PDF's methodology page states them. */
function Methodology({ report }: { report: WeeklyReport }) {
  const m = report.methodology;
  return <Card title="Methodology"
               sub={`Coresight Research surveys US consumers aged 18+ online each week. The weekly results have a maximum margin of error of ±${m.weekly_margin}%, and the four-week rolling averages ±${m.four_week_margin}%, at a 95% confidence level.`}>
    <ol className="method-weeks">{m.weeks.map(w => <li key={w.date}><span>{fmtDate(w.date)}</span><b>{w.respondents.toLocaleString("en-US")}</b></li>)}</ol>
  </Card>;
}

/** The appendix: per sentiment question, % worse, % better and net better over 28 weeks with their one-week and
 *  four-week changes; four-week averages for everyone or one income group, or single weeks (Appendix Figures 1-10). */
function Appendix({ report }: { report: WeeklyReport }) {
  const names = Object.keys(report.appendix ?? {});
  const [group, setGroup] = useState("All respondents");
  if (!names.length) return null;
  const groups = [...Object.keys(report.appendix[names[0]].four_week), "Weekly"];
  return <>
    <h2 className="report-section">Appendix: consumer sentiment data</h2>
    <div className="seg" role="group" aria-label="Respondents">
      {groups.map(g => <button key={g} aria-pressed={group === g} onClick={() => setGroup(g)}>{g === "Weekly" ? "All respondents, single weeks" : g}</button>)}
    </div>
    {names.map(name => {
      const data = report.appendix[name];
      const rows: AppendixRow[] = group === "Weekly" ? data.weekly : data.four_week[group] ?? [];
      const title = `${name}: whether they expect it to get better or worse over the next 12 months`;
      const kind = group === "Weekly" ? "single weeks" : `${group}, four-week rolling average`;
      const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `${name} - ${kind}`,
        ["", ...data.dates.map(d => d ?? ""), "1-wk chg", "4-wk chg"], rows.map(r => [r.label, ...r.values, r.week_change, r.four_week_change]),
        [title, `% of respondents, ${kind}. Changes in percentage points.`, "Source: Coresight Research US Consumer Survey"]);
      return <Card key={name} title={title} sub={`% of respondents, ${kind}.`} aside={<ExportButtons onExport={exportTable} />}>
        <div className="table-wrap" ref={el => { if (el) el.scrollLeft = el.scrollWidth; }}><table className="data report-table">
          <thead><tr><th></th>{data.dates.map((d, i) => <th key={i} className="num">{shortDate(d)}</th>)}
            <th className="num">1-wk chg</th><th className="num">4-wk chg</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.label} className={r.label === "Net better" ? "purchase-row" : undefined}>
            <th scope="row">{r.label}</th>{r.values.map((v, i) => <td key={i} className="num">{pct(v)}</td>)}
            <td className="num">{points(r.week_change)}</td><td className="num">{points(r.four_week_change)}</td>
          </tr>)}</tbody>
        </table></div>
      </Card>;
    })}
  </>;
}
