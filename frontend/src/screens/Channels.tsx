// In store vs online (/app/channels): which categories people bought in a store and which online in the past two weeks,
// from a weekly survey chosen with the Market filter: the US tracker's Q4/Q5 (Aug 2022 to Dec 2023), then Q2/Q3 and q2/q3
// (from Jan 2024, and Dec 2020 to Jul 2022 under older codes the publish joins by wording), or China's Q5/Q6 (from Feb 2023).
// Its published question files (every group, exact counts; etl → api/v1/questions/CSI-US/tracker/q2|q3|Q4|Q5.json.gz,
// CSI-CN/tracker/Q5|Q6.json.gz) are fetched once and cached; every pick of week, group or category is computed here in
// the browser, so nothing runs on the server when someone changes a filter.
// Opened from the left menu (Core research) and the Home page's cards (China's widest gap opens it on China); market,
// week, group, category and the trend's date range are kept in the address. Respondent group is one group at a time:
// Everyone (the default), or a kind (gender, age, income…) and one of its groups, its first by default, with no "All"
// (the research team, 26 Nov 2026); only groups this week has answers from are offered. The filters above and the line
// chart's own group list and buttons are the same choice. The bar chart shows, for Everyone, every category, biggest in
// store first, the chosen one highlighted where it ranks; for a kind, the chosen category for each of its groups side by
// side (the manager, 27 Nov 2026), the chosen group highlighted with Everyone's figure as a grey tick; the line chart
// shows the chosen category for the chosen group week by week, over the year up to the chosen week unless From / To are
// chosen.
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
import { fmtDate, pts } from "../stats";
import { baseText, chosenCut, drawnWeeks, EVERYONE, figure, groupLabel, rowLabel, shares, SKIP, time, trendWeeks } from "../weekly";

const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;

