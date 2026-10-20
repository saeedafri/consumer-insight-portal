"""Every stack on the same 1-core Debian box: each server runs in a container pinned to ONE CPU with a RAM
cap (staging 4.5 GB, production 9 GB). The load generator (wrk) runs in its own container on other CPUs,
so it never takes the server's core. Reports memory (idle, peak under load), requests/s and latency
(p50/p90/p99) at 10 and 100 concurrent connections, then optionally the browser journey (journey.py).

    docker build -f stacks/Dockerfile --target py|node|load -t bench-py|bench-node|bench-load .   (in scripts/ui_benchmark)
    python scripts/ui_benchmark/bench_docker.py --db /path/stores.db --memory 4.5g [--journeys] [--only fastapi-vite,...]
"""
import argparse, json, re, subprocess, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUNICORN = ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8000"]
STREAMLIT = ["streamlit", "run", "--server.port", "8000", "--server.address", "0.0.0.0", "--server.headless", "true",
             "--browser.gatherUsageStats", "false"]
DASH_BODY = json.dumps({"output": "..open.children...chart.figure...table.data..",
                        "outputs": [{"id": "open", "property": "children"}, {"id": "chart", "property": "figure"},
                                    {"id": "table", "property": "data"}],
                        "inputs": [{"id": "sector", "property": "value", "value": "Beauty"}],
                        "changedPropIds": ["sector.value"]})
SPA = "document.getElementById('open')?.textContent==='Stores open EXPECT' && document.querySelector('#chart canvas') && document.querySelectorAll('#table tr').length>=50"
ST = ("(document.querySelector('[data-testid=stMetricValue]')||{}).innerText==='EXPECT' && !document.querySelector('[data-stale=true]')"
      " && document.querySelector('[data-testid=stVegaLiteChart] svg.marks') && document.querySelector('[data-testid=stDataFrame]')")
DASH = ("document.getElementById('open') && document.getElementById('open').innerText==='Stores open EXPECT'"
        " && document.querySelectorAll('#chart .main-svg').length && document.querySelectorAll('#table td').length>=150"
        " && !document.querySelector('[data-dash-is-loading=true]')")

