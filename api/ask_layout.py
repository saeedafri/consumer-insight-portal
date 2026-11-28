"""Ask CIP's answer in the manager's layout (27 Nov 2026): one plain direct answer, three summary cards, the chart that fits
the question, and the source, for every answer type, from the figures api/ask_figures.py computed. No model writes text:
each answer type has one fixed sentence pattern, filled with the figures, the survey's country and one plain phrase for
what people did (config/ask_semantic.json "phrase", written once offline; until then a phrase made from the wording).

Who calls it: api/assistant.py answer, once the figures are computed; the Ask screen (frontend/src/screens/Ask.tsx) draws
what it returns. The types and their patterns: docs/research/ask-cip-rebuild-2026-11-27/01-template-spec.md section 4.4
(T1 latest value, T2 trend, T3 groups compared, T4 ranked answers, T5 two periods, T11 a better/worse scale).

A change or gap is said as higher/lower, up/down only when the 95% two-proportion test calls it real (api/dashboards.py
significant); otherwise "about the same" or "could be chance". Groups under SMALL people are marked and never named
highest or lowest; a figure on fewer than HIDDEN people never leads.
"""
from __future__ import annotations

import math
import re
from datetime import date

from pathlib import Path

import numpy as np
import yaml

from api.ask_figures import band, label_date, significant

SMALL = 50    # as api/assistant.py SMALL_BASE: a figure on fewer people is marked "read with caution", never highest/lowest
HIDDEN = 30   # nor in a sentence or card under this (it stays in the table)
STEADY_POINTS = 5   # a window whose highest and lowest are this close, with no real step, is "steady" (01 section 4.4 T2)
TOP_BARS = 10       # a ranked list draws its top ten (01 section 4.4 T4)
PAIRED_MAX = 8      # two periods compared draw up to eight answers (T5)
UNUSUAL_POINTS = 10  # a reading this far from the series' median, and unlike both neighbours by the test, is labelled unusual
GRAIN_OF = {"month": "Monthly", "quarter": "Quarterly", "year": "Yearly", "wave": "Each survey"}
SURVEYS = {"CSI-US": "Coresight US Consumer Survey", "CSI-CN": "Coresight China Consumer Survey"}
PEOPLE = {"US": "US adults", "CN": "adults in China"}
GROUPS = {"GenZ": "Gen Z", "Millennial": "Millennials", "GenX": "Gen X", "Boomer": "Boomers", "Male": "men", "Female": "women"}
INCOME = {"Under $50k": ("under $25,000", "$25,000 - $49,999"), "$50k-$99k": ("$50,000 - $99,999",),
          "$100k+": ("$100,000 - $149,999", "$150,000 - $199,999", "$200,000 or greater")}   # as api/ask_reader.py INCOME_GROUPS
NOT_RANKED = re.compile(   # api/assistant.py SKIP, also matching "Don't know / not sure" and longer "Other …" answers
    r"^(none of (these|the above)|other( - please specify)?|prefer not to say|don['’]?t know|not sure)\b", re.I)
NET = re.compile(r"\(.+ \+ .+\)")   # an answer Ask added by summing others ("Better (Somewhat better + Much better)")
# a scale's two sides by their answers' words: the weekly report's (config/weekly_report.yml net_words), and the China survey's
SIDES = {side: tuple(words) + extra for (side, words), extra in zip(
    yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "weekly_report.yml").read_text())["net_words"].items(),
    (("positive",), ("negative",)))}
DAY = re.compile(r"\d{1,2} \w{3} \d{4}")   # one survey's day as a period label ("5 Sep 2022")


def survey_name(family: str, country: str, title: str = "") -> str:
    """The survey's name as the answer card says it, naming the country: "Coresight US Consumer Survey", or a study's own
    title ("Coresight survey: Holiday Shopping 2025, US")."""
    name = (title or family.replace("_", " ").title()).split(":")[0].strip()   # "…and Prime Day: June 20, 2022": the date is in the source line
    return SURVEYS.get(family) or f"Coresight survey: {name}, {'China' if country == 'CN' else 'US'}"


def phrase(doc: dict) -> str:
    """What people did, said to follow "65.5% of US adults ___": the offline phrase when written (Phase 3), else made from a
    yes/no wording by rule ("Have you purchased any beauty products … in the past three months?" → "bought beauty products
    in the past three months"), else "said “Yes” to “{wording}”"."""
    if doc.get("phrase") and "{answer}" not in doc["phrase"]:
        return doc["phrase"]
    text = re.sub(r"\s*\([^)]*\)", "", doc["text"]).strip().rstrip("?. ")
    found = re.match(r"(?i)^(?:have|did) you (?:ever )?(purchased|bought|used|shopped|made|visited|watched|returned|noticed|changed|"
                     r"heard of|subscribed to|started)\b\s*(?:any )?(.*)$", text)
    if found:
        verb = {"purchased": "bought", "heard of": "have heard of", "subscribed to": "have subscribed to"}.get(found[1].lower(), found[1].lower())
        return f"{verb} {found[2]}".strip()
    found = re.match(r"(?i)^are you (?:currently )?(\w+ing)\b\s*(.*)$", text)
    if found:
        return f"are {found[1].lower()} {found[2]}".strip()
    found = re.match(r"(?i)^do you (have|own|use|expect|plan)\b\s*(.*)$", text)
    if found:
        return f"{found[1].lower()} {found[2]}".strip()
    return f"said “Yes” to “{doc['text'].strip()}”"


def answer_phrase(doc: dict, label: str) -> str:
    """What choosing one answer means ("bought beauty products from Walmart"): the offline {answer} phrase, else the answer
    with the question's short name ("chose Walmart when asked about beauty product retailers"). A net Ask added is said by
    its name alone ("Have Amazon Prime", not its parts)."""
    label = NET.sub("", label).strip()
    if label.lower() == "yes":
        return phrase(doc)
    if doc.get("phrase") and "{answer}" in doc["phrase"]:
        return doc["phrase"].replace("{answer}", label if label[:1].isupper() and not label.isupper() else label.lower())
    if not doc.get("name"):   # no short name yet (China's questions): the wording itself
        return f"chose {label} when asked “{doc['text'].strip()}”"
    name = doc["name"].strip().rstrip("?.")
    return f"chose {label} when asked about {name if name[:2].isupper() else name[0].lower() + name[1:]}"


