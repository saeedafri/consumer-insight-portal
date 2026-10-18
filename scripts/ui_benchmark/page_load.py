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
    out = subprocess.run(["footprint", "-p", ST_PID], capture_output=True, text=True).stdout
    return next((l.split("Footprint:")[1].split("(")[0].strip() for l in out.splitlines() if "Footprint:" in l), "?")


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
