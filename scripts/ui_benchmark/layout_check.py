"""Every screen at phone, tablet and laptop widths: report text that overlaps other text, text cut off without an
ellipsis, and anything wider than the screen. Exits 1 when it finds any.

Headless Chrome with DevTools on :9333, as clicktest.py. Read-only.

    python scripts/ui_benchmark/layout_check.py http://127.0.0.1:8000 --waves 412,235
"""
import argparse, asyncio, json, sys, urllib.request
from pathlib import Path
from tornado.websocket import websocket_connect

sys.path.insert(0, str(Path(__file__).parent))
from clicktest import CDP, NO_ERROR, SCREENS, Page   # noqa: E402

WIDTHS = {"phone": (360, 760, True), "phone-l": (414, 860, True), "tablet": (768, 1024, True), "laptop": (1280, 800, False)}
EXTRA = {"library": "/", "search": "/search?q=holiday", "schedule": "/schedule"}

AUDIT = r"""(() => {
  const W = document.documentElement.clientWidth, out = [];
  const name = el => (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : el.tagName.toLowerCase())
                     + ' "' + (el.textContent || '').trim().slice(0, 30) + '"';
  const scrolls = el => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p);
    if (/(auto|scroll)/.test(s.overflowX) && p.scrollWidth > p.clientWidth) return true; } return false; };
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('.sr-only, canvas, svg'); };
  if (document.documentElement.scrollWidth > W + 1) out.push(`page scrolls sideways: ${document.documentElement.scrollWidth}px in ${W}px`);
  const texts = [...document.querySelectorAll('main *, header *, nav *')].filter(el =>
    visible(el) && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()));
  for (const el of texts) {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    if (r.right > W + 1 && !scrolls(el)) out.push(`wider than screen (${Math.round(r.right)}px): ${name(el)}`);
    if (el.scrollWidth > el.clientWidth + 2 && s.overflow !== 'visible' && s.textOverflow !== 'ellipsis' && s.webkitLineClamp === 'none' && !scrolls(el)
        && !/(auto|scroll)/.test(s.overflowX)) out.push(`text cut off: ${name(el)}`);
  }
  // what a person sees: each text box cut to every ancestor that clips (scroll boxes, line clamps)
  const clip = el => { let c = {left: -1e9, top: -1e9, right: 1e9, bottom: 1e9};
    for (let p = el; p && p !== document.body; p = p.parentElement) { const s = getComputedStyle(p);
      if (s.overflow !== 'visible' || s.overflowX !== 'visible' || s.overflowY !== 'visible') { const r = p.getBoundingClientRect();
        c = {left: Math.max(c.left, r.left), top: Math.max(c.top, r.top), right: Math.min(c.right, r.right), bottom: Math.min(c.bottom, r.bottom)}; } }
    return c; };
  const boxes = texts.map(el => { const range = document.createRange(); range.selectNodeContents(el); const c = clip(el);
    return [el, [...range.getClientRects()].map(b => ({left: Math.max(b.left, c.left), top: Math.max(b.top, c.top),
      right: Math.min(b.right, c.right), bottom: Math.min(b.bottom, c.bottom)})).filter(b => b.right - b.left > 2 && b.bottom - b.top > 2)]; });
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [b, rb] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const hit = ra.some(x => rb.some(y => Math.min(x.right, y.right) - Math.max(x.left, y.left) > 3 && Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top) > 3));
    if (hit) out.push(`overlap: ${name(a)} × ${name(b)}`);
  }
  return [...new Set(out)].slice(0, 25);
})()"""


async def main(a):
    target = json.load(urllib.request.urlopen(urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")))
    page = Page(await websocket_connect(target["webSocketDebuggerUrl"], max_message_size=2**27))
    for domain in ("Runtime", "Page"):
        await page.call(f"{domain}.enable")
    await page.call("Page.navigate", {"url": f"{a.base}/auth/dev-login?next=/"})
    await asyncio.sleep(2)
    screens = [(n, p, "document.querySelector('h1')") for n, p in EXTRA.items()]
    screens += [(f"{w}:{n}", f"/w/{w}{p}", c) for w in a.waves.split(",") for n, (p, c) in SCREENS.items()]
    problems = 0
    for size, (width, height, mobile) in WIDTHS.items():
        await page.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile})
        for name, path, check in screens:
            await page.call("Page.navigate", {"url": a.base + path})
            await page.settle(f"({check}) && {NO_ERROR}", 30)
            await asyncio.sleep(0.4)   # charts finish their resize
            found = await page.js(AUDIT) or []
            problems += len(found)
            print(f"{size:<8} {name:<16} {'ok' if not found else str(len(found)) + ' problem(s)'}", flush=True)
            for f in found:
                print(f"           {f}")
    print(f"\n{problems} layout problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("base")
    p.add_argument("--waves", default="412,235")
    sys.exit(asyncio.run(main(p.parse_args())))
