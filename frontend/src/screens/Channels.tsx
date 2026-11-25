// In store vs online (/app/channels): which categories people bought in a store and which online in the past two weeks,
// from a weekly survey chosen with the Market filter: the US tracker's Q4/Q5 (Aug 2022 to Dec 2023), then Q2/Q3 and q2/q3
// (from Jan 2024), or China's Q5/Q6 (from Feb 2023). Its published question files (every group, exact counts; etl →
// api/v1/questions/CSI-US/tracker/q2|q3|Q4|Q5.json.gz, CSI-CN/tracker/Q5|Q6.json.gz) are fetched once and cached;
// every pick of week, group or category is computed here in the browser, so nothing runs on the server when someone changes a filter.
// Opened from the left menu (Core research) and the Home page's cards (China's widest gap opens it on China); market,
// week, group, category and the trend's date range are kept in the address. Respondent group is two choices: a kind of
// group (gender, age, income…), then All or one group; only groups this week has answers from are offered (older income
// bands are empty in recent weeks). All of a kind puts its groups side by side (the research team's call of 23 Nov 2026):
// the category by group, and each group's trend.
import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { CUT_NAMES, useQuestion, useWaves } from "../api";
import type { QuestionFile } from "../api";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { Delta } from "../components/Glance";
import { Card, Empty, ExportButtons, Failure, marketOptions, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import { C, useTheme } from "../theme";
import { fmtDate } from "../stats";

const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const SKIP = /^(none of|other|don.?t know)/i;

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
 *  → % of the group asked, or null; weeks: survey_id → date; labels: every answer those weeks gave. */
function shares(files: QuestionFile[], wording: RegExp) {
  const cells = new Map<string, [number | null, number]>();
  const weeks = new Map<number, string>(), labels = new Set<string>();
  for (const file of files) {
    const kept = file.waves.map(w => wording.test(file.versions[w[2] - 1] ?? ""));
    file.waves.forEach((w, i) => kept[i] && weeks.set(w[0], w[1]));
    file.w.forEach((w, k) => {
      if (!kept[w]) return;
      const label = file.answers[file.a[k]][0];
      labels.add(label);
      cells.set(`${file.waves[w][0]}|${file.cuts[file.c[k]].join(":")}|${label}`, [file.n[k], file.b[k]]);
    });
  }
  const share = (survey: number, cut: string, label: string) => {
    const cell = cells.get(`${survey}|${cut}|${label}`);
    return cell && cell[0] != null && cell[1] ? 100 * cell[0] / cell[1] : null;
  };
  return { share, weeks, labels };
}

export default function Channels() {
  const waves = useWaves().data;
  const [params, setParams] = useSearchParams();
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
    return { weeks, cuts: store1!.cuts, inStore: store.share, storeLabels: store.labels,
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
  const offered = data.cuts.filter(c => [...data.storeLabels].some(l => data.inStore(week, c.join(":"), l) != null));
  const cut = offered.some(c => c.join(":") === params.get("g")) ? params.get("g")! : "total:Total";
  const kinds = [...new Set(offered.map(c => c[0]))];
  // "All" of a kind is everyone, with the kind kept in the address (k) so its group list stays open
  const kind = cut !== "total:Total" ? cut.split(":")[0] : kinds.includes(params.get("k") ?? "") ? params.get("k")! : "total";
  const choose = (k: string) => setParams(p => { p.set("g", "total:Total"); if (k === "total") p.delete("k"); else p.set("k", k); return p; }, { replace: true });
  // the categories this week asked both ways, biggest in store first
  const categories = [...data.storeLabels].filter(l => data.labels.has(l) && !SKIP.test(l) && data.inStore(week, cut, l) != null)
    .sort((x, y) => (data.inStore(week, cut, y) ?? 0) - (data.inStore(week, cut, x) ?? 0));
  const category = categories.includes(params.get("c") ?? "") ? params.get("c")! : categories[0];
  const kindName = CUT_NAMES[kind] ?? kind;
  const sideBySide = kind !== "total" && cut === "total:Total";   // All of a kind: its groups side by side
  const groups = offered.filter(c => c[0] === kind).map(c => c[1]);
  const groupName = sideBySide ? `${kindName}, each group` : cut === "total:Total" ? "Everyone" : `${CUT_NAMES[cut.split(":")[0]] ?? ""}: ${cut.split(":")[1]}`;
  const hue = (i: number) => [C.redLine, C.s1, C.s3, C.other, C.rose, C.s2, C.grey, C.silver][i % 8];   // a group's colour, the same on both charts
  const nowStore = data.inStore(week, cut, category), nowOnline = data.onLine(week, cut, category);
  const change = (fn: typeof data.inStore, now: number | null) => prior && now != null && fn(prior[0], cut, category) != null ? now - fn(prior[0], cut, category)! : null;
  // both cards draw at one height, so the trend card has no empty space under its chart beside the long category list
  const height = Math.max(340, categories.length * 30 + 60);
  // the trend's date range (its own, as the research team asked on 23 Nov 2026: the week above does not move it)
  const oldestFirst = [...data.weeks].reverse();
  // where the address's From or To week sits among the weeks (an unknown week: the first, or the newest)
  const place = (key: string, fallback: number) => { const i = oldestFirst.findIndex(w => String(w[0]) === params.get(key)); return i < 0 ? fallback : i; };
  const [first, last] = [place("from", 0), place("to", oldestFirst.length - 1)].sort((x, y) => x - y);   // From after To: swapped
  const span = oldestFirst.slice(first, last + 1);
  const spanText = `${fmtDate(span[0][1])} to ${fmtDate(span.at(-1)![1])}`;
  const figure = (v: number | null) => v == null ? null : +v.toFixed(1);   // a % as charts and exports show it
  const source = `Source: ${survey.source}. Unweighted.`;
  const shown = sideBySide ? groups.map(g => [g, `${kind}:${g}`]) : [["", cut]];   // the trend's groups: [name, cut]
  const exportTrend = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, `${category} in store vs online`,
    ["Week", ...shown.flatMap(([g]) => [`${g} in a store %`.trim(), `${g} online %`.trim()])],
    span.map(w => [w[1], ...shown.flatMap(([, c]) => [figure(data.inStore(w[0], c, category)), figure(data.onLine(w[0], c, category))])]),
    [`${category}: ${groupName}, ${spanText}`, source]);
  /** In-store (red) and online (blue) bars, a pair per row: every category for one group, or every group for one category. */
  const bars = (rows: string[], share: (fn: Share, row: string) => number | null) => ({
    tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: number) => pct(v) },
    legend: { top: 0, left: 0, textStyle: axisText(), data: ["In a store", "Online"] },
    grid: { left: 8, right: 40, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
    yAxis: { type: "category", inverse: true, data: rows, axisLabel: { ...axisText(), width: 190, overflow: "truncate" } },
    series: [["In a store", data.inStore, C.red], ["Online", data.onLine, C.blue]].map(([name, fn, color]) => ({
      type: "bar", name, barMaxWidth: 10, barGap: "30%", itemStyle: { color, borderRadius: [2, 4, 4, 2] },
      data: rows.map(r => figure(share(fn as Share, r))) })),
  });
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
      <label><span>Respondent group</span><select value={kind} onChange={e => choose(e.target.value)}>
        {kinds.map(k => <option key={k} value={k}>{k === "total" ? "Everyone" : CUT_NAMES[k] ?? k}</option>)}</select></label>
      {kind !== "total" && <label><span>{CUT_NAMES[kind] ?? kind}</span><select value={cut} onChange={e => pick("g", e.target.value)}>
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
      <div className="card kpi"><div className="k-label">Online share of the two</div>
        <div className="k-value">{nowStore != null && nowOnline != null && nowStore + nowOnline > 0 ? pct(100 * nowOnline / (nowStore + nowOnline)) : "–"}</div>
        <div className="k-note">online ÷ (store + online)</div></div>
    </div>

    <div className="grid g2">
      {sideBySide
        ? <Card title={`${category} by ${kindName.toLowerCase()}`} sub={`${fmtDate(date)} · % of each group who bought it in a store (red) and online (blue) · click a group to see it alone`}>
            <EChart height={height} label={`${category} by ${kindName}, ${fmtDate(date)}`} onClick={p => pick("g", `${kind}:${p.name}`)}
                    option={bars(groups, (fn, g) => fn(week, `${kind}:${g}`, category))} />
          </Card>
        : <Card title="All categories, this week" sub={`${groupName} · ${fmtDate(date)} · % who bought each in a store (red) and online (blue)`}>
            <EChart height={height} label={`In store and online buying by category, ${fmtDate(date)}`} onClick={p => pick("c", p.name)}
                    option={bars(categories, (fn, l) => fn(week, cut, l))} />
          </Card>}
      <Card title={category} sub={`${groupName} · ${spanText} · ${sideBySide ? "solid: in a store, dashed: online" : "in a store (red) vs online (blue)"}`}
            aside={<ExportButtons onExport={exportTrend} />}>
        <div className="toolbar one-row" style={{ marginBottom: 8 }}>
          <label className="sr-only" htmlFor="trend-from">From</label>
          <select id="trend-from" value={span[0][0]} onChange={e => pick("from", e.target.value)} title="From">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>From {fmtDate(w[1])}</option>)}</select>
          <label className="sr-only" htmlFor="trend-to">To</label>
          <select id="trend-to" value={span.at(-1)![0]} onChange={e => pick("to", e.target.value)} title="To">
            {oldestFirst.map(w => <option key={w[0]} value={w[0]}>To {fmtDate(w[1])}</option>)}</select>
        </div>
        <EChart height={height - 48} label={`${category}: in store vs online over time`}
                option={{
                  tooltip: { ...tooltip(), trigger: "axis", valueFormatter: (v: number | null) => pct(v) },
                  legend: { top: 0, left: 0, type: "scroll", textStyle: axisText() },
                  grid: { left: 8, right: 16, top: 36, bottom: 40, containLabel: true },
                  xAxis: { type: "time", axisLabel: valueText() },
                  yAxis: { type: "value", axisLabel: { ...valueText(), formatter: "{value}%" } },
                  series: shown.flatMap(([g, c], i) => ([["In a store", data.inStore, sideBySide ? hue(i) : C.red, "solid"],
                                                          ["Online", data.onLine, sideBySide ? hue(i) : C.blue, sideBySide ? "dashed" : "solid"]] as const)
                    .map(([what, fn, color, line]) => ({
                      type: "line", name: sideBySide ? `${g}, ${what.toLowerCase()}` : what, showSymbol: false, smooth: 0.2, color, lineStyle: { width: 2, type: line },
                      data: span.map(w => [time(w[1]), fn(w[0], c, category)]) }))),
                }} />
      </Card>
    </div>
    <p className="source-line">{source} Every group is shown, however small: check its base.</p>
  </div>;
}
