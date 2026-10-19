"""Open N concurrent Chrome tabs on a Streamlit page; time until content renders; report footprint."""
import json, subprocess, sys, time, urllib.request
from tornado import ioloop, gen
from tornado.websocket import websocket_connect

CDP = "http://127.0.0.1:9333"
URL, MARKER, ST_PID = sys.argv[1], sys.argv[2], sys.argv[3]
STEPS = [int(x) for x in sys.argv[4].split(",")]


def new_tab():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    return json.load(urllib.request.urlopen(req))["webSocketDebuggerUrl"]


async def time_load(ws_url):
    ws = await websocket_connect(ws_url, max_message_size=50 * 2**20)
    msg_id = 0

    async def call(method, params=None):
        nonlocal msg_id
        msg_id += 1
        await ws.write_message(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(await ws.read_message())
            if reply.get("id") == msg_id:
                return reply

    start = time.perf_counter()
    await call("Page.navigate", {"url": URL})
    while time.perf_counter() - start < 120:
        r = await call("Runtime.evaluate", {"expression": "document.body ? document.body.innerText : ''"})
        if MARKER in r["result"]["result"].get("value", ""):
            return time.perf_counter() - start
        await gen.sleep(0.1)
    return float("nan")


def footprint():
    """macOS phys_footprint (now / peak) of the server process plus its workers, in MB.
    RSS is not used: macOS compresses idle pages, so RSS swings and under-reports."""
    pids, todo = [], [ST_PID]
    while todo:
        pid = todo.pop()
        pids.append(pid)
        todo += subprocess.run(["pgrep", "-P", pid], capture_output=True, text=True).stdout.split()
    args = [a for p in pids for a in ("-p", p)]
    out = subprocess.run(["footprint", "-f", "bytes", *args], capture_output=True, text=True).stdout
    total = lambda key: sum(int(l.split(":")[1].split()[0]) for l in out.splitlines() if l.strip().startswith(key + ":")) / 2**20
    return f"{total('phys_footprint'):.0f} MB (peak {total('phys_footprint_peak'):.0f} MB, {len(pids)} procs)"


async def main():
    print(f"idle footprint: {footprint()}")
    total = 0
    for n in STEPS:
        urls = [new_tab() for _ in range(n)]
        times = sorted(await gen.multi([time_load(u) for u in urls]))
        total += n
        await gen.sleep(5)
        print(f"+{n} concurrent loads (open sessions={total}): p50={times[len(times)//2]:.2f}s "
              f"max={times[-1]:.2f}s  footprint={footprint()}")

ioloop.IOLoop.current().run_sync(main)
