"""Ask's plan reader, part 1: the survey questions a question may need, found part by part.

A question such as "Among GLP-1 users on 16 Nov, what share bought footwear?" needs two survey questions (GLP-1 use for
the group, footwear for what is counted). Searched whole, the second often ranks low; searched part by part, and only in
the weeks the question names, every question a plan needs was among the candidates for 124 of the hard test set's 126
plans, against 114 searched whole (scripts/ask_hard.py --candidates, 22 Nov 2026). A trained search model was not the
answer: 12 of them (13-15 Nov) found topics better but were confidently wrong more often
(docs/research/ask-cip-model-training.md).

Who calls it: scripts/ask_hard.py --candidates (the recall check); next, the plan filler that gives each candidate its
role (what is counted, the group, the split) and runs the plan with api/ask_engine.py.
"""
from __future__ import annotations

import re

from etl.serving import p_value

from api import ask_figures, ask_reader
from api.ask_reader import POOLED
from api.ask_index import Index

# where a question splits into the things it joins: "among X, Y", "X who Y", "X and Y", "X vs Y", "Y because of X"
SPLIT = re.compile(r",|;|\?|\b(?:among|of people who|of those who|who|and|vs\.?|versus|or|than|between|because of|due to|for)\b", re.I)
RECALL = re.compile(r"\b(?:in|over|during|within) the (?:last|past) (?:two|2|seven|7|three|3|six|6|twelve|12|30) (?:weeks|days|months)\b")
PER_PART = 10   # candidates kept per part: the needed question was in a part's top 10 for 124 of 126 plans, top 5 for 121


def parts(question: str) -> list[str]:
    """The question and its pieces of two words or more: "Among GLP-1 users on 16 Nov, what share bought footwear?" gives
    the whole, "GLP-1 users on 16 Nov" and "what share bought footwear"."""
    return [question] + [p.strip() for p in SPLIT.split(question) if p and len(p.strip().split()) >= 2]


def weeks(question: str, ids: dict[str, int]) -> set[int] | None:
    """The survey ids of the weeks a question names ("16 Nov", "the last four weeks"), from Ask's own period reading
    over the tracker's fielded dates; None when it names none (every week may answer)."""
    # a question's own recall period is wording, not a time ("used AI in the last two weeks", "over the last 12 months")
    text = RECALL.sub(" ", " ".join(question.lower().replace("’", "'").split()))
    specs, _ = ask_reader.periods(text)
    if not specs and (m := re.search(r"\b(?:last|past) (\d+|four|five|six|eight|ten|twelve)\b(?! (?:weeks|days|months|years))", text)):
        specs = [{"last": ask_reader.number(m[1]), "unit": "wave"}]   # "every week of the last 10"
    if any("from" in s for s in specs):   # a day named ("16 Nov") is the time; "this year" beside it is wording
        specs = [s for s in specs if "from" in s]
    dates = sorted(ids)
    picked = {ids[dates[i]] for spec in specs for i in ask_figures.pick(spec, dates)}
    return picked or None


def candidates(question: str, index: Index, visible: set[int], ids: dict[str, int]) -> list[dict]:
    """Every survey question any part of the question finds, best rank first, each with the part that found it."""
    named = weeks(question, ids)
    within = visible & named if named else visible
    found: dict[str, dict] = {}
    for part in parts(question):
        for rank, hit in enumerate(index.retrieve(part, ask_reader.read(part), PER_PART, within)):
            if hit["key"] not in found or rank < found[hit["key"]]["rank"]:
                found[hit["key"]] = {**hit, "rank": rank, "part": part}
    return sorted(found.values(), key=lambda h: h["rank"])


# ---- the plan filler (v0, rules over Ask's own reader): the question's structure, each part's survey question ----
# Who calls it: scripts/ask_hard.py --filler (scored through api/ask_engine.py against the raw-file figures); next, Ask.
# v0 reads structure with patterns and picks each part's question with Ask's existing answer path; a trained one-pass
# model replaces the pieces the hard test set shows these rules get wrong (step 4 of the Ask rebuild, 22 Nov 2026).

