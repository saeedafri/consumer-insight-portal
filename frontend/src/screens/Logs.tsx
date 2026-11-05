// Operational logs for admins (api/logs.py): nginx, the API, the ETL, the container, Azure App Service and security
// events, newest first, filterable, downloadable. While sign-in is the demo, the server also asks for the admin token.
import { useEffect, useState } from "react";
import { Card } from "../components/bits";

interface Source { id: string; label: string; bytes: number | null }
interface Answer { sources: Source[]; source: string; lines: string[] }

const TOKEN = "cip_admin_token";   // this tab only (sessionStorage): gone when the tab closes
const readToken = () => { try { return sessionStorage.getItem(TOKEN) ?? ""; } catch { return ""; } };
const size = (n: number | null) => n == null ? "not written yet" : n < 1024 ? `${n} B` : n < 2 ** 20 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 2 ** 20).toFixed(1)} MB`;

export default function Logs() {
  const [source, setSource] = useState("api");
  const [q, setQ] = useState("");
  const [token, setToken] = useState(readToken);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [problem, setProblem] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const ask = new AbortController();
    const query = new URLSearchParams({ source, q, lines: "500" });
    fetch(`/api/v1/admin/logs?${query}`, { credentials: "same-origin", signal: ask.signal, headers: token ? { "X-CIP-Admin-Token": token } : {} })
      .then(async r => {
        if (r.ok) { setAnswer(await r.json()); setProblem(""); return; }
        setProblem((await r.json().catch(() => ({}))).detail ?? `${r.status} ${r.statusText}`);
      })
      .catch(e => { if (e.name !== "AbortError") setProblem(String(e)); });
    return () => ask.abort();
  }, [source, q, token, tick]);

  useEffect(() => { const every = setInterval(() => setTick(t => t + 1), 10000); return () => clearInterval(every); }, []);

  const keepToken = (value: string) => { setToken(value); try { sessionStorage.setItem(TOKEN, value); } catch { /* private window */ } };
  const download = () => {
    void fetch(`/api/v1/admin/logs/download?source=${source}`, { credentials: "same-origin", headers: token ? { "X-CIP-Admin-Token": token } : {} })
      .then(r => r.ok ? r.blob() : Promise.reject(new Error(`${r.status}`)))
      .then(blob => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `cip-${source}.log`; a.click(); URL.revokeObjectURL(a.href); })
      .catch(() => setProblem("This log has no file to download yet"));
  };

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Admin</p>
        <h1 style={{ margin: "6px 0 4px", fontSize: 26 }}>Operational logs</h1>
        <p className="lede">Everything the server writes: requests, errors, ETL runs, restarts and security events. Newest first, refreshed every 10 seconds.</p>
      </div>
      <Card>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "end" }}>
          <label>Log<br />
            <select value={source} onChange={e => setSource(e.target.value)}>
              {(answer?.sources ?? [{ id: source, label: source, bytes: null }]).map(s => <option key={s.id} value={s.id}>{s.label}{s.id === "security" ? "" : ` (${size(s.bytes)})`}</option>)}
            </select>
          </label>
          <label>Contains<br /><input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="error, 503, an email…" /></label>
          <label>Admin token<br /><input type="password" value={token} onChange={e => keepToken(e.target.value)} placeholder="only while SSO is off" autoComplete="off" /></label>
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
