// A tracker's own page (/app/trackers/<code>): one topic dashboard (GenAI, GLP-1, financial health…) on its own, not only
// inside a wave that carried it. Pick the topic and the week; the page shows that week's "at a glance" (the same Glance a
// wave's Overview shows) and every headline figure over all the weeks the tracker ran. All from files the ETL already
// publishes (api/v1/dashboards/<code>/<survey_id>.json.gz, a few KB each, fetched once and cached): nothing is computed
// on the server. Opened from the left menu (Trackers) and the Home page; topic and week are kept in the address. Export
// downloads every week as a workbook laid out like the Databank's sheets (trackerBook), or the chosen week on its own
// (weekSheet).
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { allowed, dashboardQuery, useDashboard, useMe, useWaves } from "../api";
import type { Dashboard, Metric } from "../api";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import Glance from "../components/Glance";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadBook, downloadTable } from "../csv";
import type { Sheet } from "../csv";
import { blues, C, useTheme } from "../theme";
import { fmtDate } from "../stats";
import { dashboardFeature, SECTOR_DASHBOARDS, TRACKERS, words } from "../trackers";

const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

export default function Trackers() {
  const me = useMe().data;
  const mine = TRACKERS.filter(([c]) => allowed(me, dashboardFeature(c)));   // each tracker is a menu of its own (15 Nov 2026)
  const { code = (mine[0] ?? TRACKERS[0])[0] } = useParams();
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
  const label = (k: string) => history[0]?.tile_labels?.[k] ?? words(k);
  const colours = [C.red, ...blues(Math.max(1, tiles.length - 1))];
  return <div className="stack">
    <div className="page-head"><div>
      <h1>{history[0]?.title ?? name}</h1>
      <p className="lede">This tracker ran in {weeks.length} weekly surveys, {fmtDate(weeks.at(-1)!.wave_date)} to {fmtDate(weeks[0].wave_date)}. Pick a
        week for its headline figures and takeaways; the chart shows every headline figure over all of them.</p>
    </div></div>

    <section className="card compare-bar" aria-label="Choose the tracker and week">
      <label><span>Tracker</span><select value={code} onChange={e => navigate(`/trackers/${e.target.value}`)}>
        <optgroup label="Trackers">{mine.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</optgroup>
        {allowed(me, "dashboards") && <optgroup label="Sector dashboards">{SECTOR_DASHBOARDS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</optgroup>}
      </select></label>
      <label><span>Week</span><select value={week.survey_id} onChange={e => setParams(p => { p.set("w", e.target.value); return p; }, { replace: true })}>
        {weeks.map(w => <option key={w.survey_id} value={w.survey_id}>{fmtDate(w.wave_date)} · n={w.qualified_n}</option>)}</select></label>
      <Link className="btn" to={`/w/${week.survey_id}`}>Open this week's survey</Link>
      <ExportButtons pin={false} deck={false} onExport={format => {
        if (all.some(q => q.isLoading)) throw new Error("Still loading the weeks: try again in a moment");   // a week that failed is left out
        return downloadBook(format, `${history[0].title} ${weeks[0].wave_date}`, trackerBook(history));
      }} view={{ whole: "every week", one: "this week", onExport: format => {
        const d = history.find(board => board.wave.survey_id === week.survey_id);
        if (!d) throw new Error(all.some(q => q.isLoading) ? "Still loading this week: try again in a moment" : "This week's figures did not load: reload the page");
        const sheet = weekSheet(d);
        return downloadTable(format, `${d.title} ${week.wave_date}`, sheet.header, sheet.rows, sheet.notes);
      } }} />
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

/** The tracker as a workbook laid out like the Databank's sheets (the business team, 27 Nov 2026): a tab for the
 *  headline figures, one per list and one per group split, an answer per row and a week per column, oldest first, then
 *  the people asked: one row when every answer that week had the same base (a list's buyers), else one per answer. */
function trackerBook(boards: Dashboard[]): Sheet[] {
  const latest = boards[0];   // newest first, as the page loads them
  const oldestFirst = [...boards].reverse();
  const tab = (name: string, pick: (d: Dashboard) => Metric[], about?: string): Sheet => {
    const labels = [...new Set(boards.flatMap(d => pick(d).map(m => m.label)))];   // the newest week's order first
    const figure = (d: Dashboard, label: string) => pick(d).find(m => m.label === label);
    const shared = oldestFirst.every(d => new Set(pick(d).map(m => m.base)).size <= 1);
    const bases = shared ? [["Respondents asked", ...oldestFirst.map(d => pick(d)[0]?.base ?? null)]]
      : labels.map(l => [`Respondents asked: ${l}`, ...oldestFirst.map(d => figure(d, l)?.base ?? null)]);
    return { title: name, header: [name, ...oldestFirst.map(d => d.wave.week_of)], unit: "%",
             rows: [...labels.map(l => [l, ...oldestFirst.map(d => figure(d, l)?.pct ?? null)]), ...bases],
             plain: bases.map((_, k) => labels.length + k),
             notes: [`${latest.title}: ${name}`, `% of those asked (the people asked are the bottom rows), each of the ${boards.length} weeks the tracker ran`,
                     ...(about ? [about] : []), SOURCE] };
  };
  // a list keeps each week's top answers only (the dashboards'): a blank is an answer outside that week's top, not nobody
  const top = (pick: (d: Dashboard) => Metric[]) => {
    const n = Math.max(...boards.map(d => pick(d).length));
    return `Each week's top ${n} answers. A blank cell is an answer outside that week's top ${n}, not an answer nobody gave; every answer of the question, every week, downloads from its Trends page.`;
  };
  const list = (k: string) => (d: Dashboard) => d.lists[k] ?? [];
  return [tab("Headline figures", d => headlines(d, latest)),
          ...Object.keys(latest.lists).map(k => tab(latest.list_heads?.[k] ?? words(k), list(k), top(list(k)))),
          ...Object.keys(latest.segments).map(k => tab(words(k), d => d.segments[k] ?? []))];
}

const SOURCE = "Source: Coresight Research US Consumer Survey, weekly tracker. Unweighted.";
/** A week's headline figures under the tile names of `labels` (the newest week's, so every week's row reads alike). */
const headlines = (d: Dashboard, labels = d) => Object.entries(d.tiles).flatMap(([k, m]) => m ? [{ ...m, label: labels.tile_labels?.[k] ?? m.label }] : []);

/** The chosen week on its own (Export's one-view choice, 27 Nov 2026): every headline figure, list answer and group
 *  split of that week with its %, the people asked and its change in points against the week before and last year. */
function weekSheet(d: Dashboard): Pick<Sheet, "header" | "rows" | "notes"> {
  const prior = (d.prior_label ?? "last week").replace(/^the /, "");
  const block = (name: string, items: Metric[]) => items.map(m => [name, m.label, m.pct, m.base, m.vs_prior, m.vs_ly]);
  return { header: ["Figure", "Answer", "%", "People asked", `Change vs ${prior} (pts)`, "Change vs last year (pts)"],
           rows: [...block("Headline figures", headlines(d)), ...Object.entries(d.lists).flatMap(([k, items]) => block(d.list_heads?.[k] ?? words(k), items)),
                  ...Object.entries(d.segments).flatMap(([k, items]) => block(words(k), items))],
           notes: [`${d.title}, week of ${fmtDate(d.wave.week_of)}`, "% of those asked; a list holds the week's top answers; changes in points", SOURCE] };
}