GROUP_WORDS = r"(?:people|those|respondents|shoppers|buyers|users|purchasers|consumers|adults)"
AMONG = re.compile(rf"\bamong\s+(.+?)(?:,|:|\?|\s+(?=(?:what|how|which|do|did|does|are|is|where|why)\b))\s*(.*)$"
                   rf"|\bof\s+(?:the\s+)?{GROUP_WORDS}\s+who\s+(.+?),\s*(.*)$", re.I)
VERSUS = re.compile(r"(.+?)\s+(?:vs\.?|versus|compared with|or)\s+(.+?)(?:[,?.]|$)", re.I)
DID_AND_NOT = re.compile(r"\b(?:who\s+)?did and did not\s+(.+?)(?:\s+because|\s+due|,|\?|$)", re.I)
TOP = re.compile(r"\btop\s*(\d+|three|five|ten)\b|\b(?:which|what|where)\b.*\b(?:most|leading)\b|\b(\d+|three|five|ten) most\b", re.I)
COUNTS = re.compile(r"\b(breakdown|main reason|why are|how satisfied|preferred way|more or less than|for work|compare with 2025|work, personal)\b", re.I)
CHAIN = re.compile(r"\bfunnel\b|→|->|\beach step\b", re.I)
NUMBERS = {"three": 3, "five": 5, "ten": 10}
DATES = re.compile(r"\b(?:on|in|the|from|to|for|of)?\s*\(?\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?: \d{4})?\)?(?: (?:survey|wave|week))?\b"
                   r"|\b(?:in |of |across |over )?(?:the )?(?:latest|(?:each of )?the last (?:\d+|two|three|four|five|six|eight|ten|twelve)(?: (?:survey|wave|week)s?)"
                   r"|last (?:survey|wave|week)|every week|each week)(?: (?:survey|wave|week)s?)?\b"
                   r"|\b(?:per|according to) the [^,?]+ survey\b", re.I)


def demographic(text: str) -> dict | None:
    """A group in people's words as a condition on the survey's own demographics, or None: men, women, 18-34, 55+,
    under 30, urban, strong Republicans, an income range."""
    t = text.lower().strip(" ,.?:-")
    if re.search(r"\b(women|female)\b", t):
        return {"q": "D1", "is": ["Female"]}
    if re.search(r"\b(men|male)\b", t):
        return {"q": "D1", "is": ["Male"]}
    if m := re.search(r"\b(\d{2})\s*[-–]\s*(\d{2})\b", t):
        return {"q": "D2", "between": [int(m[1]), int(m[2])]}
    if m := re.search(r"\b(?:under|younger than)[- ](\d{2})", t):
        return {"q": "D2", "between": [18, int(m[1]) - 1]}
    if m := re.search(r"\b(\d{2})\s*(?:\+|and (?:older|over|up)|or older)|\bover[- ](\d{2})", t):
        return {"q": "D2", "between": [int(m[1] or m[2]), 120]}
    for area in ("urban", "suburban", "rural"):
        if re.search(rf"\b{area}\b", t):
            return {"q": "D6", "is": [area.title()]}
    if "republican" in t:
        return {"q": "D7", "is": ["Strongly agree with most policies of the Republican"]}
    if "democrat" in t:
        return {"q": "D7", "is": ["Strongly agree with most policies of the Democratic"]}
    for label, (pattern, (low, high)) in ask_reader.INCOME_GROUPS.items():
        if re.search(pattern, t):
            bands = {(0, 50_000): ["under $25", "$25,000"], (50_000, 100_000): ["$50,000"], (100_000, 10**9): ["$100,000", "$150,000", "$200,000"]}
            return {"q": "D5", "is": bands[(low, high)]}
    return None


YES_NO = {"yes", "no", "don't know", "not sure", "cannot remember", "can't remember", "can’t remember", "don't recall", "prefer not to say"}
LIST_CUES = re.compile(r"\b(which|where|what (?:kind|type)s?|types?|categories|reasons?|why|how (?:much|satisfied))\b", re.I)


