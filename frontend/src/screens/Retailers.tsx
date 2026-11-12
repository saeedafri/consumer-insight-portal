// The retailer databank (/app/retailers): one retailer, retailers side by side, one sector, or two sectors with any of
// their retailers, from the weekly tracker since Jul 2025. Every count is built by the ETL when data is published
// (etl/retailers.py → api/v1/retailers.json.gz: counts per week; rules in config/retailers.yml and config/sectors.yml);
// this screen only adds up the weeks chosen (one, or several) and draws. Only weeks in which every chosen retailer was
// asked can be chosen, so a comparison is always like for like. Opened from the left menu (Core research → Retailer
// databank); the view, markets, retailers and weeks are kept in the address, so a link opens the same comparison.
import { Fragment } from "react";
import { Link, useSearchParams } from "react-router";
import { useRetailers } from "../api";
import type { RetailMarket, Retailers as Data } from "../api";
import EChart from "../components/EChart";
import { Card, Empty, ExportButtons, Failure, SkeletonScreen } from "../components/bits";
import { downloadTable } from "../csv";
import { fmtDate } from "../stats";
import { C } from "../theme";

type Mode = "retailer" | "retailers" | "sector" | "sectors";
const MODES: [Mode, string][] = [["retailer", "Retailer"], ["retailers", "Compare retailers"], ["sector", "Sector"], ["sectors", "Compare sectors"]];
const TITLES: Record<string, string> = { gender: "Gender", generation: "Generation", income: "Household income", region: "Region", area: "Area" };
const pct = (v: number | null | undefined) => v == null ? "–" : `${v.toFixed(1)}%`;
const share = (n: number, of: number) => of ? Math.round(1000 * n / of) / 10 : null;
const keyOf = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");
/** A series' colour, the same on every chart of the page (the chart theme's order: red first, then the blues). */
const colour = (i: number) => [C.redLine, C.s1, C.s2, C.s3, C.other][Math.min(i, 4)];

/** One side of the page: a market (the weekly retailers or a sector), the retailers chosen in it, and its weeks. */
type Side = { market: RetailMarket; picked: RetailMarket["retailers"]; valid: number[]; weeks: number[]; param: string };
/** A line on every chart: a retailer's counts over the side's chosen weeks, as a share of the side's base. */
type Series = { label: string; counts: number[]; base: number; side: number };

/** Counts added over weeks: a retailer's (missing weeks count nothing) or any per-week list. */
const sum = (rows: (number[] | undefined)[]) => rows.reduce<number[]>((t, r) => r ? r.map((v, i) => v + (t[i] ?? 0)) : t, []);

/** The weeks the address names for this side, else the newest `pool` valid weeks (several) or the newest (one). */
function chosenWeeks(param: string | null, valid: number[], data: Data, several: boolean): number[] {
  const ids = new Set((param ?? "").split(",").filter(Boolean));
  const named = valid.filter(w => ids.has(String(data.weeks[w].survey_id)));
  if (named.length) return several ? named : named.slice(-1);
  return several ? valid.slice(-data.pool) : valid.slice(-1);
}

