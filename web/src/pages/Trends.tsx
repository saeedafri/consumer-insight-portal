// A question across every wave of its tracker: real dates (missing weeks stay gaps, never joined), the focus
// answer in red with circular markers, others in blue, optional ±margin of error band and 4-week average.
import { useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { COLUMNS, CUT_OF, useBook, useTrend } from "../api";
import type { Column, Trend } from "../api";
import { Card, Empty, Failure, Loading } from "../components/bits";
import EChart, { AXIS_TEXT, TOOLTIP } from "../components/EChart";
import QuestionNav from "../components/QuestionNav";
import { downloadCsv } from "../csv";
import { C, blues } from "../theme";
import { fmtDate, moe, pct, pts, significant } from "../stats";

const RANGES = [["3m", 92], ["6m", 183], ["1y", 366], ["all", 1e5]] as const;
const DAY = 86_400_000;

export default function Trends() {
  const { id: raw, q: code } = useParams();
  const id = Number(raw);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: book, isLoading, error } = useBook(id);
  const question = useMemo(() => book?.questions.find(x => x.id === code) ?? book?.questions[0], [book, code]);
  const column = (COLUMNS.includes(params.get("col") as Column) ? params.get("col") : "Total") as Column;
  const [dim, value] = CUT_OF[column];
  const trend = useTrend(id, question?.id ?? "", dim, value);
  if (isLoading) return <Loading what="questions" />;
  if (error || !book) return <Failure error={error} />;
  if (!question) return <Empty>This wave has no questions with percentages.</Empty>;
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); v ? p.set(k, v) : p.delete(k); setParams(p, { replace: true }); };
  return <div className="split">
    <QuestionNav questions={book.questions} current={question.id} onPick={q => navigate(`/w/${id}/trends/${encodeURIComponent(q.id)}?${new URLSearchParams({ col: column })}`)} />
    <div className="stack">
      <Card>
        <div className="qhead"><code>{question.id}</code><span>{question.section}</span></div>
        <p className="qtext">{question.text}</p>
        <div className="toolbar" style={{ margin: 0 }}>
          <label className="sr-only" htmlFor="col">Respondents</label>
          <select id="col" value={column} onChange={e => set("col", e.target.value)}>{COLUMNS.map(c => <option key={c}>{c}</option>)}</select>
          <div className="seg" role="group" aria-label="Time range">
            {RANGES.map(([k]) => <button key={k} aria-pressed={(params.get("range") ?? "1y") === k} onClick={() => set("range", k)}>{k === "all" ? "All" : k}</button>)}
          </div>
          <label className="check"><input type="checkbox" checked={params.get("avg") === "1"} onChange={e => set("avg", e.target.checked ? "1" : "")} /> 4-week average</label>
          <label className="check"><input type="checkbox" checked={params.get("band") === "1"} onChange={e => set("band", e.target.checked ? "1" : "")} /> Margin of error</label>
        </div>
      </Card>
      {trend.error ? <Failure error={trend.error} /> : !trend.data ? <Loading what="trend" />
        : <TrendCard t={trend.data} column={column} waveId={id} />}
    </div>
  </div>;
}

