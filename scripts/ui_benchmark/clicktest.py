"""Click every control on every screen of the portal, for several surveys, and check the data is really there.

For each wave and screen: open it, wait until it is fully drawn (no spinner), check its data is present (charts
drawn, tables filled, numbers shown), then click every segmented button, change every select (first options),
toggle every checkbox, open the first questions in the list, go back in browser history, and check again after
each step. Records console errors, failed requests (HTTP ≥ 400) and the time each step took to settle. Then checks
the layout at four widths (no sideways scrolling) and the theme toggle.

Headless Chrome with DevTools on :9333 (scripts/ui_benchmark/shots.py notes). Read-only: it never submits data.

    python scripts/ui_benchmark/clicktest.py http://127.0.0.1:8080 --waves 412,415,261,259
"""
import argparse, asyncio, json, time, urllib.request
from tornado.websocket import websocket_connect

CDP = "http://127.0.0.1:9333"
SETTLED = "!document.querySelector('.spinner')"
SCREENS = {   # path, the check that its data is on screen
    "overview": ("", "document.querySelector('h1')?.textContent.length > 5 && (document.querySelectorAll('canvas').length > 0 || /no figure is shown under 30/.test(document.body.innerText))"),
    "questions": ("/questions", "document.querySelector('.qtext')?.textContent.length > 5 && (document.querySelectorAll('canvas').length > 0 || document.querySelectorAll('table.data td').length > 0 || /under 30|n<30/.test(document.body.innerText))"),
    "crosstab": ("/crosstab", "document.querySelectorAll('table.data td').length > 0"),
    "trends": ("/trends", "document.querySelectorAll('canvas').length > 0 || /only one wave|Pick at least one answer|No respondents in|fielded once/.test(document.body.innerText)"),
    "changes": ("/changes", "document.querySelector('h1')?.textContent.length > 5 && (document.querySelectorAll('table.data').length > 0 || /No changes match these filters/.test(document.body.innerText))"),
    "survey": ("/survey", "document.querySelectorAll('.option, table.data button').length > 0"),
    "compare": ("/compare", "document.querySelectorAll('table.compare td').length > 0 || /nothing to compare/.test(document.body.innerText)"),
}
NO_ERROR = "!document.querySelector('.state.error')"


class Page:
    def __init__(self, ws):
        self.ws, self.seq, self.errors, self.failed = ws, 0, [], []

    async def call(self, method, params=None):
        self.seq += 1
        me = self.seq
        await self.ws.write_message(json.dumps({"id": me, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.read_message())
            if msg.get("method") == "Runtime.exceptionThrown":
                self.errors.append(msg["params"]["exceptionDetails"].get("exception", {}).get("description", "exception")[:160])
            elif msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] == "error":
                self.errors.append(" ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"])[:160])
            elif msg.get("method") == "Network.responseReceived" and msg["params"]["response"]["status"] >= 400:
                r = msg["params"]["response"]
                self.failed.append(f'{r["status"]} {r["url"].split("?")[0][-80:]}')
            if msg.get("id") == me:
                return msg.get("result", {})

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    async def settle(self, check, limit=30):
        start = time.perf_counter()
        while time.perf_counter() - start < limit:
            if await self.js(f"!!({SETTLED} && ({check}))"):
                await asyncio.sleep(0.15)
                return time.perf_counter() - start
            await asyncio.sleep(0.05)
        return float("nan")


async def exercise(page, check):
    """Every control on the screen, one at a time; returns (actions, failures, slowest seconds)."""
    actions, failures, slowest = 0, [], 0.0
    plan = await page.js("""(() => {
      const label = el => (el.getAttribute('aria-label') || el.textContent || el.name || '').trim().slice(0, 40);
      const segs = [...document.querySelectorAll('main .seg button')].map((b, i) => ['seg', i, label(b)]);
      const selects = [...document.querySelectorAll('main select')].map((s, i) => ['select', i, label(s.closest('label') || s) + ':' + s.options.length]);
      const checks = [...document.querySelectorAll('main input[type=checkbox]')].slice(0, 8).map((c, i) => ['check', i, label(c.parentElement)]);
      const qnav = [...document.querySelectorAll('.qnav-list button')].slice(1, 4).map((b, i) => ['qnav', i + 1, label(b)]);
      const options = [...document.querySelectorAll('main .option')].slice(0, 2).map((b, i) => ['option', i, label(b)]);
      const heads = [...document.querySelectorAll('main table.xt thead th button')].slice(1, 3).map((b, i) => ['head', i + 1, label(b)]);
      return [...segs, ...selects, ...checks, ...qnav, ...options, ...heads];
    })()""") or []
    for kind, i, name in plan:
        act = {
            "seg": f"document.querySelectorAll('main .seg button')[{i}]?.click()",
            "select": f"(s => {{ if (!s || s.options.length < 2) return; s.selectedIndex = (s.selectedIndex + 1) % s.options.length; s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(document.querySelectorAll('main select')[{i}])",
            "check": f"document.querySelectorAll('main input[type=checkbox]')[{i}]?.click()",
            "qnav": f"document.querySelectorAll('.qnav-list button')[{i}]?.click()",
            "option": f"document.querySelectorAll('main .option')[{i}]?.click()",
            "head": f"document.querySelectorAll('main table.xt thead th button')[{i}]?.click()",
        }[kind]
        await page.js(act)
        took = await page.settle(f"({check}) && {NO_ERROR}", 20)
        actions += 1
        if took != took:   # NaN: never settled with data and no error
            failures.append(f"{kind} '{name}' → no data / error")
        else:
            slowest = max(slowest, took)
    return actions, failures, slowest