export default function Retailers() {
  const { data, isLoading, error } = useRetailers();
  const [params, setParams] = useSearchParams();
  if (isLoading) return <SkeletonScreen kind="page" />;
  if ((error as { status?: number } | null)?.status === 404) return <Empty>The retailer databank has not been published yet.</Empty>;
  if (error || !data) return <Failure error={error} />;
  if (!data.markets.length || !data.weeks.length) return <Empty>No retailer questions published yet.</Empty>;
  const set = (changes: Record<string, string | null>) => setParams(p => {
    for (const [k, v] of Object.entries(changes)) v == null ? p.delete(k) : p.set(k, v);
    return p;
  }, { replace: true });
  const mode = (MODES.find(([m]) => m === params.get("view"))?.[0] ?? "retailers") as Mode;
  const several = params.get("one") !== "1";
  const sectors = data.markets.filter(m => m.sector);
  const weekly = data.markets.find(m => !m.sector) ?? data.markets[0];
  const sideCount = mode === "sectors" ? 2 : 1;
  const sides: Side[] = Array.from({ length: sideCount }, (_, s) => {
    const suffix = s ? "2" : "";
    const pool = mode === "sector" || mode === "sectors" ? sectors : data.markets;
    const fallback = mode === "sectors" ? sectors[s] ?? sectors[0] : mode === "sector" ? sectors[0] : weekly;
    const market = pool.find(m => m.name === params.get(`m${suffix}`)) ?? fallback;
    const wanted = (params.get(`r${suffix}`) ?? (mode === "retailers" ? "Walmart,Costco" : mode === "retailer" ? "Walmart" : "")).split(",").map(keyOf);
    let picked = market.retailers.filter(r => wanted.includes(keyOf(r.name)));
    if (mode === "retailer") picked = picked.slice(0, 1);
    if (!picked.length && mode !== "sector" && mode !== "sectors") picked = market.retailers.slice(0, mode === "retailer" ? 1 : 2);
    if (!picked.length) picked = market.retailers.slice(0, 3);
    const valid = market.weeks.filter(w => picked.every(r => r.weeks[String(w)]));   // every chosen retailer asked
    return { market, picked, valid, weeks: chosenWeeks(params.get(`w${suffix}`), valid, data, several), param: suffix };
  });
  const series: Series[] = sides.flatMap((side, s) => {
    const at = side.weeks.map(w => side.market.weeks.indexOf(w));
    const base = at.reduce((t, i) => t + side.market.asked[i], 0);
    return side.picked.map(r => ({ label: sideCount > 1 ? `${r.name} (${side.market.name})` : r.name,
                                   counts: sum(side.weeks.map(w => r.weeks[String(w)])), base, side: s }));
  });
  const ready = sides.every(s => s.weeks.length);
  return <div className="stack">
    <div className="page-head"><div>
      <h1>Retailer databank</h1>
      <p className="lede">Any retailer or sector from the weekly tracker since July 2025: how many people shop there, who they are, and how
        they compare. Choose one week or several: only weeks in which every chosen retailer was asked are offered, and several weeks are
        added together (each week's respondents are different people), so smaller retailers have enough shoppers to describe.</p>
    </div>
      <div className="seg" role="group" aria-label="View">{MODES.map(([m, label]) =>
        <button key={m} aria-pressed={m === mode} onClick={() => set({ view: m, m: null, r: null, w: null, m2: null, r2: null, w2: null })}>{label}</button>)}</div>
    </div>

    <section className="card retail-bar" aria-label="Choose what to show">
      {sides.map((side, s) => <Fragment key={s}>
        {s > 0 && <span className="vs" aria-hidden="true">vs</span>}
        <Chooser data={data} side={side} mode={mode} markets={mode === "sector" || mode === "sectors" ? sectors : data.markets} several={several} set={set} />
      </Fragment>)}
      <div className="seg small" role="group" aria-label="Weeks">
        <button aria-pressed={!several} onClick={() => set({ one: "1", w: null, w2: null })}>One week</button>
        <button aria-pressed={several} onClick={() => set({ one: null, w: null, w2: null })}>Several weeks</button>
      </div>
    </section>

    {!ready ? <Empty>The chosen retailers were never asked in the same week. Choose others, or compare them by sector.</Empty> : <>
      {(mode === "sector" || mode === "sectors") && <SectorOverview data={data} sides={sides} />}
      <Reach data={data} sides={sides} series={series} />
      {mode === "retailer" && <Everywhere data={data} name={sides[0].picked[0]?.name ?? ""} />}
      <ShopperProfile data={data} sides={sides} series={series} />
      {sides[0].market.sector ? null : <Sentiment data={data} side={sides[0]} />}
      <p className="source-line">Source: Coresight Research US Consumer Survey, weekly tracker. {sides.map(s =>
        `${s.market.name}: ${weekSpan(data, s.weeks)}, base ${s.market.base}`).join("; ")}. Unweighted. Shopper profiles shown from
        {" "}{data.min_buyers} shoppers; groups do not add to 100% where people preferred not to say.</p>
    </>}
  </div>;
}

const weekSpan = (data: Data, weeks: number[]) => weeks.length === 1 ? `week of ${fmtDate(data.weeks[weeks[0]].date)}`
  : `${weeks.length} weeks, ${fmtDate(data.weeks[weeks[0]].date)} to ${fmtDate(data.weeks[weeks[weeks.length - 1]].date)}`;

/** One side's controls: the market, its retailers (one, or several to tick), and its weeks (one, or several to tick). */
function Chooser({ data, side, mode, markets, several, set }: { data: Data; side: Side; mode: Mode; markets: RetailMarket[]; several: boolean;
  set: (c: Record<string, string | null>) => void }) {
  const p = side.param;
  const names = side.picked.map(r => r.name);
  const toggle = (name: string) => {
    const next = names.includes(name) ? names.filter(n => n !== name) : [...names, name];
    set({ [`r${p}`]: next.join(",") || null, [`w${p}`]: null });
  };
  const ids = (weeks: number[]) => weeks.map(w => data.weeks[w].survey_id).join(",");
  const tickWeek = (w: number) => {
    const next = side.weeks.includes(w) ? side.weeks.filter(x => x !== w) : [...side.weeks, w].sort((a, b) => a - b);
    if (next.length) set({ [`w${p}`]: ids(next) });
  };
  return <div className="retail-side">
    <label><span>{mode === "sector" || mode === "sectors" ? "Sector" : "Market"}</span>
      <select value={side.market.name} onChange={e => set({ [`m${p}`]: e.target.value, [`r${p}`]: null, [`w${p}`]: null })}>
        {markets.map(m => <option key={m.name}>{m.name}</option>)}</select></label>
    {mode === "retailer"
      ? <label><span>Retailer</span><select value={names[0]} onChange={e => set({ [`r${p}`]: e.target.value, [`w${p}`]: null })}>
          {side.market.retailers.map(r => <option key={r.name}>{r.name}</option>)}</select></label>
      : <details className="picker"><summary><span>Retailers</span>{names.join(", ") || "None"}</summary>
          <div className="picker-list">{side.market.retailers.map(r =>
            <label key={r.name}><input type="checkbox" checked={names.includes(r.name)} onChange={() => toggle(r.name)} />{r.name}</label>)}</div>
        </details>}
    {several
      ? <details className="picker"><summary><span>Weeks</span>{weekSpan(data, side.weeks)}</summary>
          <div className="picker-quick">
            {[4, 13, 26].filter(n => n < side.valid.length).map(n => <button key={n} type="button" className="btn-chip" onClick={() => set({ [`w${p}`]: ids(side.valid.slice(-n)) })}>Last {n}</button>)}
            <button type="button" className="btn-chip" onClick={() => set({ [`w${p}`]: ids(side.valid) })}>All {side.valid.length}</button>
          </div>
          <div className="picker-list">{[...side.valid].reverse().map(w =>
            <label key={w}><input type="checkbox" checked={side.weeks.includes(w)} onChange={() => tickWeek(w)} />{fmtDate(data.weeks[w].date)}</label>)}</div>
        </details>
      : <label><span>Week</span><select value={side.weeks[0]} onChange={e => set({ [`w${p}`]: String(data.weeks[Number(e.target.value)].survey_id) })}>
          {[...side.valid].reverse().map(w => <option key={w} value={w}>{fmtDate(data.weeks[w].date)}</option>)}</select></label>}
  </div>;
}

/** A sector's own figures: how many bought in it, and its retailers ranked, over the side's weeks. */
function SectorOverview({ data, sides }: { data: Data; sides: Side[] }) {
  return <div className={`grid ${sides.length > 1 ? "g2" : ""}`}>{sides.map((side, s) => {
    const at = side.weeks.map(w => side.market.weeks.indexOf(w));
    const asked = at.reduce((t, i) => t + side.market.asked[i], 0);
    const bought = at.reduce((t, i) => t + (side.market.bought[i] ?? 0), 0);
    const everyone = side.weeks.reduce((t, w) => t + data.weeks[w].n, 0);
    const ranked = side.market.retailers.map(r => ({ name: r.name, v: share(sum(side.weeks.map(w => r.weeks[String(w)]))[0] ?? 0, asked) ?? 0 }))
      .sort((a, b) => b.v - a.v).slice(0, 15);
    const picked = new Set(side.picked.map(r => r.name));
    return <Card key={s} title={side.market.name} sub={`${side.market.purchase ? `${pct(share(bought, everyone))} ${side.market.purchase.toLowerCase()} · ` : ""}retailers bought from, % of ${asked.toLocaleString("en-US")} ${side.market.base} · ${weekSpan(data, side.weeks)}`}>
      <EChart label={`${side.market.name}: retailers`} height={Math.max(200, ranked.length * 24 + 30)} option={{
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: unknown) => `${v}%` },
        grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
        xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
        yAxis: { type: "category", data: ranked.map(r => r.name).reverse(), axisLabel: { width: 200, overflow: "truncate" } },
        series: [{ type: "bar", barMaxWidth: 16, label: { show: true, position: "right", formatter: "{c}%" },
                   data: ranked.map(r => ({ value: r.v, itemStyle: picked.has(r.name) ? undefined : { opacity: 0.45 } })).reverse() }],
      }} />
    </Card>;
  })}</div>;
}

