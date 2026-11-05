import { useEffect, useState } from "react";
import { perf } from "../perf";
import type { TransactionMetric } from "../perf";

export default function PerfHUD() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"tx" | "api" | "comp" | "graph">("tx");
  const [copied, setCopied] = useState(false);
  const [metrics, setMetrics] = useState({
    transactions: perf.getTransactions(),
    apis: perf.getApis(),
    components: perf.getComponents(),
    graphs: perf.getGraphs(),
    memoryMb: perf.getMemoryMb(),
    consoleEnabled: perf.consoleLogging,
  });

  const [scanEnabled, setScanEnabled] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("cip_scan") === "1";
    }
    return false;
  });

  useEffect(() => {
    const unsub = perf.subscribe(() => {
      setMetrics({
        transactions: perf.getTransactions(),
        apis: perf.getApis(),
        components: perf.getComponents(),
        graphs: perf.getGraphs(),
        memoryMb: perf.getMemoryMb(),
        consoleEnabled: perf.consoleLogging,
      });
    });

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "p") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      unsub();
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const latestTx: TransactionMetric | undefined = metrics.transactions[0];

  const handleCopy = () => {
    navigator.clipboard.writeText(perf.generateReport());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleScan = () => {
    const next = !scanEnabled;
    setScanEnabled(next);
    localStorage.setItem("cip_scan", next ? "1" : "0");
    if ((window as any).__REACT_SCAN__?.setOptions) {
      (window as any).__REACT_SCAN__.setOptions({ enabled: next });
    } else {
      window.location.reload();
    }
  };

  return (
    <div className="cip-perf-hud-root">
      {/* Floating Pill / Trigger */}
      {!open && (
        <button
          className="cip-perf-badge"
          onClick={() => setOpen(true)}
          title="Open CIP Performance & Telemetry Inspector (Ctrl+Shift+P)"
          aria-label="Open Performance HUD"
        >
          <span className="dot" />
          <span className="title">CIP Perf</span>
          {latestTx && (
            <span className="latest-dur">
              {latestTx.durationMs.toFixed(0)}ms
            </span>
          )}
          {metrics.memoryMb && (
            <span className="latest-mem">{metrics.memoryMb}MB</span>
          )}
        </button>
      )}

      {/* Slide-out Diagnostic Drawer */}
      {open && (
        <div className="cip-perf-panel" role="dialog" aria-label="Performance Telemetry">
          <div className="panel-header">
            <div className="title-area">
              <span className="brand-dot" />
              <h3>CIP Telemetry & Performance</h3>
              <span className="shortcut-tip">Ctrl+Shift+P</span>
            </div>
            <div className="header-actions">
              <button
                className={`btn-action ${copied ? "success" : ""}`}
                onClick={handleCopy}
                title="Copy markdown diagnostic report to clipboard"
              >
                {copied ? "✓ Copied!" : "📋 Copy Report"}
              </button>
              <button
                className={`btn-action ${metrics.consoleEnabled ? "active" : ""}`}
                onClick={() => perf.toggleConsole()}
                title="Toggle browser console logging"
              >
                {metrics.consoleEnabled ? "Console: ON" : "Console: OFF"}
              </button>
              <button
                className={`btn-action ${scanEnabled ? "active" : ""}`}
                onClick={handleToggleScan}
                title="Toggle React Scan visual render heatmap"
              >
                {scanEnabled ? "Scan: ON" : "Scan: OFF"}
              </button>
              <button
                className="btn-action"
                onClick={() => perf.clear()}
                title="Clear collected telemetry logs"
              >
                Clear
              </button>
              <button
                className="btn-close"
                onClick={() => setOpen(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          {/* KPI Snapshot Cards */}
          <div className="perf-summary-cards">
            <div className="card">
              <span className="card-lbl">Latest Page E2E</span>
              <span className="card-val">
                {latestTx && latestTx.type === "page_load"
                  ? `${latestTx.durationMs.toFixed(1)} ms`
                  : "–"}
              </span>
              <span className="card-sub">
                {latestTx && latestTx.type === "page_load"
                  ? `APIs: ${latestTx.apiDurationMs.toFixed(0)}ms | React: ${latestTx.reactDurationMs.toFixed(0)}ms | Graphs: ${latestTx.graphDurationMs.toFixed(0)}ms`
                  : "Navigate to measure"}
              </span>
            </div>

            <div className="card">
              <span className="card-lbl">Latest Filter Change</span>
              <span className="card-val">
                {metrics.transactions.find((t) => t.type === "filter_change")
                  ? `${metrics.transactions.find((t) => t.type === "filter_change")!.durationMs.toFixed(1)} ms`
                  : "–"}
              </span>
              <span className="card-sub">
                {metrics.transactions.find((t) => t.type === "filter_change")
                  ?.name ?? "Change filter to measure"}
              </span>
            </div>

            <div className="card">
              <span className="card-lbl">Slowest API</span>
              <span className="card-val">
                {metrics.apis.length > 0
                  ? `${Math.max(...metrics.apis.map((a) => a.durationMs)).toFixed(1)} ms`
                  : "–"}
              </span>
              <span className="card-sub">
                {metrics.apis.sort((a, b) => b.durationMs - a.durationMs)[0]?.endpoint ?? "None"}
              </span>
            </div>

            <div className="card">
              <span className="card-lbl">Browser Heap RAM</span>
              <span className="card-val">
                {metrics.memoryMb ? `${metrics.memoryMb} MB` : "N/A"}
              </span>
              <span className="card-sub">JS Engine Heap</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="perf-tabs">
            <button
              className={`tab-btn ${tab === "tx" ? "active" : ""}`}
              onClick={() => setTab("tx")}
            >
              ⏱️ Page & Filter Timings ({metrics.transactions.length})
            </button>
            <button
              className={`tab-btn ${tab === "api" ? "active" : ""}`}
              onClick={() => setTab("api")}
            >
              🌐 API Endpoints ({metrics.apis.length})
            </button>
            <button
              className={`tab-btn ${tab === "comp" ? "active" : ""}`}
              onClick={() => setTab("comp")}
            >
              ⚛️ Components ({metrics.components.length})
            </button>
            <button
              className={`tab-btn ${tab === "graph" ? "active" : ""}`}
              onClick={() => setTab("graph")}
            >
              📈 Graphs & Canvases ({metrics.graphs.length})
            </button>
          </div>

          {/* Tab 1: Transactions (Page loads & filter changes) */}
          {tab === "tx" && (
            <div className="tab-pane">
              {metrics.transactions.length === 0 ? (
                <div className="empty-state">No page transitions or filter changes logged yet.</div>
              ) : (
                <div className="perf-table-wrap">
                  <table className="perf-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Target</th>
                        <th>End-to-End</th>
                        <th>API Time</th>
                        <th>React Time</th>
                        <th>Graph Paint</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.transactions.map((tx) => (
                        <tr key={tx.id}>
                          <td>
                            <span className={`pill ${tx.type}`}>
                              {tx.type === "page_load" ? "Page Load" : "Filter"}
                            </span>
                          </td>
                          <td className="code-cell font-mono">{tx.name}</td>
                          <td className="num font-bold">
                            <span
                              className={
                                tx.durationMs > 500
                                  ? "text-red"
                                  : tx.durationMs > 200
                                  ? "text-amber"
                                  : "text-green"
                              }
                            >
                              {tx.durationMs.toFixed(1)} ms
                            </span>
                          </td>
                          <td className="num">{tx.apiDurationMs.toFixed(1)} ms</td>
                          <td className="num">{tx.reactDurationMs.toFixed(1)} ms</td>
                          <td className="num">{tx.graphDurationMs.toFixed(1)} ms</td>
                          <td className="num muted">
                            {new Date(tx.timestamp).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: APIs */}
          {tab === "api" && (
            <div className="tab-pane">
              {metrics.apis.length === 0 ? (
                <div className="empty-state">No API requests recorded yet.</div>
              ) : (
                <div className="perf-table-wrap">
                  <table className="perf-table">
                    <thead>
                      <tr>
                        <th>Method</th>
                        <th>Endpoint</th>
                        <th>Duration</th>
                        <th>Server-Timing</th>
                        <th>Source</th>
                        <th>Size</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.apis.map((a) => (
                        <tr key={a.id}>
                          <td>
                            <span className="pill method">{a.method}</span>
                          </td>
                          <td className="code-cell font-mono">{a.endpoint}</td>
                          <td className="num font-bold">
                            <span
                              className={
                                a.durationMs > 300
                                  ? "text-red"
                                  : a.durationMs > 150
                                  ? "text-amber"
                                  : "text-green"
                              }
                            >
                              {a.durationMs.toFixed(1)} ms
                            </span>
                          </td>
                          <td className="num muted">
                            {a.serverDurationMs !== null
                              ? `${a.serverDurationMs.toFixed(1)} ms`
                              : "–"}
                          </td>
                          <td>
                            <span className={`pill ${a.source}`}>
                              {a.source === "cache" ? "⚡ Cache" : "Network"}
                            </span>
                          </td>
                          <td className="num muted">
                            {a.sizeBytes ? `${(a.sizeBytes / 1024).toFixed(1)} KB` : "–"}
                          </td>
                          <td className="num">{a.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Components */}
          {tab === "comp" && (
            <div className="tab-pane">
              {metrics.components.length === 0 ? (
                <div className="empty-state">No component renders recorded yet.</div>
              ) : (
                <div className="perf-table-wrap">
                  <table className="perf-table">
                    <thead>
                      <tr>
                        <th>Component</th>
                        <th>Max Duration</th>
                        <th>Avg Duration</th>
                        <th>Render Count</th>
                        <th>Last Phase</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.components.map((c) => (
                        <tr key={c.id}>
                          <td className="font-mono font-bold">&lt;{c.id} /&gt;</td>
                          <td className="num font-bold">
                            <span
                              className={
                                c.maxDurationMs > 30
                                  ? "text-red"
                                  : c.maxDurationMs > 16
                                  ? "text-amber"
                                  : "text-green"
                              }
                            >
                              {c.maxDurationMs.toFixed(1)} ms
                            </span>
                          </td>
                          <td className="num">{c.avgDurationMs.toFixed(1)} ms</td>
                          <td className="num">{c.count}</td>
                          <td>
                            <span className="pill phase">{c.phase}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Graphs */}
          {tab === "graph" && (
            <div className="tab-pane">
              {metrics.graphs.length === 0 ? (
                <div className="empty-state">No ECharts canvas paintings recorded yet.</div>
              ) : (
                <div className="perf-table-wrap">
                  <table className="perf-table">
                    <thead>
                      <tr>
                        <th>Chart / Question</th>
                        <th>Canvas Render Time</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.graphs.map((g) => (
                        <tr key={g.id}>
                          <td className="font-semibold">{g.label}</td>
                          <td className="num font-bold">
                            <span
                              className={
                                g.durationMs > 100
                                  ? "text-red"
                                  : g.durationMs > 50
                                  ? "text-amber"
                                  : "text-green"
                              }
                            >
                              {g.durationMs.toFixed(1)} ms
                            </span>
                          </td>
                          <td className="num muted">
                            {new Date(g.timestamp).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
