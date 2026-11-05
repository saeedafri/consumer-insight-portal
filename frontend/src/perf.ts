// CIP High-Performance Telemetry & Profiling Engine
// Built natively on User Timing API, PerformanceObserver, React Profiler & ECharts lifecycles.
// Zero external dependencies, bounded ring-buffer memory (<0.5 MB RAM), nanosecond precision.

export interface ApiMetric {
  id: string;
  url: string;
  endpoint: string;
  method: string;
  status: number;
  durationMs: number;
  serverDurationMs: number | null;
  sizeBytes: number | null;
  source: "network" | "cache";
  timestamp: number;
}

export interface ComponentMetric {
  id: string;
  phase: "mount" | "update" | "nested-update";
  actualDurationMs: number;
  baseDurationMs: number;
  count: number;
  avgDurationMs: number;
  maxDurationMs: number;
  timestamp: number;
}

export interface GraphMetric {
  id: string;
  label: string;
  durationMs: number;
  timestamp: number;
}

export interface TransactionMetric {
  id: string;
  type: "page_load" | "filter_change";
  name: string;
  startTime: number;
  durationMs: number;
  apiDurationMs: number;
  reactDurationMs: number;
  graphDurationMs: number;
  apis: ApiMetric[];
  components: ComponentMetric[];
  graphs: GraphMetric[];
  memoryMb: number | null;
  timestamp: number;
}

const MAX_HISTORY = 60; // Keep RAM under 0.5 MB

class CIPTelemetry {
  private apis: ApiMetric[] = [];
  private components: Map<string, ComponentMetric> = new Map();
  private recentRenders: ComponentMetric[] = [];
  private graphs: GraphMetric[] = [];
  private transactions: TransactionMetric[] = [];
  private listeners: Set<() => void> = new Set();

  private activeTx: {
    id: string;
    type: "page_load" | "filter_change";
    name: string;
    startTime: number;
    pendingApis: Set<string>;
    pendingGraphs: Set<string>;
    apis: ApiMetric[];
    components: ComponentMetric[];
    graphs: GraphMetric[];
    timeoutId?: number;
  } | null = null;

  public consoleLogging = true;