/** How many shop at each: a bar per series (% of its base), the weekly trend, and the food/nonfood split (weekly market). */
function Reach({ data, sides, series }: { data: Data; sides: Side[]; series: Series[] }) {
  const weekly = !sides[0].market.sector;
  const values = series.map(s => share(s.counts[0] ?? 0, s.base));
  const trendWeeks = [...new Set(sides.flatMap(s => s.valid))].sort((a, b) => a - b);
  const trend = series.map(ser => {
    const side = sides[ser.side];
    const r = side.picked.find(p => ser.label.startsWith(p.name))!;
    return { name: ser.label, type: "line", connectNulls: side.market.sector,   // a sector runs every few months: its surveys joined symbolSize: 5, color: colour(series.indexOf(ser)),
             data: trendWeeks.map(w => { const c = r.weeks[String(w)]; const i = side.market.weeks.indexOf(w); return c && i >= 0 ? share(c[0], side.market.asked[i]) : null; }) };
  });
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Retailer shoppers",
    ["Retailer", "% shoppers", "Shoppers", "Base", ...(weekly ? ["Food %", "Nonfood %"] : [])],
    series.map((s, i) => [s.label, values[i], s.counts[0] ?? 0, s.base, ...(weekly ? [share(s.counts[1] ?? 0, s.base), share(s.counts[2] ?? 0, s.base)] : [])]),
    ["Shoppers in the past two weeks (weekly) or among the sector's shoppers", "Source: Coresight Research US Consumer Survey"]);
  return <>
    <div className="grid g2">
      <Card title={weekly ? "Bought in the past two weeks" : "Bought from, among the sector's shoppers"}
            sub={`% of ${sides.map(s => s.market.base).join(" / ")}`} aside={<ExportButtons onExport={exportTable} />}>
        <div className="kpis">{series.map((s, i) => <div key={s.label} className="kpi"><span>{s.label}</span><b>{pct(values[i])}</b>
          <small>{(s.counts[0] ?? 0).toLocaleString("en-US")} of {s.base.toLocaleString("en-US")}</small></div>)}</div>
        <EChart label="Shoppers by retailer" height={Math.max(160, series.length * 34 + 30)} option={{
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: unknown) => `${v}%` },
          grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
          xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
          yAxis: { type: "category", data: series.map(s => s.label).reverse(), axisLabel: { width: 220, overflow: "truncate" } },
          series: [{ type: "bar", barMaxWidth: 18, label: { show: true, position: "right", formatter: "{c}%" },
                     data: values.map((v, i) => ({ value: v, itemStyle: { color: colour(i) } })).reverse() }],
        }} />
      </Card>
      <Card title="Week by week" sub="% each week, every week each was asked: the weeks you chose are added together above">
        <EChart label="Shoppers week by week" height={300} option={{
          tooltip: { trigger: "axis", valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) },
          legend: { bottom: 0, type: "scroll" }, grid: { left: 44, right: 16, top: 12, bottom: 48 },
          xAxis: { type: "category", data: trendWeeks.map(w => fmtDate(data.weeks[w].date)) },
          yAxis: { type: "value", axisLabel: { formatter: "{value}%" } }, series: trend,
        }} />
      </Card>
    </div>
    {weekly && <Card title="Food, nonfood or both" sub="Of each retailer's shoppers: what they bought there in the past two weeks">
      <div className={`grid g${Math.min(4, series.length)}`}>{series.map(s => {
        const [any = 0, food = 0, nonfood = 0] = s.counts, both = food + nonfood - any;
        return <figure key={s.label} className="chart-cell"><figcaption>{s.label}</figcaption>
          <EChart label={`${s.label}: food and nonfood`} height={220} option={{
            tooltip: { trigger: "item", valueFormatter: (v: unknown) => `${v}%` },
            series: [{ type: "pie", radius: "62%", label: { formatter: "{b}\n{d}%" }, color: [C.redLine, C.s2, C.sky],   // full circle; s1 is sky in dark
                       data: [["Food only", food - both], ["Nonfood only", nonfood - both], ["Both", both]].map(([name, n]) => ({ name, value: share(n as number, any) }))}],
          }} /></figure>;
      })}</div>
    </Card>}
  </>;
}

