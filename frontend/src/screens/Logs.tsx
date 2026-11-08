// The Logs page (/app/logs), admins only: a monitoring dashboard on top, the raw logs below.
//
// Where the numbers come from (all from GET /api/v1/admin/metrics, api/metrics.py; once a minute while "Live" is on, the
// tab is in view and the range ends now; per minute for the last day, per hour beyond it):
//   CPU, memory, bandwidth, memory per process   deploy/machine-log.sh, one sample every 15 s
//   requests, server time, pages, visitors       nginx's request log, counted per minute
//   caches, storage, database size               api/metrics.py (storage every 5 min) and api/main.py (the API's caches)
// The raw logs come from GET /api/v1/admin/logs, one page of 200 lines at a time, newest first.
// Every time on this page is India time on a 12-hour clock (ist, istLine), raw log lines included; other pages use the
// viewer's own zone (bits.tsx local).
// While sign-in is the demo, the server also asks for the admin token: the box shows only when the server asks for it.
// "Download everything" saves the range as one Excel file (GET /api/v1/admin/metrics/download).
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useMe } from "../api";
import { save } from "../csv";
import { Card, clock, ist } from "../components/bits";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { C, LIGHT, useTheme } from "../theme";

// ---- What the server sends (api/metrics.py and api/logs.py) ----------------------------------------------------------
interface Source { id: string; label: string; bytes: number | null }
interface LogPage { sources: Source[]; source: string; page: number; per_page: number; lines: string[]; more: boolean }
interface Sample { time: string; cpu_pct: number; cpu_peak?: number; memory_peak?: number; cores_used: number; working_set_mb: number; anon_mb: number; file_mb: number;
  limit_mb: number; machine_used_mb: number; machine_total_mb: number; net_in_kbs: number; net_out_kbs: number; load_1m: number;
  cpus: number; processes_mb: Record<string, number>; source: string }
interface Counts { requests: number; "2xx": number; "3xx": number; "4xx": number; "5xx": number; bytes: number; hit: number;
  file: number; api: number; browser: number; p50_ms: number; p95_ms: number; p99_ms: number }
interface CacheLayer { name: string; where: string; meaning: string; answered?: number; share_pct?: number; size_mb?: number | null;
  size?: string; entries?: number; detail?: Record<string, number> }
interface Disk { name: string; path: string; meaning: string; used_mb: number; total_mb: number; used_pct: number; ours_mb?: number | null }
interface Folder { name: string; path: string; meaning: string; mb: number | null }
interface Metrics {
  since: string; until: string; step: "minute" | "hour"; now: string; machine: Sample[]; traffic: (Counts & { minute: string })[];
  totals: Counts & { under_1ms: number; slowest_ms: number }; caches: CacheLayer[];
  storage: { measured: string | null; disks: Disk[]; folders: Folder[]; database: { name: string; mb: number; tables: number } | null;
    home?: { path: string; mb: number | null }[] };
  histogram: { up_to_ms: number | null; requests: number }[];
  pages: { page: string; name: string; requests: number; share_pct: number; average_ms: number; slowest_ms: number; without_python_pct: number }[];
  clients: { client: string; user: string; place: string; requests: number }[];
  problems: { source: string; minute: string; line: string; meaning: string }[];
  restarts: { time: string; build: string; what: string }[];
  sign_ins: { time: string; email: string; role: string; method: string; address: string; place: string }[];
  etl: { time: string; level: string; message: string; meaning: string }[];
}
interface Health { build?: string }

// ---- Small helpers --------------------------------------------------------------------------------------------------
const TOKEN = "cip_admin_token";   // remembered in this browser (localStorage), so a bookmark of the page opens it straight away;
                                   // emptying the box forgets it. Admin pages still need an admin account too.
const readToken = () => { try { return localStorage.getItem(TOKEN) ?? ""; } catch { return ""; } };
const num = (n: number, digits = 0) => n.toLocaleString("en-US", { maximumFractionDigits: digits });
const mb = (n: number | null | undefined) => n == null ? "not measured" : n >= 1024 ? `${num(n / 1024, 2)} GB` : `${num(n, 1)} MB`;
const bytes = (n: number) => n < 2 ** 20 ? `${num(n / 1024)} KB` : n < 2 ** 30 ? `${num(n / 2 ** 20, 1)} MB` : `${num(n / 2 ** 30, 2)} GB`;
const fileSize = (n: number | null) => n == null ? "not written yet" : bytes(n);
const ms = (n: number) => n >= 1000 ? `${num(n / 1000, 1)} s` : n < 0.5 ? "under 1 ms" : `${num(n, 1)} ms`;
const rate = (n: number) => num(n, n < 1 ? 2 : 1);
// nginx's own words for its cache (the request log's "cache" field), in plain words
const CACHE_STATES: Record<string, string> = { HIT: "sent from the cache", MISS: "not in the cache yet (the API answered, then it was kept)",
  EXPIRED: "kept too long, asked the API again", STALE: "an older copy sent while the API was busy", UPDATING: "an older copy sent while it was refreshed",
  REVALIDATED: "checked with the API, still current", BYPASS: "not cacheable, the API answered" };
const DAY = 1440;
const RANGES = [{ minutes: 60, label: "1 h" }, { minutes: 360, label: "6 h" }, { minutes: DAY, label: "24 h" }, { minutes: 7 * DAY, label: "7 days" },
  { minutes: 30 * DAY, label: "30 days" }, { minutes: 17 * 7 * DAY, label: "17 weeks" }, { minutes: 365 * DAY, label: "1 year" }];
