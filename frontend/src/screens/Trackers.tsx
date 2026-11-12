// A tracker's own page (/app/trackers/<code>): one topic dashboard (GenAI, GLP-1, financial health…) on its own, not only
// inside a wave that carried it. Pick the topic and the week; the page shows that week's "at a glance" (the same Glance a
// wave's Overview shows) and every headline figure over all the weeks the tracker ran. All from files the ETL already
// publishes (api/v1/dashboards/<code>/<survey_id>.json.gz, a few KB each, fetched once and cached): nothing is computed
// on the server. Opened from the left menu (Trackers) and the Home page; topic and week are kept in the address.
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { dashboardQuery, useDashboard, useWaves } from "../api";
import type { Dashboard } from "../api";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import Glance from "../components/Glance";
import { Card, Empty, Failure, SkeletonScreen } from "../components/bits";
import { blues, C, useTheme } from "../theme";
import { fmtDate } from "../stats";
import { SECTOR_DASHBOARDS, TRACKERS } from "../trackers";

const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

export default function Trackers() {
  const { code = TRACKERS[0][0] } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: waves, isLoading, error } = useWaves();
  useTheme();   // a theme switch re-renders, so the lines take the new theme's colours
  const weeks = (waves ?? []).filter(w => w.dashboards?.includes(code));   // newest first
  const all = useQueries({ queries: weeks.map(w => dashboardQuery(code, w.survey_id)) });
  const history = useMemo(() => all.map(q => q.data).filter((d): d is Dashboard => !!d), [all]);
  if (isLoading) return <SkeletonScreen kind="page" />;
  if (error || !waves) return <Failure error={error} />;
  const name = [...TRACKERS, ...SECTOR_DASHBOARDS].find(([c]) => c === code)?.[1] ?? code;
  if (!weeks.length) return <Empty>No week has carried this tracker yet. <Link to="/trackers/genai">Open the GenAI tracker</Link>.</Empty>;
  const week = weeks.find(w => String(w.survey_id) === params.get("w")) ?? weeks[0];
  const tiles = history[0] ? Object.keys(history[0].tiles).filter(k => history[0].tiles[k]) : [];
  const label = (k: string) => history[0]?.tile_labels?.[k] ?? k.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase());
  const colours = [C.red, ...blues(Math.max(1, tiles.length - 1))];
  return <div className="stack">
    <div className="page-head"><div>
      <h1>{history[0]?.title ?? name}</h1>
      <p className="lede">This tracker ran in {weeks.length} weekly surveys, {fmtDate(weeks.at(-1)!.wave_date)} to {fmtDate(weeks[0].wave_date)}. Pick a
        week for its headline figures and takeaways; the chart shows every headline figure over all of them.</p>
    </div></div>

    <section className="card compare-bar" aria-label="Choose the tracker and week">
      <label><span>Tracker</span><select value={code} onChange={e => navigate(`/trackers/${e.target.value}`)}>
        <optgroup label="Trackers">{TRACKERS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</optgroup>
        <optgroup label="Sector dashboards">{SECTOR_DASHBOARDS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</optgroup>
      </select></label>
      <label><span>Week</span><select value={week.survey_id} onChange={e => setParams(p => { p.set("w", e.target.value); return p; }, { replace: true })}>
        {weeks.map(w => <option key={w.survey_id} value={w.survey_id}>{fmtDate(w.wave_date)} · n={w.qualified_n}</option>)}</select></label>
      <Link className="btn" to={`/w/${week.survey_id}`}>Open this week's survey</Link>
    </section>

    <Glance code={code} id={week.survey_id} />
    <TileDonuts code={code} id={week.survey_id} />

    {tiles.length > 0 && history.length > 1 && <Card title="Headline figures over time" sub={`% of respondents, each week the tracker ran (${history.length} of ${weeks.length} loaded)`}>
      <EChart height={320} label={`${name}: headline figures over time`}
              option={{
                tooltip: { ...tooltip(), trigger: "axis", valueFormatter: (v: number | null) => v == null ? "–" : `${v.toFixed(1)}%` },
                legend: { top: 0, left: 0, textStyle: axisText(), type: "scroll" },
                grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
                xAxis: { type: "time", axisLabel: valueText() },
                yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
                series: tiles.map((k, i) => ({
                  type: "line", name: label(k), color: colours[i], symbol: "circle", symbolSize: 6, lineStyle: { width: i ? 1.8 : 2.5 },
                  data: [...history].reverse().map(d => [time(d.wave.week_of), d.tiles[k]?.pct ?? null]) })),
              }} />
    </Card>}
  </div>;
}

/** The chosen week's headline figures as donuts: the share who said it against everyone else asked (each tile is one
 *  yes-or-no split, so the two slices add up to 100%). */
function TileDonuts({ code, id }: { code: string; id: number }) {
  const { data: d } = useDashboard(code, id);
  const tiles = Object.entries(d?.tiles ?? {}).filter(([, m]) => m?.pct != null);
  if (!d || !tiles.length) return null;
  return <Card title="This week's headline figures" sub={`% of respondents, week of ${fmtDate(d.wave.week_of)}`}>
    <div className={`grid g${Math.min(4, tiles.length)}`}>{tiles.map(([k, m], i) => {
      const name = d.tile_labels?.[k] ?? k;
      return <figure key={k} className="chart-cell"><figcaption>{name}</figcaption>
        <EChart label={`${name}: ${m!.pct!.toFixed(1)}%`} height={200} option={{
          tooltip: { ...tooltip(), trigger: "item", formatter: (p: { name: string; value: number }) => `${p.name}: ${p.value.toFixed(1)}% (n=${m!.base})` },
          series: [{ type: "pie", radius: ["52%", "78%"], padAngle: 1, itemStyle: { borderRadius: 3 },
                     label: { position: "center", formatter: () => `${m!.pct!.toFixed(1)}%`, color: C.ink, fontSize: 20, fontWeight: 700 },
                     emphasis: { scaleSize: 4, label: { show: true } },
                     data: [{ name, value: m!.pct!, itemStyle: { color: i ? C.s2 : C.red } },
                            { name: "Everyone else asked", value: 100 - m!.pct!, itemStyle: { color: C.line }, label: { show: false } }] }],
        }} /></figure>;
    })}</div>
  </Card>;
}
