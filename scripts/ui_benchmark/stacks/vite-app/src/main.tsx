// The matched screen (matched.html) as a React 19 single-page app: select, metric, ECharts bar, table.
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as echarts from "echarts";

const SECTORS = ["Apparel", "Beauty", "Department", "Dollar", "Electronics", "Grocery", "Home", "Sporting"];
type Summary = { open: number; states: { state: string; stores: number; revenue: number }[] };

function App() {
  const [sector, setSector] = useState("Apparel");
  const [data, setData] = useState<Summary | null>(null);
  const chart = useRef<HTMLDivElement>(null);
  useEffect(() => { fetch(`/api/summary/${sector}`).then(r => r.json()).then(setData); }, [sector]);
  useEffect(() => {
    if (!data || !chart.current) return;
    (echarts.getInstanceByDom(chart.current) ?? echarts.init(chart.current)).setOption({
      animation: false, xAxis: { type: "category", data: data.states.map(s => s.state) }, yAxis: {},
      series: [{ type: "bar", data: data.states.map(s => s.stores) }] });
  }, [data]);
  return <>
    <select id="sector" value={sector} onChange={e => setSector(e.target.value)}>
      {SECTORS.map(s => <option key={s}>{s}</option>)}
    </select>
    <h3 id="open">{data ? "Stores open " + data.open.toLocaleString("en-US") : "Loading"}</h3>
    <div id="chart" ref={chart} style={{ width: 900, height: 300 }} />
    <table id="table"><tbody>
      {data?.states.map(s => <tr key={s.state}><td>{s.state}</td><td>{s.stores}</td><td>{Math.round(s.revenue)}</td></tr>)}
    </tbody></table>
  </>;
}

createRoot(document.getElementById("root")!).render(<App />);
