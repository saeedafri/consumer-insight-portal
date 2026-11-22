"""Ask CIP's first step: a question in plain words → a plan (which periods, how grouped, which cuts, what is asked).

Who calls it: api/assistant.py. Rules only, no model: about a millisecond. What the question is *about* (the survey
question and its answers) is found afterwards by api/ask_index.py from the words left over (`about`).

A plan: {kind: share|count|top|trend|change, when: [period spec, ...] (two when comparing), grain: wave|biweek|
4week|month|quarter|year|None, cuts: {dim: [values] or "all"}, top: n, country: US|CN (config/countries.yml), about: str}. A period spec is one of
{"latest": k} (the k-th latest wave, 1 = latest), {"first": k}, {"last": n, "unit": wave|week|month|year},
{"year": y}, {"month": (y, m)}, {"quarter": (y, q)}, {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} or {"all": True}.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

COUNTRY_WORDS = {code: re.compile(r"\b(" + "|".join(re.escape(w) for w in c.get("ask_words", [])) + r")(?![a-z])")
                 for code, c in yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "countries.yml").read_text()).items()}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name} | \
         {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name} | {"sept": 9}
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "ten": 10, "twelve": 12}
GRAINS = [(r"\b(bi-?weekly|fortnight(ly)?|every (2|two) weeks|two-week)\b", "biweek"),
          (r"\b(4-?weekly|four-?weekly|every (4|four) weeks|4-week|four-week|rolling 4)\b", "4week"),
          (r"\b(weekly|week by week|each week|every week|by week|per week|wave by wave|each wave|every wave|each survey|every survey|survey by survey|oldest first|newest first)\b", "wave"),
          (r"\b(monthly|month by month|by month|per month|each month|every month)\b", "month"),
          (r"\b(quarterly|by quarter|per quarter|each quarter)\b", "quarter"),
          (r"\b(yearly|annually|by year|per year|each year|year by year|year over year|yoy)\b", "year")]
# cut words → (dimension, value as the question files spell it); "by <dimension>" asks for every value
CUT_VALUES = [(r"\bgen ?z\b|\bzoomers?\b", "generation", "GenZ"), (r"\bmillennials?\b", "generation", "Millennial"),
              (r"\bgen ?x\b", "generation", "GenX"), (r"\b(baby )?boomers?\b", "generation", "Boomer"),
              (r"\b(women|female|females|woman)\b", "gender", "Female"), (r"\b(men|male|males|man)\b", "gender", "Male"),
              (r"\bnortheast\b", "census_region", "Northeast"), (r"\bmidwest\b", "census_region", "Midwest"),
              (r"\b(the )?south\b(?! korea)", "census_region", "South"), (r"\b(the )?west\b", "census_region", "West"),
              (r"\burban\b", "urbanicity", "Urban"), (r"\bsuburban\b", "urbanicity", "Suburban"), (r"\brural\b", "urbanicity", "Rural"),
              # "young people" is the survey's youngest age band, "older people" its oldest (config/weighting.yml age_band)
              (r"\b(young|younger) (people|adults|consumers|shoppers|americans)\b", "age_band", "18-29"),
              (r"\b(old|older|elderly) (people|adults|consumers|shoppers|americans)\b|\bseniors\b", "age_band", "Over 60")]
# "high income" is the bands from $100,000, "low income" those under $50,000 (the weekly survey's bands since 2022), each
# shown as one figure (ask_figures.compute merge): read as a subject they refused 1 in 25 unanswered bank questions
# ("Thanksgiving spending for high income"), and as bands they gave 3 to 7 columns for one asked group (22 Nov 2026)
# by dollar range, so any wave's bands fit: the weekly survey's since 2022 and older ones ("$100,000-$124,999", "$200,000+");
# a fixed list of 2022 bands sent "high income" in an older wave to another study (22 Nov 2026)
# or by their dollars: "households earning below $50,000, $50,000-$99,999, and $100,000 or more" (ChatGPT's key, 22 Nov 2026)
INCOME_GROUPS = {"Low income (under $50,000)": (r"\b(low|lower)[- ](income|earners?|earning)\b|\b(below|under|less than) \$50,?000\b", (0, 50_000)),
                 "Middle income ($50,000-$99,999)": (r"\b(middle|mid)[- ](income|earners?|earning)\b|\bmiddle class\b|\$50,?000 ?(-|–|to) ?\$?99,?999\b",
                                                     (50_000, 100_000)),
                 "High income ($100,000 or more)": (r"\b(high|higher|upper)[- ](income|earners?|earning)\b|\baffluent\b|\bwealthy\b"
                                                    r"|\$100,?000(\+| or more| and (over|above|up))|\b(over|above) \$100,?000\b", (100_000, 10**9))}
CUT_VALUES += [(pattern, "income_band", label) for label, (pattern, _) in INCOME_GROUPS.items()]
CUT_DIMS = [(r"\b(?:by|and) (generation|generations|gen)\b|\b(?:across|each|every|all) generations?\b|\bwhich generations?\b", "generation"),
            (r"\b(?:by|and) (gender|sex)\b|\bmen (and|vs|versus|or) women\b|\bwomen (and|vs|versus|or) men\b", "gender"),
            (r"\b(?:by|and) age( group| band)?s?\b|\bage (group|band)s?\b(?:\s*\([^)]*\))?|\bwhich age( group)?s?\b(?:\s*\([^)]*\))?", "age_band"), (r"\b(?:by|and) (household )?income\b|\bincome (group|band|level)s?\b(?:\s*\([^)]*\))?", "income_band"),
            (r"\bby region\b|\bregions?\b|\b(the )?south (vs|versus|and|or) (the )?west\b", "census_region"), (r"\burbanicity\b|\burban,? suburban\b", "urbanicity")]
KINDS = [(r"\bhow many (people|respondents|users|consumers|shoppers|adults|americans)\b|\bnumber of (people|respondents)\b", "count"),
         (r"\b(top|winner|won|most popular|leading|leader|highest|best|biggest|largest|most common(ly)?|rank|ranking|favou?rite)\b|\bwhich\b(?=[^?]*\bmost\b)", "top"),   # "which retailers do people shop at most?" ranks; only "which" leaves the
                                                       # subject ("which five retailers were most used" lost "retailers", 22 Nov 2026)
         (r"\b(trend|over time|history|historically|evolution|track(ed)?|rising or falling|going up or down|up or down)\b", "trend"),
         (r"\b(change|changed|increase|increased|decrease|decreased|grow|grew|growth|rise|rose|fall|fell|drop|dropped|shift)\b", "change")]
POOLED = re.compile(r"\b(pooled|combined|all together|in total)\b")   # "the last 4 surveys pooled": one figure over them
FILLER = re.compile(r"\b(what|which|who|how|many|much|percent(age)?|share|proportion|of|the|in|on|for|did|do|does|is|are|was|"
                    r"were|have|has|had|people|respondents|consumers|shoppers|users|americans|adults|show|me|tell|give|"
                    r"please|can|you|across|between|and|vs|versus|compare|compared|comparison|to|from|with|wave|waves|"
                    r"survey|surveys|latest|recent|week|weeks|month|months|year|years|quarter|last|past|this|that|"
                    r"chart|graph|data|figure|figures|number|a|an|by|per|each|every|all|time|since|until|through|more|less|fewer|"
                    r"than|any|it|its|they|their|them|we|our|us|about|there|at|or|pooled|combined|these|those|using|correct)\b", re.I)



def by_cut(text: str) -> str:
    """The question with the groups it names said as their cut ("Amazon Gen Z vs Boomers" → "Amazon vs by generation"),
    for Ask's reader (api/ask_model.py read_pick): it read named groups as no survey question at all, and "by generation"
    rightly (21 Nov 2026). The groups themselves stay the rules' reading (read: cuts)."""
    dims = []
    for pattern, dim, *_ in CUT_VALUES + CUT_DIMS:   # "which age group (18-29, …)" too: the reader took D2, "What is your age group?"
        text, found = re.subn(pattern, " ", text, flags=re.I)
        if found:
            dims.append(dim)
    return " ".join(text.split()) + "".join(f" by {d.replace('census_', '').replace('_band', '')}" for d in dict.fromkeys(dims))

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
    # a day ("16 Nov 2026", "Nov 16, 2026", "2026-11-16", "16 Nov"): the survey of that week, its wave dated that day or
    # up to 6 days before; read as the whole month it gave "16 Nov 2026" three waves pooled (Gemini's benchmark, 22 Nov 2026)
    day = (rf"(\d{{1,2}})\s+({month_names})\.?,?(?:\s+(\d{{4}}))?(?!\s*\d)|({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?"
           rf"(?:\s+(\d{{4}}))?(?!\s*\d)|(\d{{4}})-(\d\d)-(\d\d)")
    def on(g) -> date:
        if g[6]:
            return date(int(g[6]), int(g[7]), int(g[8]))
        dd, mm, yy = (g[0], g[1], g[2]) if g[0] else (g[4], g[3], g[5])
        year = int(yy) if yy else today.year if (MONTHS[mm], int(dd)) <= (today.month, today.day) else today.year - 1
        return date(year, MONTHS[mm], int(dd))
    today = date.today()
    quoted = [q.span() for q in re.finditer(r"[“\"][^”\"]*[”\"]", text)]   # an answer's own name: “Target Circle Week (July 9-15, 2023)”
    inside = lambda m: any(a <= m.start() < b for a, b in quoted)   # noqa: E731
    for m in re.finditer(rf"\b(?:(?:from|between)\s+)?(?:{day})\s+(?:to|and|until|through|-)\s+(?:{day})", text):
        if inside(m):
            continue
        g = m.groups()
        take(m, {"from": str(on(g[:9]) - timedelta(days=6)), "to": str(on(g[9:]))})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(rf"\b(?:{day})", text):
        if (m[1] or m[4] or m[7]) and not inside(m) and not re.fullmatch(r"(?:4(?:th)?\s+jul(?:y)?|jul(?:y)?\.?\s+4(?:th)?)", m[0].strip()):
            # a month with no day stays a month (below); "July 4th" is the holiday (45 bank questions read it as 4 July)
            when = on(m.groups())
            take(m, {"from": str(when - timedelta(days=6)), "to": str(when)})
            text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(rf"\b(from|between)\s+({month_names})?\s*(\d{{4}})\s+(to|and|until|through|-)\s+({month_names})?\s*(\d{{4}})\b", text):
        start = f"{m[3]}-{MONTHS.get(m[2], 1):02d}-01"
        end_month = MONTHS.get(m[5], 12)
        take(m, {"from": start, "to": f"{m[6]}-{end_month:02d}-{calendar.monthrange(int(m[6]), end_month)[1]:02d}"})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(rf"\bsince\s+({month_names})\.?\s+(\d{{4}})\b", text):   # "since Aug 2025": from then on, not August alone
        take(m, {"from": f"{m[2]}-{MONTHS[m[1]]:02d}-01", "to": "9999-12-31"})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(rf"\b({month_names})\.?\s+(\d{{4}})\b", text):
        take(m, {"month": (int(m[2]), MONTHS[m[1]])})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bq([1-4])\s*(\d{4})\b|\b(\d{4})\s*q([1-4])\b", text):
        take(m, {"quarter": (int(m[2] or m[3]), int(m[1] or m[4]))})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    # the calendar as the asker reads it today: "this quarter", "year to date", "October", "Q4". A question not asked then
    # says so (api/assistant.py) instead of answering from history (Codex and Gemini reviews, 20 Nov 2026)
    quarter = (today.month + 2) // 3
    for m in re.finditer(r"\b(?:this|the current|current)\s+(month|quarter|year)\b(?!'s)|\b(year to date|ytd|so far this year)\b", text):
        take(m, {"month": {"month": (today.year, today.month)}, "quarter": {"quarter": (today.year, quarter)},
                 "year": {"year": today.year}, None: {"from": f"{today.year}-01-01", "to": today.isoformat()}}[m[1]])
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\b(?:last|previous|prior)\s+quarter\b", text):
        take(m, {"quarter": (today.year, quarter - 1) if quarter > 1 else (today.year - 1, 4)})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bq([1-4])\b", text):   # a quarter with no year: the latest one so far
        q = int(m[1])
        take(m, {"quarter": (today.year if q <= quarter else today.year - 1, q)})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    # a month with no year, after a word that makes it a date ("in October", "October vs September"): the latest one so
    # far. Never on its own: "may" is a verb and "march" a word
    bare = rf"({month_names})\b(?!\.?\s*\d)"
    for m in re.finditer(rf"\b(?:in|during|for|of|from|to|vs\.?|versus|and|than|between|through|until|compared to)\s+{bare}"
                         rf"|^(?:in\s+)?(?!may\b|march\b){bare}(?=\s+(?:vs\.?|versus|and|or|compared to)\s)", text):
        month = MONTHS[m[1] or m[2]]
        take(m, {"month": (today.year if month <= today.month else today.year - 1, month)})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bsince\s+(\d{4})\b", text):
        take(m, {"from": f"{m[1]}-01-01", "to": "9999-12-31"})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    # a year is a period after "in", "during", "since"…, or set against another year; "Valentine's Day 2025" is a topic
    for m in re.finditer(r"\b(?:in|during|throughout|for|over|across|year|of)\s+(20\d{2})\b(?!\s*(holiday|season|back|easter|"
                         r"valentine|christmas|black|cyber|prime|super|thanksgiving|halloween|mother|father|president|olympic|memorial|labor|"
                         r"independence|new year|singles|summer|spring|fall|winter|promotion|sale))", text):
        take(m, {"year": int(m[1])})
    for m in re.finditer(r"\b(20\d{2})\s+(?:vs\.?|versus|and|or|compared to|against)\s+(20\d{2})\b", text):
        take(m, {"year": int(m[1])})
        found.append((m.start(2), {"year": int(m[2])}))
    # "last 4 weeks", "previous 3 months", "past 8 weeks"; not "in the past two weeks"/"past 12 months", the survey's own
    # wording of what a question covers
    for m in re.finditer(r"\b(?:last|previous|recent|all|(?:each of |all of |in )?the)\s+(\d+|one|two|three|four|five|six|eight|ten|twelve)\s+(waves?|weeks?|months?|years?|surveys?)\b"
                         r"|\bpast\s+(\d+)\s+(waves?|weeks?|surveys?)\b(?<!past 2 weeks)", text):
        unit = (m[2] or m[4]).rstrip("s").replace("survey", "wave")
        take(m, {"last": number(m[1] or m[3]), "unit": unit})
    # "last month" is a period; "(in the) past month" is how surveys word what a question covers ("used marijuana in the
    # past month"), read as a period it answered "not asked then" (question bank, 12 Nov 2026)
    for m in re.finditer(r"\b(since|than|vs\.?|versus|compared (?:to|with)|from)?\s*(?:last|previous)\s+(week|month|year)\b", text):
        take(m, {"latest": 2} if m[2] == "week" else {"last": 1, "unit": m[2], "previous": True})
        if m[1] and m[2] != "week":   # "changed since last year": that year against now, not last year against the one before
            found.append((m.end(), {"latest": 1}))
    for m in re.finditer(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?:latest|most recent|last)\s+(wave|survey|week)\b", text):
        take(m, {"latest": ORDINALS[m[1]]})
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\bfirst\s+(?:and|vs\.?|versus|to)\s+(?:the\s+)?(latest|last|most recent|newest)\s+(?:wave|survey|week)s?\b", text):
        take(m, {"first": 1})   # "the first and latest wave": two periods
        found.append((m.end(), {"latest": 1}))
        text = text[:m.start()] + " " * len(m[0]) + text[m.end():]
    for m in re.finditer(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(wave|survey|week)\b", text):
        take(m, {"first": ORDINALS[m[1]]})
    for m in re.finditer(r"\b(previous|prior)\s+(wave|survey|week)\b|\bweek before\b", text):
        take(m, {"latest": 2})
    dated = any(k in spec for _, spec in found for k in ("from", "month", "year", "quarter"))
    for m in re.finditer(r"\b(latest|most recent|this week'?s?|current|newest|this wave|this survey|last wave|last survey|right now|currently|"
                         r"at the moment|these days|nowadays)\b", text):   # "right now" kept the economy question below a match (20 Nov 2026)
        if dated and m[1] in ("current", "currently", "right now", "at the moment", "these days", "nowadays"):
            spans.append(m.span())   # "currently using" in the 16 Nov survey: that survey, not the latest one as well
            continue
        take(m, {"latest": 1})
    for m in re.finditer(r"\b(all|every|each) (waves|surveys|weeks|time)\b|\ball wave\b|\ball[- ]time\b|\bover time\b|\bhistor(y|ically)\b", text):
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
    # "in each of the four survey weeks", "compare across the AI shopping waves": one figure per wave, not one pooled over
    # them (it pooled 7 of ChatGPT's 40 answer-key questions, 22 Nov 2026); not stripped from the subject ("AI shopping")
    if not grain and re.search(r"\beach of the\b|\bacross (?:the |these |all |those )?(?:[\w-]+ ){0,3}?(?:waves|weeks|surveys)\b", text) \
            and not POOLED.search(text):
        grain = "wave"
    kind = next((k for pattern, k in KINDS if re.search(pattern, text)), "share")
    if any("from" in w for w in when):   # "the last 4 surveys (26 Oct to 16 Nov)": the dates said, once
        when = [w for w in when if "last" not in w]
    if (kind == "share" and (grain or any("all" in w or "from" in w for w in when))) or (kind == "count" and {"all": True} in when):
        kind = "trend"   # "last 4 weeks" alone is one pooled figure; with a grain ("monthly") it is a series, and so is "how
                         # many" in all waves (one count over every wave before: "How many people bought Amazon prime in all
                         # Waves", fresh set, 15 Nov 2026)
    if kind == "change" and when == [{"latest": 1}] and grain == "wave":   # "the latest share and its weekly change": the
        when = [{"latest": 2}, {"latest": 1}]                              # week before and the latest (ChatGPT's key, 22 Nov 2026)
    if kind == "trend" and not grain and POOLED.search(text):
        kind = "share"   # "the last 4 surveys pooled": one figure over them
    cuts: dict = {}
    for pattern, dim in CUT_DIMS:
        if re.search(pattern, text):
            cuts[dim] = "all"
    for pattern, dim, value in CUT_VALUES:
        if re.search(pattern, text) and cuts.get(dim) != "all":
            cuts.setdefault(dim, []).append(value)
    named = [label for label, (pattern, _) in INCOME_GROUPS.items() if re.search(pattern, text)]
    if re.search(r"\b(each|every|all|by|across) income groups?\b|\bincome groups? \(", text):
        named = list(INCOME_GROUPS)   # "each income group (low, $50,000-$99,999, high)": the three
    merge = {label: INCOME_GROUPS[label][1] for label in named}
    if merge:
        cuts["income_band"] = "all"   # every band, summed into the groups named (ask_figures.compute merge)
    # "which five retailers were most used", "the five most commonly purchased categories"
    top = re.search(r"\b(?:top|which)\s+(\d+|three|five|ten)\b|\b(\d+|three|five|ten)(?= most\b)", text)
    # waves are only ever compared within one country (config/countries.yml): "China" asks the China survey, no name the first
    country = next((code for code, words in COUNTRY_WORDS.items() if words.search(text)), next(iter(COUNTRY_WORDS)))
    about = re.sub(r"[\u201c\"](yes|no|don't know|not sure)[\u201d\"]", " ", rest)   # a quoted Yes is an answer, not the subject (it found the tax-return question)
    for words in COUNTRY_WORDS.values():
        about = words.sub(" ", about)
    for pattern, *_ in CUT_DIMS + CUT_VALUES + GRAINS + KINDS:   # before the filler words: "by generation" is one phrase
        about = re.sub(pattern, " ", about)
    about = FILLER.sub(" ", re.sub(r"\b(20[12]\d|q[1-4]|\d+)\b", " ", about))
    about = re.sub(rf"\b({'|'.join(MONTHS)})\b", " ", about)
    return {"question": text, "country": country, "kind": kind, "when": when, "grain": grain, "cuts": cuts, "top": number(top[1] or top[2]) if top else None,
            "merge": merge, "compare": len(when) >= 2 or bool(re.search(r"\b(compare|compared|versus|vs\.?|against)\b", text)),
            "about": " ".join(re.findall(r"[a-z0-9$%'-]+", about))}
