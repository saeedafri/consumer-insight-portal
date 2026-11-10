// In store vs online (/app/channels): which categories people bought in a store and which online in the past two weeks,
// from the weekly questions q2 (in a store) and q3 (online). Two published question files (every week since 2020, every
// group, exact counts; etl → api/v1/questions/CSI-US/tracker/q2|q3.json.gz) are fetched once and cached; every pick of
// week, group or category is computed here in the browser, so nothing runs on the server when someone changes a filter.
// Opened from the left menu (Core research) and the Home page's card; week, group and category are kept in the address.
import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { CUT_NAMES, useQuestion, useWaves } from "../api";
import type { QuestionFile } from "../api";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { Delta } from "../components/Glance";
import { Card, Empty, Failure, SkeletonScreen } from "../components/bits";
import { C, useTheme } from "../theme";
import { fmtDate } from "../stats";

const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const SKIP = /^(none of|other|don.?t know)/i;

/** A question file as share lookups: share(survey_id, "dim:value", answer label) → % of the group asked, or null. */
function shares(file: QuestionFile) {
  const cells = new Map<string, [number | null, number]>();
  file.w.forEach((w, k) => cells.set(`${file.waves[w][0]}|${file.cuts[file.c[k]].join(":")}|${file.answers[file.a[k]][0]}`, [file.n[k], file.b[k]]));
  return (survey: number, cut: string, label: string) => {
    const cell = cells.get(`${survey}|${cut}|${label}`);
    return cell && cell[0] != null && cell[1] ? 100 * cell[0] / cell[1] : null;
  };
}