def offered(index: Index, key: str, within: set[int]) -> list[str]:
    """The answers a question offered in the named weeks: its file also holds the answers of codes reused for other
    questions (a "Yes" in the weekly category lists), which a plan must never pick."""
    counts = index.counts(key)
    rows = {i for i, w in enumerate(counts["waves"]) if w[0] in within}
    seen = {int(a) for w, c, a in zip(counts["w"], counts["c"], counts["a"]) if w in rows and c == 0}
    return [counts["answers"][a][2] for a in sorted(seen)]


def screener(index: Index, key: str, text: str, within: set[int]) -> str | None:
    """The module's yes/no question for a group or share of buyers ("off-price buyers" is O1 "Have you purchased from an
    off-price retailer?", not O2's list of stores): same code letters, asked in the same weeks, sharing a word."""
    from api.ask_index import stems
    prefix = re.match(r"[A-Za-z]+", index.docs[key]["qcode"])[0].upper()
    said = set(stems(text))
    for other, doc in sorted(index.docs.items(), key=lambda kv: kv[1]["qcode"]):
        if other != key and re.match(r"[A-Za-z]+", doc["qcode"])[0].upper() == prefix and not within.isdisjoint(doc["surveys"]) \
                and said & set(stems(doc["text"])):
            answers = {a.lower() for a in offered(index, other, within)}
            if "yes" in answers and answers <= YES_NO:
                return other
    return None


GENERIC = {"product", "products", "purchas", "bought", "buy", "share", "people", "past", "two", "week", "weeks", "month", "months",
           "survey", "latest", "each", "last", "online", "store", "stores", "categori"}


def items(text: str, answers: list[str]) -> list[str]:
    """The list answers a phrase names in other words: "grocery" is "Food or beverages (i.e., groceries)", "going to a bar"
    is "Gone to a bar", "none of the activities" is "None of these". The one answer sharing the most of the phrase's own
    words (by stem, the survey's frame words aside); none when two tie or nothing is shared."""
    from api.ask_index import stems
    said = set(stems(text)) - GENERIC
    did = re.search(r"\b(shoppers|users|buyers|purchasers)\b", text, re.I)   # "GenAI shoppers": those who have done it
    scored = sorted(((len(said & (set(stems(a)) - GENERIC)), bool(did and re.match(r"(have|has|yes|purchased|bought|used)\b", a, re.I)), a)
                     for a in answers), reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][:2] == scored[0][:2]):
        return []
    return [scored[0][2]]


def condition(text: str, index: Index, within: set[int], avoid: str | None = None) -> dict | None:
    """One part's survey question and answers, read by Ask's own answer path in the named weeks: its named answers (a
    total's parts, "any" for anyone who chose one) among those it offered then, Yes for a yes/no question, else any."""
    from api import assistant   # the answer path reads this module's callers; imported here, never at load
    if group := demographic(text) if len(text.split()) <= 4 else None:
        return group
    found = assistant.answer(text, index, within, True, combined=False)
    if found.get("mode") != "figures" or not found.get("sources"):
        return None
    key = found["sources"][0]["key"]
    if avoid and key == avoid:   # what is counted is never the group's own question ("Amazon's share among holiday purchasers")
        found = next((assistant.answer(text, index, within, True, key=c["key"], combined=False) for c in candidates(text, index, within, {})
                      if c["key"] != avoid and c.get("family") == index.docs[avoid]["family"]), None) or {}
        if found.get("mode") != "figures" or not found.get("sources"):
            return None
        key = found["sources"][0]["key"]
    answers = offered(index, key, within)
    yes_no = bool(answers) and {a.lower() for a in answers} <= YES_NO
    named_here = (found.get("verify") or {}).get("focus") or []
    if not yes_no and not named_here and len(answers) >= 4 and not LIST_CUES.search(text) \
            and re.search(r"\b(buy|bought|buyers?|purchas\w*|shop\w*)\b", text, re.I) and (other := screener(index, key, text, within)):
        key, answers, yes_no = other, offered(index, other, within), True
    asked_as = index.counts(key)["sources"]
    codes = {sid: asked_as[sid][0] for sid in within if sid in asked_as}   # each week's own code (FW1's older codes name q6)
    named = (found.get("verify") or {}).get("focus") or [] if key == found["sources"][0]["key"] else []
    if any(n.startswith("Any (") for n in named):
        return {"q": codes, "key": key, "any": True}
    labels = [part for n in named for part in (re.search(r"\((.+ \+ .+)\)$", n)[1].split(" + ") if re.search(r"\((.+ \+ .+)\)$", n) else [n.split(": ")[-1]])]
    labels = [a for a in labels if a in answers] or [answers[i] for i in assistant.focus(text, answers, loose=True)] \
        or (items(text, answers) if not yes_no else [])
    if not labels and "Yes" in answers:
        labels = ["Yes"]
    return {"q": codes, "key": key, **({"is": labels} if labels else {"any": True})}


