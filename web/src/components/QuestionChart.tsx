// One question as a chart, following the Coresight chart rules: light-blue bars with one red highlight,
// horizontal bars for long labels (never angled), an ombre of blues for several series, data labels in ink.
import { useMemo } from "react";
import type { Column, Group, Question, Row } from "../api";
import { isFiller } from "../api";
import { C, blues, labelOn, scaleColours } from "../theme";
import { count, moe, pct, pts, significant, SMALL_BASE } from "../stats";
import EChart, { AXIS_TEXT, TOOLTIP } from "./EChart";

export type View = "bars" | "columns" | "stacked" | "donut" | "table";
export const VIEWS: { key: View; label: string }[] = [
  { key: "bars", label: "Bars" }, { key: "columns", label: "Columns" }, { key: "stacked", label: "Stacked" },
  { key: "donut", label: "Donut" }, { key: "table", label: "Table" }];

export function viewsFor(q: Question): View[] {
  const grid = q.groups.length > 1;
  const single = q.type === "single" && q.groups[0].rows.length <= 7;
  return (["bars", "columns", "stacked", "donut", "table"] as View[]).filter(v =>
    v === "stacked" ? grid || q.type === "single" : v === "donut" ? single : true);
}

const esc = (s: string) => s.replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]!));

/** The hover card: answer, value, people behind it, its base and how it moved. */
export function tip(row: Row, column: Column, group: Group, question: Question, wave: string): string {
  const v = row[column];
  const base = group.bases[column] ?? group.base;
  const lines = [`<div style="font-weight:600;margin-bottom:4px">${esc(row.label)}</div>`,
    `<div style="font-size:20px;font-weight:700;color:${C.red}">${pct(v)} <span style="font-size:12px;font-weight:500;color:#5f5c5b">±${moe(v ?? 0, base).toFixed(1)} pts</span></div>`,
    `<div style="color:#5f5c5b">${column}${group.label ? ` · ${esc(group.label)}` : ""} · ≈${count(v ?? 0, base).toLocaleString("en-US")} of ${base.toLocaleString("en-US")} respondents</div>`];
  if (base < SMALL_BASE) lines.push(`<div style="color:#8a5a00;margin-top:4px">Small base (under ${SMALL_BASE}): read with caution</div>`);
  if (column === "Total") {
    const vsPrior = row.flags.includes("base_changed_prior") ? "base changed, not comparable"
      : row.prior == null || !row.prior_base ? "not available"
      : `${pts((v ?? 0) - row.prior)} (${pct(row.prior)}) ${significant(v ?? 0, base, row.prior, row.prior_base) ? "<b>significant</b>" : "not significant"}`;
    const vsLy = row.ly == null ? "not loaded" : `${pts((v ?? 0) - row.ly)} (${pct(row.ly)})`;
    lines.push(`<div style="margin-top:6px;border-top:1px solid ${C.mist};padding-top:6px">vs last week: ${vsPrior}<br/>vs last year: ${vsLy}</div>`);
  }
  lines.push(`<div style="color:#7f7f7f;margin-top:4px;font-size:11px">${esc(question.id)} · wave of ${wave}</div>`);
  return lines.join("");
}

function ordered(rows: Row[], sort: boolean, column: Column): Row[] {
  if (!sort) return rows;
  const body = rows.filter(r => !isFiller(r.label)).sort((a, b) => (b[column] ?? 0) - (a[column] ?? 0));
  return [...body, ...rows.filter(r => isFiller(r.label))];
}

export default function QuestionChart({ question, group = 0, view, columns, sort, wave, height }:
  { question: Question; group?: number; view: View; columns: Column[]; sort: boolean; wave: string; height?: number }) {
  const g = question.groups[Math.min(group, question.groups.length - 1)];
  const rows = ordered(g.rows, sort, columns[0]);
  const option = useMemo(() => build(question, g, rows, view, columns, wave), [question, g, rows, view, columns, wave]);
  if (view === "table") return <QuestionTable question={question} rows={rows} group={g} columns={columns} />;
  const h = height ?? (view === "bars" ? Math.max(180, rows.length * (columns.length > 1 ? 18 * columns.length + 12 : 34) + 40)
    : view === "stacked" ? Math.max(160, (question.groups.length > 1 ? question.groups.length : 1) * 46 + 80) : 340);
  return <EChart option={option} height={h} label={`${question.id}: ${question.text}`} />;
}

