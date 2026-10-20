"use client";
// Static export: the same screen rendered in the browser, data from FastAPI's /api/summary (as the Vite app).
import { useEffect, useState } from "react";
import Chart from "./chart";
import Picker from "./picker";

type Summary = { open: number; states: { state: string; stores: number; revenue: number }[] };

export default function Page() {
  const [sector, setSector] = useState("Apparel");
  const [d, setData] = useState<Summary | null>(null);
  useEffect(() => { fetch(`/api/summary/${sector}`).then(r => r.json()).then(setData); }, [sector]);
  return <>
    <Picker value={sector} onPick={setSector} />
    <h3 id="open">{d ? "Stores open " + d.open.toLocaleString("en-US") : "Loading"}</h3>
    {d && <Chart states={d.states} />}
    <table id="table"><tbody>
      {d?.states.map(s => <tr key={s.state}><td>{s.state}</td><td>{s.stores}</td><td>{Math.round(s.revenue)}</td></tr>)}
    </tbody></table>
  </>;
}