/** Who each retailer's shoppers are: gender as full circles (male blue, female red: two blues read as one in dark mode), the other groups as bars next to the base's own mix. */
function ShopperProfile({ data, sides, series }: { data: Data; sides: Side[]; series: Series[] }) {
  const offset = sides[0].market.sector ? 1 : 3;   // counts start after [shoppers] or [shoppers, food, nonfood]
  const dims = Object.entries(data.groups);
  const start = (d: number) => dims.slice(0, d).reduce((t, [, g]) => t + g.length, 0);
  const references = sides.map(side => {
    const at = side.weeks.map(w => side.market.weeks.indexOf(w));
    const counts = side.market.sector ? sum(at.map(i => side.market.buyers[i])) : sum(side.weeks.map(w => data.weeks[w].profile));
    const n = side.market.sector ? at.reduce((t, i) => t + side.market.asked[i], 0) : side.weeks.reduce((t, w) => t + data.weeks[w].n, 0);
    return { label: side.market.sector ? `All ${side.market.name.toLowerCase()} shoppers` : "All adults", counts, n };
  });
  const shown = series.filter(s => (s.counts[0] ?? 0) >= data.min_buyers);
  const hidden = series.filter(s => (s.counts[0] ?? 0) < data.min_buyers);
  const rows = [...shown.map(s => ({ label: s.label, n: s.counts[0], at: (i: number) => s.counts[offset + i] })),
                ...references.map(r => ({ label: r.label, n: r.n, at: (i: number) => r.counts[i] }))];
  const exportTable = (format: Parameters<typeof downloadTable>[0]) => downloadTable(format, "Shopper profile", ["Group", ...rows.map(r => r.label)],
    dims.flatMap(([d, groups], k) => groups.map((g, i) => [`${TITLES[d] ?? d}: ${g}`, ...rows.map(r => share(r.at(start(k) + i) ?? 0, r.n))])),
    ["Shopper profile: % of each retailer's shoppers in each group", "Source: Coresight Research US Consumer Survey"]);
  return <Card title="Who shops there" sub={`% of each retailer's shoppers${hidden.length ? ` · not shown (under ${data.min_buyers} shoppers): ${hidden.map(s => s.label).join(", ")}` : ""}`}
               aside={<ExportButtons onExport={exportTable} />}>
    {shown.length ? <>
      <div className={`grid g${Math.min(4, shown.length)}`}>{shown.map(s => <figure key={s.label} className="chart-cell">
        <figcaption>{s.label}: {(TITLES[dims[0][0]] ?? dims[0][0]).toLowerCase()}</figcaption>
        <EChart label={`${s.label}: gender`} height={200} option={{
          tooltip: { trigger: "item", valueFormatter: (v: unknown) => `${v}%` },
          legend: { bottom: 0 },
          series: [{ type: "pie", radius: "62%", center: ["50%", "44%"], label: { position: "inside", formatter: "{d}%", color: "#fff", fontWeight: 700 }, color: [C.s2, C.red, C.other],
                     data: dims[0][1].map((g, i) => ({ name: g, value: share(s.counts[offset + i] ?? 0, s.counts[0]) })) }],
        }} /></figure>)}</div>
      <div className="grid g2">{dims.slice(1).map(([d, groups], k) => <figure key={d} className="chart-cell"><figcaption>{TITLES[d] ?? d}</figcaption>
        <EChart label={TITLES[d] ?? d} height={240} option={{
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: unknown) => `${v}%` },
          legend: { bottom: 0, type: "scroll" }, grid: { left: 40, right: 12, top: 12, bottom: 44 },
          xAxis: { type: "category", data: groups }, yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
          series: rows.map((r, j) => ({ name: r.label, type: "bar", barMaxWidth: 22, color: j >= shown.length ? C.other : colour(series.indexOf(shown[j])),
                                        data: groups.map((_, i) => share(r.at(start(k + 1) + i) ?? 0, r.n)) })),
        }} /></figure>)}</div>
    </> : <p className="muted">Too few shoppers in the chosen weeks to describe: choose more weeks.</p>}
  </Card>;
}

