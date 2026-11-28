// The sector databank (/app/sectors): the Databank's sector tables. Per sector, one column per survey the sector ran
// (sectors rotate through the weekly tracker, so about every 12 weeks): the share who bought in the category, then its
// retailers, brands and categories as tabs, under three cards from its newest survey (leading retailer, top product,
// median spend: the research team's row of 23 Nov 2026), and below them every sector's spend side by side with the
// chosen sector's average spend survey by survey (the roadmap's Sector Spend Insights, 27 Nov 2026). Every number is
// built by the ETL when data is published (etl/sectors.py → api/v1/sectors.json.gz); which sectors and questions:
// config/sectors.yml. This screen only draws, and lays the tables out for Export: every tab and the median spend in one
// workbook.
// Opened from the left menu ("Sector databank"); the sector and tab are kept in the address so a view can be shared.
// The Market filter offers China but cannot choose it: China's weekly survey asks no sector questions.
import { useSearchParams } from "react-router";
import { useSectors } from "../api";
import type { Sector } from "../api";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { Card, Empty, ExportButtons, Failure, marketOptions, SkeletonScreen } from "../components/bits";
import { FigureCard } from "../components/Glance";
import { downloadBook, downloadTable } from "../csv";
import type { Format, Sheet } from "../csv";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { direction, dollars, fmtDate } from "../stats";
import { C, useTheme } from "../theme";

const pct = (v: number | null) => v == null ? "–" : `${v.toFixed(1)}%`;
const SOURCE = "Source: Coresight Research US Consumer Survey";

export default function Sectors() {
  const { data, isLoading, error } = useSectors();
  const [params, setParams] = useSearchParams();
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404) return <Empty>The sector tables have not been published yet.</Empty>;
  if (error || !data) return <Failure error={error} />;
  const sector = data.sectors.find(s => s.name === params.get("sector")) ?? data.sectors[0];
  if (!sector) return <Empty>No sector has been asked yet.</Empty>;
  const pick = (key: string, value: string) => setParams(p => { p.set(key, value); if (key === "sector") p.delete("tab"); return p; }, { replace: true });
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Sector databank</h1>
      <p className="lede">Who bought in each retail sector, and where, in every weekly survey that asked about it. The purchase rate is
        the % of all respondents; retailers, brands and categories are the % of the sector's buyers.</p>
    </div></div>
    <div className="toolbar one-row">
      <label className="sr-only" htmlFor="market">Market</label>
      <select id="market" defaultValue="US">{marketOptions(["US"], "no sector questions")}</select>
      <label className="sr-only" htmlFor="sector">Sector</label>
      <select id="sector" value={sector.name} onChange={e => pick("sector", e.target.value)}>
        {data.sectors.map(s => <option key={s.name}>{s.name}</option>)}
      </select>
    </div>
    <SectorCards sector={sector} onTab={t => pick("tab", t)} />
    <SectorTable sector={sector} tab={params.get("tab")} onTab={t => pick("tab", t)} />
    <SpendBySector sectors={data.sectors} sector={sector} onPick={name => pick("sector", name)} />
  </div>;
}

/** The sector's newest survey in three cards, as etl/sectors.py newest_cards wrote them: its leading retailer and top
 *  product or category (each opens its tab), and the median spend or the purchase rate. */
function SectorCards({ sector, onTab }: { sector: Sector; onTab: (title: string) => void }) {
  return <section aria-label={`${sector.name} at a glance`}>
    <p className="muted section-note">{sector.name} in its newest survey, {fmtDate(sector.waves[sector.waves.length - 1].date)}</p>
    <div className="grid g3">{sector.cards.map((c, i) =>
      <FigureCard key={c.kind} {...c} lead={i === 0} onClick={c.tab ? () => onTab(c.tab!) : undefined} />)}</div>
  </section>;
}

