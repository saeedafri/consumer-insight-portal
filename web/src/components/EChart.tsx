// One ECharts canvas: only the chart types and components CIP uses are bundled (≈190 KB gzipped, its own cached chunk).
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { C } from "../theme";

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

export const TOOLTIP = {
  trigger: "item", confine: true, backgroundColor: "#FFFFFF", borderColor: C.mist, borderWidth: 1, padding: [10, 12],
  textStyle: { color: C.ink, fontFamily: "Montserrat Variable, sans-serif", fontSize: 12 },
  extraCssText: "box-shadow: 0 6px 24px rgba(45,42,41,.14); border-radius: 8px; max-width: 320px; white-space: normal;",
};
export const AXIS_TEXT = { color: C.ink, fontFamily: "Montserrat Variable, sans-serif", fontSize: 11 };

export default function EChart({ option, height, onClick, label }:
  { option: EChartsCoreOption; height: number; onClick?: (p: { name: string; seriesName: string; dataIndex: number }) => void; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    const c = echarts.init(el.current!, undefined, { renderer: "canvas" });
    chart.current = c;
    const resize = new ResizeObserver(() => c.resize());
    resize.observe(el.current!);
    return () => { resize.disconnect(); c.dispose(); };
  }, []);
  useEffect(() => { chart.current!.setOption({ animationDuration: 250, textStyle: AXIS_TEXT, ...option }, { notMerge: true }); }, [option]);
  useEffect(() => {
    const c = chart.current!;
    c.off("click");
    if (onClick) c.on("click", p => onClick(p as never));
  }, [onClick]);
  return <div ref={el} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