/** How positive people feel (the apparel survey's grid): each retailer's newest figure up to the last chosen week. */
function Sentiment({ data, side }: { data: Data; side: Side }) {
  const until = data.weeks[side.weeks[side.weeks.length - 1]].date;
  const found = side.picked.map(r => ({ name: r.name, figure: (r.sentiment ?? []).filter(([d]) => d <= until).pop() ?? r.sentiment?.[0] ?? null }));
  if (!found.some(f => f.figure)) return null;
  return <Card title="How positive people feel" sub="Very or somewhat positive, among those asked: the apparel survey asks about 28 apparel retailers every few months">
    <EChart label="Sentiment" height={Math.max(140, found.length * 34 + 30)} option={{
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: unknown) => (v == null ? "not asked" : `${v}%`) },
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
      yAxis: { type: "category", data: found.map(f => f.figure ? `${f.name} (${fmtDate(f.figure[0])}, n=${f.figure[2]})` : `${f.name} (not asked)`).reverse(), axisLabel: { width: 260, overflow: "truncate" } },
      series: [{ type: "bar", barMaxWidth: 18, label: { show: true, position: "right", formatter: "{c}%" },
                 data: found.map((f, i) => ({ value: f.figure ? share(f.figure[1], f.figure[2]) : null, itemStyle: { color: colour(i) } })).reverse() }],
    }} />
  </Card>;
}

