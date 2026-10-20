"""Static UI mockups for CIP, built from real wave data, then screenshotted to PNG.

    python docs/Ui-Design-Claude/ui/make_mockups.py            # writes mockups/*.html and images/*.png

Numbers are real (cip_stg, 20 Oct 2026): 2026 Holiday tracker waves 1-4 (surveys 235, 266, 412, 415) and
2025 wave 3 (survey 240), qualified US adults. The question catalogue is the 28 Sep 2026 wave's.
Significance letters: two-proportion z-test between banner columns at 95 %.
"""
from __future__ import annotations

import math
import subprocess
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT, IMG = HERE / "mockups", HERE / "images"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ── real data ───────────────────────────────────────────────────────────────────────────────────
STATUS = ["Not yet started", "Still shopping", "Finished shopping", "Do not make holiday purchases"]
WAVES = [   # (label, week of, qualified, XM3 counts in STATUS order)
    ("Wave 1", "Sep 28", 403, (205, 111, 44, 43)),
    ("Wave 2", "Oct 5", 401, (216, 116, 33, 36)),
    ("Wave 3", "Oct 12", 404, (222, 117, 32, 33)),
    ("Wave 4", "Oct 19", 400, (212, 143, 19, 26)),   # 53.0 / 35.7 / 4.8 → started 40.5
]
LY_W3 = ("2025 wave 3", "Oct 27, 2025", 402, (179, 164, 30, 29))
GEN = {   # XM3 by generation, wave 3: counts per status, base
    "Gen Z": ((22, 15, 5, 0), 42), "Millennial": ((52, 45, 17, 7), 121),
    "Gen X": ((64, 29, 8, 10), 111), "Boomer": ((84, 28, 2, 16), 130),
}
BOUGHT = {"wave": (125, 404), "prior": (92, 149)}   # XM1 = Yes; prior week asked of 'started' only
RETAILERS = [("Walmart", 63, 41), ("Amazon", 51, 35), ("Dollar General", 27, 19), ("Dollar Tree", 26, 20),
             ("Target", 25, 23), ("Costco", 20, 14), ("Old Navy", 19, 14), ("Home Depot", 19, 9)]   # n wave 3 /125, n wave 2 /92
CATEGORIES = [("Clothing, footwear, accessories or bags", 49), ("Toys or games", 46), ("Food and drink", 44),
              ("Electronics", 39), ("Holiday decorations / Christmas lights", 38), ("Books, music, video or games", 35)]
TOPICS = [   # real question catalogue (28 Sep 2026 wave): code, type, base, text
    ("Holiday shopping", [
        ("XM3", "Single choice", 403, "What is the current status of your holiday shopping?"),
        ("XM1", "Single choice", 155, "Did you make any holiday purchases in the last seven days?"),
        ("XM1A", "Multiple choice", 96, "Which, if any, of these categories did you buy for the holidays in the last seven days?"),
        ("XM2", "Multiple choice", 96, "From which, if any, of the following retailers did you make holiday-related purchases in the last seven days?"),
        ("HX2", "Single choice", 369, "How will your holiday spending in 2026 compare to 2025?"),
        ("HX5", "Single choice", 369, "Do you expect your personal financial situation to be better or worse for holiday 2026?")]),
    ("Weekly shopping (core tracker)", [
        ("q1", "Multiple choice", 403, "Which, if any, of these have you done in the past two weeks?"),
        ("q2", "Multiple choice", 403, "Which categories have you purchased in a store in the past two weeks?"),
        ("q3", "Multiple choice", 403, "And which categories have you purchased online in the past two weeks?")]),
    ("Beauty", [
        ("BT1", "Single choice", 403, "Have you purchased any beauty products in the past three months?"),
        ("BT13", "Multiple choice", 264, "Which retailers or platforms have you purchased beauty products from in the past three months?")]),
    ("Tariffs", [
        ("TF1", "Single choice", 403, "What impact, if any, do you think tariffs have on you personally?"),
        ("TF3", "Multiple choice", 403, "Which, if any, of the following are your greatest concerns about tariffs?")]),
    ("AI and shopping", [
        ("D28", "Multiple choice", 403, "Which, if any, of the following AI tools have you used in the last two weeks?"),
        ("D32", "Multiple choice", 46, "And which of these have you used to help you shop?")]),
]


def pct(n, b):
    return 100 * n / b


def sig(n1, b1, n2, b2):
    """True when column 1's share is significantly higher than column 2's (two-proportion z, 95 %)."""
    if not (b1 and b2):
        return False
    p1, p2, p = n1 / b1, n2 / b2, (n1 + n2) / (b1 + b2)
    se = math.sqrt(p * (1 - p) * (1 / b1 + 1 / b2)) if 0 < p < 1 else 0
    return se > 0 and (p1 - p2) / se > 1.96


