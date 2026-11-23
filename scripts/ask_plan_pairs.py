"""Builds the training pairs for Ask's plan writer (a small model that turns an analyst's question into a plan; the plan
engine, api/ask_engine.py, then works out the figures). Each pair is a seed question in plain words, the candidate survey
questions the model is shown (numbered, with their answers), and the plan it must write, in the compact form below.

Every plan is drawn from real survey questions of a real week and run through the plan engine; only plans that compute
(enough people in every figure) are kept, so the model never learns a plan that cannot be answered. Real analyst
questions from the hard and held-out sets are added in the same form: scripts/ask_hard.yml and ask_heldout.yml for
training, scripts/ask_heldout2.yml as the untouched test. The Colab notebook (scripts/colab/ask_plan_writer.ipynb)
rewords the seeds, trains the model and scores it.

Run by hand when the catalogue changes (about 10 minutes, no AI, no cost):
    python scripts/ask_plan_pairs.py --published <api/v1> --out ~/Downloads/Collab/ask-plan-writer
Written 22 Nov 2026 (Ask rebuild, plan writer).

The compact plan the model writes (candidate numbers, never codes; weeks are read by Ask's rules, api/ask_plan.weeks):
    {"op": "share" | "top" | "counts" | "chain", "ask": C, "among": C, "by": [{"name": "...", "c": C}, ...],
     "steps": [C, ...], "top": 3}
    C = {"q": 2, "a": ["Yes"]} | {"q": 2, "any": 1} | {"both": [C, C]} | {"either": [C, C]} | {"not": C} | {"demo": "sex:F"}
    demo: sex:F, sex:M, age:18-34 (any band), income:<50k, income:50-99k, income:100k+, area:Urban, party:R, party:D
"""
import argparse
import gzip
import json
import random
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import logging  # noqa: E402

from api import ask_engine, ask_index, ask_plan  # noqa: E402
from api.ask_engine import NONE_LIKE, clean, people_of  # noqa: E402

CANDIDATES, ANSWERS, ANSWER_CHARS = 6, 6, 40   # what the model sees: short prompts are fast on a CPU (step-6 research)
MIN_BASE = 40                                    # every figure of a kept plan stands on at least this many people
DEMOGRAPHIC = {"D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"}
DEMOS = {"sex:F": ("women", {"q": "D1", "is": ["Female"]}), "sex:M": ("men", {"q": "D1", "is": ["Male"]}),
         "income:<50k": ("households under $50,000", {"q": "D5", "is": ["under $25", "$25,000"]}),
         "income:50-99k": ("households earning $50,000-$99,999", {"q": "D5", "is": ["$50,000"]}),
         "income:100k+": ("households earning $100,000 or more", {"q": "D5", "is": ["$100,000", "$150,000", "$200,000"]}),
         "area:Urban": ("urban residents", {"q": "D6", "is": ["Urban"]}), "area:Suburban": ("suburban residents", {"q": "D6", "is": ["Suburban"]}),
         "area:Rural": ("rural residents", {"q": "D6", "is": ["Rural"]}),
         "party:R": ("strong Republicans", {"q": "D7", "is": ["Strongly agree with most policies of the Republican"]}),
         "party:D": ("strong Democrats", {"q": "D7", "is": ["Strongly agree with most policies of the Democratic"]})}
AGE_PAIRS = [((18, 34), (55, 120)), ((18, 29), (60, 120)), ((18, 24), (25, 34)), ((35, 54), (55, 120)), ((18, 34), (35, 54)),
             ((18, 28), (29, 120)), ((25, 44), (45, 64))]
SCALE_WORDS = ("better", "worse", "more", "less", "likely", "satisfied", "agree", "increase", "decrease", "positive", "negative")


def age(band: tuple[int, int]) -> tuple[str, str, dict]:
    low, high = band
    words = f"{low} and older" if high >= 120 else f"{low}-{high}"
    return (f"age:{low}+" if high >= 120 else f"age:{low}-{high}"), words, {"q": "D2", "between": [low, high]}


