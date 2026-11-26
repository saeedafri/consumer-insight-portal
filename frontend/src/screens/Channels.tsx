// In store vs online (/app/channels): which categories people bought in a store and which online in the past two weeks,
// from a weekly survey chosen with the Market filter: the US tracker's Q4/Q5 (Aug 2022 to Dec 2023), then Q2/Q3 and q2/q3
// (from Jan 2024, and Dec 2020 to Jul 2022 under older codes the publish joins by wording), or China's Q5/Q6 (from Feb 2023).
// Its published question files (every group, exact counts; etl → api/v1/questions/CSI-US/tracker/q2|q3|Q4|Q5.json.gz,
// CSI-CN/tracker/Q5|Q6.json.gz) are fetched once and cached; every pick of week, group or category is computed here in
// the browser, so nothing runs on the server when someone changes a filter.
// Opened from the left menu (Core research) and the Home page's cards (China's widest gap opens it on China); market,
// week, group, category, the trend's group and its date range are kept in the address. Respondent group is two choices:
// a kind of group (gender, age, income…), then All or one group; only groups this week has answers from are offered
// (older income bands are empty in recent weeks). The bar chart compares (all categories, or a kind's groups side by
// side, the research team's call of 23 Nov 2026); the line chart inspects one group at a time, chosen on its own
// buttons, week by week over the last year by default (the research team's call of 25 Nov 2026).
import { useMemo, useRef } from "react";
import { useSearchParams } from "react-router";
import { CUT_NAMES, isFiller, useQuestion, useWaves } from "../api";
import type { QuestionFile } from "../api";
import EChart, { axisText, downloadPng, tooltip, valueText } from "../components/EChart";
import type { Chart } from "../components/EChart";
import { Delta } from "../components/Glance";
import { Card, Empty, ExportButtons, Failure, marketOptions, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { C, useTheme } from "../theme";
import { fmtDate } from "../stats";

const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const SKIP = /^(none of|other|don.?t know)/i;
const YEAR = 365 * 86_400_000;   // the trend's default range: the last year of weeks

// Each market's weekly survey: its in-store and online questions (newest code first) and the wording of the weeks that
// count. The US tracker renumbered the two, and a code also held other questions in other weeks (q2 was "places you are
// avoiding" until Dec 2023, Q4 a food-retailer question from Jan 2024): only the weeks whose wording is this question count.
const SURVEYS = {
  US: { family: "CSI-US", store: ["q2", "Q4"], online: ["q3", "Q5"], storeWording: /in a store in the past two weeks/i,
        onlineWording: /online in the past two weeks/i, source: "Coresight Research US Consumer Survey, weekly tracker, about " +
        "400 US adults a week; questions q2 (in a store) and q3 (online), asked as Q4 and Q5 until December 2023, past two weeks" },
  CN: { family: "CSI-CN", store: ["Q5", ""], online: ["Q6", ""], storeWording: /purchased in physical stores/i,
        onlineWording: /purchased online/i, source: "Coresight Research China Consumer Survey, weekly, about 550 adults in " +
        "China a week; questions Q5 (in physical stores) and Q6 (online), past two weeks" },
};

/** % of a group (cut "dim:value") of one week (survey_id) who bought a category (answer label), or null. */
type Share = (survey: number, cut: string, label: string) => number | null;

/** Question files as one share lookup, over the weeks that asked `wording`: share(survey_id, "dim:value", answer label)
 *  → % of the group asked, or null; base(survey_id, "dim:value") → people asked; weeks: survey_id → date; labels: every
 *  answer those weeks gave. */
function shares(files: QuestionFile[], wording: RegExp) {
  const cells = new Map<string, [number | null, number]>();
  const bases = new Map<string, number>();
  const weeks = new Map<number, string>(), labels = new Set<string>();
  for (const file of files) {
    const kept = file.waves.map(w => wording.test(file.versions[w[2] - 1] ?? ""));
    file.waves.forEach((w, i) => kept[i] && weeks.set(w[0], w[1]));
    file.w.forEach((w, k) => {
      if (!kept[w]) return;
      const label = file.answers[file.a[k]][0], group = `${file.waves[w][0]}|${file.cuts[file.c[k]].join(":")}`;
      labels.add(label);
      cells.set(`${group}|${label}`, [file.n[k], file.b[k]]);
      bases.set(group, file.b[k]);   // a multiple-answer question: one base for every answer of a group's week
    });
  }
  const share = (survey: number, cut: string, label: string) => {
    const cell = cells.get(`${survey}|${cut}|${label}`);
    return cell && cell[0] != null && cell[1] ? 100 * cell[0] / cell[1] : null;
  };
  return { share, base: (survey: number, cut: string) => bases.get(`${survey}|${cut}`) ?? null, weeks, labels };
}

export default function Channels() {
  const waves = useWaves().data;
  const [params, setParams] = useSearchParams();
  const barChart = useRef<Chart | null>(null), lineChart = useRef<Chart | null>(null);
  const market = params.get("market") === "CN" ? "CN" : "US", survey = SURVEYS[market];
  const tracker = waves?.find(w => w.survey_family === survey.family && w.study_type === "tracker");
  const codes = [...survey.store, ...survey.online];   // four: "" is a question this survey does not have
  const files = [useQuestion(tracker, codes[0]), useQuestion(tracker, codes[1]), useQuestion(tracker, codes[2]), useQuestion(tracker, codes[3])];
  useTheme();   // a theme switch re-renders, so the series take the new theme's colours (C)
  const loaded = files.map(f => f.data);
  const data = useMemo(() => {
    if (codes.some((code, i) => code && !loaded[i])) return null;
    const [store1, store2, online1, online2] = loaded;
    const store = shares([store1, store2].filter(Boolean) as QuestionFile[], survey.storeWording);
    const online = shares([online1, online2].filter(Boolean) as QuestionFile[], survey.onlineWording);
    const weeks = [...store.weeks].filter(([id]) => online.weeks.has(id)).sort((x, y) => y[1].localeCompare(x[1]));   // newest first
    // the online list adds a note to an answer ("Books, movies, music or video games (incl. digital purchases)"): an
    // online answer that is an in-store one plus " (…)" is that answer, else Books never pairs and is left out
    const onlineName = new Map([...online.labels].flatMap(l => {
      const own = [...store.labels].find(s => l.startsWith(`${s} (`));
      return own && !online.labels.has(own) ? [[own, l] as const] : [];
    }));
    return { weeks, cuts: store1!.cuts, inStore: store.share, storeLabels: store.labels, storeBase: store.base, onlineBase: online.base,
             onLine: (week: number, cut: string, label: string) => online.share(week, cut, onlineName.get(label) ?? label),
             labels: new Set([...online.labels, ...onlineName.keys()]) };
  }, [market, ...loaded]);   // the market and its four files
  // another market has other weeks, groups and categories: only the market is kept
  const chooseMarket = (m: string) => setParams(m === "US" ? {} : { market: m }, { replace: true });
  const failed = files.find(f => f.error)?.error;
  // a market whose questions cannot be read still offers the way back to the US
  const back = market !== "US" && <p><button type="button" className="btn-chip" onClick={() => chooseMarket("US")}>Show the United States</button></p>;
  if (!waves || files.some(f => f.isLoading)) return <SkeletonScreen kind="page" />;
  if (failed) return <>{back}<Failure error={failed} /></>;
  if (!data || !data.weeks.length) return <>{back}<Empty>In store and online buying has not been asked yet.</Empty></>;
  const pick = (k: string, v: string) => setParams(p => { p.set(k, v); return p; }, { replace: true });
  const at = Math.max(0, data.weeks.findIndex(w => String(w[0]) === params.get("w")));
  const [week, date] = data.weeks[at];
  const prior = data.weeks[at + 1];
  // China skips a week now and then: "vs last week" only when the week before was asked, else its date, as Home's cards
  // say it (etl/glance.py compare_label)
  const vs = !prior ? "vs the survey before" : time(date) - time(prior[1]) === 7 * 86_400_000 ? "vs last week"
    : `vs ${new Date(`${prior[1]}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
  // household income's "Prefer not to say / answer" is no group: left out of both charts (the research team, 25 Nov 2026)
  const cuts = data.cuts.filter(c => !(c[0] === "income_band" && isFiller(c[1])));
  const offered = cuts.filter(c => [...data.storeLabels].some(l => data.inStore(week, c.join(":"), l) != null));
  const cut = offered.some(c => c.join(":") === params.get("g")) ? params.get("g")! : "total:Total";
  const kinds = [...new Set(offered.map(c => c[0]))];
  // "All" of a kind is everyone, with the kind kept in the address (k) so its group list stays open
  const kind = cut !== "total:Total" ? cut.split(":")[0] : kinds.includes(params.get("k") ?? "") ? params.get("k")! : "total";
  // a group chosen here resets the line chart's own group (t, tk), so the line follows it again
  const pickGroup = (g: string, k?: string) => setParams(p => {
    p.set("g", g); p.delete("t"); p.delete("tk");
    if (k === "total") p.delete("k"); else if (k) p.set("k", k);
    return p;
  }, { replace: true });
  // the categories this week asked both ways, biggest in store first
  const categories = [...data.storeLabels].filter(l => data.labels.has(l) && !SKIP.test(l) && data.inStore(week, cut, l) != null)
    .sort((x, y) => (data.inStore(week, cut, y) ?? 0) - (data.inStore(week, cut, x) ?? 0));
  const category = categories.includes(params.get("c") ?? "") ? params.get("c")! : categories[0];
  const kindName = CUT_NAMES[kind] ?? kind;
  const sideBySide = kind !== "total" && cut === "total:Total";   // All of a kind: its groups side by side
  const groups = offered.filter(c => c[0] === kind).map(c => c[1]);
  const groupName = sideBySide ? `${kindName}, each group` : cut === "total:Total" ? "Everyone" : `${CUT_NAMES[cut.split(":")[0]] ?? ""}: ${cut.split(":")[1]}`;
  const nowStore = data.inStore(week, cut, category), nowOnline = data.onLine(week, cut, category);
  const change = (fn: typeof data.inStore, now: number | null) => prior && now != null && fn(prior[0], cut, category) != null ? now - fn(prior[0], cut, category)! : null;
  // both cards draw at one height, so the trend card has no empty space under its chart beside the long category list
  const height = Math.max(400, (sideBySide ? groups.length : categories.length) * 30 + 60);
  const figure = (v: number | null) => v == null ? null : +v.toFixed(1);   // a % as charts and exports show it
  const source = `Source: ${survey.source}. Unweighted.`;

  // the trend's date range: its own, the last year unless From / To are chosen (the week above does not move it)
  const oldestFirst = [...data.weeks].reverse();
  const yearAgo = oldestFirst.findIndex(w => time(w[1]) >= time(oldestFirst.at(-1)![1]) - YEAR);
  // where the address's From or To week sits among the weeks (an unknown week: the default)
  const place = (key: string, fallback: number) => { const i = oldestFirst.findIndex(w => String(w[0]) === params.get(key)); return i < 0 ? fallback : i; };
  const [first, last] = [place("from", yearAgo), place("to", oldestFirst.length - 1)].sort((x, y) => x - y);   // From after To: swapped
  const span = oldestFirst.slice(first, last + 1);
  // The line chart's group, one at a time (t), from the groups its own weeks have answers from: by default the group the
  // page shows, or everyone when the bars compare a kind's groups; its buttons list one kind's groups (tk, else the page's kind)
  const trendOffered = cuts.filter(c => span.some(w => data.inStore(w[0], c.join(":"), category) != null));
  const trendHas = (c: string | null) => trendOffered.some(x => x.join(":") === c);
  const trendCut = trendHas(params.get("t")) ? params.get("t")! : !sideBySide && trendHas(cut) ? cut : "total:Total";
  const trendKinds = [...new Set(trendOffered.map(c => c[0]))];
  const trendKind = trendCut !== "total:Total" ? trendCut.split(":")[0]
    : trendKinds.includes(params.get("tk") ?? "") ? params.get("tk")! : trendKinds.includes(kind) ? kind : "total";
  const trendName = trendCut === "total:Total" ? "Everyone" : `${CUT_NAMES[trendKind] ?? trendKind}: ${trendCut.slice(trendKind.length + 1)}`;
  const chooseTrendKind = (k: string) => setParams(p => { p.set("t", "total:Total"); p.set("tk", k); return p; }, { replace: true });
  // the line starts and ends where the group has both figures (Non-binary from Aug 2022), so each line's end label and
  // the gap are one week's; a week in between without them (15 US weeks of 2021-22 whose surveys asked no gender, age
  // or income question) breaks the line, and the note under it says why
  const answered = (w: [number, string]) => data.inStore(w[0], trendCut, category) != null && data.onLine(w[0], trendCut, category) != null;
  const start = span.findIndex(answered), end = span.length - [...span].reverse().findIndex(answered);
  const drawn = start < 0 ? [] : span.slice(start, end);
  const unanswered = drawn.filter(w => !answered(w)).length;
  const rangeText = drawn.length ? `${fmtDate(drawn[0][1])} to ${fmtDate(drawn.at(-1)![1])}` : "no weeks";
  const both = drawn.at(-1);   // the last week, where the gap between the two lines is marked
  const bothStore = both && figure(data.inStore(both[0], trendCut, category)), bothOnline = both && figure(data.onLine(both[0], trendCut, category));

  const barRows = sideBySide ? groups : [category, ...categories.filter(l => l !== category)];   // the chosen category on top
  const barFocus = sideBySide ? groups.find(g => trendCut === `${kind}:${g}`) ?? "" : category;
  const barShare = (fn: Share, row: string) => sideBySide ? fn(week, `${kind}:${row}`, category) : fn(week, cut, row);
  /** In-store (red) and online (blue) bars, a pair per row: every category for one group, or every group for one
   *  category. The row the line chart shows (barFocus) in full colour, the others lighter; no focus, all full. */
  const barOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => pct(v) },
    legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online"] },
    grid: { left: 8, right: 40, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
    yAxis: { type: "category", inverse: true, data: barRows, triggerEvent: true,
             axisLabel: { ...axisText(), width: 190, overflow: "truncate", color: (row?: string) => !barFocus || row === barFocus ? C.ink : C.ink3 } },
    series: [["In a store", data.inStore, C.red], ["Online", data.onLine, C.blue]].map(([name, fn, color]) => ({
      type: "bar", name, barMaxWidth: 10, barGap: "30%", itemStyle: { color, borderRadius: [2, 4, 4, 2] },
      data: barRows.map(r => ({ value: figure(barShare(fn as Share, r)), itemStyle: !barFocus || r === barFocus ? undefined : { opacity: 0.3 } })) })),
  });
  const barTitle = sideBySide ? `${category} by ${kindName.toLowerCase()}` : "All categories, this week";
  // a bar or its row's label: a category opens in the line chart; a group, in the comparison, opens its trend there
  const openRow = (row: string) => sideBySide ? pick("t", `${kind}:${row}`) : pick("c", row);
  const exportBars = (format: Format) => downloadTable(format, `${barTitle} ${date}`, [sideBySide ? kindName : "Category", "In a store %", "Online %"],
    barRows.map(r => [r, figure(barShare(data.inStore, r)), figure(barShare(data.onLine, r))]),
    [`${barTitle}: ${groupName}, ${fmtDate(date)}`, source]);

  const lineOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis",
      // the base beside each figure: a small group (Non-binary, a handful a week) swings, and "check its base" is the rule
      formatter: (points: { marker: string; seriesName: string; value: [number, number | null, number | null] }[]) =>
        `${fmtDate(new Date(points[0].value[0]).toISOString().slice(0, 10))}<br>` + points.filter(p => p.seriesName !== "gap")
          .map(p => `${p.marker}${p.seriesName} <b>${pct(p.value[1])}</b> <span style="color:${C.ink3}">n ${p.value[2] ?? "–"}</span>`).join("<br>") },
    legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online"] },
    grid: { left: 8, right: 112, top: 36, bottom: 28, containLabel: true },   // right: room for the end labels
    xAxis: { type: "time", min: "dataMin", max: "dataMax", axisLabel: valueText() },
    yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
    series: [...([["In a store", data.inStore, data.storeBase, C.red, "solid"], ["Online", data.onLine, data.onlineBase, C.blue, "dashed"]] as const)
      .map(([name, fn, base, color, line]) => ({
        type: "line", name, showSymbol: false, smooth: 0.2, color, lineStyle: { width: 2, type: line },
        data: drawn.map(w => [time(w[1]), figure(fn(w[0], trendCut, category)), base(w[0], trendCut)]),
        // each line's latest figure at its end, as in the research team's mock-up
        endLabel: { show: true, color, fontSize: 12, formatter: (p: { value: [number, number | null] }) => `${name} ${pct(p.value[1])}` },
        labelLayout: { moveOverlap: "shiftY" },   // end labels of lines that end close together move apart
      })),
      // the gap between the two lines, once, at the last week both were asked: a bracket between the lines' ends and its
      // figure as an end label between theirs (a label on the bracket itself would be turned on its side)
      ...(both && bothStore != null && bothOnline != null ? [{
        type: "line", name: "gap", silent: true, showSymbol: false, lineStyle: { opacity: 0 }, tooltip: { show: false },
        data: [[time(both[1]), (bothStore + bothOnline) / 2]], labelLayout: { moveOverlap: "shiftY" },
        endLabel: { show: true, color: C.ink2, fontSize: 11, formatter: `${bothStore >= bothOnline ? "+" : ""}${(bothStore - bothOnline).toFixed(1)} pts gap` },
        markLine: { silent: true, symbol: "none", animation: false, label: { show: false }, lineStyle: { color: C.ink3, type: "solid", width: 1 },
                    data: [[{ coord: [time(both[1]), bothStore] }, { coord: [time(both[1]), bothOnline] }]] },
      }] : [])],
  });
  const lineTitle = `${category}: in a store vs online, ${trendName}`;
  const exportTrend = (format: Format) => downloadTable(format, `${category} in store vs online`,
    ["Week", "In a store %", "Online %", "In a store base", "Online base"],
    drawn.map(w => [w[1], figure(data.inStore(w[0], trendCut, category)), figure(data.onLine(w[0], trendCut, category)),
                    data.storeBase(w[0], trendCut), data.onlineBase(w[0], trendCut)]),
    [`${lineTitle}, ${rangeText}`, source]);

  return <div className="stack">
    <div className="page-head"><div>
      <h1>In store vs online</h1>
      <p className="lede">Share of people who bought each category in a store or online.</p>
    </div></div>

    <section className="card compare-bar" aria-label="Choose what to show">
      <label><span>Market</span><select value={market} onChange={e => chooseMarket(e.target.value)}>
        {marketOptions(Object.keys(SURVEYS))}</select></label>
      <label><span>Week</span><select value={week} onChange={e => pick("w", e.target.value)}>
        {data.weeks.map(w => <option key={w[0]} value={w[0]}>{fmtDate(w[1])}</option>)}</select></label>
      <label><span>Respondent group</span><select value={kind} onChange={e => pickGroup("total:Total", e.target.value)}>
        {kinds.map(k => <option key={k} value={k}>{k === "total" ? "Everyone" : CUT_NAMES[k] ?? k}</option>)}</select></label>
      {kind !== "total" && <label><span>{CUT_NAMES[kind] ?? kind}</span><select value={cut} onChange={e => pickGroup(e.target.value)}>
        <option value="total:Total">All</option>
        {offered.filter(c => c[0] === kind).map(c => <option key={c[1]} value={c.join(":")}>{c[1]}</option>)}</select></label>}
      <label><span>Category</span><select value={category} onChange={e => pick("c", e.target.value)}>
        {categories.map(l => <option key={l}>{l}</option>)}</select></label>
    </section>

    <div className="grid g4">
      <div className="card kpi lead"><div className="k-label">Bought in a store</div><div className="k-value">{pct(nowStore)}</div>
        <div className="k-note"><Delta d={change(data.inStore, nowStore)} label={vs} flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Bought online</div><div className="k-value">{pct(nowOnline)}</div>
        <div className="k-note"><Delta d={change(data.onLine, nowOnline)} label={vs} flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Store lead over online</div>
        <div className="k-value">{nowStore != null && nowOnline != null ? `${(nowStore - nowOnline).toFixed(1)} pts` : "–"}</div>
        <div className="k-note">{category}</div></div>
      <div className="card kpi"><div className="k-label">Online share of the category</div>
        <div className="k-value">{nowStore != null && nowOnline != null && nowStore + nowOnline > 0 ? pct(100 * nowOnline / (nowStore + nowOnline)) : "–"}</div>
        <div className="k-note">online ÷ (store + online)</div></div>
    </div>

    <div className="grid g2">
      <Card title={barTitle} aside={<ExportButtons onExport={exportBars} png={() => barChart.current && downloadPng(barChart.current, `${barTitle}: ${groupName}, ${fmtDate(date)}`, source, `${barTitle} ${date}`)} />}
            sub={sideBySide ? `${fmtDate(date)} · % of each group who bought it in a store (red) and online (blue) · click a group to see its trend`
                            : `${groupName} · ${fmtDate(date)} · % who bought each in a store (red) and online (blue) · click a category to see its trend`}>
        <EChart height={height} label={sideBySide ? `${category} by ${kindName}, ${fmtDate(date)}` : `In store and online buying by category, ${fmtDate(date)}`}
                onClick={p => openRow(String(p.componentType === "yAxis" ? p.value : p.name))} option={barOption()} build={barOption} onReady={c => { barChart.current = c; }} />
      </Card>
      <Card title={category} sub={`${trendName} · ${rangeText} · week by week, in a store (red) vs online (blue, dashed)`}
            aside={<ExportButtons onExport={exportTrend} png={() => lineChart.current && downloadPng(lineChart.current, `${lineTitle}, ${rangeText}`, source, `${category} in store vs online`)} />}>
        <div className="toolbar one-row" style={{ marginBottom: 8 }}>
          <label className="sr-only" htmlFor="trend-kind">Respondent group for the trend</label>
          <select id="trend-kind" value={trendKind} onChange={e => chooseTrendKind(e.target.value)} title="Respondent group for the trend">
            {trendKinds.map(k => <option key={k} value={k}>{k === "total" ? "Everyone" : CUT_NAMES[k] ?? k}</option>)}</select>
          <label className="sr-only" htmlFor="trend-from">From</label>
          <select id="trend-from" value={span[0][0]} onChange={e => pick("from", e.target.value)} title="From">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>From {fmtDate(w[1])}</option>)}</select>
          <label className="sr-only" htmlFor="trend-to">To</label>
          <select id="trend-to" value={span.at(-1)![0]} onChange={e => pick("to", e.target.value)} title="To">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>To {fmtDate(w[1])}</option>)}</select>
        </div>
        {trendKind !== "total" && <div className="seg" role="group" aria-label={`${CUT_NAMES[trendKind] ?? trendKind}: one group at a time`} style={{ marginBottom: 8 }}>
          {[["total", "Total"], ...trendOffered.filter(c => c[0] === trendKind)].map(c =>
            <button key={c[1]} type="button" aria-pressed={c.join(":") === trendCut} onClick={() => pick("t", c.join(":"))}>
              {c[0] === "total" ? "Everyone" : c[1]}</button>)}
        </div>}
        {drawn.length
          ? <EChart height={height - (trendKind !== "total" ? 92 : 48)} label={`${category}: in store vs online over time, ${trendName}`}
                    option={lineOption()} build={lineOption} onReady={c => { lineChart.current = c; }} />
          : <Empty>{trendName} has no answers between these weeks.</Empty>}
        {unanswered > 0 && <p className="muted small">{trendName} has no answers in {unanswered} of these weeks (their surveys did not ask
          about {(CUT_NAMES[trendKind] ?? trendKind).toLowerCase()}): the lines break there.</p>}
      </Card>
    </div>
    <p className="source-line">{source} Every group is shown, however small: check its base (n, in the trend's tooltip).</p>
  </div>;
}