function build(q: Question, g: Group, rows: Row[], view: View, columns: Column[], wave: string) {
  const multiSeries = columns.length > 1;
  const top = Math.max(...rows.filter(r => !isFiller(r.label)).map(r => r[columns[0]] ?? 0));
  // several columns: Total in red (the guide wants red in every chart), the cuts in the blue ombre
  const cuts = blues(Math.max(columns.length - 1, 1));
  const palette = multiSeries ? columns.map((c, i) => (c === "Total" ? C.red : cuts[columns[0] === "Total" ? i - 1 : i])) : [C.sky];
  const tooltip = { ...TOOLTIP, formatter: (p: { dataIndex: number; seriesIndex: number; data?: { row?: Row; group?: Group } }) => {
    const d = p.data ?? {};
    return tip(d.row ?? rows[p.dataIndex], columns[p.seriesIndex] ?? columns[0], d.group ?? g, q, wave);
  } };
  const labels = rows.map(r => r.label);

  if (view === "donut") {
    const shades = blues(rows.length - 1);
    return {
      tooltip, legend: { show: false },
      series: [{
        type: "pie", radius: ["52%", "78%"], avoidLabelOverlap: true, padAngle: 1, itemStyle: { borderRadius: 3 },
        label: { formatter: (p: { name: string; value: number }) => `${p.name.length > 28 ? p.name.slice(0, 27) + "…" : p.name}\n{b|${p.value.toFixed(1)}%}`,
                 color: C.ink, fontSize: 11, rich: { b: { fontWeight: 700, fontSize: 13 } } },
        data: rows.map((r, i) => ({ name: r.label, value: r.Total ?? 0, row: r, group: g,
                                    itemStyle: { color: i === 0 ? C.red : shades[i - 1] } })),
      }],
    };
  }

  if (view === "stacked") {
    const groups = q.groups.length > 1 ? q.groups : [g];
    const answers = groups[0].rows.map(r => r.label);
    const shades = scaleColours(answers) ?? blues(answers.length);
    return {
      tooltip: { ...TOOLTIP, formatter: (p: { data: { row: Row; group: Group } }) => tip(p.data.row, "Total", p.data.group, q, wave) },
      legend: { bottom: 0, textStyle: AXIS_TEXT, itemWidth: 12, itemHeight: 12, icon: "roundRect" },
      grid: { left: 8, right: 16, top: 8, bottom: 56, containLabel: true },
      xAxis: { type: "value", max: 100, axisLabel: { ...AXIS_TEXT, formatter: "{value}%" }, splitLine: { lineStyle: { color: C.mist } } },
      yAxis: { type: "category", inverse: true, data: groups.map(x => x.label || "Total"),
               axisLabel: { ...AXIS_TEXT, width: 200, overflow: "break" }, axisTick: { show: false } },
      series: answers.map((a, i) => ({
        type: "bar", stack: "all", name: a, barWidth: 26,
        itemStyle: { color: shades[i] },
        label: { show: true, formatter: (p: { value: number }) => (p.value >= 7 ? Math.round(p.value) : ""), color: labelOn(shades[i]), fontSize: 11, fontWeight: 600 },
        data: groups.map(x => { const r = x.rows.find(r => r.label === a); return { value: r?.Total ?? 0, row: r ?? x.rows[0], group: x }; }),
      })),
    };
  }

  const horizontal = view === "bars";
  const category = { type: "category", data: labels, inverse: horizontal, axisTick: { show: false },
                     axisLine: { lineStyle: { color: C.silver } },
                     axisLabel: horizontal ? { ...AXIS_TEXT, width: 230, overflow: "break", lineHeight: 14 }
                                           : { ...AXIS_TEXT, interval: 0, width: Math.max(60, 640 / Math.max(rows.length, 1)), overflow: "break" } };
  const value = { type: "value", max: (v: { max: number }) => Math.min(100, Math.ceil((v.max + 8) / 10) * 10),
                  axisLabel: { ...AXIS_TEXT, formatter: "{value}%" }, splitLine: { lineStyle: { color: C.mist } } };
  return {
    tooltip, legend: multiSeries ? { top: 0, textStyle: AXIS_TEXT, icon: "roundRect", itemWidth: 12, itemHeight: 12 } : { show: false },
    grid: { left: 8, right: horizontal ? 48 : 12, top: multiSeries ? 32 : 8, bottom: 8, containLabel: true },
    xAxis: horizontal ? value : category, yAxis: horizontal ? category : value,
    series: columns.map((col, si) => ({
      type: "bar", name: col, barMaxWidth: multiSeries ? 14 : 26, barGap: "15%", color: palette[si],
      itemStyle: { borderRadius: horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0], color: palette[si] },
      label: { show: !multiSeries || rows.length <= 8, position: horizontal ? "right" : "top", color: C.ink, fontSize: 11,
               fontWeight: 600, formatter: (p: { value: number }) => `${p.value.toFixed(multiSeries ? 0 : 1)}%` },
      data: rows.map(r => ({
        value: r[col] ?? 0, row: r, group: g,
        itemStyle: { color: !multiSeries && (r[col] ?? 0) === top && !isFiller(r.label) ? C.red : palette[si],
                     opacity: (g.bases[col] ?? g.base) < SMALL_BASE ? 0.55 : 1 },
      })),
    })),
  };
}

export function QuestionTable({ question, rows, group, columns }: { question: Question; rows: Row[]; group: Group; columns: Column[] }) {
  return <div className="table-wrap"><table className="data">
    <caption className="sr-only">{question.text}</caption>
    <thead><tr><th>Answer</th>{columns.map(c => <th key={c} className="num">{c}<small>n={(group.bases[c] ?? 0).toLocaleString("en-US")}</small></th>)}
      {columns.includes("Total") && <><th className="num">Last week</th><th className="num">Change</th></>}</tr></thead>
    <tbody>{rows.map(r => {
      const sig = r.prior != null && r.prior_base ? significant(r.Total ?? 0, group.base, r.prior, r.prior_base) : false;
      return <tr key={r.label}><th scope="row">{r.label}</th>
        {columns.map(c => <td key={c} className={`num ${(group.bases[c] ?? 0) < SMALL_BASE ? "small" : ""}`}>{pct(r[c])}</td>)}
        {columns.includes("Total") && <><td className="num muted">{pct(r.prior)}</td>
          <td className={`num ${sig ? "sig" : "muted"}`}>{r.flags.includes("base_changed_prior") ? "base changed" : r.prior == null ? "–" : pts((r.Total ?? 0) - r.prior)}</td></>}
      </tr>;
    })}</tbody>
  </table></div>;
}