/** One tab of the sector as the Databank lays it out: the purchase-rate row on top, then the tab's answers, then the base. */
function sheetOf(sector: Sector, table: Sector["tables"][number]): Sheet {
  const rows = [...(sector.purchase ? [[sector.purchase.label, ...sector.purchase.values]] : []), ...table.rows.map(r => [r.label, ...r.values]),
                ["Respondents asked", ...table.bases]];
  return { title: table.title, header: [table.title, ...sector.waves.map(w => w.date)], rows, unit: "%", plain: [rows.length - 1],
           notes: [`${sector.name}: ${table.title}`, "% of respondents; retailers, brands and categories are % of the sector's buyers.", SOURCE] };
}

/** The middle buyer's spend band in each survey (etl/sectors.py median_band), as a tab of its own: bands, not %. */
const spendSheet = (sector: Sector): Sheet[] => sector.spend ? [{ title: "Median spend", header: ["Median spend", ...sector.waves.map(w => w.date)],
  rows: [["Median spend band", ...sector.spend.median], ...(sector.spend.average ? [["Average spend ($, estimated)", ...sector.spend.average]] : [])],
  notes: [`${sector.name}: median spend`, "The middle buyer's spend band in each survey, and the average estimated from the bands' mid-points (the top band at its floor)",
          SOURCE] }] : [];

/** One sector as the Databank lays it out, a tab at a time on screen; Export downloads every tab in Excel or CSV, or
 *  the tab on screen on its own (the business team, 27 Nov 2026), and the tab on screen as a slide or a pin. */
function SectorTable({ sector, tab, onTab }: { sector: Sector; tab: string | null; onTab: (title: string) => void }) {
  const table = sector.tables.find(t => t.title === tab) ?? sector.tables[0];
  const first = sector.waves[0], last = sector.waves.at(-1)!;
  const exportTab = (format: Format) => {
    const shown = sheetOf(sector, table);
    return downloadTable(format, `${sector.name} - ${table.title}`, shown.header, shown.rows, shown.notes, { unit: shown.unit, plain: shown.plain });
  };
  // Excel and CSV: every tab, or the tab on screen only; PowerPoint and Pin: the tab on screen (a slide charts one table)
  const exportTable = (format: Format) => format === "xlsx" || format === "csv"
    ? downloadBook(format, `${sector.name} databank`, [...sector.tables.map(t => sheetOf(sector, t)), ...spendSheet(sector)])
    : exportTab(format);
  return <Card title={sector.name}
               sub={`${sector.waves.length} surveys, ${fmtDate(first.date)} to ${fmtDate(last.date)}. About 400 US adults each: margin of error up to ±${sector.margin}% at 95% confidence, wider for the smaller buyer bases.`}
               aside={<div className="toolbar one-row"><Tabs value={table.title} onValueChange={onTab}><TabsList>
                 {sector.tables.map(t => <TabsTrigger key={t.title} value={t.title}>{t.title}</TabsTrigger>)}
               </TabsList></Tabs><ExportButtons onExport={exportTable} view={{ whole: "every tab", one: "this tab", onExport: exportTab }} /></div>}>
    {/* opens on the newest surveys (right); the history is a scroll to the left */}
    <div className="table-wrap" ref={el => { if (el) el.scrollLeft = el.scrollWidth; }}><table className="data report-table">
      <thead><tr><th>{table.title}</th>{sector.waves.map(w => <th key={w.survey_id} className="num">{fmtDate(w.date)}</th>)}</tr></thead>
      <tbody>
        {sector.purchase && <tr className="purchase-row">
          <th scope="row">{sector.purchase.label}</th>{sector.purchase.values.map((v, i) => <td key={i} className="num">{pct(v)}</td>)}
        </tr>}
        {table.rows.map(row => <tr key={row.label}>
          <th scope="row">{row.label}</th>{row.values.map((v, i) => <td key={i} className="num">{pct(v)}</td>)}
        </tr>)}
      </tbody>
      <tfoot><tr><th scope="row">Respondents asked</th>{table.bases.map((b, i) => <td key={i} className="num">{b ?? "–"}</td>)}</tr></tfoot>
    </table></div>
  </Card>;
}