type Range = { minutes: number } | { start: string; end: string };   // start and end: the browser's local time, as typed
const query = (r: Range) => "minutes" in r ? `minutes=${r.minutes}`
  : `start=${new Date(r.start).toISOString()}&end=${new Date(r.end).toISOString()}`;
const LIVE_EVERY = 60000;   // a minute: the numbers are per minute; each refresh costs the server ~0.1-0.3 s of its one CPU
/** Calls `tick` every `ms` while the tab is in view: a hidden tab or a minimised window asks the server nothing. */
function useEvery(ms: number, on: boolean, tick: () => void) {
  useEffect(() => {
    if (!on) return;
    const every = setInterval(() => { if (document.visibilityState === "visible") tick(); }, ms);
    return () => clearInterval(every);
  }, [ms, on]);   // eslint-disable-line react-hooks/exhaustive-deps
}
// A logged line's own time (UTC, in each writer's style: the API "2026-11-07 15:33:29,510", gunicorn "[… +0000]", nginx
// "2026/11/07 08:52:58", start.sh "…Z", the request and machine logs' "time" field) shown in India time with seconds, like
// the rest of this page. Only what is shown changes: the files and their downloads keep the servers' UTC.
const STAMP = /^(\[?)(\d{4})[-/](\d\d)[-/](\d\d)[ T](\d\d:\d\d:\d\d)(?:[,.]\d+)?(?: ?(?:Z|[+-]\d\d:?\d\d))?(\]?)/;
const SECONDS: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" };
const istLine = (line: string) => {
  const m = line.match(STAMP);
  return m ? `${m[1]}${clock(`${m[2]}-${m[3]}-${m[4]}T${m[5]}Z`, "Asia/Kolkata", SECONDS)}${m[6]}${line.slice(m[0].length)}`
    : line.replace(/"time":"([^"]+)"/, (_, t: string) => `"time":"${clock(t, "Asia/Kolkata", SECONDS)}"`);
};
const NO_SAMPLES = "Machine samples start a minute after the server starts (deploy/machine-log.sh).";
const PER_PAGE = 200;
const grid = (min: number): CSSProperties => ({ display: "grid", gap: 16, gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${min}px), 1fr))` });
const mono: CSSProperties = { fontFamily: "monospace", fontSize: 12, lineHeight: 1.5, wordBreak: "break-word" };
const small: CSSProperties = { fontSize: 12, color: "var(--ink-2)" };

export default function Logs() {
  const [token, setToken] = useState(readToken);
  const [range, setRange] = useState<Range>({ minutes: 60 });
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [live, setLive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [denied, setDenied] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  const [beat, setBeat] = useState(0);
  const headers: Record<string, string> = token ? { "X-CIP-Admin-Token": token } : {};

  // the dashboard's numbers: on open, on a new range or token, and every minute while live (see useEvery)
  useEffect(() => {
    const ask = new AbortController();
    const get = { credentials: "same-origin" as const, signal: ask.signal, headers };
    fetch(`/api/v1/admin/metrics?${query(range)}`, get)
      .then(async r => {
        if (r.ok) { setMetrics(await r.json()); setDenied(""); setUpdated(new Date()); return; }
        const detail = (await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`;
        // two different refusals: the account is not an admin (no token helps), or the token is missing or wrong
        setDenied(detail === "Only an admin can do that"
          ? "notAdmin"
          : r.status === 401 || r.status === 403 ? `${detail}. Enter the admin token above (from staging.env, CIP_ADMIN_TOKEN).` : detail);
      })
      .catch(e => { if (e.name !== "AbortError") setDenied(String(e)); });
    fetch("/api/v1/admin/health", get).then(r => r.ok ? r.json() : null).then(h => h && setHealth(h)).catch(() => { /* the build id is a nicety */ });
    return () => ask.abort();
  }, [range, token, beat]);
  // only a range that ends now and is held per minute changes from one minute to the next
  const moving = "minutes" in range && range.minutes <= DAY;
  useEvery(LIVE_EVERY, live && moving, () => setBeat(b => b + 1));
  const downloadAll = () => {
    setSaving(true);
    fetch(`/api/v1/admin/metrics/download?${query(range)}`, { credentials: "same-origin", headers })
      .then(r => r.ok ? r.blob() : Promise.reject(new Error(`${r.status}`)))
      .then(blob => save(blob, `cip-logs-${new Date().toISOString().slice(0, 10)}.xlsx`))
      .catch(e => setDenied(`The download failed (${e.message}); try a shorter range.`))
      .finally(() => setSaving(false));
  };

  // trimmed: a token pasted with a space or line break around it would otherwise never match
  const keepToken = (value: string) => { const clean = value.trim(); setToken(clean); try { if (clean) localStorage.setItem(TOKEN, clean); else localStorage.removeItem(TOKEN); } catch { /* private window */ } };
  const me = useMe().data;

  return (
    <div className="stack">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "end", justifyContent: "space-between" }}>
        <div>
          <p className="eyebrow">Admin</p>
          <h1 style={{ margin: "6px 0 4px", fontSize: 26 }}>Operational monitoring</h1>
          <p className="lede">The machine, traffic, caches and storage, then everything the server writes: requests, errors, ETL runs, restarts and security events.</p>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
          <div className="seg" role="group" aria-label="Time range">
            {RANGES.map(r => <button key={r.minutes} aria-pressed={"minutes" in range && range.minutes === r.minutes} onClick={() => setRange({ minutes: r.minutes })}>{r.label}</button>)}
          </div>
          <form style={{ display: "flex", gap: 6, alignItems: "end", flexWrap: "wrap" }}
                onSubmit={e => { e.preventDefault(); if (custom.start && custom.end) setRange({ ...custom }); }}>
            <label style={small}>From (your time)<br /><input type="datetime-local" value={custom.start} onChange={e => setCustom(c => ({ ...c, start: e.target.value }))} /></label>
            <label style={small}>To<br /><input type="datetime-local" value={custom.end} onChange={e => setCustom(c => ({ ...c, end: e.target.value }))} /></label>
            <button className="btn" type="submit" disabled={!custom.start || !custom.end}>Show these dates</button>
          </form>
          {moving && <button className="btn" onClick={() => setLive(!live)}>{live ? "Pause" : "Resume"} auto-refresh</button>}
          <button className="btn primary" onClick={downloadAll} disabled={saving}>{saving ? "Preparing…" : "Download everything (Excel)"}</button>
          {/* only a demo sign-in is asked for the token: a sign-in through the identity provider opens this page as it is */}
          {denied && denied !== "notAdmin" && <label>Admin token<br /><input type="password" value={token}
            onChange={e => keepToken(e.target.value)} placeholder="demo sign-in only" autoComplete="off" /></label>}
        </div>
      </div>
      <p className="muted" style={{ margin: "-6px 0 0", fontSize: 12 }}>
        {live && moving && <span className="chip live" style={{ marginRight: 8 }}>Live, every minute while this tab is open</span>}
        {metrics && `${ist(metrics.since)} to ${ist(metrics.until)}, figures per ${metrics.step} · `}
        {updated ? `updated ${ist(updated.toISOString(), false)}` : "loading…"}
        {health?.build && ` · build ${health.build}`}
      </p>

      {denied && <Card><p role="alert" style={{ color: "var(--red-text)", margin: 0 }}>
        {denied === "notAdmin"
          ? <>You are signed in as <b>{me?.email ?? "an account"}</b>, which is not an admin, so this page stays closed whatever the token. Only the super admin opens it (config/access.yml people: super_admin).</>
          : denied}</p></Card>}
      {metrics && <Dashboard m={metrics} headers={headers} />}
      <RawLogs headers={headers} token={token} />
      <Archives headers={headers} token={token} />
    </div>
  );
}