class Week:
    """One week's questions as the generator draws them: each code with its index key, name, answers and kind."""

    def __init__(self, index: ask_index.Index, published: Path, date: str, sid: int):
        self.date, self.sid, self.index = date, sid, index
        self.people = people_of(published / "waves" / str(sid) / "people.json.gz")
        self.size = ask_engine.size_of(self.people)
        self.questions = {}
        for key, doc in index.docs.items():
            if sid not in doc["surveys"] or doc["family"] != "CSI-US":
                continue
            code = index.counts(key)["sources"].get(sid, (None,))[0]
            question = ask_engine.question_in(self.people, code) if code else None
            if not question or code.upper() in DEMOGRAPHIC or not question["rows"]:
                continue
            multi = all(r[1] == 0 for r in question["rows"])
            answers = ask_engine.answers_of(self.people, code)
            _, asked = ask_engine.mask(self.people, self.size, {"q": code, "any": True})
            if len(answers) >= 2 and asked.sum() >= 2 * MIN_BASE:
                self.questions[code] = {"code": code, "key": key, "name": doc.get("name") or doc["text"][:70], "text": doc["text"],
                                        "answers": answers, "multi": multi, "yes": "Yes" in answers}

    def pick(self, rng: random.Random, multi: bool | None = None, exclude=(), near: str | None = None) -> dict | None:
        """A question of this week; with near, one an analyst would join to it: the same module most of the time
        (GP1 with GP7), else a core weekly question asked a year or more (q5, CS1, D14), else any."""
        pool = [q for q in self.questions.values() if (multi is None or q["multi"] == multi) and q["code"] not in exclude]
        if near and pool:
            prefix = lambda c: re.match(r"[A-Za-z]+", c)[0].upper()   # noqa: E731
            module = [q for q in pool if prefix(q["code"]) == prefix(near)]
            core = [q for q in pool if self.index.docs[q["key"]]["waves"] >= 40]
            pool = module if module and rng.random() < .7 else core if core and rng.random() < .8 else pool
        return rng.choice(pool) if pool else None


def answers_for(q: dict, rng: random.Random, n: int = 1) -> list[str]:
    real = [a for a in q["answers"] if not NONE_LIKE.match(a) and not re.match(r"(other|don't know|not sure|prefer not)", a, re.I)]
    return rng.sample(real, min(n, len(real))) if real else []


def scale_pair(q: dict) -> list[str] | None:
    """Two answers of a scale's one side ("Much better", "Somewhat better"), for a net."""
    for word in SCALE_WORDS:
        side = [a for a in q["answers"] if re.search(rf"\b{word}\b", a, re.I) and not re.search(r"\b(not|n't|no)\b", a, re.I)]
        if len(side) == 2:
            return side
    return None


def said(q: dict, answers: list[str] | None = None, any_answer: bool = False) -> str:
    """A condition in seed words: “Have used GenAI to shop” to “Use of GenAI for shopping”."""
    if any_answer:
        return f"chose any answer (not none) to “{q['name']}”"
    if answers == ["Yes"]:
        return f"said yes to “{q['name']}”"
    return f"said {' or '.join(f'“{a}”' for a in answers)} to “{q['name']}”"


