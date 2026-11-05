// Operational logs for admins (api/logs.py): a monitoring dashboard (machine, traffic, server time, errors) over the
// raw logs: nginx, the API, the ETL, the container, Azure App Service and security events, newest first, filterable,
// downloadable. While sign-in is the demo, the server also asks for the admin token.
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Card } from "../components/bits";
import EChart, { axisText, tooltip, valueText } from "../components/EChart";
import { C, LIGHT, useTheme } from "../theme";

interface Source { id: string; label: string; bytes: number | null }
interface Answer { sources: Source[]; source: string; lines: string[] }
interface Sample { time: string; cpu_pct: number; working_set_mb: number; anon_mb: number; file_mb: number; limit_mb: number;
  net_in_kbs: number; net_out_kbs: number; load_1m: number; cpus: number; disk_used: string; processes_mb: Record<string, number> }
interface Counts { requests: number; "2xx": number; "3xx": number; "4xx": number; "5xx": number; bytes: number; hit: number; file: number; api: number;
  p50_ms: number; p95_ms: number; p99_ms: number }
interface Metrics { since: string; now: string; machine: Sample[]; traffic: (Counts & { minute: string })[]; totals: Counts & { under_1ms: number };
  histogram: { up_to_ms: number | null; requests: number }[]; pages: { page: string; requests: number; slowest_ms: number }[];
  clients: { client: string; requests: number }[]; problems: { source: string; line: string }[]; restarts: string[]; etl: string[] }
interface Health { build?: string }