MORE_LIKELY = re.compile(r"\b(?:are|were|is)\s+(.+?)\s+more likely(?:\s+than\s+(.+?))?\s+to\s+(.+?)(?:[?.]|$)", re.I)
BOTH = re.compile(r"\bboth\s+(.+?)\s+and\s+(.+?)(?=[,?]|$)|(.+?)\s+AND\s+(.+?)(?=[,?]|$)")
EITHER = re.compile(r"\beither(?: one)?\b|counting each (?:person|one) once|\bor both\b", re.I)
NOT_ALSO = re.compile(r"\b(?:did|do|does) NOT(?: also)?\b")
EACH = re.compile(r"\b(each|every)\b|\bweek by week\b", re.I)
CUT_QUESTIONS = {"gender": "D1", "urbanicity": "D6"}   # "by gender", "urban, suburban and rural": every answer of it


def sides(left: str, right: str) -> tuple[str, dict, str, dict] | None:
    """The two groups of "X vs Y" in people's words: the fewest words next to "vs" that read as a demographic, or one
    said earlier ("What share of women used AI…, compared with men")."""
    for k in range(1, 5):
        b = " ".join(right.split()[:k]).strip("?,.;:")
        if not (gb := demographic(b)):
            continue
        for a in list(reversed(left.split())) + [" ".join(left.split()[-j:]) for j in range(2, 5)]:   # one word first
            if (ga := demographic(a)) and ga != gb:
                return a, ga, b, gb
    return None


def age_bands(text: str) -> dict | None:
    """Several age bands named at once ("18-34, 35-54, 55+"): one group each."""
    found = re.findall(r"\b\d{2}\s*[-–]\s*\d{2}\b|\b\d{2}\s*\+|\b\d{2} and (?:older|over)\b", text)
    return {band: demographic(band) for band in found} if len(found) >= 2 else None


def resolve(text: str, index: Index, within: set[int], joined: str | None, avoid: str | None = None) -> dict | None:
    """What is counted: one part, or two joined by both / either / not ("both ChatGPT and Gemini": one question's two
    answers; "both cut spending and paying attention", "either an off-price retailer or a dollar store": two questions,
    the verb said once carried to the second, "bought from")."""
    cond = condition(text, index, within, avoid)
    if joined and cond and len(cond.get("is", [])) >= 2:   # two answers of one question
        return {"both": [{**cond, "is": [a]} for a in cond["is"]]} if joined == "both" else cond
    split = BOTH.search(text) if joined == "both" else re.search(r"^(.*?)\beither\s+(.+?)\s+or\s+(.+?)(?=[,?]|$)", text, re.I) if joined == "either" else None
    if split:
        if joined == "both":
            left, right = (split[1], split[2]) if split[1] else (split[3], split[4])
        else:
            verb = re.sub(r"^\s*(?:what share|how many(?: people)?)\s+", "", split[1], flags=re.I)
            left, right = verb + split[2], verb + split[3]
        conds = [condition(left, index, within), condition(right, index, within)]
        if all(conds) and conds[0]["key"] != conds[1]["key"]:
            return {joined: conds}
    return cond