/** One retailer across every sector it is asked in: % of each sector's shoppers in that sector's newest survey. */
function Everywhere({ data, name }: { data: Data; name: string }) {
  const k = keyOf(name);
  const rows = data.markets.filter(m => m.sector).flatMap(m => {
    const r = m.retailers.find(x => keyOf(x.name) === k);
    const w = r && [...m.weeks].reverse().find(x => r.weeks[String(x)]);
    if (!r || w == null) return [];
    return [{ sector: m.name, date: data.weeks[w].date, v: share(r.weeks[String(w)][0], m.asked[m.weeks.indexOf(w)]) ?? 0 }];
  }).sort((a, b) => b.v - a.v);
  if (!rows.length) return null;
  return <Card title={`${name} in each sector`} sub="% of each sector's shoppers who bought from it, in that sector's newest survey">
    <EChart label={`${name} by sector`} height={Math.max(160, rows.length * 28 + 30)} option={{
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v: unknown) => `${v}%` },
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      yAxis: { type: "category", data: rows.map(r => `${r.sector} (${fmtDate(r.date)})`).reverse(), axisLabel: { width: 260, overflow: "truncate" } },
      series: [{ type: "bar", barMaxWidth: 16, label: { show: true, position: "right", formatter: "{c}%" }, data: rows.map(r => r.v).reverse() }],
    }} />
    <p className="small muted"><Link to={`/retailers?view=sector&m=${encodeURIComponent(rows[0].sector)}&r=${encodeURIComponent(name)}`}>Open {rows[0].sector} →</Link></p>
  </Card>;
}
