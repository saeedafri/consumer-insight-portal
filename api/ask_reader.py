"""Ask CIP's first step: a question in plain words → a plan (which periods, how grouped, which cuts, what is asked).

Who calls it: api/assistant.py. Rules only, no model: about a millisecond. What the question is *about* (the survey
question and its answers) is found afterwards by api/ask_index.py from the words left over (`about`).

A plan: {kind: share|count|top|trend|change, when: [period spec, ...] (two when comparing), grain: wave|biweek|
4week|month|quarter|year|None, cuts: {dim: [values] or "all"}, top: n, about: str}. A period spec is one of
{"latest": k} (the k-th latest wave, 1 = latest), {"first": k}, {"last": n, "unit": wave|week|month|year},
{"year": y}, {"month": (y, m)}, {"quarter": (y, q)}, {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} or {"all": True}.
"""
from __future__ import annotations

import calendar
import re

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name} | \
         {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name} | {"sept": 9}
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "ten": 10, "twelve": 12}
GRAINS = [(r"\b(bi-?weekly|fortnight(ly)?|every (2|two) weeks|two-week)\b", "biweek"),
          (r"\b(4-?weekly|four-?weekly|every (4|four) weeks|4-week|four-week|rolling 4)\b", "4week"),
          (r"\b(weekly|week by week|each week|every week|by week|per week|wave by wave|each wave|every wave)\b", "wave"),
          (r"\b(monthly|month by month|by month|per month|each month|every month)\b", "month"),
          (r"\b(quarterly|by quarter|per quarter|each quarter)\b", "quarter"),
          (r"\b(yearly|annually|by year|per year|each year|year by year|year over year|yoy)\b", "year")]
# cut words → (dimension, value as the question files spell it); "by <dimension>" asks for every value
CUT_VALUES = [(r"\bgen ?z\b|\bzoomers?\b", "generation", "GenZ"), (r"\bmillennials?\b", "generation", "Millennial"),
              (r"\bgen ?x\b", "generation", "GenX"), (r"\b(baby )?boomers?\b", "generation", "Boomer"),
              (r"\b(women|female|females|woman)\b", "gender", "Female"), (r"\b(men|male|males|man)\b", "gender", "Male"),
              (r"\bnortheast\b", "census_region", "Northeast"), (r"\bmidwest\b", "census_region", "Midwest"),
              (r"\b(the )?south\b(?! korea)", "census_region", "South"), (r"\b(the )?west\b", "census_region", "West"),
              (r"\burban\b", "urbanicity", "Urban"), (r"\bsuburban\b", "urbanicity", "Suburban"), (r"\brural\b", "urbanicity", "Rural")]
CUT_DIMS = [(r"\bby (generation|generations|gen)\b|\bacross generations\b", "generation"),
            (r"\bby (gender|sex)\b|\bmen (and|vs|versus) women\b|\bwomen (and|vs|versus) men\b", "gender"),
            (r"\bby age\b|\bage (group|band)s?\b", "age_band"), (r"\bby income\b|\bincome (group|band|level)s?\b", "income_band"),
            (r"\bby region\b|\bregions?\b", "census_region"), (r"\burbanicity\b|\burban,? suburban\b", "urbanicity")]
KINDS = [(r"\bhow many (people|respondents|users|consumers|shoppers|adults|americans)\b|\bnumber of (people|respondents)\b", "count"),
         (r"\b(top|winner|won|most popular|leading|leader|highest|best|biggest|largest|most common|rank|ranking|favou?rite)\b", "top"),
         (r"\b(trend|over time|history|historically|evolution|track(ed)?)\b", "trend"),
         (r"\b(change|changed|increase|increased|decrease|decreased|grow|grew|growth|rise|rose|fall|fell|drop|dropped|shift)\b", "change")]
FILLER = re.compile(r"\b(what|which|who|how|many|much|percent(age)?|share|proportion|of|the|in|on|for|did|do|does|is|are|was|"
                    r"were|have|has|had|people|respondents|consumers|shoppers|users|americans|adults|show|me|tell|give|"
                    r"please|can|you|across|between|and|vs|versus|compare|compared|comparison|to|from|with|wave|waves|"
                    r"survey|surveys|latest|recent|week|weeks|month|months|year|years|quarter|last|past|this|that|"
                    r"chart|graph|data|figure|figures|number|a|an|by|per|each|every|all|time|since|until|through|more|less|fewer|"
                    r"than|any|it|they|their|them|we|our|us|about|there|at|or)\b", re.I)


def number(word: str) -> int:
    return int(word) if word.isdigit() else NUMBERS.get(word, 1)