def exact(fig: dict, p: int, c: int, a: int) -> float | None:
    """A share from its people and base (never two rounded figures), or None when not asked or under HIDDEN people."""
    base = int(fig["bases"][p, c, a])
    if not base or math.isnan(fig["pct"][p, c, a]) or base < HIDDEN:
        return None
    return float(fig["pct"][p, c, a]) if "tested" in fig else 100 * float(fig["people"][p, c, a]) / base


def real(fig: dict, p1: int, c1: int, p2: int, c2: int, a: int) -> bool:
    """Whether two figures of one answer differ by the 95% test (on unweighted shares when weighted are shown)."""
    tested = fig.get("tested", fig["pct"])
    return significant(float(tested[p1, c1, a]), int(fig["bases"][p1, c1, a]), float(tested[p2, c2, a]), int(fig["bases"][p2, c2, a]))


def change_words(now: float, was: float, sure: bool) -> str:
    """ "up 5.0 percentage points from" or "about the same as": a direction only when the test says it is real."""
    if not sure or round(now - was, 1) == 0:
        return "about the same as"
    return f"{'up' if now > was else 'down'} {abs(now - was):.1f} percentage points from"


def change_card(label: str, now: float, was: float, sure: bool) -> dict:
    """A card for a change: its points with a direction tone, or "About the same" when the test cannot tell it from chance."""
    same = not sure or round(now - was, 1) == 0
    return {"label": label, "value": "About the same" if same else f"{now - was:+.1f} pts", "note": f"From {was:.1f}%",
            "tone": "same" if same else "up" if now > was else "down"}


def day_of(period: dict) -> str:
    """A period's date: its last survey's day."""
    return period["to"] or period["from"]


def one_survey(period: dict) -> bool:
    """A period that is one survey's day ("5 Sep 2022"), not a pooled month, quarter, year or span."""
    return bool(DAY.fullmatch(period["label"]))


def when_said(period: dict, newest: str) -> str:
    """ "In the latest survey (28 Sep 2026)", "When last asked (12 May 2025)" for a question not asked for a year, "In Q3 2026"."""
    old = day_of(period) and (date.fromisoformat(newest) - date.fromisoformat(day_of(period))).days > 365
    label = period["label"]
    if "–" in label:
        return f"In the surveys of {label}"
    if one_survey(period):
        return f"{'When last asked' if old else 'In the latest survey'} ({label})"
    return f"{'When last asked, in' if old else 'In'} {label}"


def on(label: str) -> str:
    """ "on 28 Sep 2026" for a survey's day, "in Q3 2026" for a period."""
    return f"on {label}" if DAY.fullmatch(label) else f"in the surveys of {label}" if "–" in label else f"in {label}"


def month_year(period: dict) -> str:
    """A first period as a sentence names it: "September 2022" for one survey, its own name for a pooled one ("Q4 2023")."""
    if not one_survey(period) or not day_of(period):
        return period["label"]
    return date.fromisoformat(day_of(period)).strftime("%B %Y")


def short(period: dict) -> str:
    """The same, for a card's label: "Sep 2022", "Q4 2023"."""
    name = month_year(period)
    return f"{name[:3]} {name[-4:]}" if name[:1].isalpha() and name.split()[0] not in ("Q1", "Q2", "Q3", "Q4") and len(name.split()) == 2 else name


def names(labels: list[str]) -> str:
    """ "Gen Z, Millennials and Gen X"."""
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def sides_of(answers: list[str], asked: list[int]) -> dict[str, list[int]]:
    """A scale's two sides by the words of the answers asked ("Much better" + "Somewhat better"); empty when it is not a
    scale. `asked`: the answers the latest period offered (a question file holds every answer its reused code ever had)."""
    found = {side: [a for a in asked if any(w in answers[a].lower() for w in words) and not NOT_RANKED.match(answers[a])
                    and not NET.search(answers[a]) and not re.search(r"[$%\d]", answers[a])] for side, words in SIDES.items()}   # "More than $100" is an amount
    return found if all(found.values()) and not set(found["positive"]) & set(found["negative"]) else {}


def side_word(answers: list[str], side: str, members: list[int]) -> str:
    """The one word a scale's side is said by ("better", "positive"), as api/assistant.py side_word does for the weekly report."""
    return next((w for w in SIDES[side] if all(w in answers[a].lower() for a in members)), side)