# ── shared look ─────────────────────────────────────────────────────────────────────────────────
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@400;500;600&display=swap" rel="stylesheet">')

BASE_CSS = """
:root{--ink:#1a1a2e;--ink-2:#52514e;--ink-3:#77766f;--line:#e1e4e8;--line-2:#eceef1;--desk:#eef0f3;--paper:#fff;
--red:#d62e2f;--red-ink:#a61f20;--up:#166b41;--up-weak:#e5f2eb;--down:#a61f20;--down-weak:#f9e9e8;--warn:#8a5a00;--warn-weak:#fbf1dc;
--s-not:#c4cad3;--s-still:#2a78d6;--s-done:#163f7a;--s-none:#eceef1;--blue:#2a78d6;--blue-ink:#1f62b8;
--sans:'IBM Plex Sans',Helvetica,Arial,sans-serif;--cond:'IBM Plex Sans Condensed','IBM Plex Sans',Arial,sans-serif}
*{box-sizing:border-box}html,body{margin:0}body{font-family:var(--sans);color:var(--ink);background:var(--desk);font-size:14px;line-height:1.45}
.num{font-variant-numeric:tabular-nums}
.base{font-size:12px;color:var(--ink-3)}
.chip{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:1px 8px;font-size:12px;font-weight:500;white-space:nowrap}
.chip.up{background:var(--up-weak);color:var(--up)}.chip.down{background:var(--down-weak);color:var(--down)}
.chip.flat{background:var(--line-2);color:var(--ink-2)}.chip.warn{background:var(--warn-weak);color:var(--warn)}
.chip.missing{background:transparent;color:var(--ink-3);border:1px dashed #c4cad3}
"""

ICONS = {   # 18px line icons
    "overview": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "explore": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "analysis": '<path d="M4 4h16v16H4z"/><path d="M4 10h16M10 4v16"/>',
    "trends": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "tracker": '<path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="9"/>',
    "saved": '<path d="M6 3h12v18l-6-4-6 4z"/>',
    "export": '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/>',
}


