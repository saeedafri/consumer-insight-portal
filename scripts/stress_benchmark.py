#!/usr/bin/env python3
"""FastAPI Stress-Test Benchmark: 50 Concurrent Analysts Generating 10-Banner Cross-Tabs.

Tests:
  1. /api/v1/waves/{id}/crosstab across 10 demographic/behavioral banner combinations
  2. /api/v1/search across realistic market research queries
  3. /api/v1/questions/{family}/{study_type}/{qcode} across survey questions

Monitors:
  - Latency: Min, Mean, P50, P95, P99, Max per endpoint and overall
  - Server Memory: Baseline RSS, Peak RSS, Memory Spike Delta, Spike %, Post-test RSS
  - Database Connection Pool: Active checked-out connections, overflow, capacity saturation,
    connection timeouts, and FastAPI admission control 503s.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
import math
import os
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit

import psutil

# 10 demographic/behavioral banner cut pairs supported by the serving engine
BANNERS = [
    ("gender", "generation"),
    ("gender", "age_band"),
    ("income_band", "census_region"),
    ("generation", "income_band"),
    ("gender", "income_band"),
    ("age_band", "generation"),
    ("census_region", "urbanicity"),
    ("generation", "census_region"),
    ("age_band", "income_band"),
    ("gender", "urbanicity"),
]

SEARCH_TERMS = [
    "holiday shopping",
    "amazon prime",
    "grocery inflation",
    "apparel spending",
    "walmart target",
    "electronics",
    "consumer confidence",
    "social commerce",
    "personal finances",
    "store foot traffic",
]

QUESTIONS = ["q1", "q2", "q3", "q4", "q5", "q6", "XM1", "XM1A", "XM2", "XM3"]


class HttpKeepAliveClient:
    """High-throughput async HTTP/1.1 client with keep-alive and gzip decompression."""

    def __init__(self, base_url: str, cookie: str = ""):
        u = urlsplit(base_url)
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or (443 if u.scheme == "https" else 80)
        self.cookie = cookie
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        for attempt in range(3):
            try:
                if self.writer is None or self.writer.is_closing():
                    self.reader, self.writer = await asyncio.open_connection(
                        self.host, self.port, limit=2**24
                    )
                req = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {self.host}\r\n"
                    f"Cookie: {self.cookie}\r\n"
                    f"Accept-Encoding: gzip\r\n"
                    f"Connection: keep-alive\r\n\r\n"
                )
                self.writer.write(req.encode())
                await self.writer.drain()

                status_line = await self.reader.readline()
                if not status_line:
                    raise ConnectionResetError("Empty response")
                status = int(status_line.split()[1])

                headers: dict[str, str] = {}
                while True:
                    line = await self.reader.readline()
                    if line in (b"\r\n", b"\n", b""):
                        break
                    k, _, v = line.decode("latin1").partition(":")
                    headers[k.strip().lower()] = v.strip()

                content_len = int(headers.get("content-length", 0))
                body = await self.reader.readexactly(content_len) if content_len > 0 else b""

                if headers.get("content-encoding") == "gzip" and body:
                    try:
                        body = gzip.decompress(body)
                    except Exception:
                        pass

                return status, headers, body
            except (ConnectionResetError, asyncio.IncompleteReadError, OSError):
                if self.writer:
                    try:
                        self.writer.close()
                        await self.writer.wait_closed()
                    except Exception:
                        pass
                self.writer = None
                self.reader = None
                if attempt == 2:
                    raise
        raise RuntimeError("Request failed after retries")

    async def close(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None


@dataclass
class RequestRecord:
    endpoint_type: str
    path: str
    status: int
    duration_ms: float
    timestamp: float
    error: str | None = None


@dataclass
class PoolSample:
    timestamp: float
    size: int
    checkedin: int
    checkedout: int
    overflow: int
    active: int
    status_str: str


@dataclass
class MemorySample:
    timestamp: float
    rss_mb: float
    vms_mb: float
    cpu_percent: float


class ServerMonitor:
    def __init__(self, base_url: str, server_pid: int | None):
        self.base_url = base_url
        self.server_pid = server_pid
        self.process = psutil.Process(server_pid) if server_pid and psutil.pid_exists(server_pid) else None
        self.memory_samples: list[MemorySample] = []
        self.pool_samples: list[PoolSample] = []
        self._stop_event = asyncio.Event()

    async def run(self):
        http = HttpKeepAliveClient(self.base_url)
        while not self._stop_event.is_set():
            t = time.perf_counter()
            # 1. Sample Memory
            if self.process and self.process.is_running():
                try:
                    mem = self.process.memory_info()
                    cpu = self.process.cpu_percent(interval=None)
                    self.memory_samples.append(
                        MemorySample(
                            timestamp=t,
                            rss_mb=mem.rss / (1024 * 1024),
                            vms_mb=mem.vms / (1024 * 1024),
                            cpu_percent=cpu,
                        )
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # 2. Sample Pool via /healthz
            try:
                status, _, body = await http.get("/healthz")
                if status == 200:
                    data = json.loads(body)
                    pool = data.get("pool", {})
                    if pool and "checkedout" in pool:
                        size = pool.get("size", 10)
                        checkedin = pool.get("checkedin", 0)
                        checkedout = pool.get("checkedout", 0)
                        overflow = pool.get("overflow", 0)
                        active = checkedout + max(0, overflow)
                        self.pool_samples.append(
                            PoolSample(
                                timestamp=t,
                                size=size,
                                checkedin=checkedin,
                                checkedout=checkedout,
                                overflow=overflow,
                                active=active,
                                status_str=pool.get("status", ""),
                            )
                        )
            except Exception:
                pass

            await asyncio.sleep(0.05)  # 50ms sampling resolution
        await http.close()

    def stop(self):
        self._stop_event.set()


def calculate_percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0, "p50": 0, "p90": 0, "p95": 0, "p99": 0, "max": 0, "mean": 0}
    s = sorted(values)
    n = len(s)

    def p(q: float) -> float:
        idx = min(n - 1, max(0, int(math.ceil(q * n)) - 1))
        return s[idx]

    return {
        "min": s[0],
        "p50": p(0.50),
        "p90": p(0.90),
        "p95": p(0.95),
        "p99": p(0.99),
        "max": s[-1],
        "mean": statistics.fmean(s),
    }


async def simulate_analyst(
    analyst_id: int,
    base_url: str,
    wave_id: int,
    records: list[RequestRecord],
    mode: str = "standard",
    iterations: int = 1,
):
    """Simulates one analyst generating 10-banner cross-tabulations, searching, and viewing questions."""
    # 1. Sign in via dev-login to get unique authenticated session
    login_client = HttpKeepAliveClient(base_url)
    status, headers, _ = await login_client.get(
        f"/auth/dev-login?email=analyst_{analyst_id}@coresight.com&next=/"
    )
    cookie = headers.get("set-cookie", "").split(";")[0]
    await login_client.close()

    client = HttpKeepAliveClient(base_url, cookie=cookie)

    try:
        for it in range(iterations):
            # Select questions to generate cross-tabs for
            qs = random.sample(QUESTIONS, min(3, len(QUESTIONS)))

            # Step A: Generate 10-banner cross-tabulations
            for b_idx, (dim1, dim2) in enumerate(BANNERS):
                q = qs[b_idx % len(qs)]
                weeks = 4 if (b_idx % 3 == 0) else 1  # test both 1-week and 4-week pooled
                path = f"/api/v1/waves/{wave_id}/crosstab?q={quote(q)}&by={dim1},{dim2}&weeks={weeks}"
                t0 = time.perf_counter()
                err = None
                status = 0
                try:
                    status, _, _ = await client.get(path)
                except Exception as e:
                    err = str(e)
                dur = (time.perf_counter() - t0) * 1000.0
                records.append(RequestRecord("crosstab", path, status, dur, t0, err))

                if mode == "standard":
                    await asyncio.sleep(random.uniform(0.02, 0.08))

            # Step B: Realistic Search
            search_query = random.choice(SEARCH_TERMS)
            path = f"/api/v1/search?q={quote(search_query)}&limit=40"
            t0 = time.perf_counter()
            err = None
            status = 0
            try:
                status, _, _ = await client.get(path)
            except Exception as e:
                err = str(e)
            dur = (time.perf_counter() - t0) * 1000.0
            records.append(RequestRecord("search", path, status, dur, t0, err))

            if mode == "standard":
                await asyncio.sleep(random.uniform(0.02, 0.05))

            # Step C: Question Explorer lookup
            target_q = random.choice(QUESTIONS)
            path = f"/api/v1/questions/CSI-US/tracker/{quote(target_q)}"
            t0 = time.perf_counter()
            err = None
            status = 0
            try:
                status, _, _ = await client.get(path)
            except Exception as e:
                err = str(e)
            dur = (time.perf_counter() - t0) * 1000.0
            records.append(RequestRecord("questions", path, status, dur, t0, err))

            if mode == "standard":
                await asyncio.sleep(random.uniform(0.02, 0.05))
    finally:
        await client.close()


def find_server_pid(port: int = 8000) -> int | None:
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], text=True
        ).strip()
        if out:
            pids = [int(p) for p in out.splitlines()]
            return pids[0]
    except Exception:
        pass
    return None


async def run_benchmark_suite(
    base_url: str = "http://127.0.0.1:8000",
    num_analysts: int = 50,
    wave_id: int = 415,
):
    server_pid = find_server_pid(8000)
    print("=" * 80)
    print("  FASTAPI STRESS BENCHMARK: 50 CONCURRENT ANALYSTS GENERATING 10-BANNER CROSS-TABS")
    print("=" * 80)
    print(f"Target Server URL:  {base_url}")
    print(f"Detected Server PID: {server_pid} (process: {psutil.Process(server_pid).name() if server_pid else 'N/A'})")
    print(f"Concurrent Analysts: {num_analysts}")
    print(f"Primary Wave ID:     {wave_id}")
    print(f"Banner Cut Sets:     {len(BANNERS)} pairs: {', '.join(f'{a}x{b}' for a, b in BANNERS[:4])} ...")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 1: OPERATING LOAD BENCHMARK (50 Concurrent Analysts, Realistic Pacing)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[PHASE 1] Executing Operating Load: {num_analysts} Concurrent Analysts (Realistic Pacing)...")
    monitor_1 = ServerMonitor(base_url, server_pid)
    monitor_task_1 = asyncio.create_task(monitor_1.run())

    await asyncio.sleep(0.5)
    baseline_mem_1 = monitor_1.memory_samples[-1].rss_mb if monitor_1.memory_samples else 0.0

    records_1: list[RequestRecord] = []
    t_start_1 = time.perf_counter()

    analyst_tasks_1 = [
        simulate_analyst(i, base_url, wave_id, records_1, mode="standard", iterations=1)
        for i in range(num_analysts)
    ]
    await asyncio.gather(*analyst_tasks_1)
    t_elapsed_1 = time.perf_counter() - t_start_1

    await asyncio.sleep(0.5)
    monitor_1.stop()
    await monitor_task_1

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 2: HIGH-CONCURRENCY BURST (All 50 Analysts Fire Simultaneously, Zero Pacing)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[PHASE 2] Executing Burst Stress: 50 Concurrent Analysts Firing Simultaneously...")
    monitor_2 = ServerMonitor(base_url, server_pid)
    monitor_task_2 = asyncio.create_task(monitor_2.run())

    await asyncio.sleep(0.5)
    baseline_mem_2 = monitor_2.memory_samples[-1].rss_mb if monitor_2.memory_samples else 0.0

    records_2: list[RequestRecord] = []
    t_start_2 = time.perf_counter()

    burst_tasks = [
        simulate_analyst(i, base_url, wave_id, records_2, mode="burst", iterations=1)
        for i in range(num_analysts)
    ]
    await asyncio.gather(*burst_tasks)
    t_elapsed_2 = time.perf_counter() - t_start_2

    await asyncio.sleep(0.5)
    monitor_2.stop()
    await monitor_task_2

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE 3: MULTI-WAVE DEEP CROSS-TAB STRESS (50 Analysts hitting waves 415, 412, 266, 235, 265)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[PHASE 3] Executing Multi-Wave Deep Stress: 50 Analysts crossing 5 distinct waves...")
    monitor_3 = ServerMonitor(base_url, server_pid)
    monitor_task_3 = asyncio.create_task(monitor_3.run())

    await asyncio.sleep(0.5)
    baseline_mem_3 = monitor_3.memory_samples[-1].rss_mb if monitor_3.memory_samples else 0.0

    records_3: list[RequestRecord] = []
    t_start_3 = time.perf_counter()

    waves_pool = [415, 412, 266, 235, 265]
    multi_wave_tasks = [
        simulate_analyst(i, base_url, waves_pool[i % len(waves_pool)], records_3, mode="burst", iterations=1)
        for i in range(num_analysts)
    ]
    await asyncio.gather(*multi_wave_tasks)
    t_elapsed_3 = time.perf_counter() - t_start_3

    await asyncio.sleep(0.5)
    monitor_3.stop()
    await monitor_task_3

    # Process and summarize results
    return {
        "phase1": analyze_run(
            "Phase 1: Operating Analyst Load (Realistic Pacing)",
            records_1,
            monitor_1,
            t_elapsed_1,
            num_analysts,
            baseline_mem_1,
        ),
        "phase2": analyze_run(
            "Phase 2: High-Concurrency Burst (Simultaneous Firing)",
            records_2,
            monitor_2,
            t_elapsed_2,
            num_analysts,
            baseline_mem_2,
        ),
        "phase3": analyze_run(
            "Phase 3: Multi-Wave Deep Cross-Tab Stress",
            records_3,
            monitor_3,
            t_elapsed_3,
            num_analysts,
            baseline_mem_3,
        ),
    }


def analyze_run(
    title: str,
    records: list[RequestRecord],
    monitor: ServerMonitor,
    elapsed_sec: float,
    num_analysts: int,
    baseline_rss: float,
) -> dict:
    total_reqs = len(records)
    rps = total_reqs / elapsed_sec if elapsed_sec > 0 else 0

    # Group by endpoint
    by_endpoint: dict[str, list[RequestRecord]] = defaultdict(list)
    for r in records:
        by_endpoint[r.endpoint_type].append(r)

    endpoint_stats = {}
    for ep, recs in by_endpoint.items():
        lats = [r.duration_ms for r in recs if r.status in (200, 304)]
        pcts = calculate_percentiles(lats)
        status_counts = defaultdict(int)
        for r in recs:
            status_counts[r.status] += 1
        endpoint_stats[ep] = {
            "count": len(recs),
            "percentiles": pcts,
            "status_counts": dict(status_counts),
        }

    all_lats = [r.duration_ms for r in records if r.status in (200, 304)]
    overall_pcts = calculate_percentiles(all_lats)

    status_dist = defaultdict(int)
    for r in records:
        status_dist[r.status] += 1

    # Memory Analysis
    mem_rss = [m.rss_mb for m in monitor.memory_samples] if monitor.memory_samples else [baseline_rss]
    peak_rss = max(mem_rss) if mem_rss else baseline_rss
    post_rss = mem_rss[-1] if mem_rss else baseline_rss
    delta_rss = peak_rss - baseline_rss
    spike_pct = (delta_rss / baseline_rss * 100.0) if baseline_rss > 0 else 0.0

    # Pool Analysis
    pool_actives = [p.active for p in monitor.pool_samples] if monitor.pool_samples else [0]
    pool_checkedouts = [p.checkedout for p in monitor.pool_samples] if monitor.pool_samples else [0]
    pool_overflows = [max(0, p.overflow) for p in monitor.pool_samples] if monitor.pool_samples else [0]
    pool_sizes = [p.size for p in monitor.pool_samples] if monitor.pool_samples else [10]

    peak_active = max(pool_actives) if pool_actives else 0
    peak_checkedout = max(pool_checkedouts) if pool_checkedouts else 0
    peak_overflow = max(pool_overflows) if pool_overflows else 0
    pool_size = pool_sizes[-1] if pool_sizes else 10
    total_pool_capacity = pool_size + 20  # configured max_overflow=20 -> 30 capacity
    pool_saturation_pct = (peak_active / total_pool_capacity * 100.0) if total_pool_capacity > 0 else 0.0

    count_503 = status_dist.get(503, 0)
    count_500 = status_dist.get(500, 0)
    count_200 = status_dist.get(200, 0)
    count_304 = status_dist.get(304, 0)

    print("\n" + "=" * 80)
    print(f"  RESULTS: {title.upper()}")
    print("=" * 80)
    print(f"Total Requests:     {total_reqs:,} in {elapsed_sec:.2f}s ({rps:,.1f} req/s)")
    print(f"Status Breakdown:   200 OK: {count_200:,} | 304 Not Mod: {count_304:,} | 503 Busy: {count_503:,} | 500 Err: {count_500:,}")
    print("-" * 80)
    print(f"{'Endpoint':<20} {'Count':>7} {'Min(ms)':>8} {'P50(ms)':>8} {'P95(ms)':>8} {'P99(ms)':>8} {'Max(ms)':>8}")
    print("-" * 80)
    for ep in ["crosstab", "search", "questions"]:
        if ep in endpoint_stats:
            p = endpoint_stats[ep]["percentiles"]
            c = endpoint_stats[ep]["count"]
            print(f"{ep:<20} {c:>7} {p['min']:>8.1f} {p['p50']:>8.1f} {p['p95']:>8.1f} {p['p99']:>8.1f} {p['max']:>8.1f}")
    print("-" * 80)
    print(f"{'OVERALL':<20} {total_reqs:>7} {overall_pcts['min']:>8.1f} {overall_pcts['p50']:>8.1f} {overall_pcts['p95']:>8.1f} {overall_pcts['p99']:>8.1f} {overall_pcts['max']:>8.1f}")
    print("=" * 80)
    print("  MEMORY & PROCESS HEALTH")
    print(f"  Baseline RSS:     {baseline_rss:8.2f} MB")
    print(f"  Peak RSS:         {peak_rss:8.2f} MB")
    print(f"  Memory Delta:     {delta_rss:8.2f} MB (+{spike_pct:.1f}%)")
    print(f"  Post-Test RSS:    {post_rss:8.2f} MB")
    print("-" * 80)
    print("  DATABASE CONNECTION POOL & ADMISSION CONTROL")
    print(f"  SQLAlchemy Pool Config:  Size={pool_size}, Max Overflow=20 (Max Capacity={total_pool_capacity})")
    print(f"  Peak Checked Out:        {peak_checkedout} connections")
    print(f"  Peak Overflow:           {peak_overflow} connections")
    print(f"  Peak Active in Pool:     {peak_active} / {total_pool_capacity} connections ({pool_saturation_pct:.1f}% saturation)")
    print(f"  Hard Pool Exhaustion:    {'YES - POOL EXHAUSTED' if peak_active >= total_pool_capacity else 'NO - WITHIN LIMITS'}")
    print(f"  FastAPI 503 Admission:   {count_503} requests shed by BUILD_WAIT queueing ({count_503 / total_reqs * 100:.1f}%)")
    print("=" * 80)

    return {
        "title": title,
        "elapsed_sec": elapsed_sec,
        "total_requests": total_reqs,
        "rps": rps,
        "overall_percentiles": overall_pcts,
        "endpoint_stats": endpoint_stats,
        "status_distribution": dict(status_dist),
        "memory": {
            "baseline_rss_mb": baseline_rss,
            "peak_rss_mb": peak_rss,
            "delta_rss_mb": delta_rss,
            "spike_percent": spike_pct,
            "post_rss_mb": post_rss,
        },
        "database_pool": {
            "pool_size": pool_size,
            "max_overflow": 20,
            "total_capacity": total_pool_capacity,
            "peak_checkedout": peak_checkedout,
            "peak_overflow": peak_overflow,
            "peak_active": peak_active,
            "saturation_percent": pool_saturation_pct,
            "hard_pool_exhaustion": (peak_active >= total_pool_capacity),
            "fastapi_503_count": count_503,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Stress test FastAPI endpoints with 50 concurrent analysts")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--analysts", type=int, default=50)
    parser.add_argument("--wave", type=int, default=415)
    parser.add_argument("--out", default="scripts/stress_benchmark_results.json")
    args = parser.parse_args()

    results = asyncio.run(run_benchmark_suite(args.base, args.analysts, args.wave))

    out_path = Path(args.out)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nFull raw benchmark output saved to: {out_path.resolve()}\n")


if __name__ == "__main__":
    main()
