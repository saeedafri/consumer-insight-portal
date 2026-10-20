// SSR: the server queries SQLite and renders the whole screen on every request; a sector change is a
// soft navigation that asks the server to render again (React Server Components).
import { DatabaseSync } from "node:sqlite";
import Chart from "./chart";
import Picker from "./picker";

export const dynamic = "force-dynamic";
type Summary = { open: number; states: { state: string; stores: number; revenue: number }[] };
const cache = new Map<string, Summary>();
let query: ReturnType<DatabaseSync["prepare"]> | undefined;   // opened on first request, not at build time

function summary(sector: string): Summary {
  if (!cache.has(sector)) {
    query ??= new DatabaseSync(process.env.NAIVE_DB!, { readOnly: true })
      .prepare("select state, count(*) n, sum(revenue) revenue, sum(closed = 0) open from stores where sector = ? group by state");
    const rows = query.all(sector) as { state: string; n: number; revenue: number; open: number }[];
    cache.set(sector, { open: rows.reduce((a, r) => a + r.open, 0), states: rows.map(r => ({ state: r.state, stores: r.n, revenue: r.revenue })) });
  }
  return cache.get(sector)!;
}

export default async function Page({ searchParams }: { searchParams: Promise<{ sector?: string }> }) {
  const sector = (await searchParams).sector ?? "Apparel";
  const d = summary(sector);
  return <>
    <Picker value={sector} />
    <h3 id="open">{"Stores open " + d.open.toLocaleString("en-US")}</h3>
    <Chart states={d.states} />
    <table id="table"><tbody>
      {d.states.map(s => <tr key={s.state}><td>{s.state}</td><td>{s.stores}</td><td>{Math.round(s.revenue)}</td></tr>)}
    </tbody></table>
  </>;
}