/** Every sector's spend in its newest survey (the roadmap's Sector Spend Insights, 27 Nov 2026): the middle buyer's band
 *  and the average estimated from the answer bands (etl/sectors.py average_spend) with its change against the survey
 *  before and a year earlier; beside it, the chosen sector's average survey by survey. A sector's name opens it. */
function SpendBySector({ sectors, sector, onPick }: { sectors: Sector[]; sector: Sector; onPick: (name: string) => void }) {
  useTheme();   // a theme switch re-renders, so the line takes the new theme's colours
  const withSpend = sectors.filter(s => s.spend?.average?.some(v => v != null));
  if (!withSpend.length) return null;   // a file published before 27 Nov 2026 has no averages
  const newest = (s: Sector) => s.spend!.average!.at(-1) ?? null;
  const change = (s: Sector, yearAgo: boolean) => s.spend!.changes?.find(c => (c.label === "vs LY") === yearAgo)?.d ?? null;
  const exportSpend = (format: Format) => downloadTable(format, "Spend by sector",
    ["Sector", "Newest survey", "Median spend", "Average spend ($, estimated)", "Change vs LY ($)", "Change vs the survey before ($)"],
    withSpend.map(s => [s.name, s.waves.at(-1)!.date, s.spend!.median.at(-1) ?? null, newest(s), change(s, true), change(s, false)]),
    ["Spend by sector: each sector's newest survey, past three months", "Average estimated from the answer bands' mid-points, the top band at its floor", SOURCE]);
  const averages = sector.spend?.average ?? [];
  const points = sector.waves.map((w, i) => [fmtDate(w.date), averages[i] ?? null, sector.spend?.median[i] ?? null] as const);
  const option = () => ({
    tooltip: { ...tooltip(), trigger: "axis", formatter: ([p]: { dataIndex: number }[]) =>
      `${points[p.dataIndex][0]}<br>Average <b>${dollars(points[p.dataIndex][1])}</b><br><span style="color:${C.ink3}">Median band ${points[p.dataIndex][2] ?? "–"}</span>` },
    grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: points.map(p => p[0]), axisLabel: { ...axisText(), hideOverlap: true } },
    yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "${value}" } },
    series: [{ type: "line", name: "Average spend", color: C.red, symbol: "circle", symbolSize: 6, data: points.map(p => p[1]) }],
  });
  return <div className="grid g2">
    <Card title="Spend by sector" sub="Each sector's newest survey: the middle buyer's spend band and the average estimated from the bands, past three months · a sector opens it"
          aside={<ExportButtons onExport={exportSpend} pin={false} deck={false} />}>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Sector</th><th>Newest survey</th><th>Median spend</th><th className="num">Average (est.)</th><th>Change</th></tr></thead>
        <tbody>{withSpend.map(s => <tr key={s.name}>
          <th scope="row"><button type="button" className="link-button" aria-current={s.name === sector.name || undefined} onClick={() => onPick(s.name)}>
            {s.name === sector.name ? <b>{s.name}</b> : s.name}</button></th>
          <td>{fmtDate(s.waves.at(-1)!.date)}</td><td>{s.spend!.median.at(-1) ?? "–"}</td><td className="num">{dollars(newest(s))}</td>
          <td>{(s.spend!.changes ?? []).flatMap(({ d, label }) => d == null ? [] : [<span key={label} className={`chip flat ${direction(d)}`}>
            {d > 0 ? "▲" : d < 0 ? "▼" : "±"} ${Math.abs(d)} <small>{label}</small></span>])}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="muted small">Sectors whose survey asks no spend question (eCommerce, social commerce) are not listed. An average jumps when a
        sector's answer bands changed (mass merchants' top band was "More than $200" until April 2024): read it with the median band.</p>
    </Card>
    <Card title={`${sector.name}: average spend`} sub="Each survey the sector ran, estimated from the answer bands; the median band in the hover">
      {averages.some(v => v != null) ? <EChart height={320} label={`${sector.name}: average spend per survey`} option={option()} build={option} />
        : <Empty>{sector.name}'s survey asks no spend question.</Empty>}
    </Card>
  </div>;
}