async def main(a):
    target = json.load(urllib.request.urlopen(urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")))
    ws = await websocket_connect(target["webSocketDebuggerUrl"], max_message_size=2**27)
    page = Page(ws)
    for domain in ("Runtime", "Network", "Page"):
        await page.call(f"{domain}.enable")
    await page.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    await page.call("Page.navigate", {"url": f"{a.base}/auth/dev-login?next=/"})
    await asyncio.sleep(2)
    rows, total_actions, all_failures = [], 0, []
    for wave in [int(x) for x in a.waves.split(",")]:
        for name, (path, check) in SCREENS.items():
            start = time.perf_counter()
            await page.call("Page.navigate", {"url": f"{a.base}/w/{wave}{path}"})
            loaded = await page.settle(f"({check}) && {NO_ERROR}", 45)
            first = time.perf_counter() - start
            actions, failures, slowest = await exercise(page, check) if loaded == loaded else (0, ["screen never showed its data"], 0)
            await page.js("history.back()")
            back = await page.settle(f"{NO_ERROR}", 20)
            ok = loaded == loaded and not failures and back == back
            rows.append((wave, name, f"{first:.2f}", actions, f"{slowest:.2f}", "pass" if ok else "FAIL: " + "; ".join(failures)[:120]))
            total_actions += actions
            all_failures += [f"w{wave} {name}: {f}" for f in failures]
            print(f"{wave:>4} {name:<10} loaded {first:5.2f} s · {actions:>3} actions · slowest {slowest:4.2f} s · {'pass' if ok else 'FAIL ' + '; '.join(failures)[:120]}", flush=True)
    # layout at four widths: nothing may scroll sideways
    layout = []
    for width in (1440, 1024, 768, 390):
        await page.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 700})
        for path in (f"/w/{a.waves.split(',')[0]}", f"/w/{a.waves.split(',')[0]}/crosstab", "/"):
            await page.call("Page.navigate", {"url": a.base + path})
            await page.settle("document.querySelector('main')?.children.length > 0", 20)
            over = await page.js("document.documentElement.scrollWidth - innerWidth")
            layout.append((width, path, over))
            print(f"layout {width:>4}px {path:<22} sideways overflow {over} px {'pass' if over <= 1 else 'FAIL'}", flush=True)
    # theme toggle round trip
    await page.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    await page.call("Page.navigate", {"url": f"{a.base}/w/{a.waves.split(',')[0]}"})
    await page.settle(SCREENS["overview"][1], 30)
    themes = []
    for _ in range(2):
        await page.js("document.querySelector('.theme-btn').click()")
        await page.settle(SCREENS["overview"][1], 20)
        themes.append(await page.js("document.documentElement.dataset.theme"))
    print(f"theme toggle: {' → '.join(themes)} {'pass' if len(set(themes)) == 2 else 'FAIL'}")
    print(f"\nTOTAL: {len(rows)} screen visits, {total_actions} clicks/changes, {sum(1 for r in rows if r[5] == 'pass')} passed, "
          f"{len(all_failures)} failures, {len(page.errors)} console errors, {len(page.failed)} failed requests")
    for e in sorted(set(page.errors))[:20]:
        print("console:", e)
    for f in sorted(set(page.failed))[:20]:
        print("request:", f)
    urllib.request.urlopen(f"{CDP}/json/close/{target['id']}").read()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("--waves", default="412,415")
    asyncio.run(main(p.parse_args()))