def fill(question: str, index: Index, visible: set[int], ids: dict[str, int]) -> dict | None:
    """The plan for one question (api/ask_engine.py runs it), or None when a part finds no survey question."""
    named = weeks(question, ids)
    dates = sorted(d for d, sid in ids.items() if sid in named) if named else [max(ids)]
    test = bool(re.search(r"\bsignifican", question, re.I))
    days = len(re.findall(r"\b\d{1,2} (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", question, re.I))
    if len(dates) > 2 and not EACH.search(question) and (days >= 2 or re.search(r"\bbetween\b", question, re.I)):
        dates = [dates[0], dates[-1]]   # "between 21 Sep and 16 Nov", "28 Sep vs 16 Nov": the two weeks, not those between
    within = visible & {ids[d] for d in dates}
    plan: dict = {"waves": dates}
    if POOLED.search(question):
        plan["per"] = "pooled"
    if test:
        plan["test"] = True
    rest = DATES.sub(" ", question)
    if CHAIN.search(rest):
        body = re.split(r"\bfunnel from\b|:", rest, maxsplit=1)[-1]
        steps = [s for s in re.split(r"→|->|\bthen\b|\bto\b", body) if len(s.split()) >= 2]
        plan.update(op="chain", steps=[condition(s, index, within) for s in steps])
        return plan if all(plan["steps"]) else None
    among = said_among = ""
    if (m := AMONG.search(rest)) and not re.search(r"\b(vs\.?|versus)\b", m[1] or m[3] or "") and not demographic(m[1] or m[3] or ""):
        among, rest = (m[1], m[2]) if m[1] else (m[3], m[4])
        said_among = among   # as the person said it, for the answer ("people who expect the economy to get worse")
        among = re.sub(rf"^\s*(?:the\s+)?{GROUP_WORDS}\s+(?:who|that|with)\s+", "", among, flags=re.I)
        conds = [condition(g, index, within) for g in re.split(r"\bwho\b", among) if g.strip()]
        if not all(conds):
            return None
        plan["among"] = conds[0] if len(conds) == 1 else {"both": conds}
    # "Are GenAI shoppers more likely than other AI users to …": the group and the rest; never "women or men", a
    # demographic split (it took "women" against everyone else, 38 bank questions, 22 Nov 2026)
    if (m := MORE_LIKELY.search(rest)) and not demographic(m[1]):
        group = condition(m[1], index, within)
        if not group:
            return None
        plan["by"] = {"groups": {m[1].strip(): group, (m[2] or "everyone else").strip(): {"not": group}}}
        rest = m[3]
    elif m := DID_AND_NOT.search(rest):
        split = condition(m[1], index, within)
        if not split:
            return None
        plan["by"] = {"groups": {"did": split, "did not": {"not": split}}}
        rest = rest[:m.start()] + rest[m.end():]
    elif len(incomes := [g for g, (pattern, _) in ask_reader.INCOME_GROUPS.items() if re.search(pattern, rest.lower())]) >= 2:
        plan["by"] = {"groups": {g: demographic(g.lower().split("(")[1]) for g in incomes}}
        for _, (pattern, _) in ask_reader.INCOME_GROUPS.items():   # the dollars said, out of what is counted
            rest = re.sub(pattern, " ", rest, flags=re.I)
    elif bands := age_bands(rest):
        plan["by"] = {"groups": bands}
        for band in bands:
            rest = rest.replace(band, " ")
        rest = re.sub(r"\b(?:for |among )?ages?\b|\b(?:vs\.?|versus|or|and)\b(?=[\s,]*(?:[,?]|$))", " ", rest)
    else:
        for m in re.finditer(r"\s+(?:vs\.?|versus|compared with|or|and)\s+", rest, re.I):
            if found := sides(rest[:m.start()], rest[m.end():]):
                a, ga, b, gb = found
                plan["by"] = {"groups": {a: ga, b: gb}}
                rest = rest[:m.start()].replace(a, " ") + " " + rest[m.end():].replace(b, " ", 1)
                break
    rest = re.sub(r"\b(?:strong(?:ly)?|supporters?|only|(?:for |of )?households(?: earning)?|differ(?: for| on| between)?)\b", " ", rest, flags=re.I) \
        if "by" in plan else rest   # the group's own words, out of what is counted
    rest = re.sub(r"(?:\s*[,;:]\s*(?:and|or|vs\.?)?\s*)+(?=[,?.]|$)|\s+(?:and|or|vs\.?)\s*(?=[,?.]|$)", " ", rest)
    cut = next((CUT_QUESTIONS[d] for d, v in ask_reader.read(rest)["cuts"].items() if v == "all" and d in CUT_QUESTIONS), None)
    if cut and "by" not in plan:
        plan["by"] = {"q": cut}
    if m := TOP.search(rest):
        plan.update(op="top", top=NUMBERS.get((m[1] or m[2] or "5").lower(), int(m[1] or m[2] or 5) if (m[1] or m[2] or "5").isdigit() else 5))
    elif COUNTS.search(rest):
        plan["op"] = "counts"
    joined = "both" if BOTH.search(rest) else "either" if EITHER.search(rest) else None
    asked = NOT_ALSO.sub(" ", rest)
    if among and len(ask_reader.read(asked)["about"].split()) <= 3:   # "what is the main reason", among those spending more
        asked = f"{asked.rstrip(' ?.,')} ({among.strip()})"
    group_key = (plan.get("among") or {}).get("key")
    ask = resolve(asked, index, within, joined, group_key)
    if not ask:
        return None
    if NOT_ALSO.search(rest):
        ask = {"not": ask}
    plan["ask"] = {"q": ask["q"], "key": ask.get("key")} if plan.get("op") in ("top", "counts") and "q" in ask else ask
    plan["say"] = {"among": said_among.strip(" ,?.:"), "ask": NOT_ALSO.sub(" ", rest).strip(" ,?.:")}   # the person's own words, for the answer
    return plan