const TOKEN = "cip_admin_token";   // this tab only (sessionStorage): gone when the tab closes
const readToken = () => { try { return sessionStorage.getItem(TOKEN) ?? ""; } catch { return ""; } };
const size = (n: number | null) => n == null ? "not written yet" : n < 1024 ? `${n} B` : n < 2 ** 20 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 2 ** 20).toFixed(1)} MB`;
const bytes = (n: number) => n < 2 ** 20 ? `${(n / 1024).toFixed(0)} KB` : n < 2 ** 30 ? `${(n / 2 ** 20).toFixed(1)} MB` : `${(n / 2 ** 30).toFixed(2)} GB`;
const num = (n: number, digits = 0) => n.toLocaleString("en-US", { maximumFractionDigits: digits });
const ms = (n: number) => n >= 1000 ? `${num(n / 1000, 1)} s` : `${num(n, 1)} ms`;
const RANGES = [{ minutes: 15, label: "15 min" }, { minutes: 60, label: "1 h" }, { minutes: 360, label: "6 h" }, { minutes: 1440, label: "24 h" }];
const NO_SAMPLES = "Machine samples start a minute after the server starts (deploy/machine-log.sh).";

export default function Logs() {
  const [source, setSource] = useState("api");
  const [q, setQ] = useState("");
  const [token, setToken] = useState(readToken);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [problem, setProblem] = useState("");
  const [tick, setTick] = useState(0);
  const [minutes, setMinutes] = useState(60);
  const [live, setLive] = useState(true);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [denied, setDenied] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  const [beat, setBeat] = useState(0);
  const headers: Record<string, string> = token ? { "X-CIP-Admin-Token": token } : {};

  useEffect(() => {
    const ask = new AbortController();
    const query = new URLSearchParams({ source, q, lines: "500" });
    fetch(`/api/v1/admin/logs?${query}`, { credentials: "same-origin", signal: ask.signal, headers })
      .then(async r => {
        if (r.ok) { setAnswer(await r.json()); setProblem(""); return; }
        setProblem((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
      })
      .catch(e => { if (e.name !== "AbortError") setProblem(String(e)); });
    return () => ask.abort();
  }, [source, q, token, tick]);

  useEffect(() => { const every = setInterval(() => setTick(t => t + 1), 10000); return () => clearInterval(every); }, []);

  useEffect(() => {
    const ask = new AbortController();
    const get = { credentials: "same-origin" as const, signal: ask.signal, headers };
    fetch(`/api/v1/admin/metrics?minutes=${minutes}`, get)
      .then(async r => {
        if (r.ok) { setMetrics(await r.json()); setDenied(""); setUpdated(new Date()); return; }
        const detail = (await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`;
        setDenied(r.status === 401 || r.status === 403 ? `${detail}. Enter the admin token above.` : detail);
      })
      .catch(e => { if (e.name !== "AbortError") setDenied(String(e)); });
    fetch("/api/v1/admin/health", get).then(r => r.ok ? r.json() : null).then(h => h && setHealth(h)).catch(() => { /* the build id is a nicety */ });
    return () => ask.abort();
  }, [minutes, token, beat]);

  useEffect(() => {
    if (!live) return;
    const every = setInterval(() => setBeat(b => b + 1), 15000);
    return () => clearInterval(every);
  }, [live]);

  const keepToken = (value: string) => { setToken(value); try { sessionStorage.setItem(TOKEN, value); } catch { /* private window */ } };
  const download = () => {
    void fetch(`/api/v1/admin/logs/download?source=${source}`, { credentials: "same-origin", headers })
      .then(r => r.ok ? r.blob() : Promise.reject(new Error(`${r.status}`)))
      .then(blob => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `cip-${source}.log`; a.click(); URL.revokeObjectURL(a.href); })
      .catch(() => setProblem("This log has no file to download yet"));
  };

  return (
    <div className="stack">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "end", justifyContent: "space-between" }}>
        <div>
          <p className="eyebrow">Admin</p>
          <h1 style={{ margin: "6px 0 4px", fontSize: 26 }}>Operational monitoring</h1>
          <p className="lede">The machine, traffic and server time, then everything the server writes: requests, errors, ETL runs, restarts and security events.</p>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
          <div className="seg" role="group" aria-label="Time range">
            {RANGES.map(r => <button key={r.minutes} aria-pressed={minutes === r.minutes} onClick={() => setMinutes(r.minutes)}>{r.label}</button>)}
          </div>
          <button className="btn" onClick={() => setLive(!live)}>{live ? "Pause" : "Resume"} auto-refresh</button>
          <label>Admin token<br /><input type="password" value={token} onChange={e => keepToken(e.target.value)} placeholder="only while SSO is off" autoComplete="off" /></label>
        </div>
      </div>
      <p className="muted" style={{ margin: "-6px 0 0", fontSize: 12 }}>
        {live && <span className="chip live" style={{ marginRight: 8 }}>Live, every 15 s</span>}
        {updated ? `updated ${updated.toLocaleTimeString("en-GB")}` : "loading…"}
        {health?.build && ` · build ${health.build}`}
      </p>

      {denied && <Card><p role="alert" style={{ color: "var(--red-text)", margin: 0 }}>{denied}</p></Card>}
      {metrics && <Dashboard m={metrics} minutes={minutes} />}

      <Card title="Raw logs" sub="Newest first, refreshed every 10 seconds.">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
          <label>Log<br />
            <select value={source} onChange={e => setSource(e.target.value)}>
              {(answer?.sources ?? [{ id: source, label: source, bytes: null }]).map(s => <option key={s.id} value={s.id}>{s.label}{s.id === "security" ? "" : ` (${size(s.bytes)})`}</option>)}
            </select>
          </label>
          <label>Contains<br /><input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="error, 503, an email…" /></label>
          <button className="btn" onClick={() => setTick(t => t + 1)}>Refresh</button>
          {source !== "security" && <button className="btn" onClick={download}>Download</button>}
        </div>
        {problem && <p role="alert" style={{ color: "var(--red)", marginTop: 12 }}>{problem}</p>}
        <pre style={{ marginTop: 14, maxHeight: "65vh", overflow: "auto", fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {answer?.lines.length ? answer.lines.join("\n") : answer ? "Nothing logged here yet." : "Loading…"}
        </pre>
      </Card>
    </div>
  );
}

function Tile({ label, value, note, style }: { label: string; value: ReactNode; note: ReactNode; style?: CSSProperties }) {
  return <div className="card kpi" style={style}>
    <div className="k-label" style={{ minHeight: 0, color: "inherit", opacity: .85 }}>{label}</div>
    <div className="k-value" style={{ color: "inherit", fontSize: 28 }}>{value}</div>
    <div className="k-note" style={{ color: "inherit", opacity: .85 }}>{note}</div>
  </div>;
}