def merged_income(fig: dict) -> dict:
    """The seven income bands as three groups (under $50k, $50k-$99k, $100k+), people and bases added, "prefer not to
    say" left out: as the samples and the weekly screens show income. Unchanged when the bands are not these or are weighted."""
    columns = [v for _, v in fig["columns"]]
    if "tested" in fig or fig["columns"][0][0] != "income_band" or not all(any(c in bands for bands in INCOME.values()) or
                                                                           c.lower().startswith("prefer") for c in columns):
        return fig
    people, bases, kept = [], [], []
    for group, bands in INCOME.items():
        picked = [i for i, c in enumerate(columns) if c in bands]
        if picked:
            people.append(fig["people"][:, picked].sum(axis=1))
            bases.append(fig["bases"][:, picked].sum(axis=1))
            kept.append(("income_band", group))
    people, bases = np.stack(people, axis=1), np.stack(bases, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = np.where(bases > 0, 100 * people / bases, np.nan)
    return {**fig, "columns": kept, "people": people, "bases": bases, "pct": pct}


def series(fig: dict, a: int, c: int = 0) -> list[float | None]:
    """One answer's share in every period, rounded for the chart (None where not asked or too few people)."""
    return [None if (v := exact(fig, p, c, a)) is None else round(v, 1) for p in range(len(fig["periods"]))]


def verdict(fig: dict, a: int, points: list[int]) -> str:
    """Steady / Rising / Falling / Up and down for a window of readings (01 section 4.4 T2)."""
    shares = [exact(fig, p, 0, a) for p in points]
    steps = [(1 if shares[i + 1] > shares[i] else -1) if real(fig, points[i], 0, points[i + 1], 0, a) else 0 for i in range(len(points) - 1)]
    overall = real(fig, points[0], 0, points[-1], 0, a)
    if max(shares) - min(shares) <= STEADY_POINTS and not any(steps):
        return "Steady"
    if overall and shares[-1] > shares[0] and -1 not in steps:
        return "Rising"
    if overall and shares[-1] < shares[0] and 1 not in steps:
        return "Falling"
    return "Up and down"


def window(fig: dict, points: list[int]) -> tuple[list[int], str]:
    """The readings this year, or of the last 12 months when this year has fewer than three, and the card's label."""
    last = day_of(fig["periods"][points[-1]])
    year = [p for p in points if day_of(fig["periods"][p]).startswith(last[:4])]
    if len(year) >= 3:
        return year, f"During {last[:4]}"
    cutoff = str(int(last[:4]) - 1) + last[4:]
    return [p for p in points if day_of(fig["periods"][p]) > cutoff], "Last 12 months"


def unusual(fig: dict, a: int, points: list[int]) -> list[dict]:
    """Readings unlike both neighbours by the 95% test, in the same direction, and UNUSUAL_POINTS from the median (01 4.3)."""
    shares = [exact(fig, p, 0, a) for p in points]
    middle = float(np.median(shares)) if shares else 0
    found = []
    for i in range(1, len(points) - 1):
        before, now, after = shares[i - 1], shares[i], shares[i + 1]
        same_wording = set(fig["periods"][points[i]].get("versions") or []) <= set(fig["periods"][points[-1]].get("versions") or [])   # else a join bug
        if same_wording and ((now > before and now > after) or (now < before and now < after)) and abs(now - middle) >= UNUSUAL_POINTS \
                and real(fig, points[i - 1], 0, points[i], 0, a) and real(fig, points[i], 0, points[i + 1], 0, a):
            period = fig["periods"][points[i]]
            found.append({"date": day_of(period), "label": f"Unusual {'high' if now > middle else 'low'}: {now:.1f}% ({short(period)})"})
    return found


def periods_offered(fig: dict) -> dict:
    """The period buttons a line offers, by how often the question is asked (01 4.3, the meeting of 27 Nov 2026): every two to
    five weeks or more often, monthly, quarterly and yearly; a module asked about quarterly, quarterly and yearly; less often,
    none. And the range buttons when the question spans more than a year."""
    days = [date.fromisoformat(d) for d in fig.get("asked", [])]
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    gap = gaps[len(gaps) // 2] if gaps else 999
    grains = ["Monthly", "Quarterly", "Yearly"] if gap <= 35 else ["Quarterly", "Yearly"] if gap <= 120 else []
    if grains and gap <= 35 and len(days) <= 26:   # each survey only while it stays readable (01 4.3); counted in surveys,
        # as a weekly question opens by month (ask_figures.auto_grain)
        grains = ["Each survey", *grains]
    ranges = ["Last 12 months", f"Since {days[0].year}"] if days and (days[-1] - days[0]).days > 400 else []
    return {"grains": grains, "grain": GRAIN_OF.get(fig.get("grain") or "", ""), "ranges": ranges}


def latest_value(fig: dict, doc: dict, a: int, who: str, newest: str, before: tuple[str, float, bool] | None) -> dict | None:
    """T1: the latest figure, against the survey before when there was one; every answer drawn in the survey's order."""
    now = exact(fig, -1, 0, a)
    if now is None:
        return None
    period = fig["periods"][-1]
    lead = f"{when_said(period, newest)}, {now:.1f}% of {who} {answer_phrase(doc, fig['answers'][a])}"
    cards = [{"label": "Latest survey", "value": f"{now:.1f}%", "note": period["label"], "tone": "main"}]
    if before:
        then, was, sure = before
        lead += f", {change_words(now, was, sure)} on {then} ({was:.1f}%)"
        cards.append(change_card(f"Since {then}", now, was, sure))
    elif len(fig.get("asked", [])) > 1:   # asked before, but not in the survey just before this one
        cards.append({"label": "First asked", "value": short({"label": label_date(fig["asked"][0]), "from": fig["asked"][0], "to": fig["asked"][0]}),
                      "note": "Every survey's result is below", "tone": ""})
    else:
        cards.append({"label": "Asked once", "value": short(period), "note": "No other survey asked this", "tone": ""})
    no = next((i for i, x in enumerate(fig["answers"]) if x.lower() == "no"), None)
    if fig["answers"][a].lower() == "yes" and no is not None and exact(fig, -1, 0, no) is not None:
        cards.append({"label": "Said no", "value": f"{exact(fig, -1, 0, no):.1f}%", "note": period["label"], "tone": ""})
    every = [i for i in range(len(fig["answers"])) if not NET.search(fig["answers"][i]) and exact(fig, -1, 0, i) is not None]
    return {"type": "T1", "lead": lead + ".", "cards": cards,
            "chart": {"kind": "columns", "categories": [fig["answers"][i] for i in every],
                      "series": [{"name": period["label"], "data": [round(exact(fig, -1, 0, i), 1) for i in every]}]}}


def trend(fig: dict, doc: dict, a: int, who: str, newest: str) -> dict | None:
    """T2: the latest reading, the change since the first, and how the share moved this year (or the last 12 months)."""
    points = [p for p in range(len(fig["periods"])) if exact(fig, p, 0, a) is not None]
    if len(points) < 2:
        return None
    periods = fig["periods"]
    first, last = points[0], points[-1]
    now, was = exact(fig, last, 0, a), exact(fig, first, 0, a)
    sure = real(fig, first, 0, last, 0, a)
    compared = (f"{abs(now - was):.1f} percentage points {'higher' if now > was else 'lower'} than" if sure and round(now - was, 1)
                else "about the same as")
    lead = (f"{when_said(periods[last], newest)}, {now:.1f}% of {who} {answer_phrase(doc, fig['answers'][a])}. "
            f"This is {compared} in {month_year(periods[first])} ({was:.1f}%)")
    cards = [{"label": "Latest survey" if one_survey(periods[last]) else "Latest",
              "value": f"{now:.1f}%", "note": periods[last]["label"], "tone": "main"},
             change_card(f"Since {short(periods[first])}", now, was, sure)]
    span, label = window(fig, points)
    if len(span) >= 3:
        moved = verdict(fig, a, span)
        low, high = min(exact(fig, p, 0, a) for p in span), max(exact(fig, p, 0, a) for p in span)
        when = label[0].lower() + label[1:]
        if moved in ("Rising", "Falling"):
            lead += f", and the share has {'risen' if moved == 'Rising' else 'fallen'} {when}, from {exact(fig, span[0], 0, a):.1f}% to {now:.1f}%"
        else:
            lead += f", and the share has {'stayed' if moved == 'Steady' else 'gone up and down'} between {low:.1f}% and {high:.1f}% {when}"
        cards.append({"label": label, "value": moved, "note": f"Between {low:.1f}% and {high:.1f}%", "tone": ""})
    odd = unusual(fig, a, points)
    return {"type": "T2", "lead": lead + ".", "cards": cards,
            "chart": {"kind": "line", "categories": [p["label"] for p in periods], "dates": [day_of(p) for p in periods],
                      "series": [{"name": fig["answers"][a], "data": series(fig, a)}], "unusual": odd},
            "notes": [f"{odd[0]['label']}: a reading far from the others, so treat it with care."] if odd else []}


def around(fig: dict, doc: dict, a: int, who: str, at: int) -> dict | None:
    """T15, a "why" question: the surveys record what people did and said, not why; so the reading asked about, the surveys
    before and after it, whether the move from the one before was real, and whether it was the same question asked the same way."""
    points = [p for p in range(len(fig["periods"])) if exact(fig, p, 0, a) is not None]
    if at not in points or points.index(at) == 0:
        return None
    i = points.index(at)
    before, after = points[i - 1], points[i + 1] if i + 1 < len(points) else None
    now, was = exact(fig, at, 0, a), exact(fig, before, 0, a)
    sure = real(fig, before, 0, at, 0, a)
    label = lambda p: fig["periods"][p]["label"]   # noqa: E731
    same = set(fig["periods"][at].get("versions") or []) == set(fig["periods"][before].get("versions") or [])
    unit = "survey" if one_survey(fig["periods"][at]) else "period"   # pooled spans are periods, not surveys
    lead = (f"The surveys record what people did and said, not why. {capital(on(label(at)))}, {now:.1f}% of {who} {answer_phrase(doc, fig['answers'][a])}; "
            f"the {unit} before was {was:.1f}% ({label(before)})" + (f" and the one after {exact(fig, after, 0, a):.1f}% ({label(after)})" if after is not None else "")
            + f". The {'rise' if now > was else 'fall'} from {label(before)} {'was real' if sure else 'could be chance'}, and it was "
            + ("the same question, asked the same way." if same else "a different wording of the question."))
    cards = [{"label": "That reading", "value": f"{now:.1f}%", "note": label(at), "tone": "main"},
             {"label": f"{capital(unit)} before", "value": f"{was:.1f}%", "note": label(before), "tone": ""}]
    if after is not None:
        cards.append({"label": f"{capital(unit)} after", "value": f"{exact(fig, after, 0, a):.1f}%", "note": label(after), "tone": ""})
    return {"type": "T15", "lead": lead, "cards": cards}


def scale(fig: dict, who: str, newest: str, sides: dict) -> dict | None:
    """T11: a better/worse scale, said by its two sides in the latest period (and against the first when over time)."""
    total = lambda p, side: sum(exact(fig, p, 0, a) or 0 for a in sides[side])   # noqa: E731
    good, bad = side_word(fig["answers"], "positive", sides["positive"]), side_word(fig["answers"], "negative", sides["negative"])
    p, base = len(fig["periods"]) - 1, int(fig["bases"][-1, 0, sides["positive"][0]])
    pos, neg = total(p, "positive"), total(p, "negative")
    if not base or not pos + neg:
        return None
    x, y = pos / 100, neg / 100   # two answers of one sample: their difference's own spread (multinomial)
    apart = abs(x - y) / math.sqrt(max(x + y - (x - y) ** 2, 1e-9) / base) > 1.96
    (hi_word, hi), (lo_word, lo) = ((bad, neg), (good, pos)) if neg > pos else ((good, pos), (bad, neg))
    start = when_said(fig["periods"][p], newest)
    lead = (f"{start}, more {'of ' if who == 'those asked' else ''}{who} said {hi_word} ({hi:.1f}%) than {lo_word} ({lo:.1f}%)." if apart else
            f"{start}, {who} were split: {pos:.1f}% said {good} and {neg:.1f}% {bad}.")
    cards = [{"label": f"Said {hi_word}", "value": f"{hi:.1f}%", "note": fig["periods"][p]["label"], "tone": "main"},
             {"label": f"Said {lo_word}", "value": f"{lo:.1f}%", "note": fig["periods"][p]["label"], "tone": ""},
             {"label": "Net", "value": f"{pos - neg:+.1f} pts", "note": f"{good.capitalize()} minus {bad}", "tone": ""}]
    start = next((q for q in range(p) if total(q, "positive") + total(q, "negative")), None)   # an older wording may have other answers
    if start is not None:   # over time: the first period said too, the net's change and its year, the two sides drawn as lines
        first = fig["periods"][start]
        lead += f" In {month_year(first)} it was {total(start, 'positive'):.1f}% {good} and {total(start, 'negative'):.1f}% {bad}."
        net = lambda q: total(q, "positive") - total(q, "negative")   # noqa: E731
        size = lambda q: int(fig["bases"][q, 0, sides["positive"][0]])   # noqa: E731
        moved = lambda q1, q2: any(significant(total(q2, side), size(q2), total(q1, side), size(q1)) for side in ("positive", "negative"))   # noqa: E731
        kept = [q for q in range(p + 1) if total(q, "positive") + total(q, "negative")]
        year, label = window(fig, kept)
        nets = [net(q) for q in year]
        steady = max(nets) - min(nets) <= STEADY_POINTS and not any(moved(a, b) for a, b in zip(year, year[1:]))
        verdict_ = "Steady" if steady else "Rising" if nets[-1] > nets[0] and moved(year[0], year[-1]) else \
            "Falling" if nets[-1] < nets[0] and moved(year[0], year[-1]) else "Up and down"
        real_change = moved(start, p)
        cards = [{"label": "Net now", "value": f"{net(p):+.1f} pts", "note": f"{capital(good)} minus {bad}, {fig['periods'][p]['label']}", "tone": "main"},
                 {"label": f"Net since {short(first)}", "value": f"{net(p) - net(start):+.1f} pts" if real_change else "About the same",
                  "note": f"From {net(start):+.1f}", "tone": ("up" if net(p) > net(start) else "down") if real_change else "same"},
                 {"label": label, "value": verdict_ if len(year) >= 3 else f"{net(p):+.1f}", "note": f"Net between {min(nets):+.1f} and {max(nets):+.1f}", "tone": ""}]
        chart = {"kind": "line", "categories": [q["label"] for q in fig["periods"]], "dates": [day_of(q) for q in fig["periods"]],
                 "series": [{"name": f"Said {word}", "data": [round(total(q, side), 1) if total(q, "positive") + total(q, "negative") else None
                                                              for q in range(len(fig["periods"]))]} for side, word in (("positive", good), ("negative", bad))]}
    else:   # one period: every answer in the scale's own order, each side shaded
        every = [i for i in range(len(fig["answers"])) if not NET.search(fig["answers"][i]) and exact(fig, p, 0, i) is not None]
        chart = {"kind": "columns", "categories": [fig["answers"][i] for i in every],
                 "sides": ["positive" if i in sides["positive"] else "negative" if i in sides["negative"] else "" for i in every],
                 "series": [{"name": fig["periods"][p]["label"], "data": [round(exact(fig, p, 0, i), 1) for i in every]}]}
    return {"type": "T11", "lead": lead, "cards": cards, "chart": chart}


def groups(fig: dict, doc: dict, a: int, who: str, newest: str) -> dict | None:
    """T3: which groups are highest (those tied with the top named together) and lowest in the latest period, whether the
    gap is real; one column per group, or one line per group over time."""
    fig = merged_income(fig)
    p = len(fig["periods"]) - 1
    rows = [(exact(fig, p, c, a), c, GROUPS.get(v, v), int(fig["bases"][p, c, a])) for c, (_, v) in enumerate(fig["columns"])]
    big = [r for r in rows if r[0] is not None and r[3] >= SMALL]
    if len(big) < 2:
        return None
    top, low = max(big), min(big)
    tied = [r for r in big if r is top or not real(fig, p, top[1], p, r[1], a)]
    gap_real = real(fig, p, top[1], p, low[1], a)
    span = lambda rs: f"{min(r[0] for r in rs):.1f}% to {max(r[0] for r in rs):.1f}%"   # noqa: E731
    what = answer_phrase(doc, fig["answers"][a])
    dim = fig["columns"][0][0]   # "adults in households earning under $50k", "adults in China aged 18-25"
    place = "in China" if "China" in who else "in the US"
    group = lambda rs, again=False: (f"{'adults in China' if 'China' in who else 'US adults'} in households earning {names([r[2][0].lower() + r[2][1:] for r in rs])}"   # noqa: E731
                        if dim == "income_band" else f"{'adults in China' if 'China' in who else 'US adults'} aged {names([r[2] for r in rs])}"
                        if dim == "age_band" and rs[0][2][:1].isdigit() else names([r[2] for r in rs]) + ("" if again else f" {place}"))   # the country once
    start = when_said(fig["periods"][p], newest)
    if not gap_real:
        lead = f"{start}, {group(big)} were about equally likely to say they {what} ({span(big)}); the differences could be chance."
    elif len(tied) > 1:
        lead = f"{start}, {group(tied)} were about equally likely to say they {what} ({span(tied)}); {group([low], True)} were the least likely ({low[0]:.1f}%)."
    else:
        lead = f"{start}, {group([top])} were the most likely to say they {what} ({top[0]:.1f}%), and {group([low], True)} the least likely ({low[0]:.1f}%)."
    note = top[2] + (f"; about the same as {names([r[2] for r in tied if r is not top])}" if len(tied) > 1 else "")
    cards = extremes((note, top[0]), (low[2], low[0]), gap_real)
    labels = [GROUPS.get(v, v) for _, v in fig["columns"]]
    small = [r[3] < SMALL for r in rows]
    if p:
        chart = {"kind": "line", "categories": [q["label"] for q in fig["periods"]], "dates": [day_of(q) for q in fig["periods"]],
                 "series": [{"name": labels[c], "data": series(fig, a, c)} for c in range(len(labels))]}
    else:
        chart = {"kind": "columns", "categories": labels, "small": small,
                 "series": [{"name": fig["periods"][p]["label"], "data": [None if r[0] is None else round(r[0], 1) for r in rows]}]}
    notes = ["Fewer than 50 people answered in a marked group: read with caution. Groups with fewer than 50 people are not compared."] if any(small) else []
    return {"type": "T3", "lead": lead, "cards": cards, "chart": chart, "notes": notes}


def ranked_answers(fig: dict, doc: dict, who: str, newest: str, single: bool) -> dict | None:
    """T4 (and a single choice's most common answer), in the latest period: the top answer, the next, whether the gap
    between them is real; the top ten drawn biggest first (a single choice in its own order)."""
    p = len(fig["periods"]) - 1
    rows = sorted(((exact(fig, p, 0, a), a) for a in range(len(fig["answers"])) if not NOT_RANKED.match(fig["answers"][a])
                   and not NET.search(fig["answers"][a]) and exact(fig, p, 0, a) is not None), reverse=True)
    if len(rows) < 2:
        return None
    (x, a), (y, b) = rows[0], rows[1]
    level = not significant(x, int(fig["bases"][p, 0, a]), y, int(fig["bases"][p, 0, b]))   # two answers of one survey
    label = lambda i: fig["answers"][i]   # noqa: E731
    start = when_said(fig["periods"][p], newest)
    third = f" and {label(rows[2][1])} ({rows[2][0]:.1f}%)" if len(rows) > 2 else ""
    if single:
        lead = (f"{start}, {label(a)} and {label(b)} were the most common answers among {who}, about level ({x:.1f}% and {y:.1f}%)." if level else
                f"{start}, the most common answer among {who} was {label(a)} ({x:.1f}%), ahead of {label(b)} ({y:.1f}%){third}.")
    else:
        lead = (f"{start}, {label(a)} and {label(b)} were about level: {x:.1f}% of {who} {answer_phrase(doc, label(a))}, {y:.1f}% {label(b)}." if level else
                f"{start}, {label(a)} was the most common answer: {x:.1f}% of {who} {answer_phrase(doc, label(a))}, ahead of {label(b)} ({y:.1f}%){third}.")
    cards = [{"label": "Top answer", "value": f"{x:.1f}%", "note": label(a), "tone": "main"},
             {"label": "Second", "value": f"{y:.1f}%", "note": label(b), "tone": ""},
             {"label": "Gap between them", "value": f"{round(x, 1) - round(y, 1):.1f} pts", "note": "Could be chance" if level else "A real gap", "tone": ""}]
    drawn = sorted(rows, key=lambda r: r[1]) if single else rows[:TOP_BARS]
    return {"type": "T4", "lead": lead, "cards": cards,
            "chart": {"kind": "columns" if single else "bars", "categories": [label(i) for _, i in drawn],
                      "series": [{"name": fig["periods"][p]["label"], "data": [round(v, 1) for v, _ in drawn]}]},
            "notes": [] if single else ["People could choose more than one answer, so the shares add up to more than 100%."]}


def two_periods(fig: dict, doc: dict, a: int, who: str, shown: list[int]) -> dict | None:
    """T5: two periods compared for the main answer; up to eight answers drawn as paired columns."""
    now, was = exact(fig, 1, 0, a), exact(fig, 0, 0, a)
    if now is None or was is None:
        return None
    sure = real(fig, 0, 0, 1, 0, a)
    first, second = fig["periods"][0]["label"], fig["periods"][1]["label"]
    words = change_words(now, was, sure)
    lead = f"{on(second)[0].upper()}{on(second)[1:]}, {now:.1f}% of {who} {answer_phrase(doc, fig['answers'][a])}, {words} {on(first) if words.startswith('about') else first} ({was:.1f}%)."
    cards = [{"label": first, "value": f"{was:.1f}%", "note": fig["answers"][a], "tone": ""},
             {"label": second, "value": f"{now:.1f}%", "note": fig["answers"][a], "tone": "main"},
             change_card("Change", now, was, sure) | {"note": "A real change" if sure and round(now - was, 1) else "Could be chance"}]
    drawn = [i for i in shown if exact(fig, 0, 0, i) is not None and exact(fig, 1, 0, i) is not None][:PAIRED_MAX]
    return {"type": "T5", "lead": lead, "cards": cards,
            "chart": {"kind": "paired", "categories": [fig["answers"][i] for i in drawn],
                      "series": [{"name": fig["periods"][q]["label"], "data": [round(exact(fig, q, 0, i), 1) for i in drawn]} for q in (0, 1)]}}


def amounts(fig: dict, doc: dict, who: str, newest: str, middle: str, average: int) -> dict | None:
    """T8: an amount asked in ranges: the middle answer, the average worked out from the ranges, the range chosen most;
    every range drawn in its own order (never ranked). `middle`, `average`: api/ask_figures.py middle for everyone."""
    p = len(fig["periods"]) - 1
    ranges = sorted(((band(label), a) for a, label in enumerate(fig["answers"]) if band(label) and exact(fig, p, 0, a) is not None),
                    key=lambda r: r[0][0])
    if len(ranges) < 3:
        return None
    most = max(ranges, key=lambda r: exact(fig, p, 0, r[1]))[1]
    lead = (f"{when_said(fig['periods'][p], newest)}, the middle answer among {who} was {middle}; "
            f"the average was about ${average:,} (worked out from the ranges people chose).")
    cards = [{"label": "Middle answer", "value": middle, "note": "Half chose less, half more", "tone": "main"},
             {"label": "Average (estimate)", "value": f"${average:,}", "note": "From the ranges people chose", "tone": ""},
             {"label": "Most chosen range", "value": f"{exact(fig, p, 0, most):.1f}%", "note": fig["answers"][most], "tone": ""}]
    return {"type": "T8", "lead": lead, "cards": cards,
            "chart": {"kind": "columns", "categories": [fig["answers"][a] for _, a in ranges],
                      "series": [{"name": fig["periods"][p]["label"], "data": [round(exact(fig, p, 0, a), 1) for _, a in ranges]}]},
            "notes": ["Amounts were asked in ranges, so the average is an estimate; the top range counts at its lower end."]}


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def opening(first: str, last: str, newest: str) -> str:
    """How a sentence opens for worked-out figures: "In the latest survey (23 Nov 2026)", "In the survey of 16 Nov 2026",
    "In the surveys of 2 Nov 2026 to 23 Nov 2026"."""
    if first != last:
        return f"In the surveys of {label_date(first)} to {label_date(last)}"
    return f"In the latest survey ({label_date(last)})" if last == newest else f"In the survey of {label_date(last)}"


def extremes(top: tuple, low: tuple, gap: bool) -> list[dict]:
    """The Highest / Lowest / Difference cards (T3, T6, T9, T20), from rows (name, share %, …), the difference of the shown figures."""
    return [{"label": "Highest", "value": f"{top[1]:.1f}%", "note": top[0], "tone": "main"},
            {"label": "Lowest", "value": f"{low[1]:.1f}%", "note": low[0], "tone": ""},
            {"label": "Difference", "value": f"{round(top[1], 1) - round(low[1], 1):.1f} pts", "note": "A real gap" if gap else "Could be chance", "tone": ""}]


# Figures worked out elsewhere (a combined question's plan, api/ask_plan.py; two kinds of group at once, api/assistant.py
# two_groups), laid out the same way. Each row: (name, share %, people, base).
def compared_rows(rows: list[tuple], what: str, start: str, type_: str, notes: list[str] | None = None) -> dict | None:
    """T6 / T20: groups' shares of one answer side by side (two groups: "x% of A …, compared with y% of B"; more: the highest,
    those tied with it, and the lowest), whether the gap is real; one column per group, never one under HIDDEN people."""
    rows = [r for r in rows if r[1] is not None and r[3] >= HIDDEN]
    big = [r for r in rows if r[3] >= SMALL]
    if len(big) < 2:
        return None
    sure = lambda r, s: significant(r[1], r[3], s[1], s[3])   # noqa: E731
    if len(rows) == 2:
        (x, y) = rows
        gap = sure(x, y)
        lead = (f"{start}, {x[1]:.1f}% of {x[0]} {what}, compared with {y[1]:.1f}% of {y[0]}, "
                f"{'a real difference' if gap else 'a difference that could be chance'}.")
        cards = [{"label": capital(x[0]), "value": f"{x[1]:.1f}%", "note": "", "tone": "main"},
                 {"label": capital(y[0]), "value": f"{y[1]:.1f}%", "note": "", "tone": ""},
                 {"label": "Difference", "value": f"{round(x[1], 1) - round(y[1], 1):+.1f} pts", "note": "A real difference" if gap else "Could be chance", "tone": ""}]
    else:
        top, low = max(big, key=lambda r: r[1]), min(big, key=lambda r: r[1])
        tied = [r for r in big if r is top or not sure(r, top)]
        gap = sure(top, low)
        span = lambda rs: f"{min(r[1] for r in rs):.1f}% to {max(r[1] for r in rs):.1f}%"   # noqa: E731
        who = lambda rs: "most groups" if len(rs) > 3 else names([r[0] for r in rs])   # noqa: E731  most tied: said so, not listed
        lead = (f"{start}, {who(big)} were about equally likely to say they {what} ({span(big)}); the differences could be chance." if not gap else
                f"{start}, {who(tied)} were {'about equally' if len(tied) > 1 else 'the most'} likely to say they {what} ({span(tied)}), "
                f"and {low[0]} the least likely ({low[1]:.1f}%).")
        cards = extremes(top, low, gap)
    small = [r[3] < SMALL for r in rows]
    return {"type": type_, "lead": lead, "cards": cards, "notes": (notes or []) + (
                ["Fewer than 50 people answered in a marked group: read with caution. Groups with fewer than 50 people are not compared."] if any(small) else []),
            "chart": {"kind": "columns", "categories": [capital(r[0]) for r in rows], "small": small,
                      "series": [{"name": start, "data": [round(r[1], 1) for r in rows]}]}}


def series_rows(points: list[tuple], what: str, who: str, newest: str) -> dict | None:
    """A combined question's share week by week: points (day, share %, people, base), the latest against the first; a week
    under HIDDEN people is left out."""
    points = [p for p in points if p[1] is not None and p[3] >= HIDDEN]
    if len(points) < 2:
        return None
    (d0, was, _, b0), (d1, now, _, b1) = points[0], points[-1]
    sure = significant(now, b1, was, b0)
    lead = f"{opening(d1, d1, newest)}, {now:.1f}% of {who} {what}, {change_words(now, was, sure)} on {label_date(d0)} ({was:.1f}%)."
    low, high = min(p[1] for p in points), max(p[1] for p in points)
    return {"type": "T2", "lead": lead, "notes": [],
            "cards": [{"label": "Latest survey", "value": f"{now:.1f}%", "note": label_date(d1), "tone": "main"},
                      change_card(f"Since {label_date(d0)}", now, was, sure),
                      {"label": "Range", "value": f"{round(high, 1) - round(low, 1):.1f} pts", "note": f"Between {low:.1f}% and {high:.1f}%", "tone": ""}],
            "chart": {"kind": "line", "categories": [label_date(p[0]) for p in points], "dates": [p[0] for p in points],
                      "series": [{"name": what, "data": [round(p[1], 1) for p in points]}]}}


def ranked_rows(rows: list[tuple], start: str, who: str) -> dict | None:
    """T4 from worked-out rows (a combined question's top answers among a group): the top answer, the next, the gap."""
    rows = sorted((r for r in rows if r[1] is not None and r[3] >= HIDDEN and not NOT_RANKED.match(r[0])), key=lambda r: -r[1])
    if len(rows) < 2:
        return None
    (a, b) = rows[:2]
    level = not significant(a[1], a[3], b[1], b[3])
    lead = (f"{start}, {a[0]} and {b[0]} were about level among {who} ({a[1]:.1f}% and {b[1]:.1f}%)." if level else
            f"{start}, {a[0]} was the most common answer among {who} ({a[1]:.1f}%), ahead of {b[0]} ({b[1]:.1f}%).")
    return {"type": "T4", "lead": lead, "notes": [],
            "cards": [{"label": "Top answer", "value": f"{a[1]:.1f}%", "note": a[0], "tone": "main"},
                      {"label": "Second", "value": f"{b[1]:.1f}%", "note": b[0], "tone": ""},
                      {"label": "Gap between them", "value": f"{round(a[1], 1) - round(b[1], 1):.1f} pts", "note": "Could be chance" if level else "A real gap", "tone": ""}],
            "chart": {"kind": "bars", "categories": [r[0] for r in rows[:TOP_BARS]], "series": [{"name": start, "data": [round(r[1], 1) for r in rows[:TOP_BARS]]}]}}


def single_row(row: tuple, what: str, start: str, who: str, parts: list[tuple] | None = None) -> dict | None:
    """T7 / T6: one worked-out figure ("7.7% of US adults bought both online and in store"), with its parts beside it when
    they were worked out (rows too); nothing under HIDDEN people."""
    if row[1] is None or row[3] < HIDDEN:
        return None
    shown = [("Result", row[1])] + [(capital(p[0])[:60], p[1]) for p in (parts or [])[:2] if p[1] is not None and p[3] >= HIDDEN]
    cards = [{"label": name, "value": f"{share:.1f}%", "note": "" if i else start.removeprefix("In the "), "tone": "" if i else "main"}
             for i, (name, share) in enumerate(shown)]
    for card in cards[1:]:
        card["note"] = "One part on its own"
    return {"type": "T7", "lead": f"{start}, {row[1]:.1f}% of {who} {what}.", "cards": cards,
            "notes": ["Counted person by person from each survey's answers."],
            "chart": {"kind": "columns", "categories": [name for name, _ in shown], "series": [{"name": start, "data": [round(v, 1) for _, v in shown]}]}}


def grid_items(answers: list[str], asked: list[int]) -> dict[str, list[int]]:
    """A grid's items and each item's answers ("Walmart: Very positive" … → {"Walmart": [i, …]}), or {} when the answers are
    not a grid: most answers "item: answer", with the same answer words under two items or more."""
    items: dict[str, list[int]] = {}
    for a in asked:
        if ": " in answers[a] and not NET.search(answers[a]):
            items.setdefault(answers[a].split(": ", 1)[0], []).append(a)
    endings = [answers[a].split(": ", 1)[1].lower() for members in items.values() for a in members]
    return items if len(items) >= 2 and len(endings) >= 0.5 * len(asked) and len(set(endings)) < len(endings) else {}


def grid(fig: dict, items: dict[str, list[int]], newest: str) -> dict | None:
    """T9: each item's positive side (its "positive" / "better" answers added up; a ranking grid's first answer) in the latest
    period, items under SMALL people left out: the highest, the lowest and the gap; one bar per item, the lowest always drawn."""
    p = len(fig["periods"]) - 1
    rows = []
    for item, members in items.items():
        positive = [a for a in members if any(w in fig["answers"][a].split(": ", 1)[1].lower() for w in SIDES["positive"])] or members[:1]
        base = int(max(fig["bases"][p, 0, a] for a in members))
        if base >= SMALL:
            rows.append((item, sum(exact(fig, p, 0, a) or 0 for a in positive), base))
    if len(rows) < 2:
        return None
    rows.sort(key=lambda r: -r[1])
    top, low = rows[0], rows[-1]
    side = "positive views" if any(any(w in fig["answers"][a].lower() for w in SIDES["positive"]) for m in items.values() for a in m) else "first places"
    gap = significant(top[1], top[2], low[1], low[2])
    drawn = rows[:TOP_BARS - 1] + [low] if len(rows) > TOP_BARS else rows
    return {"type": "T9", "cards": extremes(top, low, gap),
            "lead": (f"{when_said(fig['periods'][p], newest)}, {top[0]} had the most {side} ({top[1]:.1f}%) and {low[0]} the fewest ({low[1]:.1f}%)"
                     + ("." if gap else ", a gap that could be chance.")),
            "chart": {"kind": "bars", "categories": [r[0] for r in drawn], "series": [{"name": capital(side), "data": [round(r[1], 1) for r in drawn]}]},
            "notes": [f"Each item's share counts only the people asked about it; items with fewer than {SMALL} people are left out."]}


def build(fig: dict, doc: dict, plan: dict, shown: list[int], country: str, newest: str, whole: bool = True,
          before: tuple[str, float, bool] | None = None, title: str = "", middle: tuple[str, int] | None = None) -> dict | None:
    """The answer in the manager's layout for the figures computed (api/assistant.py answer), or None for a kind this does not
    lay out yet (the screen then draws today's headline and tiles). `plan`: the question's own reading, before Ask filled in
    every wave for a question with history (so a list asked with no time is its latest ranking); `whole`: the base is everyone asked in the survey, not a
    sub-group the question was put to ("those asked"); `before`: the survey before a single latest one (date, share, whether
    the change is real), as answer() works it out; `title`: the study's title when it is not a weekly tracker; `middle`: an
    amount question's middle range and average (api/ask_figures.py middle), for T8."""
    if not shown or not fig["periods"]:
        return None
    who = PEOPLE.get(country, "adults") if whole else "those asked"
    if len(fig["columns"]) == 1 and fig["columns"][0][0] != "total":   # one group asked for: "Gen Z adults in the US", "women in China"
        value, place = GROUPS.get(fig["columns"][0][1], fig["columns"][0][1]), "in China" if country == "CN" else "in the US"
        who = (f"{value[6:]} {place}" if value.startswith("Among ") else   # a group defined by another answer ("Among GLP-1 users")
               f"{value} {place}" if value in ("men", "women") else f"{value} adults {place}")
    a = shown[0]
    many_periods = len(fig["periods"]) > 1
    asked = [i for i, label in enumerate(fig["answers"]) if not NET.search(label) and not np.isnan(fig["pct"][-1, 0, i])]   # a net is not one more answer
    single = abs(float(np.nansum(fig["pct"][-1, 0, asked])) - 100) <= 1.5   # the latest survey's answers: older wordings had others
    yes_no = fig["answers"][a].lower() in ("yes", "no")
    sides = sides_of(fig["answers"], asked) if single and not yes_no else {}
    # asked over time in its own words (not Ask's default of every wave for a question with history)
    over_time = plan.get("kind") == "trend" or bool(plan.get("grain")) or any(
        "all" in w or "from" in w or "last" in w or w.get("latest", 0) > 1 for w in plan.get("when", []))
    items = grid_items(fig["answers"], asked) if len(fig["columns"]) == 1 else {}
    if middle and len(fig["columns"]) == 1:   # "how much", "average": an amount asked in ranges
        found = amounts(fig, doc, who, newest, *middle)
    elif items:   # a grid: each item rated (or ranked) on the same answers
        found = grid(fig, items, newest)
    elif len(fig["columns"]) > 1:
        found = groups(fig, doc, a, who, newest)
    elif many_periods and len(fig["periods"]) == 2 and not fig.get("grain"):
        found = two_periods(fig, doc, a, who, shown)
    elif sides:
        found = scale(fig, who, newest, sides)
    elif many_periods and (yes_no or over_time or len(shown) == 1 and plan.get("kind") != "top"):
        found = trend(fig, doc, a, who, newest)
    elif yes_no or len(shown) == 1 and plan.get("kind") != "top":
        found = latest_value(fig, doc, a, who, newest, before)
    else:   # a list, no trend asked: its latest ranking, whatever periods were computed
        found = ranked_answers(fig, doc, who, newest, single)
    if not found:
        return None
    periods = [p for p in fig["periods"] if p["waves"]]
    span = periods[0]["label"] if len(periods) == 1 else f"{label_date(periods[0]['from'])} to {label_date(periods[-1]['to'])}"
    name = survey_name(doc["family"], country, title)
    if found["chart"]["kind"] == "line":
        found["chart"].update(periods_offered(fig))
    return {**found, "notes": found.get("notes", []), "survey": name, "source": f"{name}, {span}",
            "title": doc.get("title") or (doc.get("name") or "").strip()}