# ---- the answer from a plan: what Ask shows for a combined question (step 5 of the Ask rebuild, 22 Nov 2026) ----
# Who calls it: api/assistant.py answer, for a question that joins survey questions, groups, weeks or a test (COMBINED),
# before its single-question path; None hands the question back to that path.
COMBINED = re.compile(r"\bamong\b|\bof (?:the )?(?:people|those) who\b|\b(?:vs\.?|versus|compared with)\b|\bmore likely\b"
                      r"|\bdid and did not\b|\bboth\b.+\band\b|\beither\b|\bcounting each\b|\bfunnel\b|→|->|\bsignifican"
                      r"|\b\d{2}\s*[-–]\s*\d{2}\b|\b\d{2}\s*\+|\bunder[- ]\d{2}|\b(?:did|do|does) NOT\b", re.I)


def described(cond: dict, index: Index) -> str:
    """A condition in plain words: the survey question's name and the answers counted."""
    if "both" in cond or "either" in cond:
        return (" and " if "both" in cond else " or ").join(described(c, index) for c in cond.get("both") or cond["either"])
    if "not" in cond:
        return "not " + described(cond["not"], index)
    if "between" in cond:
        low, high = cond["between"]
        return f"aged {low}+" if high >= 120 else f"aged {low}-{high}"
    if isinstance(cond.get("q"), str):   # a demographic
        return " / ".join(cond.get("is", []))
    doc = index.docs.get(cond.get("key") or "", {})
    name = doc.get("name") or doc.get("text", "")[:60]
    return f"{name}: {'any' if cond.get('any') else ' or '.join(cond.get('is', []))}"


SURVEY_AGE_BANDS = {(18, 29), (30, 44), (45, 60), (61, 120)}   # the age bands Ask's single-question path cuts by already


def joins(cond: dict | None) -> bool:
    return bool(cond) and any(k in cond for k in ("both", "either", "not"))


