// The sector databank (/app/sectors): the Databank's sector tables. Per sector, one column per survey the sector ran
// (sectors rotate through the weekly tracker, so about every 12 weeks): the share who bought in the category, then its
// retailers, brands and categories as tabs. Every number is built by the ETL when data is published (etl/sectors.py →
// api/v1/sectors.json.gz); which sectors and questions: config/sectors.yml. This screen only draws.
// Opened from the left menu ("Sector databank"); the sector and tab are kept in the address so a view can be shared.
import { useSearchParams } from "react-router";
import { useSectors } from "../api";
import type { Sector } from "../api";
import { Card, Empty, Failure, SkeletonScreen } from "../components/bits";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtDate } from "../stats";

const pct = (v: number | null) => v == null ? "–" : `${v.toFixed(1)}%`;

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
      <label className="sr-only" htmlFor="sector">Sector</label>
      <select id="sector" value={sector.name} onChange={e => pick("sector", e.target.value)}>
        {data.sectors.map(s => <option key={s.name}>{s.name}</option>)}
      </select>
    </div>
    <SectorTable sector={sector} tab={params.get("tab")} onTab={t => pick("tab", t)} />
  </div>;
}

/** One sector as the Databank lays it out: the purchase-rate row on top, then the chosen tab's answers, then the base. */
function SectorTable({ sector, tab, onTab }: { sector: Sector; tab: string | null; onTab: (title: string) => void }) {
  const table = sector.tables.find(t => t.title === tab) ?? sector.tables[0];
  const first = sector.waves[0], last = sector.waves.at(-1)!;
  return <Card title={sector.name}
               sub={`${sector.waves.length} surveys, ${fmtDate(first.date)} to ${fmtDate(last.date)}. About 400 US adults each: margin of error up to ±${sector.margin}% at 95% confidence, wider for the smaller buyer bases.`}
               aside={<Tabs value={table.title} onValueChange={onTab}><TabsList>
                 {sector.tables.map(t => <TabsTrigger key={t.title} value={t.title}>{t.title}</TabsTrigger>)}
               </TabsList></Tabs>}>
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