def draw(week: Week, kind: str, rng: random.Random):
    """One seed question, its engine plan (codes) and its model plan (question codes, numbered later)."""
    q = week.pick(rng)
    if not q:
        return None
    one = lambda x: (answers_for(x, rng) or [None])   # noqa: E731
    if kind == "share":
        a = ["Yes"] if q["yes"] and rng.random() < .5 else one(q)
        if a == [None]:
            return None
        return (f"What share {said(q, a)}?", {"ask": {"q": q["code"], "is": a}}, {"op": "share", "ask": {"q": q["code"], "a": a}})
    if kind == "net":
        a = scale_pair(q)
        return a and (f"What share {said(q, a)}?", {"ask": {"q": q["code"], "is": a}}, {"op": "share", "ask": {"q": q["code"], "a": a}})
    if kind == "any":
        q = week.pick(rng, multi=True)
        return q and (f"What share {said(q, any_answer=True)}?", {"ask": {"q": q["code"], "any": True}},
                      {"op": "share", "ask": {"q": q["code"], "any": 1}})
    if kind in ("top", "counts"):
        if kind == "top" and len(q["answers"]) < 4 or kind == "counts" and (q["multi"] or len(q["answers"]) > 8):
            return None
        n = rng.choice([3, 5]) if kind == "top" else None
        seed = f"Top {n} answers to “{q['name']}”" if n else f"Breakdown of answers to “{q['name']}”"
        plan = {"op": kind, "ask": {"q": q["code"]}, **({"top": n} if n else {})}
        return seed, plan, {"op": kind, "ask": {"q": q["code"]}, **({"top": n} if n else {})}
    if kind in ("among", "among-top"):
        g = week.pick(rng, exclude={q["code"]}, near=q["code"])
        ga = ["Yes"] if g and g["yes"] else (one(g) if g else [None])
        if not g or ga == [None]:
            return None
        if kind == "among-top":
            if len(q["answers"]) < 4:
                return None
            return (f"Among people who {said(g, ga)}, top 3 answers to “{q['name']}”",
                    {"op": "top", "top": 3, "among": {"q": g["code"], "is": ga}, "ask": {"q": q["code"]}},
                    {"op": "top", "top": 3, "among": {"q": g["code"], "a": ga}, "ask": {"q": q["code"]}})
        a = ["Yes"] if q["yes"] else one(q)
        return a != [None] and (f"Among people who {said(g, ga)}, what share {said(q, a)}?",
                                {"among": {"q": g["code"], "is": ga}, "ask": {"q": q["code"], "is": a}},
                                {"op": "share", "among": {"q": g["code"], "a": ga}, "ask": {"q": q["code"], "a": a}})
    if kind in ("both", "either", "not"):
        if q["multi"] and rng.random() < .5:   # two answers of one list ("both ChatGPT and Gemini")
            a = answers_for(q, rng, 2)
            if len(a) < 2:
                return None
            c1, c2 = ({"q": q["code"], "is": [a[0]]}, {"q": q["code"], "is": [a[1]]})
            m1, m2 = ({"q": q["code"], "a": [a[0]]}, {"q": q["code"], "a": [a[1]]})
            words = f"“{a[0]}” and “{a[1]}” in “{q['name']}”" if kind != "either" else f"“{a[0]}” or “{a[1]}” in “{q['name']}”"
        else:
            g = week.pick(rng, exclude={q["code"]}, near=q["code"])
            a, ga = (["Yes"] if q["yes"] else one(q)), (["Yes"] if g and g["yes"] else (one(g) if g else [None]))
            if not g or a == [None] or ga == [None]:
                return None
            c1, c2, m1, m2 = {"q": q["code"], "is": a}, {"q": g["code"], "is": ga}, {"q": q["code"], "a": a}, {"q": g["code"], "a": ga}
            words = f"{said(q, a)} and {said(g, ga)}" if kind != "either" else f"{said(q, a)} or {said(g, ga)}"
        if kind == "not":
            return (f"Among people who {said(q, c1['is'])}, what share did NOT also say {' or '.join(f'“{x}”' for x in c2['is'])} to “{week.questions[c2['q']]['name']}”?",
                    {"among": c1, "ask": {"not": c2}}, {"op": "share", "among": m1, "ask": {"not": m2}})
        word = "both" if kind == "both" else "either"
        return (f"What share {('both ' if kind == 'both' else 'either ')}{words}?" if "said" in words else f"What share chose {word} {words}?",
                {"ask": {kind: [c1, c2]}}, {"op": "share", "ask": {kind: [m1, m2]}})
    if kind == "demo":
        a = ["Yes"] if q["yes"] else one(q)
        if a == [None]:
            return None
        style = rng.choice(["sex", "age", "income", "area", "party"])
        if style == "age":
            groups = [age(b) for b in rng.choice(AGE_PAIRS)]
        elif style == "income":
            keys = rng.choice([["income:<50k", "income:100k+"], ["income:<50k", "income:50-99k", "income:100k+"]])
            groups = [(k, DEMOS[k][0], DEMOS[k][1]) for k in keys]
        else:
            keys = {"sex": ["sex:F", "sex:M"], "area": ["area:Urban", "area:Rural"], "party": ["party:R", "party:D"]}[style]
            groups = [(k, DEMOS[k][0], DEMOS[k][1]) for k in keys]
        names = " vs ".join(w for _, w, _ in groups)
        return (f"What share {said(q, a)}: {names}?", {"ask": {"q": q["code"], "is": a}, "by": {"groups": {w: c for _, w, c in groups}}},
                {"op": "share", "ask": {"q": q["code"], "a": a}, "by": [{"name": w, "c": {"demo": k}} for k, w, _ in groups]})
    if kind == "groups":
        g = week.pick(rng, exclude={q["code"]}, near=q["code"])
        a, ga = (["Yes"] if q["yes"] else one(q)), (["Yes"] if g and g["yes"] else (one(g) if g else [None]))
        if not g or a == [None] or ga == [None]:
            return None
        cond, model = {"q": g["code"], "is": ga}, {"q": g["code"], "a": ga}
        return (f"Are people who {said(g, ga)} more likely than everyone else to have {said(q, a)}?",
                {"ask": {"q": q["code"], "is": a}, "by": {"groups": {"them": cond, "everyone else": {"not": cond}}}},
                {"op": "share", "ask": {"q": q["code"], "a": a}, "by": [{"name": "them", "c": model}, {"name": "everyone else", "c": {"not": model}}]})
    if kind == "chain":   # a survey's own funnel: each next question asked only of the step before's people
        steps, used = [], set()
        for _ in range(rng.choice([2, 3])):
            candidates = []
            for x in week.questions.values():
                if x["code"] in used:
                    continue
                a = ["Yes"] if x["yes"] else answers_for(x, rng)
                if not a:
                    continue
                true, asked = ask_engine.mask(week.people, week.size, {"q": x["code"], "is": a})
                if steps:
                    before = steps[-1][2]
                    if asked.sum() < MIN_BASE or (asked & ~before).any():
                        continue   # asked of people outside the step before: not this funnel
                candidates.append((x, a, true))
            if not candidates:
                break
            x, a, true = rng.choice(candidates)
            steps.append((x, a, true))
            used.add(x["code"])
        if len(steps) < 2:
            return None
        seed = "Funnel: " + " → ".join(said(x, a) for x, a, _ in steps)
        return seed, {"op": "chain", "steps": [{"q": x["code"], "is": a} for x, a, _ in steps]}, \
            {"op": "chain", "steps": [{"q": x["code"], "a": a} for x, a, _ in steps]}
    return None