def needs_plan(plan: dict) -> bool:
    """Whether a plan does what Ask's single-question path cannot: both / either / not, a funnel, groups defined by
    another question's answers or by ages the survey does not cut by, a group across several weeks or of two answers,
    or a change tested between two weeks. Otherwise that path answers, in its own words: sent here as well, by gender,
    standard age bands and named income groups, the 6,000-question bank lost 257 right answers (22 Nov 2026)."""
    groups = list(((plan.get("by") or {}).get("groups") or {}).values())
    return (plan.get("op") == "chain" or joins(plan.get("ask")) or joins(plan.get("among"))
            or any(isinstance(g.get("q"), dict) or joins(g) for g in groups)
            or any(g.get("q") == "D2" and tuple(g["between"]) not in SURVEY_AGE_BANDS for g in groups)
            or (bool(plan.get("among")) and len(plan["waves"]) > 1)
            or (bool(plan.get("test")) and not groups and len(plan["waves"]) == 2))


def answer(question: str, index: Index, visible: set[int], weighted: bool = False) -> dict | None:
    """Ask's answer to a combined question from its plan and the plan engine's figures, or None to answer it as before."""
    from api import ask_engine, ask_figures as figures, assistant
    if not COMBINED.search(question):
        return None
    published = index.root.parent
    ids = {w["wave_date"]: sid for sid, w in index.waves.items()   # the US weekly tracker's weeks this person may see
           if sid in visible and w.get("country", "US") == "US" and w.get("study_type") == "tracker"}
    if not ids:
        return None
    plan = fill(question, index, visible, ids)
    if not plan or not needs_plan(plan):
        return None
    if weighted:
        plan["weighted"] = True   # Census weights per respondent (each wave's people.json), as the single-question path
    rows = ask_engine.run(plan, published, ids) if plan else []
    shown = [r for r in rows if r.get("pct") is not None]
    if not shown or any(r.get("group") and not r["base"] for r in rows if r.get("when") == shown[-1]["when"]):
        return None   # a group with nobody in it: the plan misread a group, so the single-question path answers
    when = lambda r: figures.label_date(r["when"]) if r["when"] != "pooled" else "pooled"   # noqa: E731
    say = plan.get("say", {})
    subject = assistant.subject_of(say.get("ask", "")) or described(plan.get("ask", {}), index)
    among = f"Among {say['among']}, " if say.get("among") else ""
    op = plan.get("op", "share")
    change = next((r for r in rows if r.get("label") == "change"), None)
    pct = lambda r: f"{r['pct']:.1f}%"   # noqa: E731
    count = lambda r: f"{r['n']:,} of {r['base']:,}"   # noqa: E731
    if op == "chain":
        headline = " → ".join(f"{r['label']} {pct(r)} ({count(r)})" for r in shown) + f", {when(shown[-1])}."
    elif op in ("top", "counts"):
        headline = (f"{among}top {len(shown)}" if op == "top" else f"{among}of {shown[0]['base']:,} asked").strip()
        headline = headline[0].upper() + headline[1:] + f", {when(shown[0])}: " + ", ".join(f"{r['label']} {pct(r)}" for r in shown) + "."
    elif "by" in plan:
        latest = [r for r in shown if r["when"] == shown[-1]["when"]]
        headline = f"{among}{subject}, {when(latest[0])}: " + "; ".join(f"{r.get('group')} {pct(r)} ({count(r)})" for r in latest) + "."
        if len(latest) == 2:
            (a, b) = latest
            p = p_value(a["n"], a["base"], b["n"], b["base"]) if a["base"] and b["base"] else 1.0
            gap = abs(a["pct"] - b["pct"])
            headline += (f" The {gap:.1f}-point gap is significant at 95% (p = {p:.3f})." if p < 0.05 else
                         f" The {gap:.1f}-point gap could be chance (p = {p:.3f}).")
    elif len(shown) > 1:
        series = ", ".join(f"{pct(r)} ({when(r)})" for r in shown)
        headline = f"{among}{subject}: {series}."
        if change:
            headline += (f" A change of {change['points']:+.1f} points, {'significant at 95%' if change['p'] < 0.05 else 'which could be chance'} (p = {change['p']:.3f}).")
    else:
        r = shown[0]
        headline = f"{among}{pct(r)} {subject} ({count(r)}, {when(r)})."
        headline = headline[0].upper() + headline[1:]
    headline = headline[0].upper() + headline[1:]
    groups = sorted({r.get("group") for r in shown if r.get("group")}, key=lambda g: [r.get("group") for r in shown].index(g))
    weeks_seen = list(dict.fromkeys(r["when"] for r in shown))
    if groups:
        head = ["Group", *[when({"when": w}) for w in weeks_seen]]
        table_rows = [[g, *[next((r["pct"] for r in shown if r.get("group") == g and r["when"] == w), None) for w in weeks_seen]] for g in groups]
        bases = [[next((r["base"] for r in shown if r.get("group") == g and r["when"] == w), None) for w in weeks_seen] for g in groups]
    else:
        labels = list(dict.fromkeys(r["label"] for r in shown))
        head = ["Answer", *[when({"when": w}) for w in weeks_seen]]
        table_rows = [[subject if lab == "share" else lab, *[next((r["pct"] for r in shown if r["label"] == lab and r["when"] == w), None) for w in weeks_seen]] for lab in labels]
        bases = [[next((r["base"] for r in shown if r["label"] == lab and r["when"] == w), None) for w in weeks_seen] for lab in labels]
    chart = None
    if len(table_rows) > 1 or len(weeks_seen) > 1:
        line = len(weeks_seen) > 2 and len(table_rows) <= 5
        chart = {"type": "line" if line else "bar", "unit": "%",
                 "categories": head[1:] if line else [str(r[0]) for r in table_rows],
                 "series": [{"name": str(r[0]), "data": r[1:]} for r in table_rows] if line else
                           [{"name": w, "data": [r[i + 1] for r in table_rows]} for i, w in enumerate(head[1:])]}
    keys = []
    for cond in [plan.get("ask"), plan.get("among"), *(plan.get("steps") or []), *((plan.get("by") or {}).get("groups") or {}).values()]:
        stack = [cond] if cond else []
        while stack:
            c = stack.pop()
            stack += c.get("both", []) + c.get("either", []) + ([c["not"]] if "not" in c else [])
            if c.get("key") and c["key"] not in keys:
                keys.append(c["key"])
    last = max(ids[w] for w in plan["waves"])
    sources = [{"id": f"S{i + 1}", "key": k, "survey_id": last, "wave_date": max(plan["waves"]), "qcode": index.docs[k]["qcode"],
                "question": index.docs[k]["text"], "name": index.docs[k].get("name", ""), "family": index.docs[k]["family"],
                "waves": len(plan["waves"]), "link": f"/w/{last}/questions/{index.docs[k]['qcode']}"} for i, k in enumerate(keys) if k in index.docs]
    read_as = [{"label": "Counted", "value": described(plan["ask"], index)}] if plan.get("ask") else []
    read_as += [{"label": "Among", "value": described(plan["among"], index)}] if plan.get("among") else []
    read_as += [{"label": "Split by", "value": " / ".join(plan["by"]["groups"]) if "groups" in plan["by"] else plan["by"]["q"]}] if plan.get("by") else []
    read_as += [{"label": "Steps", "value": " → ".join(described(c, index) for c in plan["steps"])}] if plan.get("steps") else []
    read_as += [{"label": "Weeks", "value": ", ".join(figures.label_date(w) for w in plan["waves"]) + (" pooled" if plan.get("per") == "pooled" else "")}]
    notes = ["Worked out from each week's respondents: every figure is a share of those asked the question, in the group named."]
    return {"answer": headline, "headline": headline, "mode": "figures", "no_source": False, "chart": chart,
            "table": {"head": head, "rows": table_rows, "bases": [b[-1] or 0 for b in bases], "cell_bases": bases},
            "sources": sources, "suggestions": [], "notes": notes, "understood": "plan", "read_as": read_as, "plan": plan,
            "source_line": f"From {', '.join(s['qcode'] for s in sources)} ({'; '.join(s['question'][:80] for s in sources)}).",
            "scope": {"country": "US", "period": ", ".join(figures.label_date(w) for w in plan["waves"][:3]) + ("…" if len(plan["waves"]) > 3 else ""),
                      "waves": len(plan["waves"]), "base": max((r["base"] for r in shown), default=0)}}