def periods(text: str) -> tuple[list[dict], str]:
    """Every period the question names, in the order named, and the text with those phrases blanked out."""
    found: list[tuple[int, dict]] = []
    spans: list[tuple[int, int]] = []

    def take(m, spec):
        found.append((m.start(), spec))
        spans.append(m.span())
    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    for m in re.finditer(rf"\b(from|between)\s+({month_names})?\s*(\d{{4}})\s+(to|and|until|through|-)\s+({month_names})?\s*(\d{{4}})\b", text):
        start = f"{m[3]}-{MONTHS.get(m[2], 1):02d}-01"
        end_month = MONTHS.get(m[5], 12)
        take(m, {"from": start, "to": f"{m[6]}-{end_month:02d}-{calendar.monthrange(int(m[6]), end_month)[1]:02d}"})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(rf"\b({month_names})\.?\s+(\d{{4}})\b", text):
        take(m, {"month": (int(m[2]), MONTHS[m[1]])})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bq([1-4])\s*(\d{4})\b|\b(\d{4})\s*q([1-4])\b", text):
        take(m, {"quarter": (int(m[2] or m[3]), int(m[1] or m[4]))})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bsince\s+(\d{4})\b", text):
        take(m, {"from": f"{m[1]}-01-01", "to": "9999-12-31"})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    # a year is a period after "in", "during", "since"…, or set against another year; "Valentine's Day 2025" is a topic
    for m in re.finditer(r"\b(?:in|during|throughout|for|over|across|year|of)\s+(20[12]\d)\b(?!\s*(holiday|season|back|easter|"
                         r"valentine|christmas|black|cyber|prime|super|thanksgiving|halloween|mother|father|president|olympic|memorial|labor|"
                         r"independence|new year|singles|summer|spring|fall|winter|promotion|sale))", text):
        take(m, {"year": int(m[1])})
    for m in re.finditer(r"\b(20[12]\d)\s+(?:vs\.?|versus|and|or|compared to|against)\s+(20[12]\d)\b", text):
        take(m, {"year": int(m[1])})
        found.append((m.start(2), {"year": int(m[2])}))
    # "last 4 weeks", "previous 3 months", "past 8 weeks"; not "in the past two weeks"/"past 12 months", the survey's own
    # wording of what a question covers
    for m in re.finditer(r"\b(?:last|previous|recent)\s+(\d+|one|two|three|four|five|six|eight|ten|twelve)\s+(waves?|weeks?|months?|years?|surveys?)\b"
                         r"|\bpast\s+(\d+)\s+(waves?|weeks?|surveys?)\b(?<!past 2 weeks)", text):
        unit = (m[2] or m[4]).rstrip("s").replace("survey", "wave")
        take(m, {"last": number(m[1] or m[3]), "unit": unit})
    for m in re.finditer(r"\b(?:last|past|previous)\s+(week|month|year)\b", text):
        take(m, {"latest": 2} if m[1] == "week" else {"last": 1, "unit": m[1], "previous": True})
    for m in re.finditer(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?:latest|most recent|last)\s+(wave|survey|week)\b", text):
        take(m, {"latest": ORDINALS[m[1]]})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(wave|survey|week)\b", text):
        take(m, {"first": ORDINALS[m[1]]})
    for m in re.finditer(r"\b(previous|prior)\s+(wave|survey|week)\b|\bweek before\b", text):
        take(m, {"latest": 2})
    for m in re.finditer(r"\b(latest|most recent|this week'?s?|current|newest|this wave|last wave|last survey)\b", text):
        take(m, {"latest": 1})
    for m in re.finditer(r"\b(all|every|each) (waves|surveys|weeks|time)\b|\ball[- ]time\b|\bover time\b|\bhistor(y|ically)\b", text):
        take(m, {"all": True})
    found.sort(key=lambda f: f[0])
    seen, out = set(), []
    for _, spec in found:
        key = repr(sorted(spec.items()))
        if key not in seen:
            seen.add(key)
            out.append(spec)
    for lo, hi in spans:
        text = text[:lo] + " " * (hi - lo) + text[hi:]
    return out, text


def read(question: str) -> dict:
    """The plan for one question (see the module header)."""
    text = " ".join(question.lower().replace("’", "'").split())
    when, rest = periods(text)
    grain = next((g for pattern, g in GRAINS if re.search(pattern, text)), None)
    kind = next((k for pattern, k in KINDS if re.search(pattern, text)), "share")
    if kind == "share" and (grain or any("all" in w or "from" in w for w in when)):
        kind = "trend"   # "last 4 weeks" alone is one pooled figure; with a grain ("monthly") it is a series
    cuts: dict = {}
    for pattern, dim in CUT_DIMS:
        if re.search(pattern, text):
            cuts[dim] = "all"
    for pattern, dim, value in CUT_VALUES:
        if re.search(pattern, text) and cuts.get(dim) != "all":
            cuts.setdefault(dim, []).append(value)
    top = re.search(r"\btop\s+(\d+|three|five|ten)\b", text)
    about = rest
    for pattern, *_ in CUT_DIMS + CUT_VALUES + GRAINS + KINDS:   # before the filler words: "by generation" is one phrase
        about = re.sub(pattern, " ", about)
    about = FILLER.sub(" ", re.sub(r"\b(20[12]\d|q[1-4]|\d+)\b", " ", about))
    about = re.sub(rf"\b({'|'.join(MONTHS)})\b", " ", about)
    return {"question": text, "kind": kind, "when": when, "grain": grain, "cuts": cuts, "top": number(top[1]) if top else None,
            "compare": len(when) >= 2 or bool(re.search(r"\b(compare|compared|versus|vs\.?|against)\b", text)),
            "about": " ".join(re.findall(r"[a-z0-9$%'-]+", about))}