def codes_in(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        if isinstance(node.get("q"), str) and node["q"].upper() not in DEMOGRAPHIC:
            found.append(node["q"])
        for value in node.values():
            found += codes_in(value)
    elif isinstance(node, list):
        for value in node:
            found += codes_in(value)
    return list(dict.fromkeys(found))


def numbered(node, numbers: dict):
    """The model plan with codes put as candidate numbers."""
    if isinstance(node, dict):
        return {k: (numbers[v] if k == "q" and isinstance(v, str) and v in numbers else numbered(v, numbers)) for k, v in node.items()}
    if isinstance(node, list):
        return [numbered(v, numbers) for v in node]
    return node


def shown(week: Week, codes: list[str], words: str, rng: random.Random, used: dict) -> list[dict]:
    """The candidates the model sees: the plan's questions and look-alikes (the same module, the same words), shuffled."""
    pool = list(codes)
    prefix = {re.match(r"[A-Za-z]+", c)[0].upper() for c in codes}
    hits = [h["qcode"] for h in week.index.find(words, None, 12, {week.sid})]
    near = [c for c in week.questions if re.match(r"[A-Za-z]+", c)[0].upper() in prefix] + [c for c in hits if c in week.questions]
    for c in rng.sample(near, len(near)) + rng.sample(list(week.questions), len(week.questions)):
        if len(pool) >= CANDIDATES:
            break
        if c not in pool:
            pool.append(c)
    rng.shuffle(pool)
    return [{"n": i + 1, "code": c, "name": week.questions[c]["name"], "answers": visible(week.questions[c]["answers"], used.get(c, []))}
            for i, c in enumerate(pool)]


def visible(answers: list[str], used: list[str]) -> list[str]:
    """The answers the model sees: the plan's own first, then the rest, up to ANSWERS, each cut to ANSWER_CHARS (the
    engine matches an answer by its start, so the cut label still counts the right people)."""
    shown_labels = list(dict.fromkeys([a for a in answers if a[:ANSWER_CHARS] in {u[:ANSWER_CHARS] for u in used}] + answers))[:ANSWERS]
    return [a[:ANSWER_CHARS] for a in shown_labels]


def answers_used(node, found: dict | None = None) -> dict:
    """Each question code's answers a plan names."""
    found = {} if found is None else found
    if isinstance(node, dict):
        if isinstance(node.get("q"), str) and node.get("a"):
            found.setdefault(node["q"], []).extend(node["a"])
        for value in node.values():
            answers_used(value, found)
    elif isinstance(node, list):
        for value in node:
            answers_used(value, found)
    return found


def shorten(node):
    """The model plan's answers cut as the model sees them."""
    if isinstance(node, dict):
        return {k: ([a[:ANSWER_CHARS] for a in v] if k == "a" else shorten(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [shorten(v) for v in node]
    return node


def computes(plan: dict, published: Path, ids: dict, date: str) -> bool:
    rows = ask_engine.run({"waves": [date], **plan}, published, ids)
    figures = [r for r in rows if "base" in r]
    return bool(figures) and all(r["base"] >= MIN_BASE and r["pct"] is not None for r in figures)


MIX = {"share": 3000, "net": 1200, "any": 900, "top": 1500, "counts": 1200, "among": 3500, "among-top": 1000, "both": 2200,
       "either": 1300, "not": 1000, "demo": 3000, "groups": 1800, "chain": 1200}   # what analysts ask, combined questions weighted up


def real_cases(path: Path, index, ids, rng, weeks: dict) -> list[dict]:
    """The hard and held-out sets' questions in the same form: candidates from Ask's own finder, the plan's questions in."""
    out = []
    for case in yaml.safe_load(path.read_text()):
        plan = case.get("plan")
        if not plan:
            continue
        date = str(plan["waves"][-1])
        week = weeks.get(date) or weeks.setdefault(date, Week(index, index.root.parent, date, ids[date]))
        codes = [c for c in codes_in(plan) if c in week.questions] or None
        if not codes:
            continue
        found = [h["qcode"] for h in ask_plan.candidates(case["question"], index, {ids[str(w)] for w in plan["waves"]}, ids)]
        pool = list(codes) + [c for c in found if c in week.questions and c not in codes]
        pool = pool[:CANDIDATES]
        rng.shuffle(pool)
        numbers = {c: i + 1 for i, c in enumerate(pool)}
        model = to_model(plan)
        out.append({"id": case["id"], "question": case["question"], "source": path.stem,
                    "candidates": [{"n": numbers[c], "code": c, "name": week.questions[c]["name"],
                                    "answers": visible(week.questions[c]["answers"], answers_used(model).get(c, []))} for c in pool],
                    "plan": numbered(shorten(model), numbers)})
    return out


def to_model(plan: dict) -> dict:
    """A hand-written test plan (scripts/ask_hard.yml) in the model's compact form, demographics as demo tokens."""
    def cond(c):
        if c is None:
            return None
        if "both" in c or "either" in c:
            key = "both" if "both" in c else "either"
            return {key: [cond(x) for x in c[key]]}
        if "not" in c:
            return {"not": cond(c["not"])}
        if c.get("q") == "D2":
            low, high = c["between"]
            return {"demo": f"age:{low}+" if high >= 120 else f"age:{low}-{high}"}
        if c.get("q") in ("D1", "D5", "D6", "D7"):
            return {"demo": next((k for k, (_, d) in DEMOS.items() if d == c), f"{c['q']}:{'|'.join(c.get('is', []))}")}
        return {"q": c["q"], **({"any": 1} if c.get("any") else {"a": c.get("is", [])})}
    out = {"op": plan.get("op", "share")}
    if plan.get("op") in ("top", "counts"):
        out["ask"] = {"q": plan["ask"]["q"]}
        if plan.get("top"):
            out["top"] = plan["top"]
    elif plan.get("op") == "chain":
        out["steps"] = [cond(s) for s in plan["steps"]]
    else:
        out["ask"] = cond(plan["ask"])
    if plan.get("among"):
        out["among"] = cond(plan["among"])
    if plan.get("by") and "groups" in plan["by"]:
        out["by"] = [{"name": n, "c": cond(c)} for n, c in plan["by"]["groups"].items()]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", type=Path, default=ROOT / "data" / "published" / "current" / "api" / "v1")
    ap.add_argument("--out", type=Path, default=Path.home() / "Downloads" / "Collab" / "ask-plan-writer")
    ap.add_argument("--scale", type=float, default=1.0, help="share of MIX to draw (0.01 for a quick check)")
    args = ap.parse_args()
    logging.disable(logging.WARNING)   # here, not at import: a test importing this module must keep its logs
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = ask_index.Index(args.published / "questions", waves)
    ids = ask_engine.surveys(args.published)
    dates = [d for d in sorted(ids) if d >= "2024-01-01"]   # today's questions; 2020-22 was mostly coronavirus modules
    weights = [1 + 3 * (i >= len(dates) - 60) for i in range(len(dates))]   # the last 60 weeks four times as often
    weeks: dict[str, Week] = {}
    pairs, tried = [], 0
    for kind, count in MIX.items():
        target, made = max(1, round(count * args.scale)), 0
        while made < target and tried < 400_000:
            tried += 1
            date = rng.choices(dates, weights)[0]
            week = weeks.get(date) or weeks.setdefault(date, Week(index, args.published, date, ids[date]))
            drawn = draw(week, kind, rng)
            if not drawn or not computes(drawn[1], args.published, ids, date):
                continue
            seed, _, model = drawn
            codes = codes_in(model)
            cands = shown(week, codes, " ".join(week.questions[c]["name"] for c in codes), rng, answers_used(model))
            numbers = {c["code"]: c["n"] for c in cands}
            pairs.append({"id": f"S{len(pairs):06d}", "kind": kind, "week": date, "seed": seed, "candidates": cands,
                          "plan": numbered(shorten(model), numbers)})
            made += 1
        print(f"{kind:10} {made:5} pairs", flush=True)
    with gzip.open(args.out / "pairs.jsonl.gz", "wt", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    for name in ("ask_hard", "ask_heldout", "ask_heldout2"):
        real = real_cases(ROOT / "scripts" / f"{name}.yml", index, ids, rng, weeks)
        (args.out / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in real))
        print(f"{name}: {len(real)} real questions", flush=True)
    print(f"{len(pairs)} pairs from {len(weeks)} weeks, {tried} drawn -> {args.out}")


if __name__ == "__main__":
    main()
