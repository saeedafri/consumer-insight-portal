// One ECharts canvas: only the chart types and components CIP uses are bundled (≈190 KB gzipped, its own cached chunk).
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendPlainComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { C, DARK, inLight, LIGHT, savedTheme, useTheme } from "../theme";
import { perf } from "../perf";

echarts.use([AriaComponent, BarChart, LineChart, PieChart, GridComponent, LegendPlainComponent, TooltipComponent, CanvasRenderer]);

const FONT = "Roboto Variable, Roboto, sans-serif";   // data text; headings stay Montserrat
// The house chart look, registered once per theme: 12 px axes (category in ink-2, values in ink-3), dashed
// horizontal grid only, the solid series ramp. Screens set only what is particular to their chart.
const look = (t: typeof LIGHT) => ({
  color: [t.redLine, t.s1, t.s2, t.s3, t.other],
  backgroundColor: "transparent",
  textStyle: { fontFamily: FONT, color: t.ink, fontSize: 12 },
  categoryAxis: { axisLine: { lineStyle: { color: t.lineStrong } }, axisTick: { show: false }, axisLabel: { color: t.ink2, fontSize: 12 }, splitLine: { show: false } },
  valueAxis: { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: t.ink3, fontSize: 12 }, splitLine: { lineStyle: { color: t.line, type: [2, 3] } } },
  timeAxis: { axisLine: { lineStyle: { color: t.lineStrong } }, axisLabel: { color: t.ink3, fontSize: 12, hideOverlap: true }, splitLine: { show: false } },
  line: { symbol: "circle", symbolSize: 5, lineStyle: { width: 1.5 } },
  legend: { textStyle: { color: t.ink2, fontSize: 12 }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
  tooltip: { backgroundColor: t.raised, borderColor: t.line, borderWidth: 1, textStyle: { color: t.ink, fontSize: 12 } },
});
echarts.registerTheme("cip-light", look(LIGHT));
echarts.registerTheme("cip-dark", look(DARK));
const themeName = () => (savedTheme() === "dark" ? "cip-dark" : "cip-light");

// Read at render time (functions, not constants): screens build options with the current theme's colours.
export const tooltip = () => ({
  trigger: "item", confine: true, backgroundColor: C.raised, borderColor: C.line, borderWidth: 1, padding: [10, 12],
  textStyle: { color: C.ink, fontFamily: FONT, fontSize: 12 },
  extraCssText: `box-shadow: ${C.shadow2}; border-radius: 8px; max-width: 320px; white-space: normal;`,
});
/** Category labels; value axes use `valueText`. */
export const axisText = () => ({ color: C.ink2, fontFamily: FONT, fontSize: 12 });
export const valueText = () => ({ color: C.ink3, fontFamily: FONT, fontSize: 12 });

export type Chart = echarts.ECharts;
export const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;

/** A PNG a reader can paste into a deck: the question on top, the chart, the source and base underneath. */
export async function downloadPng(chart: Chart, title: string, source: string, file: string) {
  // always the light theme, whatever the screen shows: the option is rebuilt with the light palette off screen
  const box = Object.assign(document.createElement("div"), { style: `position:fixed;left:-10000px;top:0;width:${chart.getWidth()}px;height:${chart.getHeight()}px` });
  document.body.append(box);
  const light = echarts.init(box, "cip-light", { renderer: "canvas" });
  const build = builders.get(chart);
  light.setOption({ ...common(""), ...(build ? inLight(build) : chart.getOption()), animation: false });
  const img = new Image();
  img.src = light.getDataURL({ pixelRatio: 2, backgroundColor: LIGHT.surface });
  light.dispose(); box.remove();
  await img.decode();
  const pad = 48, width = img.width + pad * 2, font = "Montserrat Variable, sans-serif";
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  const wrap = (text: string, size: number, weight: number) => {
    ctx.font = `${weight} ${size}px ${font}`;
    const lines: string[] = [];
    let line = "";
    for (const word of text.split(" ")) {
      if (ctx.measureText(line + word).width > width - pad * 2 && line) { lines.push(line.trim()); line = ""; }
      line += word + " ";
    }
    return [...lines, line.trim()];
  };
  const head = wrap(title, 34, 600), foot = wrap(source, 22, 400);
  canvas.width = width;
  canvas.height = pad + head.length * 44 + 24 + img.height + 24 + foot.length * 30 + pad;
  ctx.fillStyle = LIGHT.surface; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = LIGHT.red; ctx.fillRect(pad - 20, pad - 4, 8, head.length * 44);   // the report's red bar
  ctx.fillStyle = LIGHT.ink; ctx.font = `600 34px ${font}`;
  head.forEach((l, i) => ctx.fillText(l, pad, pad + 32 + i * 44));
  ctx.drawImage(img, pad, pad + head.length * 44 + 24);
  ctx.fillStyle = LIGHT.ink2; ctx.font = `400 22px ${font}`;
  foot.forEach((l, i) => ctx.fillText(l, pad, canvas.height - pad - (foot.length - 1 - i) * 30));
  const a = Object.assign(document.createElement("a"), { href: canvas.toDataURL("image/png"), download: `${file}.png` });
  a.click();
}

/** The option builder behind each chart, so a PNG can be rebuilt in the light palette. */
const builders = new WeakMap<Chart, () => EChartsCoreOption>();
const common = (label: string) => ({
  animation: !REDUCED_MOTION,
  animationDuration: 480, animationEasing: "cubicOut" as const,
  animationDurationUpdate: 320, animationEasingUpdate: "cubicInOut" as const,
  aria: { enabled: true, label: { general: { withoutTitle: `${label}. ` } } },
});

export default function EChart({ option, build, height, onClick, label, onReady }:
  { option: EChartsCoreOption; build?: () => EChartsCoreOption; height: number; onClick?: (p: { name: string; seriesName: string; dataIndex: number }) => void;
    label: string; onReady?: (chart: Chart) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const theme = useTheme();
  useEffect(() => {
    const c = echarts.init(el.current!, themeName(), { renderer: "canvas" });
    chart.current = c;
    onReady?.(c);
    const resize = new ResizeObserver(() => c.resize());
    resize.observe(el.current!);
    return () => { resize.disconnect(); c.dispose(); };
  }, []);
  useEffect(() => { if (build && chart.current) builders.set(chart.current, build); }, [build]);
  // a theme switch re-colours this canvas in place (the screen rebuilds its option with the new palette too)
  useEffect(() => { chart.current?.setTheme(themeName()); }, [theme]);
  // aria: ECharts writes a spoken description of the data (series, ranges, values) onto the chart element
  useEffect(() => {
    const c = chart.current;
    if (!c) return;
    const deregister = perf.registerPendingGraph(label);
    const t0 = performance.now();
    const onFinished = () => {
      const dur = performance.now() - t0;
      perf.logGraph({
        label,
        durationMs: Math.round(dur * 10) / 10,
      });
      deregister();
      c.off("finished", onFinished);
    };
    c.on("finished", onFinished);

    // Bars grow from the axis when a question opens; a new cut or sort moves the same bars to their new values
    // instead of redrawing, so the change itself is visible. Parts a new chart type does not share are replaced.
    c.setOption({ ...common(label), ...option }, { replaceMerge: ["series", "xAxis", "yAxis", "grid", "legend"] });   // only registered components: ECharts asserts on others
  }, [option, label]);
  useEffect(() => {
    const c = chart.current!;
    c.off("click");
    if (onClick) c.on("click", p => onClick(p as never));
  }, [onClick]);
  return <div ref={el} role="img" aria-label={label} tabIndex={0} style={{ height, width: "100%" }} />;
}
