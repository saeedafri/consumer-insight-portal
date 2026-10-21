"""Full-size screenshots of the running portal through headless Chrome (DevTools on :9333), signed in with the
local dev login. Saves PNGs and prints, per page, how long until it was fully drawn and the page's JavaScript
heap (what the dashboard costs the browser in memory).

    python scripts/ui_benchmark/shots.py http://127.0.0.1:8000 out_dir /path1 /path2 ...  [--ready JS]
"""
import argparse, asyncio, base64, json, time, urllib.parse, urllib.request
from pathlib import Path
from tornado.websocket import websocket_connect

CDP = "http://127.0.0.1:9333"
READY = ("document.querySelector('main') && !document.querySelector('.spinner') && "
         "[...document.querySelectorAll('canvas')].length >= (document.querySelectorAll('[role=img]').length)")


async def main(a):
    target = json.load(urllib.request.urlopen(urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")))
    ws = await websocket_connect(target["webSocketDebuggerUrl"], max_message_size=2**27)
    seq = 0

    async def call(method, params=None):
        nonlocal seq
        seq += 1
        await ws.write_message(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(await ws.read_message())
            if reply.get("id") == seq:
                return reply.get("result", {})

    await call("Performance.enable")
    await call("Emulation.setDeviceMetricsOverride", {"width": a.width, "height": a.height, "deviceScaleFactor": 1, "mobile": a.width < 700})
    await call("Page.navigate", {"url": f"{a.base}/auth/dev-login?next=/"})
    await asyncio.sleep(2)
    await call("Runtime.evaluate", {"expression": f"localStorage.setItem('cip-theme', '{a.theme}')"})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for path in a.paths:
        start = time.perf_counter()
        await call("Page.navigate", {"url": a.base + path})
        ready = float("nan")
        while time.perf_counter() - start < 60:
            r = await call("Runtime.evaluate", {"expression": f"!!({a.ready})", "returnByValue": True})
            if r.get("result", {}).get("value") is True:
                ready = time.perf_counter() - start
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.6)   # let chart animations finish before the picture
        shot = await call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": a.full, "fromSurface": True})
        name = urllib.parse.quote(path.strip("/").replace("/", "_") or "library", safe="")[:80] + ".png"
        (out / name).write_bytes(base64.b64decode(shot["data"]))
        metrics = {m["name"]: m["value"] for m in (await call("Performance.getMetrics"))["metrics"]}
        print(f"{path:<50} drawn in {ready:5.2f} s · JS heap {metrics['JSHeapUsedSize'] / 2**20:5.1f} MB · DOM nodes {int(metrics['Nodes']):>5}  → {name}", flush=True)
    urllib.request.urlopen(f"{CDP}/json/close/{target['id']}").read()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("out")
    p.add_argument("paths", nargs="+")
    p.add_argument("--ready", default=READY)
    p.add_argument("--width", type=int, default=1440)
    p.add_argument("--height", type=int, default=900)
    p.add_argument("--full", action="store_true", help="capture the whole page, not just the viewport")
    p.add_argument("--theme", default="light", choices=["light", "dark"])
    asyncio.run(main(p.parse_args()))
