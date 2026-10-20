"use client";
import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export default function Chart({ states }: { states: { state: string; stores: number }[] }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    (echarts.getInstanceByDom(el.current!) ?? echarts.init(el.current!)).setOption({
      animation: false, xAxis: { type: "category", data: states.map(s => s.state) }, yAxis: {},
      series: [{ type: "bar", data: states.map(s => s.stores) }] });
  }, [states]);
  return <div id="chart" ref={el} style={{ width: 900, height: 300 }} />;
}
