// A question across every wave of its tracker: real dates (missing weeks stay gaps, never joined), the focus
// answer in red with circular markers, others in blue, optional ±margin of error band and 4-week average.
import { useMemo, useRef } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { COLUMNS, CUT_OF, present, useBook, useQuestion, useWaves } from "../api";
import { cellsOf, toTrend } from "../question";
import type { Column, Trend } from "../api";
import { Card, copyLink, Empty, Failure, Loading, SourceLine, sourceText, ExportButtons } from "../components/bits";
import EChart, { axisText, downloadPng, tooltip } from "../components/EChart";
import type { Chart } from "../components/EChart";
import QuestionNav from "../components/QuestionNav";
import { downloadTable } from "../csv";
import type { Format } from "../csv";
import { C, blues } from "../theme";
import { fmtDate, moe, pct, pts, significant } from "../stats";
import { perf } from "../perf";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { ChevronLeft, ChevronRight, Image as ImageIcon, Link as LinkIcon } from "lucide-react";

const RANGES = [["3m", 92], ["6m", 183], ["1y", 366], ["all", 1e5]] as const;
const DAY = 86_400_000;
const WEEKLY_GAP = 10;   // days: a longer silence is a missing wave or another season, never "the previous wave"

/** The answer's previous wave, only when it is the week before (not across a gap or season). */
function previous(t: Trend, s: Trend["series"][number], i: number): number | null {
  for (let k = i - 1; k >= 0; k--) {
    if (t.waves[k].version !== t.waves[i].version) return null;
    if (new Date(t.waves[i].wave_date).getTime() - new Date(t.waves[k].wave_date).getTime() > WEEKLY_GAP * DAY) return null;
    if (s.pct[k] != null) return k;
  }
  return null;
}

