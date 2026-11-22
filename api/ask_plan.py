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
                   r"|\b(?:in |of |across |over )?(?:the )?(?:latest|last \w+|each of the last \w+|every week|each week)(?: (?:survey|wave|week)s?)?\b"
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
    scored = sorted(((len(said & (set(stems(a)) - GENERIC)), a) for a in answers), reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return []
    return [scored[0][1]]


def condition(text: str, index: Index, within: set[int], avoid: str | None = None) -> dict | None:
    """One part's survey question and answers, read by Ask's own answer path in the named weeks: its named answers (a
    total's parts, "any" for anyone who chose one) among those it offered then, Yes for a yes/no question, else any."""
    from api import assistant   # the answer path reads this module's callers; imported here, never at load
    if group := demographic(text) if len(text.split()) <= 4 else None:
        return group
    found = assistant.answer(text, index, within, True)
    if found.get("mode") != "figures" or not found.get("sources"):
        return None
    key = found["sources"][0]["key"]
    if avoid and key == avoid:   # what is counted is never the group's own question ("Amazon's share among holiday purchasers")
        found = next((assistant.answer(text, index, within, True, key=c["key"]) for c in candidates(text, index, within, {})
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
    among = ""
    if (m := AMONG.search(rest)) and not re.search(r"\b(vs\.?|versus)\b", m[1] or m[3] or "") and not demographic(m[1] or m[3] or ""):
        among, rest = (m[1], m[2]) if m[1] else (m[3], m[4])
        among = re.sub(rf"^\s*(?:the\s+)?{GROUP_WORDS}\s+(?:who|that|with)\s+", "", among, flags=re.I)
        conds = [condition(g, index, within) for g in re.split(r"\bwho\b", among) if g.strip()]
        if not all(conds):
            return None
        plan["among"] = conds[0] if len(conds) == 1 else {"both": conds}
    if m := MORE_LIKELY.search(rest):   # "Are GenAI shoppers more likely than other AI users to …": the group and the rest
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
    plan["ask"] = {"q": ask["q"]} if plan.get("op") in ("top", "counts") and "q" in ask else ask
    return plan
