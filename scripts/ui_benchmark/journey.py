"""Matched-journey benchmark: N fresh browser tabs open the page at the same moment (load-to-ready),
then all N change the sector at the same moment (click-to-result). "Ready" is a JavaScript condition
that must hold the chart, the table and the expected metric, not just a text marker.

Each step closes the previous step's tabs, so open sessions = N. Polls every 20 ms.

python journey.py --url URL --pid SERVER_PID --ready JS --after JS --action native|typeahead
                  [--input CSS] [--value Beauty] [--steps 1,5,10,20,40]
"""
import argparse, json, statistics, subprocess, time, urllib.request
from tornado import gen, ioloop
from tornado.websocket import websocket_connect

CDP = "http://127.0.0.1:9333"


def cdp_json(path, method="GET"):
    return json.load(urllib.request.urlopen(urllib.request.Request(f"{CDP}{path}", method=method)))


def footprint(pid):
    """macOS phys_footprint of the server and its workers, in MB; "docker:NAME" = the container's memory."""
    if pid.startswith("docker:"):
        return docker_memory(pid[7:])
    pids, todo = [], [pid]
    while todo:
        p = todo.pop()
        pids.append(p)
        todo += subprocess.run(["pgrep", "-P", p], capture_output=True, text=True).stdout.split()
    out = subprocess.run(["footprint", "-f", "bytes", *[a for p in pids for a in ("-p", p)]], capture_output=True, text=True).stdout
    return sum(int(l.split(":")[1].split()[0]) for l in out.splitlines() if l.strip().startswith("phys_footprint:")) / 2**20


def docker_memory(name):
    """docker stats memory (cgroup usage minus inactive file cache), in MB."""
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name], capture_output=True, text=True).stdout
    value = out.split("/")[0].strip()
    number, unit = float(value[:-3]), value[-3:]
    return number * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[unit]


class Tab:
    def __init__(self, target):
        self.target, self.msg_id = target, 0

    async def open(self):
        self.ws = await websocket_connect(self.target["webSocketDebuggerUrl"], max_message_size=50 * 2**20)

    async def call(self, method, params=None):
        self.msg_id += 1
        await self.ws.write_message(json.dumps({"id": self.msg_id, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(await self.ws.read_message())
            if reply.get("id") == self.msg_id:
                return reply

    async def holds(self, expr):
        r = await self.call("Runtime.evaluate", {"expression": f"!!({expr})", "returnByValue": True})
        return r.get("result", {}).get("result", {}).get("value") is True

    async def wait_for(self, expr, start, limit=60):
        while time.perf_counter() - start < limit:
            if await self.holds(expr):
                return time.perf_counter() - start
            await gen.sleep(0.02)
        return float("nan")

    async def load(self, url, ready):
        start = time.perf_counter()
        await self.call("Page.navigate", {"url": url})
        return await self.wait_for(ready, start)

    async def change(self, a, after):
        start = time.perf_counter()
        if a.action == "native":
            await self.call("Runtime.evaluate", {"expression":
                f"(s => {{ s.value = {json.dumps(a.value)}; s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(document.querySelector({json.dumps(a.input)}))"})
        elif a.action == "popover":  # Dash 4 dropdown: real mouse click opens it, then pick the option
            r = await self.call("Runtime.evaluate", {"returnByValue": True, "expression":
                f"(b => {{ const r = b.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})(document.querySelector({json.dumps(a.input)}))"})
            x, y = r["result"]["result"]["value"]
            for kind in ("mousePressed", "mouseReleased"):
                await self.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1})
            pick = f"[...document.querySelectorAll('[role=option]')].find(o => o.innerText.trim() === {json.dumps(a.value)})"
            while not await self.holds(pick):
                await gen.sleep(0.01)
            await self.call("Runtime.evaluate", {"expression": f"{pick}.click()"})
        else:  # a typeahead dropdown (Streamlit selectbox): focus, type, Enter
            await self.call("Runtime.evaluate", {"expression": f"document.querySelector({json.dumps(a.input)}).focus()"})
            await self.call("Input.insertText", {"text": a.value})
            await gen.sleep(0.05)
            for kind in ("keyDown", "keyUp"):
                await self.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        return await self.wait_for(after, start)


def summary(values):
    v = sorted(x for x in values if x == x)
    if not v:
        return "all timed out"
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    return f"p50={statistics.median(v):.2f}s p95={p95:.2f}s max={v[-1]:.2f}s ok={len(v)}/{len(values)}"


async def new_windows(n):
    """One visible window per simulated user: background tabs get throttled timers and skip painting."""
    browser = Tab({"webSocketDebuggerUrl": cdp_json("/json/version")["webSocketDebuggerUrl"]})
    await browser.open()
    ids = [(await browser.call("Target.createTarget", {"url": "about:blank", "newWindow": True}))["result"]["targetId"] for _ in range(n)]
    browser.ws.close()
    return [{"id": i, "webSocketDebuggerUrl": f"ws://127.0.0.1:9333/devtools/page/{i}"} for i in ids]


async def main(a):
    print(f"idle footprint: {footprint(a.pid):.0f} MB", flush=True)
    for n in [int(x) for x in a.steps.split(",")]:
        targets = await new_windows(n)
        tabs = [Tab(t) for t in targets]
        await gen.multi([t.open() for t in tabs])
        loads = await gen.multi([t.load(a.url, a.ready) for t in tabs])
        await gen.sleep(2)
        clicks = await gen.multi([t.change(a, a.after) for t in tabs])
        print(f"{n:>3} users | load-to-ready {summary(loads)} | click-to-result {summary(clicks)} | server {footprint(a.pid):.0f} MB", flush=True)
        for t in targets:
            urllib.request.urlopen(f"{CDP}/json/close/{t['id']}").read()
        await gen.sleep(3)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("--url", "--pid", "--ready", "--after", "--action"):
        p.add_argument(name, required=True)
    p.add_argument("--input", default="input", help="the control: a <select> for native, the typeahead's input otherwise")
    p.add_argument("--value", default="Beauty")
    p.add_argument("--steps", default="1,5,10,20,40")
    args = p.parse_args()
    ioloop.IOLoop.current().run_sync(lambda: main(args))