def icon(name):
    return (f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def change(now, before, label, significant=False):
    """Colour only a statistically significant change; anything else stays grey."""
    if before is None:
        return f'<span class="chip missing">{label}: not loaded</span>'
    d = now - before
    if abs(d) < 0.05:
        return f'<span class="chip flat">no change {label}</span>'
    kind = ("up" if d > 0 else "down") if significant else "flat"
    return f'<span class="chip {kind}">{"▲" if d > 0 else "▼"} {abs(d):.1f} pts {label}</span>'


# ── Option C: the recommended "research desk" shell ─────────────────────────────────────────────
C_CSS = BASE_CSS + """
.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}
.rail{background:var(--paper);border-right:1px solid var(--line);padding:18px 12px;display:flex;flex-direction:column;gap:2px}
.brand{display:flex;align-items:center;gap:10px;padding:0 8px 18px}
.brand .mark{width:28px;height:28px;border-radius:6px;background:var(--red);color:#fff;display:grid;place-items:center;font-weight:700;font-size:14px}
.brand b{font-size:15px;letter-spacing:-.01em}.brand span{display:block;font-size:12px;color:var(--ink-3)}
.rail a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:6px;color:var(--ink-2);text-decoration:none;font-weight:500;position:relative}
.rail a.on{color:var(--ink);background:var(--desk)}.rail a.on::before{content:"";position:absolute;left:-12px;top:6px;bottom:6px;width:3px;background:var(--red);border-radius:0 3px 3px 0}
.rail .group{font-size:12px;color:var(--ink-3);padding:16px 10px 6px}
.rail .foot{margin-top:auto;font-size:12px;color:var(--ink-3);padding:10px;border-top:1px solid var(--line-2)}
.main{display:flex;flex-direction:column;min-width:0}
.top{display:flex;align-items:center;gap:14px;padding:12px 28px;background:var(--paper);border-bottom:1px solid var(--line)}
.search{flex:1;max-width:560px;display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;padding:8px 12px;color:var(--ink-3);background:#fafbfc}
.search kbd{margin-left:auto;font-family:var(--sans);font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 5px;color:var(--ink-3)}
.wave{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;padding:7px 12px;font-weight:500;background:var(--paper)}
.wave small{color:var(--ink-3);font-weight:400}
.avatar{width:30px;height:30px;border-radius:50%;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:12px;font-weight:600;margin-left:auto}
.context{display:flex;flex-wrap:wrap;gap:6px 18px;padding:10px 28px;font-size:13px;color:var(--ink-2);border-bottom:1px solid var(--line);background:#f7f8fa}
.context b{color:var(--ink);font-weight:600}
.page{padding:26px 28px 40px;display:grid;gap:22px;max-width:1240px}
h1{font-size:26px;line-height:1.2;font-weight:600;letter-spacing:-.015em;margin:0;max-width:44ch}
.lede{color:var(--ink-2);max-width:72ch;margin:6px 0 0}
.block{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:20px 22px}
.block h2{font-size:16px;font-weight:600;margin:0 0 2px}.block .q{color:var(--ink-2);font-size:13px;margin:0 0 16px;max-width:80ch}
.cols{display:grid;gap:22px}.cols.two{grid-template-columns:1.25fr 1fr}.cols.three{grid-template-columns:repeat(3,1fr)}
/* the signature: shopping status as one whole */
.strip{display:flex;height:46px;border-radius:6px;overflow:hidden;margin:6px 0 14px}
.strip span{display:flex;align-items:center;padding:0 12px;font-weight:600;font-size:15px;color:#fff;min-width:0;white-space:nowrap}
.strip .not{background:var(--s-not);color:var(--ink)}.strip .still{background:var(--s-still)}.strip .done{background:var(--s-done)}.strip .none{background:var(--s-none);color:var(--ink-2)}
.legend{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.legend>div{border-top:3px solid;padding-top:8px}.legend .v{font-size:28px;font-weight:600;letter-spacing:-.02em}
.legend .l{font-weight:500}.legend .c{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.bars{display:grid;gap:9px}
.bar{display:grid;grid-template-columns:minmax(120px,1.1fr) 2fr 54px 96px;align-items:center;gap:10px;font-size:13px}
.bar .track{height:12px;background:var(--line-2);border-radius:3px;overflow:hidden}.bar .track i{display:block;height:100%;background:var(--blue)}
.bar .v{text-align:right;font-weight:600}
.takeaways{margin:0;padding:0;list-style:none;display:grid;gap:10px}
.takeaways li{padding-left:14px;border-left:3px solid var(--line);max-width:80ch}
.takeaways li.key{border-left-color:var(--red)}
.note{font-size:12px;color:var(--ink-3);max-width:90ch}
table.x{border-collapse:collapse;width:100%;font-family:var(--cond);font-size:14px}
table.x th,table.x td{padding:9px 10px;border-bottom:1px solid var(--line-2);text-align:right;white-space:nowrap}
table.x th:first-child,table.x td:first-child{text-align:left;font-family:var(--sans);white-space:normal}
table.x thead th{font-weight:600;font-size:13px;color:var(--ink);vertical-align:bottom;border-bottom:1px solid var(--line)}
table.x thead .letter{display:block;font-weight:500;color:var(--ink-3);font-size:12px}
table.x .lt{color:var(--blue-ink);font-weight:600;font-size:12px;margin-left:4px}
table.x tr.basebar td{color:var(--ink-3);font-size:12px;background:#fafbfc}
table.x tr.net td{font-weight:600;background:#f7f8fa}
table.x td.small{color:var(--warn)}
.panel{display:grid;gap:14px;align-content:start}
.field label{display:block;font-size:12px;color:var(--ink-3);margin-bottom:4px}
.select{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:var(--paper);display:flex;justify-content:space-between}
.btn{display:inline-flex;align-items:center;gap:8px;border-radius:8px;padding:8px 14px;font-weight:600;border:1px solid var(--line);background:var(--paper);color:var(--ink)}
.btn.primary{background:var(--red);border-color:var(--red);color:#fff}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.qlist{display:grid}
.qrow{display:grid;grid-template-columns:64px 1fr 120px 150px 110px;gap:14px;align-items:center;padding:11px 4px;border-bottom:1px solid var(--line-2)}
.qrow .code{font-weight:600;color:var(--ink-2)}.qrow .t{font-weight:500}.qrow mark{background:#fff1b8;color:inherit;padding:0 1px}
.topic{font-weight:600;margin:16px 0 4px;color:var(--ink)}
.facet{display:flex;gap:8px;flex-wrap:wrap}.facet span{border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:13px;background:var(--paper)}
.facet span.on{border-color:var(--ink);background:var(--ink);color:#fff}
.mini{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.mini .g b{display:block;font-size:22px;font-weight:600}.mini .g .t{height:8px;background:var(--line-2);border-radius:3px;margin:6px 0}.mini .g .t i{display:block;height:100%;background:var(--s-still)}
@media (max-width:700px){.app{grid-template-columns:1fr}.rail{display:none}.top{padding:10px 16px;flex-wrap:wrap}.search{max-width:none;flex-basis:100%}.wave{flex:1}.wave small,.avatar,.search kbd{display:none}
.context{padding:8px 16px}.context span:nth-child(n+3){display:none}.page{padding:16px;gap:16px;max-width:100vw}.block,.legend>div,.cols>*{min-width:0}.chip{white-space:normal}
.cols.two,.cols.three{grid-template-columns:1fr}.legend,.mini{grid-template-columns:1fr 1fr}
.bar{grid-template-columns:1fr 1.2fr 46px}.bar .chip{display:none}h1{font-size:21px}.strip span{font-size:13px;padding:0 6px}.block{padding:16px}}
"""


def c_shell(active, body, title, week="Oct 12, 2026", wave="wave 3 of the holiday season", n=404,
            context="Compared with <b>Oct 5</b></span><span>Last year's same week <b>not loaded</b> (hibernated in Forsta)"):
    nav = [("overview", "Overview"), ("explore", "Explore questions"), ("analysis", "Analysis"), ("trends", "Trends")]
    trackers = [("tracker", "Holiday tracker")]
    mine = [("saved", "Saved views"), ("export", "Exports")]
    link = lambda key, label, k=None: f'<a class="{"on" if (k or key) == active else ""}" href="#">{icon(key)}{label}</a>'
    rail = "".join(link(k, l) for k, l in nav)
    rail += '<div class="group">Trackers</div>' + "".join(link(k, l, "holiday") for k, l in trackers)
    rail += '<div class="group">Yours</div>' + "".join(link(k, l) for k, l in mine)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · CIP</title>{FONTS}<style>{C_CSS}</style></head><body><div class="app">
<nav class="rail" aria-label="Main"><div class="brand"><div class="mark">C</div><div><b>Consumer Insight</b><span>Coresight Research</span></div></div>
{rail}<div class="foot">US weekly consumer survey since 2018. 320 waves.</div></nav>
<div class="main"><header class="top"><div class="search">{icon("explore")}Search questions, retailers, topics<kbd>⌘K</kbd></div>
<div class="wave">Week of {week} <small>{wave}</small> ▾</div><div class="avatar">AK</div></header>
<div class="context"><span><b>{n}</b> qualified US adults</span><span>Fielded Monday {week}</span><span>{context}</span><span>Data as of Oct 19, 16:23</span></div>
<main class="page">{body}</main></div></div></body></html>"""


def status_strip(counts, base):
    shares = [pct(n, base) for n in counts]
    cls = ["not", "still", "done", "none"]
    return '<div class="strip" role="img" aria-label="Holiday shopping status">' + "".join(
        f'<span class="{c}" style="flex:{s:.2f}">{s:.0f}%</span>' for c, s in zip(cls, shares)) + "</div>"


def overview_c():
    (_, _, b, now), (_, _, pb, prior) = WAVES[2], WAVES[1]
    colors = ["var(--s-not)", "var(--s-still)", "var(--s-done)", "#c9ced6"]
    legend = "".join(
        f'<div style="border-color:{col}"><div class="l">{lab}</div><div class="v num">{pct(n, b):.1f}%</div>'
        f'<div class="c">{change(pct(n, b), pct(p, pb), "vs last week", sig(n, b, p, pb) or sig(p, pb, n, b))}{change(0, None, "vs last year")}</div>'
        f'<div class="base">{n} of {b}</div></div>'
        for lab, n, p, col in zip(["Not yet started", "Still shopping", "Finished", "Not buying for the holidays"], now, prior, colors))
    started_now, started_prior = pct(now[1] + now[2], b), pct(prior[1] + prior[2], pb)
    retail = "".join(
        f'<div class="bar"><span>{r}</span><span class="track"><i style="width:{pct(n, 125) * 1.6:.0f}%"></i></span>'
        f'<span class="v num">{pct(n, 125):.1f}%</span>{change(pct(n, 125), pct(p, 92), "", sig(n, 125, p, 92) or sig(p, 92, n, 125))}</div>' for r, n, p in RETAILERS[:5])
    gens = "".join(
        f'<div class="g"><span>{g}{"" if base >= 50 else ' <span class="chip warn">small base</span>'}</span><b class="num">{pct(c[1] + c[2], base):.0f}%</b>'
        f'<div class="t"><i style="width:{pct(c[1] + c[2], base):.0f}%"></i></div><span class="base">started, n={base}</span></div>'
        for g, (c, base) in GEN.items())
    body = f"""
<section><h1>Over a third of US consumers have started holiday shopping, level with last week</h1>
<p class="lede">{started_now:.1f}% have started ({pct(now[2], b):.1f}% finished) against {started_prior:.1f}% a week earlier. Millennials are furthest along; Boomers have barely begun.</p></section>
<section class="block"><h2>Holiday shopping status</h2><p class="q">What is the current status of your holiday shopping? Asked of all {b} qualified respondents.</p>
{status_strip(now, b)}<div class="legend">{legend}</div></section>
<div class="cols two">
<section class="block"><h2>Where holiday shoppers bought this week</h2><p class="q">Retailers used for holiday purchases in the last seven days. Base: the 125 who made a holiday purchase.</p>
<div class="bars">{retail}</div><p class="note" style="margin-top:12px">Change is against last week's 92 purchasers.</p></section>
<section class="block"><h2>Bought for the holidays in the last seven days</h2><p class="q">Did you make any holiday purchases in the last seven days?</p>
<div class="legend" style="grid-template-columns:1fr"><div style="border-color:var(--blue)"><div class="v num">{pct(*BOUGHT["wave"]):.1f}%</div>
<div class="c"><span class="chip warn">vs last week: not comparable</span></div><div class="base">125 of 404, asked of everyone</div></div></div>
<p class="note" style="margin-top:12px">Last week this was asked only of the 149 who had started shopping (61.7%), so the two figures describe different people.</p></section></div>
<section class="block"><h2>Started shopping, by generation</h2><p class="q">Still shopping or finished, as a share of each generation.</p><div class="mini">{gens}</div></section>
"""
    return c_shell("overview", body, "Overview")


def explore_c():
    rows = ""
    for topic, qs in TOPICS:
        rows += f'<div class="topic">{topic}</div>'
        for code, kind, base, text in qs:
            t = escape(text).replace("holiday", "<mark>holiday</mark>") if topic == "Holiday shopping" else escape(text)
            asked = "everyone" if base >= 400 else f"{base} respondents"
            trend = "320 waves" if code.startswith(("q", "CS", "D1")) else ("4 waves this season" if code.startswith("XM") else "This wave")
            rows += (f'<div class="qrow"><span class="code">{code}</span><span class="t">{t}</span><span class="base">{kind}</span>'
                     f'<span class="base">Asked of {asked}</span><span class="base">{trend}</span></div>')
    body = f"""
<section><h1>Explore this week's questions</h1><p class="lede">79 questions were asked in the week of Sep 28. Search finds them by wording, answer or retailer, across every wave since 2018.</p></section>
<section class="block"><div class="toolbar"><div class="search" style="max-width:none;flex:1;color:var(--ink)">{icon("explore")} holiday<kbd>Enter</kbd></div>
<span class="btn">All waves</span></div>
<div class="facet" style="margin-top:14px"><span class="on">All topics</span><span>Holiday shopping 6</span><span>Weekly shopping 5</span><span>Beauty 15</span><span>Tariffs 4</span><span>AI and shopping 8</span><span>Economy 3</span><span>About the respondent 8</span></div>
<div class="qlist" style="margin-top:8px"><div class="qrow" style="color:var(--ink-3);font-size:12px;border-bottom:1px solid var(--line)"><span>Code</span><span>Question</span><span>Answer type</span><span>Who was asked</span><span>History</span></div>{rows}</div></section>"""
    return c_shell("explore", body, "Explore questions", week="Sep 28, 2026", wave="wave 1 of the holiday season", n=403,
                   context="Compared with <b>Sep 21</b></span><span>Holiday questions began this week")


def analysis_c():
    _, _, b, tot = WAVES[2]
    cols = [("Total", tot, b)] + [(g, c, base) for g, (c, base) in GEN.items()]
    letters = ["", "A", "B", "C", "D"]
    head = "".join(f'<th>{name}<span class="letter">{letters[i] or "&nbsp;"}</span></th>' for i, (name, _, _) in enumerate(cols))
    def row(label, counts_of, cls=""):
        cells = ""
        for i, (_, c, base) in enumerate(cols):
            n = counts_of(c)
            higher = "".join(letters[j] for j, (_, c2, b2) in enumerate(cols) if j and i and j != i and sig(n, base, counts_of(c2), b2))
            small = " small" if base < 50 else ""
            cells += f'<td class="num{small}">{pct(n, base):.1f}%{f"<span class=lt>{higher}</span>" if higher else ""}</td>'
        return f'<tr class="{cls}"><td>{label}</td>{cells}</tr>'
    body_rows = "".join(row(lab, (lambda c, k=k: c[k])) for k, lab in enumerate(STATUS))
    body_rows += row("Started shopping (still + finished)", lambda c: c[1] + c[2], "net")
    bases = "".join(f'<td class="num">{base}</td>' for _, _, base in cols)
    body = f"""
<section><h1>Holiday shopping status by generation</h1><p class="lede">Built from the question, the break and the group you choose. Changing any of them answers in the browser; nothing waits on the server.</p></section>
<div class="cols" style="grid-template-columns:260px 1fr">
<aside class="block panel"><div class="field"><label>Question</label><div class="select">Holiday shopping status ▾</div></div>
<div class="field"><label>Break by</label><div class="select">Generation ▾</div></div>
<div class="field"><label>Compare</label><div class="select">Columns against each other ▾</div></div>
<div class="field"><label>Group (filter)</label><div class="select">Everyone ▾</div></div>
<div class="field"><label>Show</label><div class="facet"><span class="on">Percent</span><span>Count</span><span>Both</span></div></div>
<div class="toolbar"><span class="btn primary">Save view</span><span class="btn">{icon("export")} Excel</span></div></aside>
<section class="block"><h2>What is the current status of your holiday shopping?</h2><p class="q">Week of Oct 12, 2026. Column percentages. A letter marks a figure significantly higher than that column (95%).</p>
<table class="x"><thead><tr><th>Answer</th>{head}</tr></thead><tbody>
<tr class="basebar"><td>Respondents (base)</td>{bases}</tr>{body_rows}</tbody></table>
<p class="note" style="margin-top:12px">Gen Z has 42 respondents, fewer than 50; read its figures with care. Shown in amber.</p></section></div>"""
    return c_shell("analysis", body, "Analysis")


def trends_c():
    W, H, L, R, T, B = 820, 300, 56, 24, 20, 40
    xs = [L + i * (W - L - R) / 4 for i in range(5)]   # Sep 28, Oct 5, Oct 12, Oct 19, Oct 26
    y = lambda v: T + (H - T - B) * (1 - (v - 20) / 50)
    started = [pct(c[1] + c[2], b) for _, _, b, c in WAVES]
    notyet = [pct(c[0], b) for _, _, b, c in WAVES]
    ly_started = pct(LY_W3[3][1] + LY_W3[3][2], LY_W3[2])
    path = lambda vals: "M" + " L".join(f"{xs[i]:.0f},{y(v):.1f}" for i, v in enumerate(vals))
    grid = "".join(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#eceef1"/><text x="{L - 10}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="12" fill="#77766f">{v}%</text>' for v in (20, 30, 40, 50, 60, 70))
    labels = "".join(f'<text x="{x:.0f}" y="{H - 14}" text-anchor="middle" font-size="12" fill="#52514e">{t}</text>' for x, t in zip(xs, ["Sep 28", "Oct 5", "Oct 12", "Oct 19", "Oct 26"]))
    dots = lambda vals, col: "".join(f'<circle cx="{xs[i]:.0f}" cy="{y(v):.1f}" r="4.5" fill="{col}"/>' for i, v in enumerate(vals))
    ly_gap = "".join(f'<rect x="{xs[i] - 18:.0f}" y="{T}" width="36" height="{H - T - B}" fill="url(#hatch)" opacity=".55"/>' for i in (2, 3))   # Oct 13 and 20, 2025
    svg = f"""<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Started shopping and not yet started, by week">
<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#d5d9df" stroke-width="2"/></pattern></defs>
{grid}{ly_gap}{labels}
<path d="{path(notyet)}" fill="none" stroke="#9aa3ae" stroke-width="2.5"/>{dots(notyet, "#9aa3ae")}
<path d="{path(started)}" fill="none" stroke="var(--s-still)" stroke-width="3"/>{dots(started, "#2a78d6")}
<circle cx="{xs[4]:.0f}" cy="{y(ly_started):.1f}" r="6" fill="#fff" stroke="#163f7a" stroke-width="2.5"/>
<text x="{xs[4] - 10:.0f}" y="{y(ly_started) + 24:.1f}" text-anchor="end" font-size="12" fill="#163f7a">Last year, Oct 27: {ly_started:.0f}% started</text>
<text x="{xs[3] + 8:.0f}" y="{y(started[3]) + 24:.1f}" font-size="12" font-weight="600" fill="#1f62b8">Started {started[3]:.1f}%</text>
<text x="{xs[3] + 8:.0f}" y="{y(notyet[3]) - 10:.1f}" font-size="12" fill="#52514e">Not yet started {notyet[3]:.1f}%</text>
<text x="{xs[2] - 18:.0f}" y="{T + 14}" font-size="11" fill="#77766f">Same weeks of 2025 not loaded</text></svg>"""
    table = "".join(f'<tr><td>{lab} ({wk})</td><td class="num">{n:.1f}%</td><td class="num">{s:.1f}%</td><td class="num">{b}</td></tr>'
                    for (lab, wk, b, _), n, s in zip(WAVES, notyet, started))
    body = f"""
<section><h1>Holiday shopping is starting later than last season</h1><p class="lede">Four weeks into the 2026 season, {started[3]:.0f}% have started. Last season's nearest loaded week (Oct 27, 2025) had {ly_started:.0f}%. The two missing 2025 weeks are hibernated in Forsta and will appear here once they are loaded.</p></section>
<section class="block"><h2>Started shopping and not yet started, by week</h2><p class="q">Holiday shopping status, all qualified respondents, 2026 season. Hatched weeks: last season's data not loaded yet.</p>{svg}</section>
<section class="block"><table class="x"><thead><tr><th>Week</th><th>Not yet started</th><th>Started</th><th>Base</th></tr></thead><tbody>{table}</tbody></table></section>"""
    return c_shell("trends", body, "Trends")


# ── Option A: today's Coresight portal pattern (SIP / MIP / MDP, the analysts' PDF) ──────────────
def overview_a():
    (_, _, b, now), (_, _, pb, p) = WAVES[2], WAVES[1]
    def tile(h, n, m):
        d = pct(n, b) - pct(m, pb)
        return (f'<div class="t"><div class="h">{h}</div><div class="v">{pct(n, b):.1f}%</div>'
                f'<div class="s">{"▲" if d > 0 else "▼"} {abs(d):.1f} pts vs prior week</div></div>')
    tiles = "".join(tile(h, n, m) for h, n, m in [("NOT YET STARTED", now[0], p[0]),
                                                  ("STARTED SHOPPING", now[1] + now[2], p[1] + p[2]),
                                                  ("FINISHED SHOPPING", now[2], p[2])])
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{BASE_CSS}
body{{background:#fff;font-family:Arial,Helvetica,sans-serif}}.hd{{background:#fff;border-bottom:3px solid var(--red);display:flex;align-items:center;gap:28px;padding:12px 32px}}
.hd b{{color:var(--red);font-size:20px}}.hd a{{color:#333;text-decoration:none;font-weight:600;font-size:14px}}.hd a.on{{color:var(--red);border-bottom:2px solid var(--red);padding-bottom:4px}}
.bn{{background:var(--red);color:#fff;font-weight:700;padding:8px 14px;margin:18px 32px 0}}.tiles{{display:grid;grid-template-columns:repeat(5,1fr);margin:0 32px;border:1px solid #ddd}}
.t{{padding:14px;text-align:center;border-right:1px solid #ddd}}.t .h{{font-size:11px;font-weight:700}}.t .v{{color:var(--red);font-size:32px;font-weight:700;margin:12px 0}}.t .s{{font-size:12px}}
.kt li{{background:#eef2f7;border-bottom:1px solid #333;padding:9px 12px;list-style:none;font-size:13px}}.kt{{margin:0 32px;padding:0}}
.sb{{display:flex;gap:10px;margin:18px 32px}}.sb span{{border:1px solid #ccc;padding:6px 10px;font-size:13px}}</style></head><body>
<div class="hd"><b>coresight</b><a class="on">Overview</a><a>Survey report</a><a>Analysis</a><a>Trends</a><a>Mappings</a><a>Publications</a><a>Data health</a><a style="margin-left:auto">Sign out</a></div>
<div class="sb"><span>Wave: Week of Oct 12, 2026 ▾</span><span>Group: Everyone ▾</span></div>
<div class="bn">THIS WEEK AT A GLANCE · Wave 3 · Week of Oct 12, 2026</div><div class="tiles">{tiles}
<div class="t"><div class="h">BOUGHT IN PAST 7 DAYS</div><div class="v">30.9%</div><div class="s">▼ 30.8 pts vs prior week</div></div>
<div class="t"><div class="h">#1 HOLIDAY RETAILER</div><div class="v" style="font-size:22px">Walmart</div><div class="s">50.4% of purchasers</div></div></div>
<div class="bn">KEY TAKEAWAYS</div><ul class="kt"><li>Progress: 37% of US consumers have started holiday shopping (8% finished) and 55% have not started.</li>
<li>Activity: 31% bought for the holidays in the past 7 days (n=404).</li><li>Retailers: Walmart (50%), Amazon (41%) and Dollar General (22%) lead.</li>
<li>By generation: Gen Z 48%, Millennial 51%, Gen X 33%, Boomer 23%.</li></ul></body></html>"""


# ── Option B: a billing-console (Chargebee-like) SaaS pattern ───────────────────────────────────
def overview_b():
    (_, _, b, now), (_, _, pb, p) = WAVES[2], WAVES[1]
    def card(h, n, m, base=b, pbase=pb):
        d = pct(n, base) - pct(m, pbase)
        return (f'<div class="card"><div class="h">{h}</div><div class="v">{pct(n, base):.1f}%</div>'
                f'<div class="s" style="color:{"#1b7f4f" if d >= 0 else "#a61f20"}">{"+" if d >= 0 else "−"}{abs(d):.1f} pts vs last week</div></div>')
    cards = (card("Not yet started", now[0], p[0]) + card("Started shopping", now[1] + now[2], p[1] + p[2])
             + card("Finished", now[2], p[2]) + card("Bought in past 7 days", 125, 92, 404, 149))
    rows = "".join(f'<tr><td>{r}</td><td>{pct(n, 125):.1f}%</td><td>{n}</td>'
                   f'<td style="color:{"#1b7f4f" if pct(n, 125) >= pct(m, 92) else "#a61f20"}">{pct(n, 125) - pct(m, 92):+.1f} pts</td></tr>'
                   for r, n, m in RETAILERS[:6])
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{BASE_CSS}
body{{font-family:var(--sans);background:#f6f7f9}}.app{{display:grid;grid-template-columns:240px 1fr;min-height:100vh}}
.sd{{background:#12172b;color:#c9cfdf;padding:20px 14px}}.sd b{{color:#fff;display:block;margin:0 8px 22px;font-size:16px}}.sd a{{display:block;padding:9px 10px;border-radius:6px;color:#c9cfdf;font-size:14px}}
.sd a.on{{background:#252c48;color:#fff}}.mn{{padding:24px 32px}}.tb{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}.tb h1{{font-size:22px;margin:0}}
.tb .btn{{background:#3c50e0;color:#fff;border-radius:6px;padding:8px 14px;font-weight:600}}.flt{{display:flex;gap:8px;margin:0 0 20px}}.flt span{{background:#fff;border:1px solid #dde;border-radius:6px;padding:5px 10px;font-size:13px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.card{{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.1);padding:18px}}.card .h{{color:#667;font-size:13px}}.card .v{{font-size:28px;font-weight:600;margin:8px 0}}.card .s{{font-size:13px}}
table{{width:100%;background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.1);border-collapse:collapse;margin-top:22px}}td,th{{padding:12px 16px;border-bottom:1px solid #eee;text-align:left;font-size:14px}}
</style></head><body><div class="app">
<nav class="sd"><b>Insights</b><a class="on">Dashboard</a><a>Questions</a><a>Reports</a><a>Trends</a><a>Saved views</a><a>Exports</a><a>Settings</a></nav>
<div class="mn"><div class="tb"><h1>Dashboard</h1><span class="btn">+ New report</span></div>
<div class="flt"><span>Week of Oct 12, 2026 ▾</span><span>All respondents ▾</span></div><div class="cards">{cards}</div>
<table><thead><tr><th>Top holiday retailers</th><th>Share of purchasers</th><th>Respondents</th><th>Change vs last week</th></tr></thead><tbody>{rows}</tbody></table></div></div></body></html>"""


PAGES = {   # file → (html, window width, height)
    "option-a-coresight-portal": (overview_a, 1440, 760),
    "option-b-billing-console": (overview_b, 1440, 760),
    "option-c-research-desk": (overview_c, 1440, 1140),
    "c-explore": (explore_c, 1440, 1240),
    "c-analysis": (analysis_c, 1440, 860),
    "c-trends": (trends_c, 1440, 1060),
}


def main():
    OUT.mkdir(exist_ok=True)
    IMG.mkdir(exist_ok=True)
    for name, (page, w, h) in PAGES.items():
        html = OUT / f"{name}.html"
        html.write_text(page(), encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--disable-gpu", f"--window-size={w},{h}",
                        "--virtual-time-budget=4000", f"--screenshot={IMG / (name + '.png')}", html.as_uri()],
                       check=True, capture_output=True)
    # headless Chrome will not size a window below ~500 px, so the phone view is a 390 px frame inside a wider page
    frame = OUT / "c-overview-mobile.html"
    frame.write_text('<!doctype html><body style="margin:0;background:#fff"><iframe src="option-c-research-desk.html" '
                     'style="width:390px;height:1820px;border:0;display:block"></iframe></body>', encoding="utf-8")
    shot = IMG / "c-overview-mobile.png"
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--window-size=600,1820", "--virtual-time-budget=4000",
                    f"--screenshot={shot}", frame.as_uri()], check=True, capture_output=True)
    from PIL import Image
    Image.open(shot).crop((0, 0, 390, 1820)).save(shot)
    print("\n".join(sorted(p.name for p in IMG.glob("*.png"))))


if __name__ == "__main__":
    main()