// ---- The dashboard --------------------------------------------------------------------------------------------------
function Tile({ label, value, note, style }: { label: string; value: ReactNode; note: ReactNode; style?: CSSProperties }) {
  return <div className="card kpi" style={style}>
    <div className="k-label" style={{ minHeight: 0, color: "inherit", opacity: .85 }}>{label}</div>
    <div className="k-value" style={{ color: "inherit", fontSize: 28 }}>{value}</div>
    <div className="k-note" style={{ color: "inherit", opacity: .85 }}>{note}</div>
  </div>;
}

function Dashboard({ m, headers }: { m: Metrics; headers: Record<string, string> }) {
  const theme = useTheme();
  const [address, setAddress] = useState("");   // the visitor opened below Top visitors
  const minutes = Math.max(1, (Date.parse(`${m.until}Z`) - Date.parse(`${m.since}Z`)) / 60000);
  const per = m.step;
  const t = m.totals;
  const last = m.machine.at(-1);
  const errorPct = t.requests ? (100 * t["5xx"]) / t.requests : 0;
  // an hour's sample is its average, and carries the hour's peak; older samples carry no CPU
  const peakCpu = Math.max(0, ...m.machine.map(s => s.cpu_peak ?? s.cpu_pct).filter(Number.isFinite));
  const peakMemory = Math.max(0, ...m.machine.map(s => s.memory_peak ?? s.working_set_mb).filter(Number.isFinite));
  const range: [number, number] = [Date.parse(`${m.since}Z`), Math.min(Date.parse(`${m.until}Z`), Date.parse(m.now))];
  const pale = { background: "var(--tag)", borderColor: "transparent" };
  const processes = Object.entries(last?.processes_mb ?? {}).sort((a, b) => a[1] - b[1]);

  const charts = useMemo(() => {
    const at = (minute: string) => Date.parse(`${minute}Z`);
    const timeAxis = { type: "time", min: range[0], max: range[1], axisLabel: valueText() };
    // the unit is in each card's subtitle and in the axis labels: an axis title would sit under the legend
    const valueAxis = (unit: string, extra = {}) => ({ type: "value", axisLabel: { ...valueText(), formatter: `{value}${unit}` }, ...extra });
    const base = { tooltip: { ...tooltip(), trigger: "axis" }, legend: { top: 0, left: 0 }, grid: { left: 8, right: 8, top: 52, bottom: 4, containLabel: true }, xAxis: timeAxis };
    const line = (name: string, color: string, data: [number, number | null][], extra = {}) =>
      ({ name, type: "line", showSymbol: false, color, data, ...extra });
    const machine = (pick: (s: Sample) => number) => m.machine.map(s => [Date.parse(s.time), pick(s)] as [number, number]);
    const histLabel = (b: { up_to_ms: number | null }, i: number) =>
      b.up_to_ms == null ? `over ${ms(m.histogram[i - 1]?.up_to_ms ?? 5000)}` : `up to ${ms(b.up_to_ms)}`;
    const bars = (labels: string[], values: number[], colors: string[] | string, unit: string) => ({
      tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
      xAxis: { type: "value", axisLabel: { show: false }, splitLine: { show: false } },
      yAxis: { type: "category", data: labels, axisLabel: axisText() },
      series: [{ type: "bar", barMaxWidth: 16, data: values.map((v, i) => ({ value: v, itemStyle: { color: Array.isArray(colors) ? colors[i] : colors, borderRadius: [0, 4, 4, 0] } })),
        label: { show: true, position: "right", color: C.ink, formatter: (p: { value: number }) => `${num(p.value)}${unit}` } }],
    });
    return {
      requests: { ...base, yAxis: valueAxis(""), series: (["2xx", "3xx", "4xx", "5xx"] as const).map(k => ({
        name: { "2xx": "OK (2xx)", "3xx": "Redirect / not modified (3xx)", "4xx": "Refused or not found (4xx)", "5xx": "Server error (5xx)" }[k],
        type: "bar", stack: "all", barMaxWidth: 14, color: { "2xx": C.s1, "3xx": C.sky, "4xx": C.rose, "5xx": C.red }[k],
        data: m.traffic.map(x => [at(x.minute), x[k]]) })) },
      times: { ...base, yAxis: valueAxis(" ms", { type: "log", min: 0.1 }), series: [
        line("Half of requests faster than (p50)", C.s3, m.traffic.map(x => [at(x.minute), x.p50_ms || null])),
        line("95 % faster than (p95)", C.s1, m.traffic.map(x => [at(x.minute), x.p95_ms || null])),
        line("99 % faster than (p99)", C.red, m.traffic.map(x => [at(x.minute), x.p99_ms || null]))] },
      cpu: { ...base, yAxis: valueAxis(" %", { min: 0, max: 100 }), series: [line("CPU used", C.red, machine(s => s.cpu_pct))] },
      memory: { ...base, yAxis: valueAxis(" MB", { min: 0 }), series: [
        line("Our container (as Azure counts it)", C.s1, machine(s => s.working_set_mb)),
        line("Our processes' own memory", C.s3, machine(s => s.anon_mb))] },
      network: { ...base, yAxis: valueAxis(" KB/s"), series: [
        line("Received", C.s3, machine(s => s.net_in_kbs)), line("Sent", C.s1, machine(s => s.net_out_kbs))] },
      answered: {
        tooltip: { ...tooltip(), valueFormatter: (v: number) => num(v) }, legend: { orient: "vertical", right: 0, top: "middle" },
        series: [{ type: "pie", radius: ["52%", "78%"], center: ["32%", "50%"], label: { show: false }, color: [C.s1, C.sky, C.red],   // Python, the costly path, in red
          itemStyle: { borderColor: C.surface, borderWidth: 2 },
          data: [{ name: "nginx cache", value: t.hit }, { name: "Published file", value: t.file }, { name: "API (Python)", value: t.api }] }] },
      histogram: bars(m.histogram.map(histLabel).reverse(), m.histogram.map(b => b.requests).reverse(),
        m.histogram.map(b => b.up_to_ms == null || b.up_to_ms > 1000 ? C.red : C.bar).reverse(), ""),
      processes: bars(processes.map(p => p[0]), processes.map(p => p[1]), C.bar, " MB"),
    };
  }, [m, theme]);

  return <>
    {/* ---- the six numbers that matter most ---- */}
    <div style={grid(170)}>
      <Tile label="Requests" value={num(t.requests)} note={`${rate(t.requests / (minutes * 60))} per second on average`}
            style={{ background: LIGHT.blue, borderColor: LIGHT.blue, color: "#FFFFFF" }} />
      <Tile label="Server time" value={ms(t.p95_ms)} note={`95 % of requests answered faster · ${num(t.under_1ms, 1)} % under 1 ms · slowest ${ms(t.slowest_ms)}`} style={pale} />
      <Tile label="Server errors (5xx)" value={num(t["5xx"])} note={`${num(errorPct, 2)} % of requests · ${num(t["4xx"])} refused or not found (4xx)`}
            style={t["5xx"] ? { background: C.red, borderColor: C.red, color: "#FFFFFF" } : { background: "var(--fill)", borderColor: "transparent" }} />
      <Tile label="CPU now" value={last ? `${num(last.cpu_pct, 1)} %` : "–"} style={pale}
            note={last ? <>of {last.cpus} CPUs ({last.cores_used.toFixed(2)} in use) · peak {num(peakCpu, 1)} %<br /><span style={{ opacity: .85 }}>Azure's P0v3 plan is 1 vCPU = 2 threads; the container sees both</span></> : "no samples yet"} />
      <Tile label="Our memory now" value={last ? `${num(last.working_set_mb)} MB` : "–"} style={{ background: "var(--fill)", borderColor: "transparent" }}
            note={last ? <>{num(last.anon_mb)} MB our processes + {num(last.file_mb)} MB file cache (freed when needed) · peak {num(peakMemory)} MB<br />
              <span style={{ opacity: .85 }}>The machine has {num(last.machine_total_mb)} MB; {num(last.machine_used_mb)} MB in use by everything on it, Azure's own agents included</span></> : "no samples yet"} />
      <Tile label="Data sent" value={bytes(t.bytes)} note={last ? `in this range · now ${num(last.net_out_kbs, 1)} KB/s out, ${num(last.net_in_kbs, 1)} KB/s in` : "in this range"} style={pale} />
    </div>

    {/* ---- over time ---- */}
    <div style={grid(440)}>
      <Card title={`Requests per ${per}`} sub="By answer type. Server errors (5xx) are the ones to worry about.">
        {m.traffic.length ? <EChart option={charts.requests} height={260} label={`Requests per ${per} by answer type`} /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title={`Server time per ${per}`} sub="Time inside our server, from the request arriving to the answer leaving: the internet's travel time is not included. Log scale.">
        {m.traffic.length ? <EChart option={charts.times} height={260} label={`Server time percentiles per ${per} in milliseconds`} /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="CPU" sub={`Share of the 2 CPUs the container may use (100 % = both fully busy)${per === "hour" ? "; each point is an hour's average" : ""}.`}>
        {m.machine.length ? <EChart option={charts.cpu} height={240} label="CPU percent over time" /> : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
      <Card title="Memory" sub="Our container as Azure's memory metric counts it, and the part that is our processes' own (the rest is file cache).">
        {m.machine.length ? <EChart option={charts.memory} height={240} label="Memory in megabytes over time" /> : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
      <Card title="Bandwidth" sub="Network received and sent by the container, KB per second.">
        {m.machine.length ? <EChart option={charts.network} height={240} label="Network bandwidth over time" /> : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
      <Card title="Response times" sub="How many requests took how long (server time); over 1 s in red.">
        <EChart option={charts.histogram} height={300} label="Response time histogram" />
      </Card>
    </div>

    {/* ---- caches and storage ---- */}
    <div style={grid(300)}>
      <Card title="How requests were answered" sub="nginx cache and published files never reach Python, the costly path.">
        {t.requests ? <EChart option={charts.answered} height={200} label="How requests were answered: nginx cache, published file or API" /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="Memory per process" sub={last ? `Our processes, latest sample at ${ist(last.time, false)}` : undefined}>
        {!last ? <p className="muted">{NO_SAMPLES}</p>
          : processes.length ? <EChart option={charts.processes} height={Math.max(120, processes.length * 32 + 20)} label="Memory per process in megabytes" />
          : <p className="muted">The latest sample lists no processes (deploy/machine-log.sh reads them from /proc every 15 s).</p>}
      </Card>
    </div>
    <Card title="Caches" sub="Every layer that answers before the slow path, what it holds and how often it answered in this range.">
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Cache</th><th>Where</th><th>What it does</th><th className="num">Answered</th><th className="num">Share</th><th className="num">Size</th></tr></thead>
        <tbody>{m.caches.map(c => <tr key={c.name}>
          <th scope="row">{c.name}</th><td style={small}>{c.where}</td>
          <td style={small}>{c.meaning}{c.detail && <div style={{ marginTop: 4 }}>{Object.entries(c.detail).map(([k, v]) => `${CACHE_STATES[k] ?? k}: ${num(v)}`).join(" · ")}</div>}</td>
          <td className="num">{c.answered == null ? "–" : num(c.answered)}</td>
          <td className="num">{c.share_pct == null ? "–" : `${num(c.share_pct, 1)} %`}</td>
          <td className="num">{c.size ?? (c.size_mb == null ? "–" : `${mb(c.size_mb)}${c.entries != null ? ` · ${num(c.entries)} ${c.entries === 1 ? "item" : "items"}` : ""}`)}</td>
        </tr>)}</tbody>
      </table></div>
    </Card>
    <Card title="Storage" sub={`Which disk is which, what each folder holds and its size${m.storage.measured ? `; measured ${ist(m.storage.measured, false)} (every 5 minutes)` : ""}.`}>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Disk</th><th>What lives there</th><th className="num">CIP's files</th><th className="num">Used (all)</th><th className="num">Size</th><th className="num">Full</th></tr></thead>
        <tbody>{m.storage.disks.map(d => <tr key={d.name}>
          <th scope="row">{d.name}<div style={{ ...mono, ...small }}>{d.path}</div></th><td style={small}>{d.meaning}</td>
          <td className="num"><b>{d.ours_mb == null ? "–" : mb(d.ours_mb)}</b></td>
          <td className="num">{mb(d.used_mb)}</td><td className="num">{mb(d.total_mb)}</td><td className="num">{num(d.used_pct, 1)} %</td>
        </tr>)}</tbody>
      </table></div>
      <div className="table-wrap" style={{ marginTop: 14 }}><table className="data">
        <thead><tr><th>Folder</th><th>What it holds</th><th className="num">Size</th></tr></thead>
        <tbody>
          {m.storage.folders.map(f => <tr key={f.name}><th scope="row">{f.name}<div style={{ ...mono, ...small }}>{f.path}</div></th>
            <td style={small}>{f.meaning}</td><td className="num">{f.mb == null ? "not on this server" : mb(f.mb)}</td></tr>)}
          {m.storage.database && <tr><th scope="row">MySQL database<div style={{ ...mono, ...small }}>{m.storage.database.name} (Azure Database for MySQL)</div></th>
            <td style={small}>Every survey, answer and the portal's own tables, on Azure's database server (not this machine's disk). {num(m.storage.database.tables)} tables.</td>
            <td className="num">{mb(m.storage.database.mb)}</td></tr>}
        </tbody>
      </table></div>
      {!!m.storage.home?.length && <>
        <h3 className="eyebrow" style={{ margin: "16px 0 6px" }}>What is on Azure permanent storage (/home), folder by folder (measured hourly)</h3>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Folder</th><th>Whose</th><th className="num">Size</th></tr></thead>
          <tbody>{m.storage.home.map(f => <tr key={f.path}><th scope="row" style={mono}>{f.path}</th>
            <td style={small}>{f.path === "/home/cip" ? "Ours: logs, the published-files backup, open-ended coding" : "Azure App Service's own"}</td>
            <td className="num">{mb(f.mb)}</td></tr>)}</tbody>
        </table></div>
        <p className="muted" style={{ fontSize: 12 }}>Anything the disk counts as used beyond these folders is not visible to the app: the storage is Azure's, possibly shared.</p>
      </>}
      {!m.storage.disks.length && <p className="muted">Measured a minute after the server starts.</p>}
    </Card>

    {/* ---- who and what ---- */}
    <Card title="Busiest pages" sub="This dashboard's own requests are left out. Average and slowest are server time.">
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Page</th><th className="num">Requests</th><th className="num">Share</th><th className="num">Average</th><th className="num">Slowest</th><th className="num">Without Python</th></tr></thead>
        <tbody>{m.pages.map(p => <tr key={p.page}>
          <th scope="row">{p.name || "–"}<div style={{ ...mono, ...small }}>{p.page}</div></th>
          <td className="num">{num(p.requests)}</td><td className="num">{num(p.share_pct, 1)} %</td>
          <td className="num">{ms(p.average_ms)}</td><td className="num">{ms(p.slowest_ms)}</td><td className="num">{num(p.without_python_pct, 1)} %</td>
        </tr>)}</tbody>
      </table></div>
      {!m.pages.length && <p className="muted">No requests in this range.</p>}
    </Card>
    <Card title="Top visitors" sub="Signed-in person (from their session), approximate place of their internet address, and how many requests. The server's own checks are left out. Choose an address to see what it asked for and whether it is a person or a program.">
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Who</th><th>Where (approximate)</th><th>Address</th><th className="num">Requests</th></tr></thead>
        <tbody>{m.clients.map(c => <tr key={c.client} aria-selected={address === c.client}>
          <th scope="row"><button className="btn-chip" onClick={() => setAddress(address === c.client ? "" : c.client)}>{c.user || "not signed in"}</button></th>
          <td>{c.place || <span className="muted">unknown</span>}</td><td style={mono}>{c.client}</td>
          <td className="num"><span className="quota" style={{ justifyContent: "flex-end" }}>
            <span className="bar" style={{ width: 80 }}><i style={{ width: `${(100 * c.requests) / m.clients[0].requests}%`, background: C.s1 }} /></span>
            <span style={{ width: 70, textAlign: "right" }}>{num(c.requests)}</span></span></td>
        </tr>)}</tbody>
      </table></div>
      {!m.clients.length && <p className="muted">No visitors in this range.</p>}
      {address && <Visitor address={address} headers={headers} />}
      <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>Places are city-level guesses from the address (an office or a phone network's location, not a person's). <a href="https://db-ip.com" target="_blank" rel="noreferrer">IP Geolocation by DB-IP</a>.</p>
    </Card>

    <Card title="Sign-ins" sub="Who signed in, when (India time, IST), how, and from which address and approximate place. Newest first.">
      {m.sign_ins?.length ? <div className="table-wrap"><table className="data">
        <thead><tr><th>When (IST)</th><th>Who</th><th>Role</th><th>How</th><th>Where (approximate)</th><th>Address</th></tr></thead>
        <tbody>{m.sign_ins.map((x, i) => <tr key={i}><td style={{ whiteSpace: "nowrap" }}>{ist(x.time)}</td><th scope="row">{x.email}</th>
          <td>{x.role}</td><td>{x.method === "demo" ? "demo sign-in" : x.method}</td><td>{x.place || <span className="muted">unknown</span>}</td>
          <td style={mono}>{x.address || "–"}</td></tr>)}</tbody>
      </table></div> : <p className="muted">No sign-ins in this range. (Sign-ins are listed from this build on.)</p>}
    </Card>

    {/* ---- what went wrong ---- */}
    <Card title="Problems in this range" sub="Error and warning lines from the API, nginx and the ETL, each with what it means."
          aside={<span className={`chip ${m.problems.length ? "sig" : "flat"}`}>{m.problems.length} problems</span>}>
      {m.problems.length ? <div className="table-wrap"><table className="data">
        <thead><tr><th>When (IST)</th><th>From</th><th>What it means</th><th>The line</th></tr></thead>
        <tbody>{m.problems.map((p, i) => <tr key={i}>
          <td style={{ whiteSpace: "nowrap" }}>{ist(p.minute)}</td><td><span className="chip sig">{p.source}</span></td>
          <td style={{ minWidth: 220 }}>{p.meaning || <span className="muted">See the line.</span>}</td>
          <td><ProblemLine source={p.source} line={p.line} headers={headers} /></td>
        </tr>)}</tbody>
      </table></div> : <p className="muted">No errors logged in this range.</p>}
    </Card>
    <div style={grid(420)}>
      <Card title="Restarts" sub="Each time the container started (a deploy, or Azure restarting it), newest first.">
        {m.restarts.length ? <div className="table-wrap"><table className="data">
          <thead><tr><th>When (IST)</th><th>What happened</th><th>Build</th></tr></thead>
          <tbody>{m.restarts.map((r, i) => <tr key={i}><td style={{ whiteSpace: "nowrap" }}>{ist(r.time)}</td>
            <td>{r.what}</td><td style={{ ...mono, whiteSpace: "nowrap" }}>{r.build || "–"}</td></tr>)}</tbody>
        </table></div> : <p className="muted">No restarts in this range.</p>}
      </Card>
      <Card title="ETL (data loads)" sub="What the scheduled loads did, newest first. Warnings are things to look at, not outages.">
        {m.etl.length ? <div className="table-wrap"><table className="data">
          <thead><tr><th>When (IST)</th><th>Level</th><th>What happened</th></tr></thead>
          <tbody>{m.etl.map((e, i) => <tr key={i}><td style={{ whiteSpace: "nowrap" }}>{ist(e.time)}</td>
            <td><span className={`chip ${e.level === "INFO" ? "flat" : "sig"}`}>{e.level === "INFO" ? "ok" : e.level.toLowerCase()}</span></td>
            <td><span style={mono}>{e.message}</span>{e.meaning && <div style={{ ...small, marginTop: 4 }}>{e.meaning}</div>}</td></tr>)}</tbody>
        </table></div> : <p className="muted">No ETL runs in this range. The loads run daily at 09:00 IST (03:30 UTC) and Mondays at 17:30 IST (12:00 UTC).</p>}
      </Card>
    </div>
  </>;
}

// ---- One visitor: every request of theirs in the current log, and what they are ----------------------------------------
interface VisitorAnswer { address: string; place: string; kind: string; agents: string[]; came_from: string[];
  requests: { time: string; method: string; path: string; status: number; ms: number; bytes: number; user: string; agent: string; from: string; served: string }[] }
function Visitor({ address, headers }: { address: string; headers: Record<string, string> }) {
  const [v, setV] = useState<VisitorAnswer | null>(null);
  const [problem, setProblem] = useState("");
  useEffect(() => {
    setV(null);
    fetch(`/api/v1/admin/visitor?address=${encodeURIComponent(address)}`, { credentials: "same-origin", headers })
      .then(async r => r.ok ? setV(await r.json()) : setProblem((await r.json().catch(() => ({}))).detail ?? `${r.status}`))
      .catch(e => setProblem(String(e)));
  }, [address]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (problem) return <p role="alert" style={{ color: "var(--red-text)" }}>{problem}</p>;
  if (!v) return <p className="muted">Loading {address}…</p>;
  return <div style={{ marginTop: 16 }}>
    <h3 style={{ margin: "0 0 4px" }}>{v.address} · {v.place || "place unknown"}</h3>
    <p style={{ margin: "0 0 6px" }}><b>{v.kind}</b></p>
    <p style={{ ...small, margin: "0 0 10px" }}>Browser or program: {v.agents.join(" · ") || "not given"}
      {" · "}came from: {v.came_from.length ? v.came_from.join(", ") : "no other site (typed, a bookmark, or a program; sites recorded from the 7 Nov 2026 build on)"}</p>
    <div className="table-wrap" style={{ maxHeight: 420, overflow: "auto" }}><table className="data">
      <thead><tr><th>When (IST)</th><th>Request</th><th className="num">Answer</th><th className="num">Server time</th><th>Answered by</th><th>Signed in as</th></tr></thead>
      <tbody>{v.requests.map((r, i) => <tr key={i}>
        <td style={{ whiteSpace: "nowrap" }}>{ist(r.time)}</td><td style={mono}>{r.method} {r.path}</td>
        <td className="num">{r.status}</td><td className="num">{ms(r.ms)}</td><td>{r.served}</td><td>{r.user || <span className="muted">–</span>}</td>
      </tr>)}</tbody>
    </table></div>
    <p className="muted" style={{ fontSize: 11 }}>The newest {v.requests.length} requests of this address in the current request log (older ones: Older logs, or Download everything).</p>
  </div>;
}

// ---- "Show": an error with the lines around it, from its log ---------------------------------------------------------
function ProblemLine({ source, line, headers }: { source: string; line: string; headers: Record<string, string> }) {
  const [shown, setShown] = useState<{ file: string; before: string[]; found: string; after: string[] } | string | null>(null);
  const open = () => {
    if (shown) return setShown(null);
    fetch(`/api/v1/admin/logs/context?${new URLSearchParams({ source, line })}`, { credentials: "same-origin", headers })
      .then(async r => setShown(r.ok ? await r.json() : (await r.json().catch(() => ({}))).detail ?? `${r.status}`))
      .catch(e => setShown(String(e)));
  };
  return <>
    <button className="btn-chip" onClick={open}>{shown ? "Hide" : "Show"}</button>
    {!shown ? <div style={{ ...mono, ...small, marginTop: 4 }}>{istLine(line).slice(0, 170)}{line.length > 160 ? "…" : ""}</div>
      : typeof shown === "string" ? <div style={{ ...mono, marginTop: 4 }}>{istLine(line)}<div style={small}>{shown}</div></div>
      : <div style={{ marginTop: 6 }}>
          <div style={small}>In {shown.file}: the 10 lines before, the line itself (highlighted), and the 40 after it (an error's traceback follows it).</div>
          <pre style={{ ...mono, whiteSpace: "pre-wrap", maxHeight: 360, overflow: "auto", margin: "6px 0 0" }}>
            {shown.before.map(istLine).join("\n")}{shown.before.length ? "\n" : ""}<mark>{istLine(shown.found)}</mark>{"\n"}{shown.after.map(istLine).join("\n")}
          </pre>
        </div>}
  </>;
}

// ---- The raw logs, one page at a time -------------------------------------------------------------------------------
function RawLogs({ headers, token }: { headers: Record<string, string>; token: string }) {
  const [source, setSource] = useState("api");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [answer, setAnswer] = useState<LogPage | null>(null);
  const [problem, setProblem] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => { setPage(1); }, [source, q]);   // a new log or filter starts at its newest page
  useEffect(() => {
    const ask = new AbortController();
    const query = new URLSearchParams({ source, q, lines: String(PER_PAGE), page: String(page) });
    fetch(`/api/v1/admin/logs?${query}`, { credentials: "same-origin", signal: ask.signal, headers })
      .then(async r => {
        if (r.ok) { setAnswer(await r.json()); setProblem(""); return; }
        setProblem((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
      })
      .catch(e => { if (e.name !== "AbortError") setProblem(String(e)); });
    return () => ask.abort();
  }, [source, q, page, token, tick]);
  // only the newest page refreshes itself, once a minute while the tab is in view: an older page stays still while read
  useEvery(LIVE_EVERY, page === 1, () => setTick(t => t + 1));

  const download = () => {
    void fetch(`/api/v1/admin/logs/download?source=${source}`, { credentials: "same-origin", headers })
      .then(r => r.ok ? r.blob() : Promise.reject(new Error(`${r.status}`)))
      .then(blob => save(blob, `cip-${source}.log`))
      .catch(() => setProblem("This log has no file to download yet"));
  };
  const from = (page - 1) * PER_PAGE + 1;
  const pager = answer && <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
    <button className="btn" disabled={page === 1} onClick={() => setPage(1)}>Newest</button>
    <button className="btn" disabled={page === 1} onClick={() => setPage(p => p - 1)}>‹ Newer</button>
    <span className="muted" style={{ fontSize: 13 }}>Lines {num(from)}–{num(from + answer.lines.length - 1)}, page {page}</span>
    <button className="btn" disabled={!answer.more} onClick={() => setPage(p => p + 1)}>Older ›</button>
  </div>;

  return <Card title="Raw logs" sub={`Newest first, ${PER_PAGE} lines a page, the whole current file page by page, times in India time (the files themselves keep the servers' UTC); the newest page refreshes every minute while this tab is in view. Older files: Older logs, below.`}>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
      <label>Log<br />
        <select value={source} onChange={e => setSource(e.target.value)}>
          {(answer?.sources ?? [{ id: source, label: source, bytes: null }]).map(s => <option key={s.id} value={s.id}>{s.label}{s.id === "security" ? "" : ` (${fileSize(s.bytes)})`}</option>)}
        </select>
      </label>
      <label>Contains<br /><input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="error, 503, an email…" /></label>
      <button className="btn" onClick={() => setTick(t => t + 1)}>Refresh</button>
      {source !== "security" && <button className="btn" onClick={download}>Download</button>}
    </div>
    {problem && <p role="alert" style={{ color: "var(--red)", marginTop: 12 }}>{problem}</p>}
    <div style={{ marginTop: 14 }}>{pager}</div>
    <pre style={{ marginTop: 10, maxHeight: "65vh", overflow: "auto", fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {answer?.lines.length ? answer.lines.map(istLine).join("\n") : answer ? "Nothing logged here yet." : "Loading…"}
    </pre>
    <div style={{ marginTop: 10 }}>{pager}</div>
  </Card>;
}

// ---- Older logs, packed: every log that passed 20 MB, as a .zip kept for good (deploy/archive-log.py) ------------------
function Archives({ headers, token }: { headers: Record<string, string>; token: string }) {
  const [list, setList] = useState<{ name: string; bytes: number; time: string }[] | null>(null);
  useEffect(() => {
    fetch("/api/v1/admin/logs/archives", { credentials: "same-origin", headers })
      .then(r => r.ok ? r.json() : []).then(setList).catch(() => setList([]));
  }, [token]);
  const fetchArchive = (name: string) => void fetch(`/api/v1/admin/logs/archive?name=${encodeURIComponent(name)}`, { credentials: "same-origin", headers })
    .then(r => r.ok ? r.blob() : Promise.reject(new Error(`${r.status}`)))
    .then(blob => save(blob, name))
    .catch(() => { /* the list is refreshed on the next visit */ });
  return <Card title="Older logs (packed)" sub="Every log that reached 20 MB, packed as a .zip and kept for good, newest first. Any laptop or phone opens a .zip.">
    {list?.length ? <div className="table-wrap"><table className="data">
      <thead><tr><th>File</th><th>Packed (IST)</th><th className="num">Size</th><th /></tr></thead>
      <tbody>{list.map(a => <tr key={a.name}><th scope="row" style={mono}>{a.name}</th><td>{ist(a.time)}</td>
        <td className="num">{bytes(a.bytes)}</td><td className="num"><button className="btn" onClick={() => fetchArchive(a.name)}>Download</button></td></tr>)}</tbody>
    </table></div> : <p className="muted">{list ? "None yet: a log is packed when it reaches 20 MB." : "Loading…"}</p>}
  </Card>;
}
