// One ECharts canvas: only the chart types and components CIP uses are bundled (≈190 KB gzipped, its own cached chunk).
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { C } from "../theme";

echarts.use([AriaComponent, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

// Read at render time (functions, not constants), so a theme switch repaints every chart.
export const tooltip = () => ({
  trigger: "item", confine: true, backgroundColor: C.surface, borderColor: C.mist, borderWidth: 1, padding: [10, 12],
  textStyle: { color: C.ink, fontFamily: "Montserrat Variable, sans-serif", fontSize: 12 },
  extraCssText: "box-shadow: 0 6px 24px rgba(0,0,0,.18); border-radius: 8px; max-width: 320px; white-space: normal;",
});
export const axisText = () => ({ color: C.ink, fontFamily: "Montserrat Variable, sans-serif", fontSize: 11 });

export type Chart = echarts.ECharts;

/** A PNG a reader can paste into a deck: the question on top, the chart, the source and base underneath. */
export async function downloadPng(chart: Chart, title: string, source: string, file: string) {
  const img = new Image();
  img.src = chart.getDataURL({ pixelRatio: 2, backgroundColor: C.surface });
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
  ctx.fillStyle = C.surface; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = C.red; ctx.fillRect(pad - 20, pad - 4, 8, head.length * 44);   // the report's red bar
  ctx.fillStyle = C.ink; ctx.font = `600 34px ${font}`;
  head.forEach((l, i) => ctx.fillText(l, pad, pad + 32 + i * 44));
  ctx.drawImage(img, pad, pad + head.length * 44 + 24);
  ctx.fillStyle = C.ink2; ctx.font = `400 22px ${font}`;
  foot.forEach((l, i) => ctx.fillText(l, pad, canvas.height - pad - (foot.length - 1 - i) * 30));
  const a = Object.assign(document.createElement("a"), { href: canvas.toDataURL("image/png"), download: `${file}.png` });
  a.click();
}

export default function EChart({ option, height, onClick, label, onReady }:
  { option: EChartsCoreOption; height: number; onClick?: (p: { name: string; seriesName: string; dataIndex: number }) => void;
    label: string; onReady?: (chart: Chart) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    const c = echarts.init(el.current!, undefined, { renderer: "canvas" });
    chart.current = c;
    onReady?.(c);
    const resize = new ResizeObserver(() => c.resize());
    resize.observe(el.current!);
    return () => { resize.disconnect(); c.dispose(); };
  }, []);
  // aria: ECharts writes a spoken description of the data (series, ranges, values) onto the chart element
  useEffect(() => { chart.current!.setOption({ animationDuration: 250, textStyle: axisText(),
    aria: { enabled: true, label: { general: { withoutTitle: `${label}. ` } } }, ...option }, { notMerge: true }); }, [option, label]);
  useEffect(() => {
    const c = chart.current!;
    c.off("click");
    if (onClick) c.on("click", p => onClick(p as never));
  }, [onClick]);
  return <div ref={el} role="img" aria-label={label} tabIndex={0} style={{ height, width: "100%" }} />;
}