# name: image, command, environment, page path, API path (GET), "dash" (POST callback) or "rsc" (Next.js click), journey
STACKS = {
    "fastapi-vite": ("bench-py", GUNICORN + ["api_page:app"], {"STATIC_DIR": "/static/vite"}, "/app/", "/api/summary/Apparel",
                     {"ready": SPA, "action": "native"}),
    "node-vite": ("bench-node", ["node", "node_page.mjs"], {"STATIC_DIR": "/static/vite"}, "/app/", "/api/summary/Apparel",
                  {"ready": SPA, "action": "native"}),
    "next-ssr": ("bench-node", ["node", "/ssr/server.js"], {"HOSTNAME": "0.0.0.0"}, "/app?sector=Apparel", "rsc",
                 {"ready": SPA, "action": "native"}),
    "next-static": ("bench-py", GUNICORN + ["api_page:app"], {"STATIC_DIR": "/static/next"}, "/app/", "/api/summary/Apparel",
                    {"ready": SPA, "action": "native"}),
    "dash": ("bench-py", ["gunicorn", "dash_page:server", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8000"], {}, "/", "dash",
             {"ready": DASH, "action": "popover", "input": "#sector"}),
    "streamlit": ("bench-py", STREAMLIT + ["streamlit_sql.py", "--", "/data/stores.db"], {}, "/", None,
                  {"ready": ST, "action": "typeahead", "input": "[data-testid=stSelectbox] input"}),
    "streamlit-naive": ("bench-py", STREAMLIT + ["streamlit_naive.py", "--", "/data/stores.db"], {}, "/", None,
                        {"ready": ST, "action": "typeahead", "input": "[data-testid=stSelectbox] input"}),
}
PORT = 8700


def sh(*args, check=True):
    return subprocess.run(args, capture_output=True, text=True, check=check).stdout


def mib(text):
    m = re.search(r"([\d.]+)\s*(KiB|MiB|GiB|B)\b", text)
    return float(m.group(1)) * {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[m.group(2)] if m else None


class Memory:
    """Samples the container's memory about once a second (docker stats stream) and keeps the peak."""
    def __init__(self, name):
        self.peak, self.last = 0.0, 0.0
        self.proc = subprocess.Popen(["docker", "stats", "--format", "{{.MemUsage}}", name], stdout=subprocess.PIPE, text=True)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.proc.stdout:
            value = mib(line)
            if value is not None:
                self.last, self.peak = value, max(self.peak, value)

    def stop(self):
        self.proc.kill()


def wrk(url, connections, seconds, script=None, header=None):
    args = ["docker", "run", "--rm", "--network", "bench", "--cpuset-cpus", "2-5", "--name", "bench-load-run"]
    if script:
        args += ["-v", f"{script}:/post.lua:ro"]
    args += ["bench-load", "wrk", "-t4", f"-c{connections}", f"-d{seconds}s", "--latency", "--timeout", "10s"]
    args += ["-H", header] if header else []
    out = sh(*args + (["-s", "/post.lua"] if script else []) + [url])
    rps = float(re.search(r"Requests/sec:\s+([\d.]+)", out).group(1))
    lat = dict(re.findall(r"^\s+(50|90|99)%\s+(\S+)", out, re.M))
    errors = re.search(r"(Non-2xx.*|Socket errors.*)", out)
    to_ms = lambda v: float(v[:-2]) if v.endswith("ms") else float(v[:-2]) / 1000 if v.endswith("us") else float(v[:-1]) * 1000
    return rps, {k: to_ms(v) for k, v in lat.items()}, errors.group(1) if errors else ""


def wait_ready(url, limit=120):
    start = time.time()
    while time.time() - start < limit:
        try:
            if urllib.request.urlopen(url, timeout=5).status == 200:
                return time.time() - start
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"{url} never answered")


def run(name, a, out):
    image, command, env, page, api, journey = STACKS[name]
    container = f"bench-{name}"
    sh("docker", "rm", "-f", container, check=False)
    args = ["docker", "run", "-d", "--name", container, "--network", "bench", "--cpuset-cpus", "0", "--cpus", "1",
            "--memory", a.memory, "--memory-swap", a.memory, "-p", f"{PORT}:8000", "-v", f"{a.db}:/data/stores.db:ro",
            "-e", "NAIVE_DB=/data/stores.db", "-e", "PORT=8000"]
    for k, v in env.items():
        args += ["-e", f"{k}={v}"]
    sh(*args, image, *command)
    try:
        boot = wait_ready(f"http://127.0.0.1:{PORT}{page}")
        time.sleep(3)
        idle = mib(sh("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container))
        say(out, f"== {name}  memory cap {a.memory}, 1 CPU  | up in {boot:.1f} s | idle {idle:.0f} MB")
        memory = Memory(container)
        targets = [("page", f"http://{container}:8000{page}", None, None)]
        if api == "dash":
            script = Path(a.scratch) / "dash_post.lua"
            script.write_text(f"wrk.method = 'POST'\nwrk.headers['Content-Type'] = 'application/json'\nwrk.body = {json.dumps(DASH_BODY)}\n")
            targets.append(("callback", f"http://{container}:8000/_dash-update-component", str(script), None))
        elif api == "rsc":   # what a sector change asks the Next.js server for: the re-rendered page as RSC
            targets.append(("click", f"http://{container}:8000/app?sector=Beauty&_rsc", None, "RSC: 1"))
        elif api:
            targets.append(("api", f"http://{container}:8000{api}", None, None))
        if name.startswith("streamlit"):
            say(out, "   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it")
        for label, url, script, header in targets:
            wrk(url, 10, 5, script, header)   # warm-up
            for c in (10, 100):
                rps, lat, errors = wrk(url, c, a.seconds, script, header)
                say(out, f"   {label:<8} c={c:<3} {rps:>9,.0f} req/s  p50={lat.get('50', 0):7.2f} ms  p90={lat.get('90', 0):7.2f} ms"
                         f"  p99={lat.get('99', 0):7.2f} ms  mem now {memory.last:.0f} MB  {errors}")
        say(out, f"   peak memory under load: {memory.peak:.0f} MB")
        memory.stop()
        if a.journeys:
            env_ready = {k: v for k, v in journey.items() if k != "ready"}
            cmd = [a.python, "-u", str(HERE / "journey.py"), "--url", f"http://127.0.0.1:{PORT}{page}", "--pid", f"docker:{container}",
                   "--ready", journey["ready"].replace("EXPECT", "93,477"), "--after", journey["ready"].replace("EXPECT", "93,832"),
                   "--steps", "1," + a.steps] + [x for k, v in env_ready.items() for x in (f"--{k}", v)]
            say(out, "   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            for line in (result.stdout + result.stderr).strip().splitlines():
                say(out, "   " + line)
        if not sh("docker", "inspect", "-f", "{{.State.Running}}", container).strip() == "true":
            say(out, f"   CONTAINER DIED: OOMKilled={sh('docker', 'inspect', '-f', '{{.State.OOMKilled}}', container).strip()}")
    finally:
        sh("docker", "rm", "-f", container, check=False)


def say(out, line):
    print(line, flush=True)
    with open(out, "a") as f:
        f.write(line + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--memory", default="4.5g")
    p.add_argument("--seconds", type=int, default=20)
    p.add_argument("--journeys", action="store_true")
    p.add_argument("--steps", default="1,5,10,20,40")
    p.add_argument("--only", default=",".join(STACKS))
    p.add_argument("--out", default="bench-docker.txt")
    p.add_argument("--scratch", default="/tmp")
    p.add_argument("--python", default=str(HERE.parents[1] / ".venv/bin/python"))
    a = p.parse_args()
    sh("docker", "network", "create", "bench", check=False)
    say(a.out, f"#### {time.strftime('%Y-%m-%d %H:%M')}  Debian 13 containers, server on 1 CPU, --memory {a.memory}")
    for name in a.only.split(","):
        try:
            run(name, a, a.out)
        except Exception as exc:
            say(a.out, f"== {name} FAILED: {exc}")


if __name__ == "__main__":
    main()