const grid = (min: number): CSSProperties => ({ display: "grid", gap: 16, gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${min}px), 1fr))` });
const mono: CSSProperties = { fontFamily: "monospace", fontSize: 12, lineHeight: 1.5, wordBreak: "break-word" };

function Dashboard({ m, minutes }: { m: Metrics; minutes: number }) {
  const theme = useTheme();
  const t = m.totals;
  const last = m.machine.at(-1);
  const errorPct = t.requests ? (100 * t["5xx"]) / t.requests : 0;
  const peakCpu = Math.max(0, ...m.machine.map(s => s.cpu_pct).filter(Number.isFinite));   // older samples carry no CPU
  const range: [number, number] = [Date.parse(`${m.since}Z`), Date.parse(m.now)];
  const pale = { background: "var(--tag)", borderColor: "transparent" };

  const charts = useMemo(() => {
    const at = (minute: string) => Date.parse(`${minute}Z`);
    const timeAxis = { type: "time", min: range[0], max: range[1], axisLabel: valueText() };
    const valueAxis = (name: string, extra = {}) => ({ type: "value", name, nameTextStyle: valueText(), axisLabel: valueText(), ...extra });
    const base = { tooltip: { ...tooltip(), trigger: "axis" }, legend: { top: 0, left: 0 }, grid: { left: 8, right: 8, top: 40, bottom: 4, containLabel: true }, xAxis: timeAxis };
    const line = (name: string, color: string, data: [number, number | null][], extra = {}) =>
      ({ name, type: "line", showSymbol: false, color, data, ...extra });
    const machine = (pick: (s: Sample) => number) => m.machine.map(s => [Date.parse(s.time), pick(s)] as [number, number]);
    const limit = last?.limit_mb ?? 0;
    const histLabel = (b: { up_to_ms: number | null }, i: number) =>
      b.up_to_ms == null ? `> ${ms(m.histogram[i - 1]?.up_to_ms ?? 5000)}` : `≤${ms(b.up_to_ms)}`;
    const processes = Object.entries(last?.processes_mb ?? {}).sort((a, b) => a[1] - b[1]);
    const bars = (labels: string[], values: number[], colors: string[] | string, unit: string) => ({
      tooltip: { ...tooltip(), trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 8, right: 48, top: 4, bottom: 4, containLabel: true },
      xAxis: { type: "value", axisLabel: { show: false }, splitLine: { show: false } },
      yAxis: { type: "category", data: labels, axisLabel: axisText() },
      series: [{ type: "bar", barMaxWidth: 16, data: values.map((v, i) => ({ value: v, itemStyle: { color: Array.isArray(colors) ? colors[i] : colors, borderRadius: [0, 4, 4, 0] } })),
        label: { show: true, position: "right", color: C.ink, formatter: (p: { value: number }) => `${num(p.value)}${unit}` } }],
    });
    return {
      requests: { ...base, yAxis: valueAxis("requests"), series: (["2xx", "3xx", "4xx", "5xx"] as const).map(k => ({
        name: k, type: "bar", stack: "all", barMaxWidth: 14,
        color: { "2xx": C.s1, "3xx": C.sky, "4xx": C.rose, "5xx": C.red }[k],
        data: m.traffic.map(x => [at(x.minute), x[k]]) })) },
      times: { ...base, yAxis: valueAxis("ms", { type: "log", min: 0.1 }), series: [
        line("p50", C.s3, m.traffic.map(x => [at(x.minute), x.p50_ms || null])),
        line("p95", C.s1, m.traffic.map(x => [at(x.minute), x.p95_ms || null])),
        line("p99", C.red, m.traffic.map(x => [at(x.minute), x.p99_ms || null]))] },
      machine: { ...base, yAxis: [valueAxis("CPU %", { min: 0, max: 100 }), valueAxis(`MB of ${num(limit)}`, { min: 0, max: limit || null, splitLine: { show: false } })], series: [
        line("CPU %", C.red, machine(s => s.cpu_pct)),
        line("Working set MB", C.s1, machine(s => s.working_set_mb), { yAxisIndex: 1 }),
        line("Own memory MB", C.s3, machine(s => s.anon_mb), { yAxisIndex: 1 })] },
      network: { ...base, yAxis: valueAxis("KB/s"), series: [
        line("In", C.s3, machine(s => s.net_in_kbs)), line("Out", C.s1, machine(s => s.net_out_kbs))] },
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
    <div style={grid(170)}>
      <Tile label="Requests" value={num(t.requests)} note={`${num(t.requests / (minutes * 60), 1)} per second on average`}
            style={{ background: LIGHT.blue, borderColor: LIGHT.blue, color: "#FFFFFF" }} />
      <Tile label="Server time p95" value={ms(t.p95_ms)} note={`${num(t.under_1ms, 1)}% under 1 ms · p99 ${ms(t.p99_ms)}`} style={pale} />
      <Tile label="Errors (5xx)" value={`${num(t["5xx"])} errors`} note={`${num(errorPct, 2)}% of requests · ${num(t["4xx"])} 4xx`}
            style={t["5xx"] ? { background: C.red, borderColor: C.red, color: "#FFFFFF" } : { background: "var(--fill)", borderColor: "transparent" }} />
      <Tile label="CPU now" value={last ? `${num(last.cpu_pct, 1)}%` : "–"} note={last ? `peak ${num(peakCpu, 1)}% · ${last.cpus} CPU, load ${last.load_1m}` : "no samples yet"} style={pale} />
      <Tile label="Memory now" value={last ? `${num(last.working_set_mb)} MB` : "–"} note={last ? `of ${num(last.limit_mb)} MB · own memory ${num(last.anon_mb)} MB` : "no samples yet"}
            style={{ background: "var(--fill)", borderColor: "transparent" }} />
      <Tile label="Bandwidth out" value={bytes(t.bytes)} note={last ? `now ${num(last.net_out_kbs, 1)} KB/s · disk ${last.disk_used} used` : "in this range"} style={pale} />
    </div>

    <div style={grid(440)}>
      <Card title="Requests per minute" sub="By status class; 5xx are server errors.">
        {m.traffic.length ? <EChart option={charts.requests} height={260} label="Requests per minute by status class" /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="Server time" sub="p50, p95 and p99 per minute, log scale. Excludes the time on the internet.">
        {m.traffic.length ? <EChart option={charts.times} height={260} label="Server time percentiles per minute in milliseconds" /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="CPU and memory" sub="CPU as % of all CPUs; memory against the container limit.">
        {m.machine.length ? <EChart option={charts.machine} height={260} label="CPU percent and memory in megabytes over time" /> : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
      <Card title="Bandwidth" sub="Network in and out, KB per second.">
        {m.machine.length ? <EChart option={charts.network} height={260} label="Network bandwidth in and out over time" /> : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
    </div>

    <div style={grid(300)}>
      <Card title="How requests were answered" sub="nginx cache and published files never reach Python.">
        {t.requests ? <EChart option={charts.answered} height={200} label="How requests were answered: nginx cache, published file or API" /> : <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="Response times" sub="Requests per server-time bucket; over 1 s in red.">
        <EChart option={charts.histogram} height={320} label="Response time histogram" />
      </Card>
      <Card title="Memory per process" sub={last ? `Latest sample, ${new Date(last.time).toLocaleTimeString("en-GB")}` : undefined}>
        {last ? <EChart option={charts.processes} height={Math.max(120, Object.keys(last.processes_mb).length * 32 + 20)} label="Memory per process in megabytes" />
          : <p className="muted">{NO_SAMPLES}</p>}
      </Card>
    </div>

    <div style={grid(360)}>
      <Card title="Busiest pages">
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Page</th><th className="num">Requests</th><th className="num">Slowest</th></tr></thead>
          <tbody>{m.pages.map(p => <tr key={p.page}><th scope="row" style={{ ...mono, fontWeight: 500 }}>{p.page}</th>
            <td className="num">{num(p.requests)}</td><td className="num">{ms(p.slowest_ms)}</td></tr>)}</tbody>
        </table></div>
        {!m.pages.length && <p className="muted">No requests in this range.</p>}
      </Card>
      <Card title="Top visitors" sub="By client address; the server's own probes are left out.">
        {m.clients.map(c => <div key={c.client} className="quota" style={{ margin: "8px 0" }}>
          <span style={{ ...mono, width: 130, flex: "none" }}>{c.client}</span>
          <span className="bar"><i style={{ width: `${(100 * c.requests) / m.clients[0].requests}%`, background: C.s1 }} /></span>
          <span style={{ width: 70, textAlign: "right" }}>{num(c.requests)}</span>
        </div>)}
        {!m.clients.length && <p className="muted">No visitors in this range.</p>}
      </Card>
    </div>

    <div style={grid(360)}>
      <Card title="Recent problems" sub="The latest error lines from the API, nginx and the ETL."
            aside={<span className={`chip ${m.problems.length ? "sig" : "flat"}`}>{m.problems.length} problems</span>}>
        {m.problems.length ? <ul style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: 320, overflow: "auto" }}>
          {m.problems.map((p, i) => <li key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "6px 0 6px 10px", borderLeft: `3px solid ${C.red}`, marginBottom: 6 }}>
            <span className="chip sig" style={{ flex: "none" }}>{p.source}</span><span style={mono}>{p.line}</span></li>)}
        </ul> : <p className="muted">No errors logged.</p>}
      </Card>
      <Card title="Restarts and ETL" sub="Newest first.">
        <h3 className="eyebrow" style={{ margin: "0 0 6px" }}>Restarts</h3>
        <pre style={{ ...mono, whiteSpace: "pre-wrap", margin: "0 0 12px" }}>{m.restarts.join("\n") || "None logged."}</pre>
        <h3 className="eyebrow" style={{ margin: "0 0 6px" }}>ETL</h3>
        <pre style={{ ...mono, whiteSpace: "pre-wrap", margin: 0 }}>{m.etl.join("\n") || "None logged."}</pre>
      </Card>
    </div>
  </>;
}
