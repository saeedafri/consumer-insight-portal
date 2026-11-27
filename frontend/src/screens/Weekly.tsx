// The weekly topic screens (the manager's roadmap of 27 Nov 2026): Activities & retailers (/app/activities), Spending
// pressure (/app/spending) and Consumer sentiment & outlook (/app/sentiment), one question of the US weekly tracker at a
// time, laid out as In store vs online (screens/Channels.tsx): filters for the week, the respondent group and the
// answer; a bar chart of every answer for the group, or, a kind of group chosen, the answer for each of its groups side
// by side (the chosen one highlighted with Everyone's figure as a grey tick: the demographic breakdown); and the answer
// for the group week by week over the year up to the chosen week, or From / To. Which questions: TOPICS below, each tab
// a question under its codes and the wording that tells its weeks apart. Its published question files are fetched once
// and cached (frontend/src/weekly.ts); every pick is computed here, so nothing runs on the server. Opened from the left
// menu (Core research); the tab, week, group, answer and the trend's dates are kept in the address. US only: China's
// weekly survey asks none of these questions.
import { useMemo, useRef } from "react";
import { useLocation, useSearchParams } from "react-router";
import { CUT_NAMES, isFiller, useQuestion, useWaves } from "../api";
import type { QuestionFile } from "../api";
import EChart, { axisText, downloadPng, tooltip, valueText } from "../components/EChart";
import type { Chart } from "../components/EChart";
import { Delta } from "../components/Glance";
import { Card, Empty, ExportButtons, Failure, marketOptions, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { C, useTheme } from "../theme";
import { fmtDate } from "../stats";
import { shares, SKIP } from "../weekly";

const time = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const DAY = 86_400_000, YEAR = 365 * DAY;   // the trend's default range: the year up to the chosen week
const EVERYONE = "total:Total";
const SURVEY = "Coresight Research US Consumer Survey, weekly tracker, about 400 US adults a week";

/** Answers added up: a name, the answers it counts and those it takes off (a net, shown in points). */
type Sum = [name: string, plus: RegExp, minus?: RegExp];
/** One tab: a question under its codes, its weeks told apart by wording. Its answers are every answer given (a
 *  multiple-answer question), `sums` of a scale's answers, or each row of a grid added up by `rows` [plus, minus]. */
interface Tab { name: string; codes: string[]; wording: RegExp; answer: string; all: string; each: string; asked: string;
                sums?: Sum[]; rows?: [RegExp, RegExp?] }
const OUTLOOK: Sum[] = [["Net better", /better/i, /worse/i], ["Better", /better/i], ["About the same", /same/i], ["Worse", /worse/i],
                        ["Don't know", /know|sure/i]];
const EXPENSES = { codes: ["Q6"], wording: /how have your expenses changed/i, answer: "Category",
                   asked: "question q6, how expenses changed in the last twelve months (asked since July 2026)" };

export const TOPICS: Record<string, { title: string; lede: string; tabs: Tab[] }> = {
  activities: { title: "Activities & retailers", tabs: [
    { name: "Activities", codes: ["Q1", "Q3"], wording: /have you done in the past two weeks/i, answer: "Activity",
      all: "Percentage of respondents who did each in the past two weeks", each: "Percentage of each group who did it",
      asked: "question q1 (asked as Q3 from August 2022 to December 2023), past two weeks" },
    { name: "Food retailers", codes: ["Q4", "Q6"], wording: /bought any FOOD products from in the past two weeks/i, answer: "Retailer",
      all: "Percentage of respondents who bought food from each retailer in the past two weeks", each: "Percentage of each group who bought food there",
      asked: "question q4 (asked under other codes in earlier weeks), past two weeks" },
    { name: "Nonfood retailers", codes: ["Q5", "Q7"], wording: /bought any NONFOOD products from in the past two weeks/i, answer: "Retailer",
      all: "Percentage of respondents who bought nonfood products from each retailer in the past two weeks", each: "Percentage of each group who bought nonfood products there",
      asked: "question q5 (asked under other codes in earlier weeks), past two weeks" }],
    lede: "What people did, and where they bought food and nonfood products, in the past two weeks: every week since December 2020." },
  spending: { title: "Spending pressure", tabs: [
    { name: "Expenses up", ...EXPENSES, rows: [/increase/i], all: "Percentage of respondents whose expenses rose notably or significantly in the last twelve months",
      each: "Percentage of each group whose expenses rose" },
    { name: "Expenses down", ...EXPENSES, rows: [/decrease/i], all: "Percentage of respondents whose expenses fell notably or significantly in the last twelve months",
      each: "Percentage of each group whose expenses fell" },
    { name: "Net change", ...EXPENSES, rows: [/increase/i, /decrease/i], all: "Expenses up less expenses down, in points", each: "Expenses up less down, in points, for each group" },
    { name: "Where they cut back", codes: ["D15"], wording: /reduced your spending due to higher gas prices/i, answer: "Category",
      all: "Of those who cut spending because of higher gas prices, the percentage who cut back on each", each: "Percentage of each group who cut back on it",
      asked: "question D15, of those who cut spending elsewhere because of higher gas prices (asked since March 2026)" }],
    lede: "How people say their household expenses changed in the last twelve months, by category, and where they cut back." },
  sentiment: { title: "Consumer sentiment & outlook", tabs: [
    { name: "Personal finances", codes: ["CS1", "q009"], wording: /discretionary income/i, answer: "Answer", sums: OUTLOOK,
      all: "Whether respondents expect their household's discretionary income to be better or worse over the next 12 months; net better in points",
      each: "Each group's answer; net better in points", asked: "question CS1 (q009 until May 2025), next 12 months" },
    { name: "Economy", codes: ["CS2"], wording: /economy overall over the next 12 months/i, answer: "Answer", sums: OUTLOOK,
      all: "Whether respondents expect the economy to be better or worse over the next 12 months; net better in points",
      each: "Each group's answer; net better in points", asked: "question CS2 (q010 and others until 2025), next 12 months" }],
    lede: "Whether people expect their household's finances and the economy to get better or worse over the next 12 months, and how that differs by group." },
};

export default function Weekly() {
  const topic = TOPICS[useLocation().pathname.split("/")[1]] ?? TOPICS.activities;
  const waves = useWaves().data;
  const [params, setParams] = useSearchParams();
  const barChart = useRef<Chart | null>(null), lineChart = useRef<Chart | null>(null);
  const tab = topic.tabs.find(t => t.name === params.get("t")) ?? topic.tabs[0];
  const tracker = waves?.find(w => w.survey_family === "CSI-US" && w.study_type === "tracker");
  const files = [useQuestion(tracker, tab.codes[0]), useQuestion(tracker, tab.codes[1] ?? "")];
  useTheme();   // a theme switch re-renders, so the series take the new theme's colours (C)
  const loaded = files.map(f => f.data);
  const data = useMemo(() => {
    const got = loaded.filter(Boolean) as QuestionFile[];
    if (got.length < tab.codes.length) return null;
    const { share, base, weeks, labels } = shares(got, tab.wording);
    const all = [...labels];
    // each answer as [name, the answers it adds up, those it takes off]
    const rows = [...new Set(all.map(l => l.slice(0, l.lastIndexOf(": "))))];
    const parts: [string, string[], string[]][] = tab.sums
      ? tab.sums.map(([name, plus, minus]) => [name, all.filter(l => plus.test(l)), minus ? all.filter(l => minus.test(l)) : []])
      : tab.rows ? rows.map(row => {
          const own = (re?: RegExp) => re ? all.filter(l => l.startsWith(`${row}: `) && re.test(l.slice(row.length + 2))) : [];
          return [row, own(tab.rows![0]), own(tab.rows![1])];
        })
      : all.filter(l => !SKIP.test(l) && !isFiller(l)).map(l => [l, [l], []]);
    const found = new Map(parts.map(([name, plus, minus]) => [name, [plus, minus]]));
    // a single-answer question stores no cell for an answer nobody gave: 0 once the group was asked that week
    const add = (survey: number, cut: string, ls: string[]) => ls.reduce((sum, l) => sum + (share(survey, cut, l) ?? 0), 0);
    const value = (survey: number, cut: string, answer: string) => {
      const [plus, minus] = found.get(answer) ?? [[], []];
      if (!tab.sums && !tab.rows) return plus.length ? share(survey, cut, plus[0]) : null;
      return base(survey, cut) == null || !plus.length ? null : add(survey, cut, plus) - add(survey, cut, minus);
    };
    const cuts = [...new Map(got.flatMap(f => f.cuts).map(c => [c.join(":"), c])).values()];
    return { value, base, answers: parts.map(([name]) => name), cuts, nets: new Set(parts.filter(([, , minus]) => minus.length).map(([name]) => name)),
             weeks: [...weeks].sort((x, y) => y[1].localeCompare(x[1])) };   // newest first
  }, [tab, ...loaded]);
  const failed = files.find(f => f.error)?.error;
  if (!waves || files.some(f => f.isLoading)) return <SkeletonScreen kind="page" />;
  if (failed) return <Failure error={failed} />;
  const pick = (k: string, v: string) => setParams(p => { p.set(k, v); return p; }, { replace: true });
  // another tab is another question: its answer and trend dates start afresh, the week and group stay when it has them
  const chooseTab = (t: string) => setParams(p => { p.set("t", t); ["c", "from", "to"].forEach(k => p.delete(k)); return p; }, { replace: true });
  const head = <>
    <div className="page-head"><div><h1>{topic.title}</h1><p className="lede">{topic.lede}</p></div></div>
    {topic.tabs.length > 1 && <Tabs value={tab.name} onValueChange={chooseTab}><TabsList>
      {topic.tabs.map(t => <TabsTrigger key={t.name} value={t.name}>{t.name}</TabsTrigger>)}</TabsList></Tabs>}
  </>;
  if (!data || !data.weeks.length) return <div className="stack">{head}<Empty>This question has not been asked yet.</Empty></div>;

  const at = Math.max(0, data.weeks.findIndex(w => String(w[0]) === params.get("w")));
  const [week, date] = data.weeks[at];
  const prior = data.weeks[at + 1];
  const vs = !prior ? "vs the survey before" : time(date) - time(prior[1]) === 7 * DAY ? "vs last week" : `vs ${fmtDate(prior[1])}`;
  // the same week a year earlier: the survey nearest 52 weeks before, within four weeks (etl/sectors.py changes' rule)
  const offYear = (w: [number, string]) => Math.abs(time(date) - time(w[1]) - 364 * DAY);
  const yearAgo = data.weeks.slice(at + 1).filter(w => offYear(w) <= 28 * DAY).sort((x, y) => offYear(x) - offYear(y))[0];
  // a net (better less worse, up less down) in points, signed; any other answer a %
  const fmt = (a: string, v: number | null | undefined) => v == null ? "–" : data.nets.has(a) ? `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}` : `${v.toFixed(1)}%`;
  // household income's "Prefer not to say / answer" is no group (the research team, 25 Nov 2026)
  const offered = data.cuts.filter(c => !(c[0] === "income_band" && isFiller(c[1])) && data.answers.some(a => data.value(week, c.join(":"), a) != null));
  const kinds = [...new Set(offered.map(c => c[0]))];
  const asked = params.get("g") ?? "";
  const cut = (offered.find(c => c.join(":") === asked) ?? offered.find(c => c[0] === asked.split(":")[0]))?.join(":") ?? EVERYONE;
  const kind = cut.split(":")[0], kindName = CUT_NAMES[kind] ?? kind;
  const groups = offered.filter(c => c[0] === kind);
  // the answers this week has for the group: a scale in its own order, others biggest first
  const answers = data.answers.filter(a => data.value(week, cut, a) != null);
  if (!tab.sums) answers.sort((x, y) => (data.value(week, cut, y) ?? 0) - (data.value(week, cut, x) ?? 0));
  const answer = answers.includes(params.get("c") ?? "") ? params.get("c")! : answers[0];
  // a group keeps the answer on screen (else each group would open on its own biggest answer)
  const chooseGroup = (g: string) => setParams(p => { p.set("g", g); p.set("c", answer); return p; }, { replace: true });
  const chooseKind = (k: string) => chooseGroup(offered.find(c => c[0] === k)!.join(":"));   // a kind opens on its first group
  const kindOptions = kinds.map(k => <option key={k} value={k}>{k === "total" ? "Everyone" : CUT_NAMES[k] ?? k}</option>);
  const groupName = cut === EVERYONE ? "Everyone" : `${kindName}: ${cut.slice(kind.length + 1)}`;
  const now = data.value(week, cut, answer);
  const change = (then: [number, string] | undefined) => {
    const was = then && data.value(then[0], cut, answer);
    return now != null && was != null ? now - was : null;
  };
  const source = `Source: ${SURVEY}; ${tab.asked}. Unweighted.`;

  // a row of the bar chart: an answer of the group, or (a kind chosen) a group of the kind for the answer
  const sideBySide = kind !== "total";
  const barCut = (row: string) => sideBySide ? `${kind}:${row}` : cut;
  const barFigure = (row: string, who = barCut(row)) => { const v = data.value(week, who, sideBySide ? answer : row); return v == null ? null : +v.toFixed(1); };
  const rows = sideBySide ? groups.map(c => c[1]).filter(g => barFigure(g) != null) : answers;
  const focus = sideBySide ? cut.slice(kind.length + 1) : answer;
  const height = Math.max(400, rows.length * 30 + 60);   // both cards at one height, so neither has empty space
  const withEveryone = cut !== EVERYONE;
  const rowShow = (row: string, v: number | null) => fmt(sideBySide ? answer : row, v);
  const netAxis = sideBySide ? data.nets.has(answer) : rows.some(r => data.nets.has(r));
  /** The bars, biggest first (a scale in its order), the row the line chart shows in full colour and the others lighter;
   *  only that row shows its figure and Everyone's as a short grey tick (as In store vs online); every row's figures
   *  are in the hover. */
  const barOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" },
      formatter: ([p]: { name: string }[]) => `${p.name}<br>${tab.name} <b>${rowShow(p.name, barFigure(p.name))}</b>` +
        (withEveryone ? ` <span style="color:${C.ink3}">Everyone ${rowShow(p.name, barFigure(p.name, EVERYONE))}</span>` : "") +
        ` <span style="color:${C.ink3}">n ${data.base(week, barCut(p.name)) ?? "–"}</span>` },
    legend: { show: withEveryone, top: 0, left: 0, textStyle: axisText(), data: [tab.name, { name: "Everyone", icon: "path://M0 0H2V12H0Z" }] },
    grid: { left: 8, right: 8, top: withEveryone ? 32 : 8, bottom: 8, containLabel: true },
    xAxis: { type: "value", axisLabel: { ...valueText(), formatter: netAxis ? "{value}" : "{value}%" } },
    yAxis: [{ type: "category", inverse: true, data: rows, triggerEvent: true,
              axisLabel: { ...axisText(), width: 190, overflow: "truncate", color: (row?: string) => row === focus ? C.ink : C.ink3 } },
            { type: "category", inverse: true, data: rows, position: "right",
              axisLabel: { align: "right", margin: 52, color: C.red, fontSize: 11, fontWeight: 700, formatter: (r: string) => r === focus ? rowShow(r, barFigure(r)) : "" } }],
    series: [{ type: "bar", name: tab.name, barMaxWidth: 14, itemStyle: { color: C.red, borderRadius: [2, 4, 4, 2] },
               data: rows.map(r => ({ value: barFigure(r), ...(r === focus ? {} : { itemStyle: { opacity: 0.3 } }) })) },
      ...(withEveryone ? [{ type: "pictorialBar", name: "Everyone", barMaxWidth: 14, symbol: "rect", symbolSize: [2, 18], symbolPosition: "end",
        itemStyle: { color: C.other }, data: rows.map(r => r === focus ? barFigure(r, EVERYONE) : null) }] : [])],
  });
  const barTitle = sideBySide ? `${answer} by ${kindName.toLowerCase()}` : `${tab.name}, this week`;
  const exportBars = (format: Format) => downloadTable(format, `${barTitle} ${date}`,
    [sideBySide ? kindName : tab.answer, netAxis ? tab.name : `${tab.name} %`, ...(withEveryone ? ["Everyone"] : []), "People asked"],
    rows.map(r => [r, barFigure(r), ...(withEveryone ? [barFigure(r, EVERYONE)] : []), data.base(week, barCut(r))]),
    [`${barTitle}: ${groupName}, ${fmtDate(date)}`, sideBySide ? tab.each : tab.all, source], netAxis ? {} : { unit: "%" });

  // the trend's dates: the year up to the week chosen above, unless From / To are chosen; choosing another week clears them
  const oldestFirst = [...data.weeks].reverse();
  const yearBefore = oldestFirst.findIndex(w => time(w[1]) >= time(date) - YEAR);
  const place = (key: string, fallback: number) => { const i = oldestFirst.findIndex(w => String(w[0]) === params.get(key)); return i < 0 ? fallback : i; };
  const [first, last] = [place("from", yearBefore), place("to", oldestFirst.length - 1 - at)].sort((x, y) => x - y);   // From after To: swapped
  const span = oldestFirst.slice(first, last + 1);
  // the line starts and ends where the group has a figure; a week between without one breaks it, and the note counts them
  const answered = (w: [number, string]) => data.value(w[0], cut, answer) != null;
  const start = span.findIndex(answered), end = span.length - [...span].reverse().findIndex(answered);
  const drawn = start < 0 ? [] : span.slice(start, end);
  const unanswered = drawn.filter(w => !answered(w)).length;
  const rangeText = drawn.length ? `${fmtDate(drawn[0][1])} to ${fmtDate(drawn.at(-1)![1])}` : "no weeks";
  const trendFigure = (w: [number, string]) => { const v = data.value(w[0], cut, answer); return v == null ? null : +v.toFixed(1); };
  const lineOption = () => ({
    tooltip: { ...tooltip(), trigger: "axis",
      formatter: (points: { value: [number, number | null, number | null] }[]) => `${fmtDate(new Date(points[0].value[0]).toISOString().slice(0, 10))}<br>` +
        `${answer} <b>${rowShow(answer, points[0].value[1])}</b> <span style="color:${C.ink3}">n ${points[0].value[2] ?? "–"}</span>` },
    grid: { left: 8, right: 96, top: 16, bottom: 28, containLabel: true },   // right: room for the end label
    // months, or a month and day on a short span (Spending pressure's expenses start in July 2026), never a bare day
    xAxis: { type: "time", min: "dataMin", max: "dataMax", axisLabel: { ...valueText(), hideOverlap: true, formatter: { year: "{yyyy}", month: "{MMM}", day: "{MMM} {d}" } } },
    yAxis: { type: "value", scale: data.nets.has(answer), axisLabel: { ...valueText(), formatter: data.nets.has(answer) ? "{value}" : "{value}%" } },
    series: [{ type: "line", name: answer, showSymbol: false, smooth: 0.2, color: C.red, lineStyle: { width: 2 },
               data: drawn.map(w => [time(w[1]), trendFigure(w), data.base(w[0], cut)]),
               endLabel: { show: true, color: C.red, fontSize: 12, formatter: (p: { value: [number, number | null] }) => rowShow(answer, p.value[1]) } }],
  });
  const exportTrend = (format: Format) => downloadTable(format, `${answer} ${tab.name}`, ["Week", data.nets.has(answer) ? answer : `${answer} %`, "People asked"],
    drawn.map(w => [w[1], trendFigure(w), data.base(w[0], cut)]), [`${tab.name}: ${answer}, ${groupName}, ${rangeText}`, source],
    data.nets.has(answer) ? {} : { unit: "%" });

  return <div className="stack">
    {head}
    <section className="card compare-bar" aria-label="Choose what to show">
      <label><span>Market</span><select defaultValue="US">{marketOptions(["US"], "not asked")}</select></label>
      <label><span>Week</span><select value={week} onChange={e => setParams(p => { p.set("w", e.target.value); p.delete("from"); p.delete("to"); return p; }, { replace: true })}>
        {data.weeks.map(w => <option key={w[0]} value={w[0]}>{fmtDate(w[1])}</option>)}</select></label>
      <label><span>Respondent group</span><select value={kind} onChange={e => chooseKind(e.target.value)}>{kindOptions}</select></label>
      {kind !== "total" && <label><span>{kindName}</span><select value={cut} onChange={e => chooseGroup(e.target.value)}>
        {groups.map(c => <option key={c[1]} value={c.join(":")}>{c[1]}</option>)}</select></label>}
      <label><span>{tab.answer}</span><select value={answer} onChange={e => pick("c", e.target.value)}>
        {answers.map(a => <option key={a}>{a}</option>)}</select></label>
    </section>

    <div className="grid g3">
      <div className="card kpi lead"><div className="k-label">{answer}, this week</div><div className="k-value">{fmt(answer, now)}</div>
        <div className="k-note"><Delta d={change(prior)} label={vs} flags={[]} /></div></div>
      <div className="card kpi"><div className="k-label">A year earlier</div><div className="k-value">{fmt(answer, yearAgo && data.value(yearAgo[0], cut, answer))}</div>
        <div className="k-note">{yearAgo ? <Delta d={change(yearAgo)} label="vs LY" flags={[]} /> : "not asked a year earlier"}</div></div>
      <div className="card kpi"><div className="k-label">People asked</div><div className="k-value">{data.base(week, cut)?.toLocaleString("en-US") ?? "–"}</div>
        <div className="k-note">{groupName}, {fmtDate(date)}</div></div>
    </div>

    <div className="grid g2">
      <Card title={barTitle} aside={<ExportButtons onExport={exportBars} png={() => barChart.current && downloadPng(barChart.current, `${barTitle}: ${groupName}, ${fmtDate(date)}`, source, `${barTitle} ${date}`)} />}
            sub={<><span className="chip flat">{groupName}</span> <span className="chip flat">{fmtDate(date)}</span><br />{sideBySide ? tab.each : tab.all}
              {withEveryone && ", Everyone's as a grey tick"} · hover a row for its figures, click it to see its trend</>}>
        <EChart height={height} label={`${barTitle}, ${groupName}, ${fmtDate(date)}`}
                onClick={p => { const row = String(p.componentType === "yAxis" ? p.value : p.name); if (sideBySide) chooseGroup(barCut(row)); else pick("c", row); }}
                option={barOption()} build={barOption} onReady={c => { barChart.current = c; }} />
      </Card>
      <Card title={answer} sub={<><span className="chip flat">{groupName}</span> <span className="chip flat">{rangeText}</span><br />{tab.name}, week by week</>}
            aside={<ExportButtons onExport={exportTrend} png={() => lineChart.current && downloadPng(lineChart.current, `${tab.name}: ${answer}, ${groupName}, ${rangeText}`, source, `${answer} ${tab.name}`)} />}>
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
          {groups.map(c => <button key={c[1]} type="button" aria-pressed={c.join(":") === cut} onClick={() => chooseGroup(c.join(":"))}>{c[1]}</button>)}
        </div>}
        {drawn.length
          ? <EChart height={height - (kind !== "total" ? 92 : 48)} label={`${tab.name}: ${answer} over time, ${groupName}`}
                    option={lineOption()} build={lineOption} onReady={c => { lineChart.current = c; }} />
          : <Empty>{groupName} has no answers between these weeks.</Empty>}
        {unanswered > 0 && <p className="muted small">No answers from {groupName} in {unanswered} of these weeks: the line breaks there.</p>}
      </Card>
    </div>
    <p className="source-line">{source} Every group is shown, however small: check its base (n, in the hover).</p>
  </div>;
}