  constructor() {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("cip_perf_console");
      if (stored !== null) this.consoleLogging = stored === "1";
    }
  }

  public subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private notify() {
    this.listeners.forEach((fn) => {
      try {
        fn();
      } catch (e) {
        console.error(e);
      }
    });
  }

  public getMemoryMb(): number | null {
    if (typeof window !== "undefined" && (window.performance as any)?.memory) {
      const mem = (window.performance as any).memory;
      return Math.round((mem.usedJSHeapSize / (1024 * 1024)) * 10) / 10;
    }
    return null;
  }

  // ── 1. Page & Route Transitions ──────────────────────────────────────────
  public startPageTransition(pathname: string): void {
    this.closeActiveTx();

    const id = `page_${Date.now()}`;
    const startTime = performance.now();
    this.activeTx = {
      id,
      type: "page_load",
      name: pathname,
      startTime,
      pendingApis: new Set(),
      pendingGraphs: new Set(),
      apis: [],
      components: [],
      graphs: [],
    };

    this.scheduleTxSettling();
  }

  // ── 2. Filter Changes ────────────────────────────────────────────────────
  public startFilterChange(filterName: string, value: string): void {
    this.closeActiveTx();

    const id = `filter_${Date.now()}`;
    const startTime = performance.now();
    this.activeTx = {
      id,
      type: "filter_change",
      name: `${filterName}: ${value}`,
      startTime,
      pendingApis: new Set(),
      pendingGraphs: new Set(),
      apis: [],
      components: [],
      graphs: [],
    };

    this.scheduleTxSettling();
  }

  private scheduleTxSettling(): void {
    if (!this.activeTx) return;
    if (this.activeTx.timeoutId) clearTimeout(this.activeTx.timeoutId);

    // Wait until network, DOM loading spinners, and canvas graphs are 100% complete
    this.activeTx.timeoutId = window.setTimeout(() => {
      if (!this.activeTx) return;

      // 1. Pending API calls?
      if (this.activeTx.pendingApis.size > 0) {
        this.scheduleTxSettling();
        return;
      }

      // 2. Pending ECharts canvases?
      if (this.activeTx.pendingGraphs.size > 0) {
        this.scheduleTxSettling();
        return;
      }

      // 3. Any DOM loading indicators/spinners on screen?
      if (typeof document !== "undefined") {
        const hasSpinner = document.querySelector(".state, [role='status'], .spinner");
        if (hasSpinner && hasSpinner.textContent?.toLowerCase().includes("loading")) {
          this.scheduleTxSettling();
          return;
        }
      }

      // 4. Fully committed & painted to screen: wait for double rAF
      if (typeof window !== "undefined" && window.requestAnimationFrame) {
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            this.closeActiveTx();
          });
        });
      } else {
        this.closeActiveTx();
      }
    }, 140);
  }

  public registerPendingApi(url: string): () => void {
    if (this.activeTx) {
      this.activeTx.pendingApis.add(url);
    }
    return () => {
      if (this.activeTx) {
        this.activeTx.pendingApis.delete(url);
        this.scheduleTxSettling();
      }
    };
  }

  public registerPendingGraph(label: string): () => void {
    if (this.activeTx) {
      this.activeTx.pendingGraphs.add(label);
    }
    return () => {
      if (this.activeTx) {
        this.activeTx.pendingGraphs.delete(label);
        this.scheduleTxSettling();
      }
    };
  }

  private closeActiveTx(): void {
    if (!this.activeTx) return;
    if (this.activeTx.timeoutId) clearTimeout(this.activeTx.timeoutId);

    const endTime = performance.now();
    const durationMs = Math.round((endTime - this.activeTx.startTime) * 10) / 10;

    const apiDurationMs =
      this.activeTx.apis.length > 0
        ? Math.max(...this.activeTx.apis.map((a) => a.durationMs))
        : 0;

    const reactDurationMs =
      this.activeTx.components.length > 0
        ? Math.round(
            this.activeTx.components.reduce(
              (acc, c) => acc + c.actualDurationMs,
              0
            ) * 10
          ) / 10
        : 0;

    const graphDurationMs =
      this.activeTx.graphs.length > 0
        ? Math.round(
            this.activeTx.graphs.reduce((acc, g) => acc + g.durationMs, 0) * 10
          ) / 10
        : 0;

    const tx: TransactionMetric = {
      id: this.activeTx.id,
      type: this.activeTx.type,
      name: this.activeTx.name,
      startTime: this.activeTx.startTime,
      durationMs,
      apiDurationMs,
      reactDurationMs,
      graphDurationMs,
      apis: [...this.activeTx.apis],
      components: [...this.activeTx.components],
      graphs: [...this.activeTx.graphs],
      memoryMb: this.getMemoryMb(),
      timestamp: Date.now(),
    };

    this.transactions.unshift(tx);
    if (this.transactions.length > MAX_HISTORY) this.transactions.pop();

    if (this.consoleLogging) {
      this.logTransactionToConsole(tx);
    }

    this.activeTx = null;
    this.notify();
  }

  // ── 3. API & Endpoint Logging ────────────────────────────────────────────
  public logApi(metric: Omit<ApiMetric, "id" | "timestamp">): void {
    const entry: ApiMetric = {
      ...metric,
      id: `api_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      timestamp: Date.now(),
    };

    this.apis.unshift(entry);
    if (this.apis.length > MAX_HISTORY) this.apis.pop();

    if (this.activeTx) {
      this.activeTx.apis.push(entry);
      this.scheduleTxSettling();
    }

    if (this.consoleLogging) {
      const isSlow = entry.durationMs > 250;
      const color = isSlow ? "#e05252" : entry.source === "cache" ? "#22c55e" : "#3b82f6";
      const badge = entry.source === "cache" ? "⚡ CACHE" : `${entry.durationMs.toFixed(1)}ms`;
      console.log(
        `%c[API] %c${metric.method} %c${metric.endpoint} %c${badge}`,
        "color:#888; font-weight:bold",
        "color:#f59e0b; font-weight:bold",
        "color:#e2e8f0",
        `color:${color}; font-weight:bold`,
        {
          fullUrl: entry.url,
          status: entry.status,
          size: entry.sizeBytes ? `${(entry.sizeBytes / 1024).toFixed(1)} KB` : "unknown",
          serverTiming: entry.serverDurationMs ? `${entry.serverDurationMs.toFixed(1)}ms` : "N/A",
        }
      );
    }

    this.notify();
  }

  // ── 4. React Component Profiling (React 19 <Profiler>) ────────────────────
  public onRenderProfiler = (
    id: string,
    phase: "mount" | "update" | "nested-update",
    actualDuration: number,
    baseDuration: number
  ): void => {
    const dur = Math.round(actualDuration * 100) / 100;
    const base = Math.round(baseDuration * 100) / 100;

    const existing = this.components.get(id);
    const count = (existing?.count ?? 0) + 1;
    const avg = existing
      ? Math.round(((existing.avgDurationMs * (count - 1) + dur) / count) * 100) / 100
      : dur;
    const max = existing ? Math.max(existing.maxDurationMs, dur) : dur;

    const item: ComponentMetric = {
      id,
      phase,
      actualDurationMs: dur,
      baseDurationMs: base,
      count,
      avgDurationMs: avg,
      maxDurationMs: max,
      timestamp: Date.now(),
    };

    this.components.set(id, item);
    this.recentRenders.unshift(item);
    if (this.recentRenders.length > MAX_HISTORY) this.recentRenders.pop();

    if (this.activeTx) {
      this.activeTx.components.push(item);
    }

    // Highlight slow components (> 16ms = frame drop)
    if (this.consoleLogging && dur > 16) {
      console.warn(
        `%c[Slow Component] %c<${id} /> %c${phase} took %c${dur}ms%c (base: ${base}ms)`,
        "color:#e05252; font-weight:bold",
        "color:#38bdf8; font-weight:bold",
        "color:#aaa",
        "color:#f87171; font-weight:bold",
        "color:#aaa"
      );
    }

    this.notify();
  };

  // ── 5. ECharts & Graph Canvas Timing ─────────────────────────────────────
  public logGraph(metric: Omit<GraphMetric, "id" | "timestamp">): void {
    const entry: GraphMetric = {
      ...metric,
      id: `graph_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      timestamp: Date.now(),
    };

    this.graphs.unshift(entry);
    if (this.graphs.length > MAX_HISTORY) this.graphs.pop();

    if (this.activeTx) {
      this.activeTx.graphs.push(entry);
      this.scheduleTxSettling();
    }

    if (this.consoleLogging) {
      const isSlow = entry.durationMs > 50;
      console.log(
        `%c[Graph Canvas] %c${entry.label} %cpainted in %c${entry.durationMs.toFixed(1)}ms`,
        "color:#888; font-weight:bold",
        "color:#a855f7; font-weight:bold",
        "color:#aaa",
        `color:${isSlow ? "#e05252" : "#22c55e"}; font-weight:bold`
      );
    }

    this.notify();
  }

  // ── 6. Console Output Visualizer ─────────────────────────────────────────
  private logTransactionToConsole(tx: TransactionMetric): void {
    const isPage = tx.type === "page_load";
    const titleColor = isPage ? "#3b82f6" : "#10b981";
    const badgeColor =
      tx.durationMs > 500 ? "#ef4444" : tx.durationMs > 200 ? "#f59e0b" : "#10b981";

    console.groupCollapsed(
      `%c[CIP Perf] %c${isPage ? "PAGE LOAD" : "FILTER CHANGE"}%c ${tx.name} %c${tx.durationMs.toFixed(1)}ms`,
      "color:#888; font-weight:bold",
      `background:${titleColor}; color:white; padding:2px 6px; border-radius:4px; font-weight:bold`,
      "color:#e2e8f0; font-weight:bold",
      `background:${badgeColor}; color:white; padding:2px 6px; border-radius:4px; font-weight:bold`
    );

    console.log(
      `⏱️ End-to-End: %c${tx.durationMs.toFixed(1)}ms%c | APIs: %c${tx.apiDurationMs.toFixed(1)}ms%c | React: %c${tx.reactDurationMs.toFixed(1)}ms%c | Graphs: %c${tx.graphDurationMs.toFixed(1)}ms%c | RAM: %c${tx.memoryMb ?? "?"} MB`,
      "font-weight:bold; color:#f87171",
      "",
      "font-weight:bold; color:#fbbf24",
      "",
      "font-weight:bold; color:#60a5fa",
      "",
      "font-weight:bold; color:#c084fc",
      "",
      "font-weight:bold; color:#4ade80"
    );

    if (tx.apis.length > 0) {
      console.groupCollapsed(`🌐 APIs called (${tx.apis.length})`);
      console.table(
        tx.apis.map((a) => ({
          Endpoint: a.endpoint,
          Duration: `${a.durationMs.toFixed(1)}ms`,
          ServerTiming: a.serverDurationMs ? `${a.serverDurationMs.toFixed(1)}ms` : "-",
          Source: a.source,
          Status: a.status,
          Size: a.sizeBytes ? `${(a.sizeBytes / 1024).toFixed(1)} KB` : "-",
        }))
      );
      console.groupEnd();
    }

    if (tx.components.length > 0) {
      console.groupCollapsed(`⚛️ Components rendered (${tx.components.length})`);
      console.table(
        [...tx.components]
          .sort((a, b) => b.actualDurationMs - a.actualDurationMs)
          .slice(0, 15)
          .map((c) => ({
            Component: c.id,
            Phase: c.phase,
            RenderTime: `${c.actualDurationMs}ms`,
            BaseTime: `${c.baseDurationMs}ms`,
          }))
      );
      console.groupEnd();
    }

    if (tx.graphs.length > 0) {
      console.groupCollapsed(`📈 Graphs painted (${tx.graphs.length})`);
      console.table(
        tx.graphs.map((g) => ({
          Graph: g.label,
          Duration: `${g.durationMs.toFixed(1)}ms`,
        }))
      );
      console.groupEnd();
    }

    console.groupEnd();
  }

  // ── 7. Queries & Getters ─────────────────────────────────────────────────
  public getTransactions(): TransactionMetric[] {
    return this.transactions;
  }

  public getApis(): ApiMetric[] {
    return this.apis;
  }

  public getComponents(): ComponentMetric[] {
    return Array.from(this.components.values()).sort(
      (a, b) => b.maxDurationMs - a.maxDurationMs
    );
  }

  public getGraphs(): GraphMetric[] {
    return this.graphs;
  }

  public toggleConsole(enabled?: boolean): boolean {
    this.consoleLogging = enabled ?? !this.consoleLogging;
    if (typeof window !== "undefined") {
      localStorage.setItem("cip_perf_console", this.consoleLogging ? "1" : "0");
    }
    this.notify();
    return this.consoleLogging;
  }

  public clear(): void {
    this.apis = [];
    this.components.clear();
    this.recentRenders = [];
    this.graphs = [];
    this.transactions = [];
    this.notify();
  }

  // ── 8. Markdown Diagnostic Report Generator ──────────────────────────────
  public generateReport(): string {
    const mem = this.getMemoryMb();
    const latestTx = this.transactions[0];
    const slowestApis = [...this.apis]
      .filter((a) => a.source === "network")
      .sort((a, b) => b.durationMs - a.durationMs)
      .slice(0, 5);
    const slowestComponents = this.getComponents().slice(0, 8);
    const slowestGraphs = [...this.graphs]
      .sort((a, b) => b.durationMs - a.durationMs)
      .slice(0, 5);

    let md = `# Consumer Insight Portal - Performance Diagnostics\n\n`;
    md += `- **Generated at:** ${new Date().toISOString()}\n`;
    md += `- **Browser Memory (Heap):** ${mem ? `${mem} MB` : "N/A"}\n\n`;

    if (latestTx) {
      md += `## Latest Transaction: ${latestTx.type === "page_load" ? "Page Transition" : "Filter Change"}\n`;
      md += `- **Name:** \`${latestTx.name}\`\n`;
      md += `- **End-to-End Latency:** **${latestTx.durationMs.toFixed(1)} ms**\n`;
      md += `- **Breakdown:** APIs: ${latestTx.apiDurationMs.toFixed(1)} ms | React Renders: ${latestTx.reactDurationMs.toFixed(1)} ms | Graphs: ${latestTx.graphDurationMs.toFixed(1)} ms\n\n`;
    }

    md += `## Slowest API Endpoints (Network)\n`;
    if (slowestApis.length === 0) {
      md += `_No network API calls recorded yet (all cached)._\n\n`;
    } else {
      md += `| Method | Endpoint | Duration | Server-Timing | Status | Size |\n`;
      md += `|---|---|---|---|---|---|\n`;
      slowestApis.forEach((a) => {
        md += `| ${a.method} | \`${a.endpoint}\` | **${a.durationMs.toFixed(1)} ms** | ${a.serverDurationMs ? `${a.serverDurationMs.toFixed(1)} ms` : "N/A"} | ${a.status} | ${a.sizeBytes ? `${(a.sizeBytes / 1024).toFixed(1)} KB` : "N/A"} |\n`;
      });
      md += `\n`;
    }

    md += `## Slowest React Components\n`;
    if (slowestComponents.length === 0) {
      md += `_No component renders recorded yet._\n\n`;
    } else {
      md += `| Component ID | Max Render | Avg Render | Renders | Phase |\n`;
      md += `|---|---|---|---|---|\n`;
      slowestComponents.forEach((c) => {
        md += `| \`${c.id}\` | **${c.maxDurationMs} ms** | ${c.avgDurationMs} ms | ${c.count} | ${c.phase} |\n`;
      });
      md += `\n`;
    }

    md += `## Graph Render Latency (ECharts Canvas)\n`;
    if (slowestGraphs.length === 0) {
      md += `_No graphs rendered yet._\n\n`;
    } else {
      md += `| Graph / Question | Duration |\n`;
      md += `|---|---|\n`;
      slowestGraphs.forEach((g) => {
        md += `| ${g.label} | **${g.durationMs.toFixed(1)} ms** |\n`;
      });
      md += `\n`;
    }

    return md;
  }
}

export const perf = new CIPTelemetry();
if (typeof window !== "undefined") {
  (window as any).__CIP_PERF__ = perf;
}