// Each market's weekly survey: its in-store and online questions (newest code first) and the wording of the weeks that
// count. The US tracker renumbered the two, and a code also held other questions in other weeks (q2 was "places you are
// avoiding" until Dec 2023, Q4 a food-retailer question from Jan 2024): only the weeks whose wording is this question count.
const SURVEYS = {
  US: { family: "CSI-US", store: ["q2", "Q4"], online: ["q3", "Q5"], storeWording: /in a store in the past two weeks/i,
        onlineWording: /online in the past two weeks/i, source: "Coresight Research US Consumer Survey, weekly tracker, about " +
        "400 US adults a week; questions q2 (in a store) and q3 (online), asked as Q11_2/Q11_3, Q9_1/Q9_2 and Q5_1/Q5_2 from " +
        "December 2020 to July 2022, Q4/Q5 to December 2023, Q2/Q3 to April 2025 and q0004/q0005 in May 2025, past two weeks" },
  CN: { family: "CSI-CN", store: ["Q5", ""], online: ["Q6", ""], storeWording: /purchased in physical stores/i,
        onlineWording: /purchased online/i, source: "Coresight Research China Consumer Survey, weekly, about 550 adults in " +
        "China a week; questions Q5 (in physical stores) and Q6 (online), past two weeks" },
};

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
  const kinds = [...new Set(offered.map(c => c[0]))];
  // the group (g): a group this week has no answers from gives way to its kind's first group, then to everyone
  const cut = chosenCut(offered, params.get("g") ?? "");
  const kind = cut.split(":")[0];
  const groups = offered.filter(c => c[0] === kind);
  // a group keeps the category on screen (else each group would open on its own biggest category, 27 Nov 2026)
  const chooseGroup = (g: string) => setParams(p => { p.set("g", g); p.set("c", category); return p; }, { replace: true });
  const chooseKind = (k: string) => chooseGroup(offered.find(c => c[0] === k)!.join(":"));   // a kind opens on its first group
  const kindOptions = kinds.map(k => <option key={k} value={k}>{k === "total" ? "Everyone" : CUT_NAMES[k] ?? k}</option>);
  // the categories this week asked both ways, biggest in store first
  const categories = [...data.storeLabels].filter(l => data.labels.has(l) && !SKIP.test(l) && data.inStore(week, cut, l) != null)
    .sort((x, y) => (data.inStore(week, cut, y) ?? 0) - (data.inStore(week, cut, x) ?? 0));
  const category = categories.includes(params.get("c") ?? "") ? params.get("c")! : categories[0];
  const kindName = CUT_NAMES[kind] ?? kind;
  const groupName = cut === EVERYONE ? "Everyone" : `${kindName}: ${groupLabel(cut.slice(kind.length + 1))}`;
  const nowStore = data.inStore(week, cut, category), nowOnline = data.onLine(week, cut, category);
  const change = (fn: typeof data.inStore, now: number | null) => prior && now != null && fn(prior[0], cut, category) != null ? now - fn(prior[0], cut, category)! : null;
  // a row of the bar chart: a category of the group, or (a kind chosen) a group of the kind for the category; only the
  // groups with an answer for it this week
  const sideBySide = kind !== "total";
  const barCut = (row: string) => sideBySide ? `${kind}:${row}` : cut;
  const barLabel = (row: string) => sideBySide ? category : row;
  const rows = sideBySide ? groups.map(c => c[1]).filter(g => data.inStore(week, barCut(g), category) != null) : categories;
  const focus = sideBySide ? cut.slice(kind.length + 1) : category;
  // both cards draw at one height, so the trend card has no empty space under its chart beside the long category list
  const height = Math.max(400, rows.length * 30 + 60);
  const source = `Source: ${survey.source}. Unweighted.`;

  // the trend's date range: the year up to the week chosen above (the Week filter moves it, 27 Nov 2026), unless From /
  // To are chosen; choosing another week clears them
  const { oldestFirst, span } = trendWeeks(data.weeks, at, params.get("from"), params.get("to"));
  // the line starts and ends where the group has both figures (Non-binary from Aug 2022), so each line's end label and
  // the gap are one week's; a week in between without them (20 US weeks of 2021-22 have no demographics in CIP:
  // docs/CHANGELOG.md, 26 Nov 2026) breaks the line, and the note under it counts them
  const answered = (w: [number, string]) => data.inStore(w[0], cut, category) != null && data.onLine(w[0], cut, category) != null;
  const { drawn, unanswered, rangeText } = drawnWeeks(span, answered);
  const both = drawn.at(-1);   // the last week, where the gap between the two lines is marked
  const bothStore = both && figure(data.inStore(both[0], cut, category)), bothOnline = both && figure(data.onLine(both[0], cut, category));
  // the gap from the unrounded figures, as the Store lead card: from the rounded ones it read +13.3 where the card said 13.4
  const gap = both && bothStore != null && bothOnline != null ? data.inStore(both[0], cut, category)! - data.onLine(both[0], cut, category)! : null;

  const withEveryone = cut !== EVERYONE;   // Everyone's figure beside a group's
  const channels = [["In a store", data.inStore, C.red, "store"], ["Online", data.onLine, C.blue, "online"]] as const;
  const barFigure = (fn: typeof data.inStore, row: string, who = barCut(row)) => figure(fn(week, who, barLabel(row)));
  /** In-store (red) and online (blue) bars, a pair per row: every category for the group, biggest in store first, or
   *  the category for each group of a kind. The row the line chart shows stays where it ranks (26 Nov 2026), in full
   *  colour; the others lighter. Only that row shows its % and Everyone's figure as a short grey tick across each bar (a
   *  bar past it is above everyone's); every row's figures are in the hover (the user, 27 Nov 2026: on every row they
   *  made the chart busy). A pictorial bar (a tick at the bar's end) is laid out like the bars, so each tick sits on its
   *  own bar; the % sits in a column on the right, as the Retailer databank's "Who shops there" does, as at the bar's end
   *  a tick could cross it. */
  const barOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" },
      formatter: ([p]: { name: string }[]) => `${groupLabel(p.name)}<br>` + channels.map(([name, fn, , style]) => `${name} <b>${pct(barFigure(fn, p.name))}</b>` +
        ` <span style="color:${C.ink3}">${baseText((style === "store" ? data.storeBase : data.onlineBase)(week, barCut(p.name)))}</span>` +
        (withEveryone ? ` <span style="color:${C.ink3}">Everyone ${pct(barFigure(fn, p.name, EVERYONE))}</span>` : "")).join("<br>") },
    legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online", ...(withEveryone ? [{ name: "Everyone", icon: "path://M0 0H2V12H0Z" }] : [])] },
    grid: { left: 8, right: 8, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
    yAxis: [{ type: "category", inverse: true, data: rows, triggerEvent: true,
              axisLabel: { ...axisText(), width: 190, overflow: "truncate", color: (row?: string) => row === focus ? C.ink : C.ink3,
                           formatter: (row: string) => rowLabel(row, data.storeBase(week, barCut(row))) } },
            // in a store over online, beside each pair of bars (two 10 px bars 3 px apart: 13 px between their middles)
            { type: "category", inverse: true, data: rows, position: "right", axisLabel: { align: "right", margin: 44, lineHeight: 13,
              formatter: (r: string) => r === focus ? channels.map(([, fn, , style]) => `{${style}|${pct(barFigure(fn, r))}}`).join("\n") : "",
              rich: Object.fromEntries(channels.map(([, , color, style]) => [style, { color, fontSize: 11, fontWeight: 700 }])) } }],
    series: [...channels.map(([name, fn, color]) => ({
      type: "bar", name, barMaxWidth: 10, barGap: "30%", itemStyle: { color, borderRadius: [2, 4, 4, 2] },
      data: rows.map(r => ({ value: barFigure(fn, r), ...(r === focus ? {} : { itemStyle: { opacity: 0.3 } }) })) })),
      ...(withEveryone ? channels.map(([, fn]) => ({
        type: "pictorialBar", name: "Everyone", barMaxWidth: 10, barGap: "30%", symbol: "rect", symbolSize: [2, 12], symbolPosition: "end",
        itemStyle: { color: C.other }, data: rows.map(r => r === focus ? barFigure(fn, r, EVERYONE) : null) })) : [])],
  });
  const barTitle = sideBySide ? `${category} by ${kindName.toLowerCase()}` : "All categories, this week";
  const exportBars = (format: Format) => downloadTable(format, `${barTitle} ${date}`,
    [sideBySide ? kindName : "Category", "In a store %", "Online %", ...(withEveryone ? ["Everyone in a store %", "Everyone online %"] : []), "In a store base", "Online base"],
    rows.map(r => [groupLabel(r), ...channels.map(([, fn]) => barFigure(fn, r)), ...(withEveryone ? channels.map(([, fn]) => barFigure(fn, r, EVERYONE)) : []),
                   data.storeBase(week, barCut(r)), data.onlineBase(week, barCut(r))]),
    [`${barTitle}: ${groupName}, ${fmtDate(date)}`, source]);

  const lineOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis",
      // the base beside each figure: a small group (Non-binary, a handful a week) swings, and "check its base" is the rule
      formatter: (points: { marker: string; seriesName: string; value: [number, number | null, number | null] }[]) =>
        `${fmtDate(new Date(points[0].value[0]).toISOString().slice(0, 10))}<br>` + points.filter(p => p.seriesName !== "gap")
          .map(p => `${p.marker}${p.seriesName} <b>${pct(p.value[1])}</b> <span style="color:${C.ink3}">${baseText(p.value[2])}</span>`).join("<br>") },
    legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online"] },
    grid: { left: 8, right: 112, top: 36, bottom: 28, containLabel: true },   // right: room for the end labels
    xAxis: { type: "time", min: "dataMin", max: "dataMax", axisLabel: valueText() },
    yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
    // both lines solid: their colours tell them apart (the research team, 26 Nov 2026)
    series: [...([["In a store", data.inStore, data.storeBase, C.red], ["Online", data.onLine, data.onlineBase, C.blue]] as const)
      .map(([name, fn, base, color]) => ({
        type: "line", name, showSymbol: false, smooth: 0.2, color, lineStyle: { width: 2 },
        data: drawn.map(w => [time(w[1]), figure(fn(w[0], cut, category)), base(w[0], cut)]),
        // each line's latest figure at its end, as in the research team's mock-up
        endLabel: { show: true, color, fontSize: 12, formatter: (p: { value: [number, number | null] }) => `${name} ${pct(p.value[1])}` },
        labelLayout: { moveOverlap: "shiftY" },   // end labels of lines that end close together move apart
      })),
      // the gap between the two lines, once, at the last week both were asked: a bracket between the lines' ends and its
      // figure as an end label between theirs (a label on the bracket itself would be turned on its side)
      ...(both && bothStore != null && bothOnline != null && gap != null ? [{
        type: "line", name: "gap", silent: true, showSymbol: false, lineStyle: { opacity: 0 }, tooltip: { show: false },
        data: [[time(both[1]), (bothStore + bothOnline) / 2]], labelLayout: { moveOverlap: "shiftY" },
        endLabel: { show: true, color: C.ink2, fontSize: 11, formatter: `${pts(gap)} gap` },
        markLine: { silent: true, symbol: "none", animation: false, label: { show: false }, lineStyle: { color: C.ink3, type: "solid", width: 1 },
                    data: [[{ coord: [time(both[1]), bothStore] }, { coord: [time(both[1]), bothOnline] }]] },
      }] : [])],
  });
  const lineTitle = `${category}: in a store vs online, ${groupName}`;
  const exportTrend = (format: Format) => downloadTable(format, `${category} in store vs online`,
    ["Week", "In a store %", "Online %", "In a store base", "Online base"],
    drawn.map(w => [w[1], figure(data.inStore(w[0], cut, category)), figure(data.onLine(w[0], cut, category)),
                    data.storeBase(w[0], cut), data.onlineBase(w[0], cut)]),
    [`${lineTitle}, ${rangeText}`, source]);

  return <div className="stack">
    <div className="page-head"><div>
      <h1>In store vs online</h1>
      <p className="lede">Percentage of respondents who bought each category in a store or online.</p>
    </div></div>

    <section className="card compare-bar" aria-label="Choose what to show">
      <label><span>Market</span><select value={market} onChange={e => chooseMarket(e.target.value)}>
        {marketOptions(Object.keys(SURVEYS))}</select></label>
      <label><span>Week</span><select value={week} onChange={e => setParams(p => { p.set("w", e.target.value); p.delete("from"); p.delete("to"); return p; }, { replace: true })}>
        {data.weeks.map(w => <option key={w[0]} value={w[0]}>{fmtDate(w[1])}</option>)}</select></label>
      <label><span>Respondent group</span><select value={kind} onChange={e => chooseKind(e.target.value)}>{kindOptions}</select></label>
      {kind !== "total" && <label><span>{kindName}</span><select value={cut} onChange={e => chooseGroup(e.target.value)}>
        {groups.map(c => <option key={c[1]} value={c.join(":")}>{groupLabel(c[1])}</option>)}</select></label>}
      <label><span>Category</span><select value={category} onChange={e => pick("c", e.target.value)}>
        {categories.map(l => <option key={l}>{l}</option>)}</select></label>
    </section>

    <div className="grid g4">
      <div className="card kpi lead"><div className="k-label">Bought in a store</div><div className="k-value">{pct(nowStore)}</div>
        <div className="k-note"><Delta d={change(data.inStore, nowStore)} label={vs} flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Bought online</div><div className="k-value">{pct(nowOnline)}</div>
        <div className="k-note"><Delta d={change(data.onLine, nowOnline)} label={vs} flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">Store lead over online</div>
        <div className="k-value">{nowStore != null && nowOnline != null ? pts(nowStore - nowOnline) : "–"}</div>
        <div className="k-note">{category}</div></div>
      <div className="card kpi"><div className="k-label">Online share of the category</div>
        <div className="k-value">{nowStore != null && nowOnline != null && nowStore + nowOnline > 0 ? pct(100 * nowOnline / (nowStore + nowOnline)) : "–"}</div>
        <div className="k-note">online ÷ (store + online)</div></div>
    </div>

    <div className="grid g2">
      <Card title={barTitle} aside={<ExportButtons onExport={exportBars} png={() => barChart.current && downloadPng(barChart.current, `${barTitle}: ${groupName}, ${fmtDate(date)}`, source, `${barTitle} ${date}`)} />}
            sub={<><span className="chip flat">{groupName}</span> <span className="chip flat">{fmtDate(date)}</span><br />{sideBySide
              ? <>Percentage of each group who bought it in a store (red) and online (blue), Everyone's as a grey tick · hover a group
                for its figures, click it to see its trend</>
              : <>Percentage of respondents who bought each category in a store (red) and online (blue) · hover a category for its
                figures, click it to see its trend</>}</>}>
        <EChart height={height} label={sideBySide ? `${category}: in store and online buying by ${kindName.toLowerCase()}, ${fmtDate(date)}` : `In store and online buying by category, ${groupName}, ${fmtDate(date)}`}
                onClick={p => { const row = String(p.componentType === "yAxis" ? p.value : p.name); if (sideBySide) chooseGroup(barCut(row)); else pick("c", row); }}
                option={barOption()} build={barOption} onReady={c => { barChart.current = c; }} />
      </Card>
      <Card title={category} sub={<><span className="chip flat">{groupName}</span> <span className="chip flat">{rangeText}</span><br />Percentage of respondents who bought it each week, in a
              store (red) and online (blue)</>}
            aside={<ExportButtons onExport={exportTrend} png={() => lineChart.current && downloadPng(lineChart.current, `${lineTitle}, ${rangeText}`, source, `${category} in store vs online`)} />}>
        <div className="toolbar one-row" style={{ marginBottom: 8 }}>
          <label className="sr-only" htmlFor="trend-kind">Respondent group</label>
          <select id="trend-kind" value={kind} onChange={e => chooseKind(e.target.value)} title="Respondent group">{kindOptions}</select>
          <label className="sr-only" htmlFor="trend-from">From</label>
          <select id="trend-from" value={span[0][0]} onChange={e => pick("from", e.target.value)} title="From">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>From {fmtDate(w[1])}</option>)}</select>
          <label className="sr-only" htmlFor="trend-to">To</label>
          <select id="trend-to" value={span.at(-1)![0]} onChange={e => pick("to", e.target.value)} title="To">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>To {fmtDate(w[1])}</option>)}</select>
        </div>
        {kind !== "total" && <div className="seg" role="group" aria-label={`${kindName}: one group at a time`} style={{ marginBottom: 8 }}>
          {groups.map(c => <button key={c[1]} type="button" aria-pressed={c.join(":") === cut} onClick={() => chooseGroup(c.join(":"))}>{groupLabel(c[1])}</button>)}
        </div>}
        {drawn.length
          ? <EChart height={height - (kind !== "total" ? 92 : 48)} label={`${category}: in store vs online over time, ${groupName}`}
                    option={lineOption()} build={lineOption} onReady={c => { lineChart.current = c; }} />
          : <Empty>{groupName} has no answers between these weeks.</Empty>}
        {unanswered > 0 && <p className="muted small">No answers from {groupName} for this category in {unanswered} of these
          weeks: the lines break there.</p>}
      </Card>
    </div>
    <p className="source-line">{source} Every group is shown, however small: check its base (n, in the trend's tooltip).</p>
  </div>;
}