export default function Channels() {
  const waves = useWaves().data;
  const tracker = waves?.find(w => w.survey_family === "CSI-US" && w.study_type === "tracker");
  const store = useQuestion(tracker, "q2"), online = useQuestion(tracker, "q3");
  const [params, setParams] = useSearchParams();
  useTheme();   // a theme switch re-renders, so the series take the new theme's colours (C)
  const data = useMemo(() => {
    if (!store.data || !online.data) return null;
    const both = new Set(online.data.waves.map(w => w[0]));
    const weeks = store.data.waves.filter(w => both.has(w[0])).sort((x, y) => y[1].localeCompare(x[1]));   // newest first
    return { weeks, cuts: store.data.cuts, inStore: shares(store.data), onLine: shares(online.data),
             labels: new Set(online.data.answers.map(a => a[0])) };
  }, [store.data, online.data]);
  if (!waves || store.isLoading || online.isLoading) return <SkeletonScreen kind="page" />;
  if (store.error || online.error) return <Failure error={store.error ?? online.error} />;
  if (!data || !data.weeks.length) return <Empty>In store and online buying has not been asked yet.</Empty>;
  const pick = (k: string, v: string) => setParams(p => { p.set(k, v); return p; }, { replace: true });
  const at = Math.max(0, data.weeks.findIndex(w => String(w[0]) === params.get("w")));
  const [survey, date] = data.weeks[at];
  const prior = data.weeks[at + 1];
  const cut = data.cuts.some(c => c.join(":") === params.get("g")) ? params.get("g")! : "total:Total";
  // the categories this week asked both ways, biggest in store first
  const categories = store.data!.answers.map(a => a[0]).filter(l => data.labels.has(l) && !SKIP.test(l) && data.inStore(survey, cut, l) != null)
    .sort((x, y) => (data.inStore(survey, cut, y) ?? 0) - (data.inStore(survey, cut, x) ?? 0));
  const category = categories.includes(params.get("c") ?? "") ? params.get("c")! : categories[0];
  const groupName = cut === "total:Total" ? "Everyone" : `${CUT_NAMES[cut.split(":")[0]] ?? ""}: ${cut.split(":")[1]}`;
  const nowStore = data.inStore(survey, cut, category), nowOnline = data.onLine(survey, cut, category);
  const change = (fn: typeof data.inStore, now: number | null) => prior && now != null && fn(prior[0], cut, category) != null ? now - fn(prior[0], cut, category)! : null;
  return <div className="stack">
    <div className="page-head"><div>
      <h1>In store vs online</h1>
      <p className="lede">Which categories people bought in a store, and which online, in the past two weeks. Every weekly survey since 2020; pick a week,
        a group of people and a category, or click a category in the chart.</p>
    </div></div>

    <section className="card compare-bar" aria-label="Choose what to show">
      <label><span>Week</span><select value={survey} onChange={e => pick("w", e.target.value)}>
        {data.weeks.map(w => <option key={w[0]} value={w[0]}>{fmtDate(w[1])}</option>)}</select></label>
      <label><span>People</span><select value={cut} onChange={e => pick("g", e.target.value)}>
        {data.cuts.map(c => <option key={c.join(":")} value={c.join(":")}>{c[0] === "total" ? "Everyone" : `${CUT_NAMES[c[0]] ?? c[0]}: ${c[1]}`}</option>)}</select></label>
      <label><span>Category</span><select value={category} onChange={e => pick("c", e.target.value)}>
        {categories.map(l => <option key={l}>{l}</option>)}</select></label>
    </section>

    <div className="grid g4">
      <div className="card kpi lead"><div className="k-label">Bought in a store</div><div className="k-value">{pct(nowStore)}</div>
        <div className="k-note"><Delta d={change(data.inStore, nowStore)} label="vs last week" flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Bought online</div><div className="k-value">{pct(nowOnline)}</div>
        <div className="k-note"><Delta d={change(data.onLine, nowOnline)} label="vs last week" flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Store lead over online</div>
        <div className="k-value">{nowStore != null && nowOnline != null ? `${(nowStore - nowOnline).toFixed(1)} pts` : "–"}</div>
        <div className="k-note">{category}</div></div>
      <div className="card kpi"><div className="k-label">Online share of the two</div>
        <div className="k-value">{nowStore != null && nowOnline != null && nowStore + nowOnline > 0 ? pct(100 * nowOnline / (nowStore + nowOnline)) : "–"}</div>
        <div className="k-note">online ÷ (store + online)</div></div>
    </div>

    <div className="grid g2">
      <Card title="Every category, this week" sub={`${groupName} · ${fmtDate(date)} · % who bought each in a store (red) and online (blue)`}>
        <EChart height={Math.max(260, categories.length * 30 + 60)} label={`In store and online buying by category, ${fmtDate(date)}`}
                onClick={p => pick("c", p.name)}
                option={{
                  tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => pct(v) },
                  legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online"] },
                  grid: { left: 8, right: 40, top: 32, bottom: 8, containLabel: true },
                  xAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
                  yAxis: { type: "category", inverse: true, data: categories, axisLabel: { ...axisText(), width: 190, overflow: "truncate" } },
                  series: [["In a store", data.inStore, C.red], ["Online", data.onLine, C.blue]].map(([name, fn, color]) => ({
                    type: "bar", name, barMaxWidth: 10, barGap: "30%", itemStyle: { color, borderRadius: [2, 4, 4, 2] },
                    data: categories.map(l => { const v = (fn as typeof data.inStore)(survey, cut, l); return v == null ? null : +v.toFixed(1); }) })),
                }} />
      </Card>
      <Card title={category} sub={`${groupName} · every week since ${fmtDate(data.weeks.at(-1)![1])} · in a store (red) vs online (blue)`}>
        <EChart height={340} label={`${category}: in store vs online over time`}
                option={{
                  tooltip: { ...tooltip(), trigger: "axis", valueFormatter: (v: number | null) => pct(v) },
                  legend: { top: 0, left: 0, textStyle: axisText() },
                  grid: { left: 8, right: 16, top: 36, bottom: 40, containLabel: true },
                  xAxis: { type: "time", axisLabel: valueText() },
                  yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
                  dataZoom: [{ type: "slider", height: 18, bottom: 6, startValue: time(data.weeks[Math.min(data.weeks.length - 1, 51)][1]) }, { type: "inside" }],
                  series: [["In a store", data.inStore, C.red], ["Online", data.onLine, C.blue]].map(([name, fn, color]) => ({
                    type: "line", name, showSymbol: false, smooth: 0.2, color, lineStyle: { width: 2 },
                    data: [...data.weeks].reverse().map(w => [time(w[1]), (fn as typeof data.inStore)(w[0], cut, category)]) })),
                }} />
      </Card>
    </div>
    <p className="source-line">Source: Coresight Research US Consumer Survey, weekly tracker, about 400 US adults a week; questions q2 (in a store) and
      q3 (online), past two weeks. Unweighted. Groups under 30 people are not shown.</p>
  </div>;
}