function TrendCard({ t, column, waveId }: { t: Trend; column: Column; waveId: number }) {
  const [params, setParams] = useSearchParams();
  const range = RANGES.find(([k]) => k === (params.get("range") ?? "1y"))![1];
  const avg = params.get("avg") === "1", band = params.get("band") === "1";
  const at = t.waves.findIndex(w => w.survey_id === waveId);
  const start = new Date(t.waves[at].wave_date).getTime() - range * DAY;
  const idx = t.waves.map((w, i) => i).filter(i => new Date(t.waves[i].wave_date).getTime() >= start && i <= at);
  const ranked = [...t.series].sort((a, b) => (b.pct[at] ?? -1) - (a.pct[at] ?? -1));
  const chosen = (params.get("show")?.split("|") ?? ranked.slice(0, 3).map(s => s.label)).filter(l => t.series.some(s => s.label === l));
  const shown = t.series.filter(s => chosen.includes(s.label)).sort((a, b) => chosen.indexOf(a.label) - chosen.indexOf(b.label));
  const toggle = (label: string) => {
    const next = chosen.includes(label) ? chosen.filter(l => l !== label) : [...chosen, label];
    const p = new URLSearchParams(params); p.set("show", next.join("|")); setParams(p, { replace: true });
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
    const smooth = (s: (number | null)[]) => s.map((_, i) => {
      const win = s.slice(Math.max(0, i - 3), i + 1).filter((v): v is number => v != null);
      return win.length ? win.reduce((a, b) => a + b, 0) / win.length : null;
    });
    const dense = idx.length > 30;
    const series: object[] = [];
    shown.forEach((s, k) => {
      const values = avg ? smooth(s.pct) : s.pct;
      const color = k === 0 ? C.red : shades[k - 1];
      series.push({
        type: "line", name: s.label, data: points(values).map(([time, v], j, all) => {
          const i = t.waves.findIndex(w => new Date(w.wave_date + "T00:00:00").getTime() === time);
          const prev = all.slice(0, j).reverse().find(p => p[1] != null);
          const pi = prev ? t.waves.findIndex(w => new Date(w.wave_date + "T00:00:00").getTime() === prev[0]) : -1;
          const jump = !avg && v != null && i > 0 && pi >= 0 && s.base[i] && s.base[pi] && s.pct[pi] != null &&
                       significant(v, s.base[i]!, s.pct[pi]!, s.base[pi]!);
          return { value: [time, v], i, symbolSize: jump ? 9 : dense ? 0 : 6, itemStyle: jump ? { color: "#fff", borderColor: color, borderWidth: 2.5 } : undefined };
        }),
        connectNulls: false, showSymbol: true, symbol: "circle", lineStyle: { width: k === 0 ? 2.25 : 1.5, color }, itemStyle: { color },
        emphasis: { focus: "series" }, z: 10 - k,
      });
      if (band && k === 0) {
        const lower = points(s.pct.map((p, i) => (p == null || !s.base[i] ? null : p - moe(p, s.base[i]!))));
        const width = points(s.pct.map((p, i) => (p == null || !s.base[i] ? null : 2 * moe(p, s.base[i]!))));
        series.push({ type: "line", stack: "band", data: lower, lineStyle: { opacity: 0 }, symbol: "none", silent: true, tooltip: { show: false } },
                    { type: "line", stack: "band", data: width, lineStyle: { opacity: 0 }, symbol: "none", areaStyle: { color: "rgba(214,46,47,.12)" }, silent: true, tooltip: { show: false } });
      }
    });
    return {
      tooltip: { ...TOOLTIP, trigger: "axis", axisPointer: { type: "line", lineStyle: { color: C.silver } },
        formatter: (ps: { seriesName: string; color: string; data: { value: [number, number | null]; i: number } }[]) => {
          const real = ps.filter(p => p.data?.value?.[1] != null && p.data.i >= 0);
          if (!real.length) return "No wave this week (not fielded or not loaded)";
          const i = real[0].data.i;
          return `<b>Wave of ${fmtDate(t.waves[i].wave_date)}</b>` + real.map(p => {
            const s = t.series.find(x => x.label === p.seriesName)!;
            const v = p.data.value[1]!, base = s.base[i] ?? 0;
            const pi = t.waves.slice(0, i).map((_, k) => k).reverse().find(k => s.pct[k] != null);
            const change = pi == null ? "" : ` · ${pts(v - s.pct[pi]!)}${s.base[pi] && significant(v, base, s.pct[pi]!, s.base[pi]!) ? " <b>sig.</b>" : ""}`;
            return `<div style="margin-top:5px"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${p.color};margin-right:6px"></span>${s.label}<br/>` +
                   `<b style="font-size:15px">${pct(v)}</b> ±${moe(v, base).toFixed(1)} · n=${base}${avg ? " · 4-wk avg" : change}</div>`;
          }).join("");
        } },
      legend: { show: false },
      grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: "time", axisLabel: { ...AXIS_TEXT, hideOverlap: true }, axisLine: { lineStyle: { color: C.silver } }, axisTick: { show: true } },
      yAxis: { type: "value", axisLabel: { ...AXIS_TEXT, formatter: "{value}%" }, splitLine: { lineStyle: { color: C.mist } },
               min: (v: { min: number }) => Math.max(0, Math.floor((v.min - 5) / 10) * 10) },
      series,
    };
  }, [t, idx, shown, avg, band]);
  const focus = shown[0];
  const exportCsv = () => downloadCsv(`${t.qcode}-trend-${column}`, ["Wave", ...shown.map(s => `${s.label} %`), ...shown.map(s => `${s.label} base`)],
    idx.map(i => [t.waves[i].wave_date, ...shown.map(s => s.pct[i]), ...shown.map(s => s.base[i])]), [`${t.qcode} trend, ${column}`, "Source: Coresight Research US Consumer Survey"]);
  if (idx.length < 2) return <Card><Empty>This question was asked in only one wave in this range. Choose “All” or another question.</Empty></Card>;
  return <>
    <Card title={`${focus ? focus.label : "Pick an answer"}: ${idx.length} waves`} sub={`${column} · ${fmtDate(t.waves[idx[0]].wave_date)} – ${fmtDate(t.waves[at].wave_date)} · white rings mark a significant change from the previous wave`}
          aside={<button className="btn" onClick={exportCsv}>Download CSV</button>}>
      {shown.length ? <EChart option={option} height={380} label={`Trend of ${t.qcode}`} /> : <Empty>Pick at least one answer below.</Empty>}
      <div className="legend-line" role="group" aria-label="Answers shown">
        {ranked.map(s => {
          const k = chosen.indexOf(s.label);
          return <label key={s.label} className="check">
            <input type="checkbox" checked={k >= 0} onChange={() => toggle(s.label)} />
            <i style={{ background: k === 0 ? C.red : k > 0 ? blues(Math.max(shown.length - 1, 1))[k - 1] : C.mist }} />{s.label} <b>{pct(s.pct[at])}</b>
          </label>;
        })}
      </div>
    </Card>
    {focus && <Card title={`Recent waves: ${focus.label}`}>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Wave</th><th className="num">Share</th><th className="num">± margin</th><th className="num">Base</th><th className="num">vs previous wave</th></tr></thead>
        <tbody>{idx.slice(-10).reverse().map(i => {
          const v = focus.pct[i], b = focus.base[i] ?? 0;
          const pi = idx.filter(k => k < i).reverse().find(k => focus.pct[k] != null);
          const sig = v != null && pi != null && significant(v, b, focus.pct[pi]!, focus.base[pi] ?? 0);
          return <tr key={i} className={i === at ? "picked" : ""}><th scope="row">{fmtDate(t.waves[i].wave_date)}</th>
            <td className="num"><b>{pct(v)}</b></td><td className="num muted">{v == null ? "–" : `±${moe(v, b).toFixed(1)}`}</td><td className="num">{b || "–"}</td>
            <td className={`num ${sig ? "sig" : "muted"}`}>{v == null || pi == null ? "–" : pts(v - focus.pct[pi]!)}{sig ? " ●" : ""}</td></tr>;
        })}</tbody>
      </table></div>
    </Card>}
  </>;
}