export default function Trends() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  const column = (COLUMNS.includes(params.get("col") as Column) ? params.get("col") : "Total") as Column;
  const [dim, value] = CUT_OF[column];
  const waves = useWaves().data ?? [];
  const familySize = waves.filter(w => w.survey_family === book?.wave.survey_family && w.study_type === book?.wave.study_type && w.rows_built !== 0).length;
  const file = useQuestion(familySize > 1 ? book?.wave : undefined, question?.id ?? "");   // one wave: nothing to trend
  const cells = useMemo(() => file.data && cellsOf(file.data), [file.data]);
  const trend = { error: file.error, data: useMemo(() => file.data && cells && toTrend(file.data, cells, dim, value), [file.data, cells, dim, value]) };
  if (isLoading) return <Loading what="questions" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const qIndex = book.questions.findIndex(x => x.id === question.id);
  const prevQ = qIndex > 0 ? book.questions[qIndex - 1] : null;
  const nextQ = qIndex >= 0 && qIndex < book.questions.length - 1 ? book.questions[qIndex + 1] : null;
  const set = (k: string, v: string) => {
    perf.startFilterChange(k, v || "default");
    const p = new URLSearchParams(params);
    v ? p.set(k, v) : p.delete(k);
    setParams(p, { replace: true });
  };
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/trends/${encodeURIComponent(q.id)}?${new URLSearchParams({ col: column })}`)} />
    <div className="stack">
      <Card>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div className="breadcrumb">
            <Link to={`/w/${id}`}>Overview</Link>
            <span className="sep">›</span>
            <span>{question.section}</span>
            <span className="sep">›</span>
            <code>{question.id}</code>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={!prevQ}
                    onClick={() => prevQ && navigate(`/w/${id}/trends/${encodeURIComponent(prevQ.id)}?${new URLSearchParams({ col: column })}`)}
                    aria-label="Previous question"
                  >
                    <ChevronLeft size={14} />
                  </Button>
                }
              />
              <TooltipContent side="top">
                {prevQ ? `Previous: ${prevQ.id} (${prevQ.short || prevQ.text})` : "First question"}
              </TooltipContent>
            </Tooltip>
            <span style={{ fontSize: 11.5, color: "var(--ink-2)", fontWeight: 600 }}>{qIndex + 1} of {book.questions.length}</span>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={!nextQ}
                    onClick={() => nextQ && navigate(`/w/${id}/trends/${encodeURIComponent(nextQ.id)}?${new URLSearchParams({ col: column })}`)}
                    aria-label="Next question"
                  >
                    <ChevronRight size={14} />
                  </Button>
                }
              />
              <TooltipContent side="top">
                {nextQ ? `Next: ${nextQ.id} (${nextQ.short || nextQ.text})` : "Last question"}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
        <div className="qhead"><code>{question.id}</code><span>{question.section}</span></div>
        <p className="qtext">{question.text}</p>
        <div className="toolbar" style={{ margin: 0, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <label className="sr-only" htmlFor="col">Respondents</label>
          <select id="col" value={column} onChange={e => set("col", e.target.value)}>{present(book.n).map(c => <option key={c}>{c}</option>)}</select>
          <Tabs value={params.get("range") ?? "1y"} onValueChange={k => set("range", k)}>
            <TabsList>
              {RANGES.map(([k]) => (
                <TabsTrigger key={k} value={k}>{k === "all" ? "All" : k}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <label className="check" title="Each point becomes the mean of that wave and the three before it: smooths week-to-week noise, at the cost of reacting a month late."><input type="checkbox" checked={params.get("avg") === "1"} onChange={e => set("avg", e.target.checked ? "1" : "")} /> 4-week average</label>
          <label className="check" title="The shaded band is the 95 % margin of error of the red line: with about 400 people a week, ±5 points. Moves inside it can be noise."><input type="checkbox" checked={params.get("band") === "1"} onChange={e => set("band", e.target.checked ? "1" : "")} /> Margin of error</label>
        </div>
      </Card>
      {familySize === 1 ? <Card><Empty>This survey was fielded once, so there is no trend. Weekly tracker questions and repeated studies have trends.</Empty></Card>
        : trend.error ? <Failure error={trend.error} /> : !trend.data ? <Loading what="trend" />
        : <TrendCard t={trend.data} column={column} waveId={id} />}
    </div>
  </div>;
}

function TrendCard({ t, column, waveId }: { t: Trend; column: Column; waveId: number }) {
  if (!t.waves.length) return <Card><Empty>No respondents in {column === "Total" ? "this survey" : `the ${column} group`} answered this question. Choose another column or question.</Empty></Card>;
  return <TrendView t={t} column={column} waveId={waveId} />;
}

function TrendView({ t, column, waveId }: { t: Trend; column: Column; waveId: number }) {
  const [params, setParams] = useSearchParams();
  const chart = useRef<Chart | null>(null);
  const range = RANGES.find(([k]) => k === (params.get("range") ?? "1y"))![1];
  const avg = params.get("avg") === "1", band = params.get("band") === "1";
  const at = t.waves.findIndex(w => w.survey_id === waveId);
  const start = new Date(t.waves[at].wave_date).getTime() - range * DAY;
  const version = t.waves[at].version;   // one question per line: other versions reused this code for something else
  const idx = t.waves.map((w, i) => i).filter(i => t.waves[i].version === version && new Date(t.waves[i].wave_date).getTime() >= start && i <= at);
  const elsewhere = t.waves.filter(w => w.version !== version).length;
  const ranked = [...t.series].sort((a, b) => (b.pct[at] ?? -1) - (a.pct[at] ?? -1));
  const chosen = (params.get("show")?.split("|") ?? ranked.slice(0, 3).map(s => s.label)).filter(l => t.series.some(s => s.label === l));
  const shown = t.series.filter(s => chosen.includes(s.label)).sort((a, b) => chosen.indexOf(a.label) - chosen.indexOf(b.label));
  const toggle = (label: string) => {
    const next = chosen.includes(label) ? chosen.filter(l => l !== label) : [...chosen, label];
    const p = new URLSearchParams(params); p.set("show", next.join("|")); setParams(p, { replace: true });
  };
  const setChosen = (labels: string[]) => {
    const p = new URLSearchParams(params);
    p.set("show", labels.join("|"));
    setParams(p, { replace: true });
  };
  const option = useMemo(() => {
    const shades = blues(Math.max(shown.length - 1, 1));
    const gapDays = 10;   // weekly tracker: a longer silence is a missing wave, drawn as a gap
    const points = (values: (number | null)[]) => {
      const out: [number, number | null][] = [];
      idx.forEach((i, k) => {
        const time = new Date(t.waves[i].wave_date + "T00:00:00").getTime();
        if (k && time - new Date(t.waves[idx[k - 1]].wave_date + "T00:00:00").getTime() > gapDays * DAY) out.push([time - DAY, null]);
        out.push([time, values[i]]);
      });
      return out;
    };
    // the mean of this wave and up to three before it, only across weekly waves of the same question version: a gap
    // (missing or seasonal wave) or a reused code ends the window instead of averaging unlike weeks
    const smooth = (s: (number | null)[]) => s.map((v, i) => {
      if (v == null) return null;
      const win = [v];
      for (let k = i - 1; k >= 0 && win.length < 4; k--) {
        if (t.waves[k].version !== t.waves[i].version || new Date(t.waves[k + 1].wave_date).getTime() - new Date(t.waves[k].wave_date).getTime() > WEEKLY_GAP * DAY) break;
        if (s[k] != null) win.push(s[k]!);
      }
      return win.reduce((a, b) => a + b, 0) / win.length;
    });
    const dense = idx.length > 30;
    const series: object[] = [];
    shown.forEach((s, k) => {
      const values = avg ? smooth(s.pct) : s.pct;
      const color = k === 0 ? C.red : shades[k - 1];
      series.push({
        type: "line", name: s.label, data: points(values).map(([time, v], j, all) => {
          const i = t.waves.findIndex(w => new Date(w.wave_date + "T00:00:00").getTime() === time);
          const pi = i >= 0 ? previous(t, s, i) : null;
          const jump = !avg && v != null && pi != null && s.base[i] && s.base[pi] && significant(v, s.base[i]!, s.pct[pi]!, s.base[pi]!);
          return { value: [time, v], i, symbolSize: jump ? 9 : dense ? 0 : 6, itemStyle: jump ? { color: C.surface, borderColor: color, borderWidth: 2.5 } : undefined };
        }),
        connectNulls: false, showSymbol: true, symbol: "circle", lineStyle: { width: k === 0 ? 2.25 : 1.5, color }, itemStyle: { color },
        endLabel: { show: true, color, fontWeight: 700, fontSize: 11, formatter: (p: { value: [number, number | null] }) => (p.value[1] == null ? "" : `${p.value[1].toFixed(0)}%`) },
        emphasis: { focus: "series" }, z: 10 - k,
      });
      if (band && k === 0) {
        const lower = points(s.pct.map((p, i) => (p == null || !s.base[i] ? null : p - moe(p, s.base[i]!))));
        const width = points(s.pct.map((p, i) => (p == null || !s.base[i] ? null : 2 * moe(p, s.base[i]!))));
        series.push({ type: "line", stack: "band", data: lower, lineStyle: { opacity: 0 }, symbol: "none", silent: true, tooltip: { show: false } },
                    { type: "line", stack: "band", data: width, lineStyle: { opacity: 0 }, symbol: "none", areaStyle: { color: "rgba(214,46,47,.16)" }, silent: true, tooltip: { show: false } });
      }
    });
    return {
      tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "line", lineStyle: { color: C.silver } },
        formatter: (ps: { seriesName: string; color: string; data: { value: [number, number | null]; i: number } }[]) => {
          const real = ps.filter(p => p.data?.value?.[1] != null && p.data.i >= 0);
          if (!real.length) return "No wave this week (not fielded or not loaded)";
          const i = real[0].data.i;
          return `<b>Wave of ${fmtDate(t.waves[i].wave_date)}</b>` + real.map(p => {
            const s = t.series.find(x => x.label === p.seriesName)!;
            const v = p.data.value[1]!, base = s.base[i] ?? 0;
            const pi = previous(t, s, i);
            const change = pi == null ? "" : ` · ${pts(v - s.pct[pi]!)}${s.base[pi] && significant(v, base, s.pct[pi]!, s.base[pi]!) ? " <b>sig.</b>" : ""}`;
            return `<div style="margin-top:5px"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${p.color};margin-right:6px"></span>${s.label}<br/>` +
                   `<b style="font-size:15px">${pct(v)}</b> ±${moe(v, base).toFixed(1)} · n=${base}${avg ? " · 4-wk avg" : change}</div>`;
          }).join("");
        } },
      legend: { show: false },
      grid: { left: 8, right: 44, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: "time", axisLabel: { ...axisText(), hideOverlap: true }, axisLine: { lineStyle: { color: C.silver } }, axisTick: { show: true } },
      yAxis: { type: "value", axisLabel: { ...axisText(), formatter: "{value}%" }, splitLine: { lineStyle: { color: C.mist } },
               min: (v: { min: number }) => Math.max(0, Math.floor((v.min - 5) / 10) * 10) },
      series,
    };
  }, [t, idx, shown, avg, band]);
  const focus = shown[0];
  const bases = idx.map(i => focus?.base[i]).filter((b): b is number => b != null);
  const baseRange = bases.length ? `${Math.min(...bases)}–${Math.max(...bases)}` : "–";
  const exportAs = (format: Format) => downloadTable(format, `${t.qcode}-trend-${column}`, ["Wave", ...shown.map(s => `${s.label} %`), ...shown.map(s => `${s.label} base`)],
    idx.map(i => [t.waves[i].wave_date, ...shown.map(s => s.pct[i]), ...shown.map(s => s.base[i])]), [`${t.qcode} trend, ${column}`, "Source: Coresight Research US Consumer Survey"]);
  if (idx.length < 2) {
    const same = t.waves.filter(w => w.version === version).length;
    return <Card><Empty>{same < 2
      ? <>This wording of {t.qcode} was asked in only one wave{t.versions.length > 1 ? `; the code ${t.qcode} was used for ${t.versions.length - 1} other question${t.versions.length === 2 ? "" : "s"} in other waves, which are never joined into this trend` : ""}.</>
      : <>This question was asked in only one wave in this range. Choose “All” to see its {same} waves.</>}</Empty></Card>;
  }
  return <>
    <Card title={`${focus ? focus.label : "Pick an answer"}: ${idx.length} waves`} sub={`${column} · ${fmtDate(t.waves[idx[0]].wave_date)} – ${fmtDate(t.waves[at].wave_date)} · white rings mark a significant change from the previous wave`}
          aside={<div className="toolbar" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <ExportButtons onExport={exportAs} />
            <Button
              variant="outline"
              size="sm"
              onClick={() => chart.current && focus && downloadPng(chart.current, `${t.qcode} · ${focus.label}: ${idx.length} waves`,
                sourceText(fmtDate(t.waves[at].wave_date), `n ${baseRange} per wave · ${column}`), `${t.qcode}-trend`)}
            >
              <ImageIcon size={14} />
              Download PNG
            </Button>
            <Button variant="outline" size="sm" onClick={e => copyLink(e.currentTarget)}>
              <LinkIcon size={14} />
              <span>Copy link</span>
            </Button>
          </div>}>
      {t.versions.length > 1 && <p className="muted" style={{ margin: "0 0 10px", fontSize: 13 }}>
        Version {version} of {t.versions.length} of {t.qcode}: this code was also used for {t.versions.length - 1 === 1 ? "another question" : `${t.versions.length - 1} other questions`} in {elsewhere} wave{elsewhere === 1 ? "" : "s"}, left out here.
        {t.versions.filter((_, i) => i + 1 !== version).slice(0, 3).map((text, i) => <span key={i} style={{ display: "block" }}>· “{text.length > 110 ? text.slice(0, 109) + "…" : text}”</span>)}
      </p>}
      {shown.length ? <EChart option={option} height={380} label={`Trend of ${t.qcode}, ${column}`} onReady={c => { chart.current = c; }} />
        : <Empty>Pick at least one answer below.</Empty>}
      {ranked.length > 3 && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, margin: "14px 0 8px", fontSize: 12 }}>
          <span className="muted" style={{ fontWeight: 600 }}>Quick select:</span>
          <Button variant="outline" size="xs" onClick={() => setChosen(ranked.slice(0, 3).map(s => s.label))}>Top 3</Button>
          {ranked.length > 5 && <Button variant="outline" size="xs" onClick={() => setChosen(ranked.slice(0, 5).map(s => s.label))}>Top 5</Button>}
          <Button variant="outline" size="xs" onClick={() => setChosen(ranked.map(s => s.label))}>All ({ranked.length})</Button>
          <Button variant="outline" size="xs" onClick={() => setChosen([ranked[0].label])}>Top 1 only</Button>
        </div>
      )}
      <div className="legend-line" role="group" aria-label="Answers shown">
        {ranked.map(s => {
          const k = chosen.indexOf(s.label);
          return <label key={s.label} className="check">
            <input type="checkbox" checked={k >= 0} onChange={() => toggle(s.label)} />
            <i style={{ background: k === 0 ? C.red : k > 0 ? blues(Math.max(shown.length - 1, 1))[k - 1] : C.mist }} />{s.label} <b>{pct(s.pct[at])}</b>
          </label>;
        })}
      </div>
      <SourceLine wave={fmtDate(t.waves[at].wave_date)} base={`n ${baseRange} per wave`} extra={`${column}${avg ? " · 4-week average" : ""}${band ? " · band = 95 % margin of error" : ""}`} />
    </Card>
    {focus && <Card title={`Recent waves: ${focus.label}`}>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Wave</th><th className="num">Share</th><th className="num">± margin</th><th className="num">Base</th><th className="num">vs previous wave</th></tr></thead>
        <tbody>{idx.slice(-10).reverse().map(i => {
          const v = focus.pct[i], b = focus.base[i] ?? 0;
          const pi = previous(t, focus, i);
          const sig = v != null && pi != null && significant(v, b, focus.pct[pi]!, focus.base[pi] ?? 0);
          return <tr key={i} className={i === at ? "picked" : ""}><th scope="row">{fmtDate(t.waves[i].wave_date)}</th>
            <td className="num"><b>{pct(v)}</b></td><td className="num muted">{v == null ? "–" : `±${moe(v, b).toFixed(1)}`}</td><td className="num">{b || "–"}</td>
            <td className={`num ${sig ? "sig" : "muted"}`}>{v == null || pi == null ? "–" : pts(v - focus.pct[pi]!)}{sig ? " ●" : ""}</td></tr>;
        })}</tbody>
      </table></div>
    </Card>}
  </>;
}
