"""Expected vs actual for retail events (Halloween, Black Friday…), computed by the ETL so the portal only has to show it.

Who calls it: etl/publish.py, after it has written the per-question files. build() reads those files, plus the spend
answers (one database query: open numbers are not in the question files), and publish() writes one file,
api/v1/expectations.json.gz, which the Expected vs actual screen (frontend/src/screens/Expectations.tsx) shows as it
is. The API route /api/v1/expectations is the fallback when nginx is absent.

For each event of config/expectations.yml, every survey fielded before the event (what people expect to do) is set
against the survey after it the same year (did they) and the one the year before (the seasonal report's
"Expectations 2026 vs Actual 2025"). Per question: each answer's % on both sides, the difference and whether it is
significant, and for a more/less question the net score. For an event with a spend question: the median spend and the
market size (share who spend x US adults x median). Also the outlook questions asked again and again (holiday
spending and finances): each survey's answers and net score. Checked against the 7 Oct 2026 seasonal report
(tests/test_expectations.py).
"""
from __future__ import annotations

import statistics
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import bindparam, text

from etl import weekly_report
from etl.weekly_report import Question, read_questions, share, significant
from shared.core.database import get_engine

CONFIG = Path(__file__).resolve().parents[1] / "config" / "expectations.yml"
DAYS_BEFORE = 183   # expectations: asked up to half a year ahead (Black Friday plans in August)
DAYS_AFTER = 122    # what people did: asked within four months


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/expectations.yml: each event's day, question pairs and spend questions, and the US adult population."""
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def waves_around(question: Question, day: str, before: bool) -> list[int]:
    """The places (waves) of `question` fielded in the half year before the event's day of their year, or in the four
    months after it; newest first. A wave further away (a January follow-up) belongs to neither side."""
    month, dom = (int(part) for part in day.split("-"))
    found = []
    for at, fielded in enumerate(question.days):
        gap = (date(fielded.year, month, dom) - fielded).days   # days until the event; negative once it has passed
        if (0 < gap <= DAYS_BEFORE) if before else (0 < -gap <= DAYS_AFTER):
            found.append(at)
    return sorted(found, key=lambda at: question.days[at], reverse=True)


def pair_answers(expected: Question, e_at: int, actual: Question, a_at: int) -> list[tuple[int, int]]:
    """Which expected answer is which actual one. Single-choice answers keep their code when reworded ("I will spend" is
    "I spent", code 2). A multi-choice list pairs by label when every expected answer is there (so a reordered list
    stays right); a reworded list keeps its order ("Pass out candy" is "Passed out candy")."""
    mine, theirs = expected.offered(e_at), actual.offered(a_at)
    if all(expected.codes[a] is not None for a in mine) and all(actual.codes[b] is not None for b in theirs):
        by_code = {actual.codes[b]: b for b in theirs}
        return [(a, by_code[expected.codes[a]]) for a in mine if expected.codes[a] in by_code]
    by_label = {actual.labels[b]: b for b in theirs}
    if len(mine) == len(theirs) and not all(expected.labels[a] in by_label for a in mine):
        return list(zip(mine, theirs))
    return [(a, by_label[expected.labels[a]]) for a in mine if expected.labels[a] in by_label]   # else the same wording only


def compare(expected: Question, e_at: int, actual: Question, a_at: int, with_net: bool = False) -> dict:
    """One question on both sides: per answer the expected and actual %, expected minus actual, and whether that gap is
    significant (two-proportion test, Benjamini-Hochberg over the question's answers); `with_net`: the net score of a
    more/less question (% more minus % less; config/expectations.yml lists them: a spend band "Less than $25" is not one)."""
    e_total, a_total = expected.total, actual.total
    rows, tests, sides = [], [], {"up": [], "down": []}
    words = weekly_report.settings()["net_words"]
    for a, b in pair_answers(expected, e_at, actual, a_at):
        (n1, base1), (n2, base2) = expected.counts(e_at, e_total, [a]), actual.counts(a_at, a_total, [b])
        if not base1 or not base2:
            continue
        rows.append({"label": expected.labels[a], "actual_label": actual.labels[b], "expected": round(100 * n1 / base1, 1),
                     "actual": round(100 * n2 / base2, 1), "difference": round(100 * (n1 / base1 - n2 / base2), 1)})
        tests.append((n2, base2, n1, base1))
        label = expected.labels[a].lower()
        for side, key in (("up", "positive"), ("down", "negative")):
            if any(w in label for w in words[key]):
                sides[side].append((a, b))
    for row, real in zip(rows, significant(tests)):
        row["significant"] = real
    net = None
    if with_net and sides["up"] and sides["down"]:
        def score(question, at, cuts, pick):
            return share(question, at, cuts, [p[pick] for p in sides["up"]]) - share(question, at, cuts, [p[pick] for p in sides["down"]])
        net = {"expected": round(score(expected, e_at, e_total, 0), 1), "actual": round(score(actual, a_at, a_total, 1), 1)}
    return {"expected_code": expected.qcode, "actual_code": actual.qcode,
            "expected_text": expected.wordings[e_at], "actual_text": actual.wordings[a_at],
            "expected_base": expected.counts(e_at, e_total, [])[1], "actual_base": actual.counts(a_at, a_total, [])[1],
            "rows": rows, "net": net}


def spending(event: dict, question: Question | None, survey_id: int, code: str, numbers: dict) -> dict | None:
    """One side's median spend (of `code`, this side's open spend question) and the market size: the spenders' share
    (from `question`, this side's spenders question; None: no market size) x US adults x the median. None when that
    survey has no spend answers."""
    values = numbers.get((survey_id, code))
    if not values:
        return None
    at = question.position(survey_id) if question else None
    spenders = None if at is None else share(question, at, question.total,
                                             [a for a in question.offered(at) if question.codes[a] in event["spenders"]["codes"]])
    median = statistics.median(values)
    market = None if spenders is None else round(spenders / 100 * settings()["us_adults_millions"] * median / 1000, 1)
    return {"median": median, "answers": len(values), "spenders": None if spenders is None else round(spenders, 1),
            "market_billions": market}


def outlook(question: Question, title: str) -> dict:
    """One outlook question across every survey that asked it (the seasonal report's "2026 vs 2025" holiday spending
    and finances, Figures 11-12): per answer code its % in each survey, the base, and the net score (more minus less,
    or better minus worse). Labels as the newest survey words them."""
    words = weekly_report.settings()["net_words"]
    labels: dict[int, str] = {}
    for a in range(len(question.labels)):
        labels.setdefault(question.codes[a], question.labels[a])   # first seen; overwritten below by newer wording
    surveys = list(range(len(question.ids)))
    rows: dict[int, list[float | None]] = {}
    nets, bases = [], []
    for k, at in enumerate(surveys):
        base = question.counts(at, question.total, [])[1]
        bases.append(base)
        up = down = 0.0
        for a in question.offered(at):
            code, label = question.codes[a], question.labels[a].lower()
            labels[code] = question.labels[a]
            value = share(question, at, question.total, [a])
            rows.setdefault(code, [None] * len(surveys))[k] = None if value is None else round(value, 1)
            up += value if value is not None and any(w in label for w in words["positive"]) else 0
            down += value if value is not None and any(w in label for w in words["negative"]) else 0
        nets.append(round(up - down, 1) if base else None)
    return {"title": title, "question": question.qcode, "dates": question.dates, "bases": bases, "net": nets,
            "rows": [{"label": labels[code], "values": values} for code, values in sorted(rows.items())]}


def build(questions: dict[str, Question], numbers: dict[tuple[int, str], list[float]]) -> dict:
    """Every event's comparisons from the tracker's indexed question files (by code) and the open spend answers
    (by (survey_id, code)): each expectation survey against the actual survey of the same year and of the year
    before, newest first."""
    events = []
    for event in settings()["events"]:
        first_expected, first_actual = next(iter(event["questions"].items()))   # finds the event's surveys
        if first_expected not in questions or first_actual not in questions:
            continue
        before, after = questions[first_expected], questions[first_actual]
        mention = event["mentions"].lower()   # a code reused for another question (M1: mass merchants) never mentions it
        comparisons = []
        for e_at in [at for at in waves_around(before, event["day"], before=True) if mention in before.wordings[at].lower()]:
            e_id, e_day = before.ids[e_at], before.days[e_at]
            for a_at in [at for at in waves_around(after, event["day"], before=False) if mention in after.wordings[at].lower()]:
                a_id, a_day = after.ids[a_at], after.days[a_at]
                if a_day.year not in (e_day.year, e_day.year - 1):
                    continue
                pairs = [(questions[e], questions[a]) for e, a in event["questions"].items() if e in questions and a in questions]
                compared = [compare(eq, eq.position(e_id), aq, aq.position(a_id), eq.qcode in event.get("net", [])) for eq, aq in pairs
                            if eq.position(e_id) is not None and aq.position(a_id) is not None]
                spend = None
                if "spend" in event:
                    (e_spend, a_spend), = event["spend"].items()
                    rule = event.get("spenders", {}).get("question")
                    spend = {"expected": spending(event, questions.get(rule), e_id, e_spend, numbers),
                             "actual": spending(event, questions.get(event["questions"].get(rule)), a_id, a_spend, numbers)}
                comparisons.append({"expected": {"survey_id": e_id, "date": before.dates[e_at]},
                                    "actual": {"survey_id": a_id, "date": after.dates[a_at]},
                                    "same_season": a_day.year == e_day.year, "questions": compared, "spend": spend})
        if comparisons:
            events.append({"name": event["name"], "comparisons": comparisons})
    outlooks = [outlook(questions[o["question"]], o["title"]) for o in settings().get("outlooks", []) if o["question"] in questions]
    return {"us_adults_millions": settings()["us_adults_millions"], "events": events, "outlooks": outlooks}


_SPEND_ANSWERS = """
    SELECT a.survey_id, q.qcode, a.value_number
      FROM cip_question q
      JOIN cip_field f ON f.question_id = q.question_id
      STRAIGHT_JOIN cip_answer a ON a.survey_id = f.survey_id AND a.field_id = f.field_id   -- the field's answers only:
                                                                                         -- otherwise MySQL reads the whole wave (8 s, not 0.1)
      JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
     WHERE q.survey_id IN :ids AND q.qcode IN :codes AND a.value_number IS NOT NULL"""


def spend_answers(survey_ids: list[int], codes: list[str]) -> dict[tuple[int, str], list[float]]:
    """The open spend answers ("how much, in dollars…") of qualified respondents, per (survey_id, code): one query.
    A spend question is one number per respondent (one field); a grid of amounts would mix its rows here."""
    if not survey_ids or not codes:
        return {}
    query = text(_SPEND_ANSWERS).bindparams(bindparam("ids", expanding=True), bindparam("codes", expanding=True))
    found: dict[tuple[int, str], list[float]] = {}
    with get_engine("app").connect() as conn:
        for survey_id, code, value in conn.execute(query, {"ids": survey_ids, "codes": codes}):
            found.setdefault((survey_id, code), []).append(float(value))
    return found


def publish(out: Path, write) -> int:
    """Called by etl/publish.py once the question files are written: api/v1/expectations.json.gz from the files in
    `out` and the spend answers. Returns the bytes written."""
    family, study = weekly_report.settings()["family"], weekly_report.settings()["study_type"]
    events = settings()["events"]
    questions = read_questions(out / "api/v1/questions" / family / study,
                               {code for e in events for pair in e["questions"].items() for code in pair}
                               | {o["question"] for o in settings().get("outlooks", [])})
    asked = {survey_id for e in events if "spend" in e   # the waves of the event's first question, before and after
             for code in next(iter(e["questions"].items())) if code in questions for survey_id in questions[code].ids}
    numbers = spend_answers(sorted(asked), sorted({code for e in events for pair in e.get("spend", {}).items() for code in pair}))
    return write(out / "api/v1/expectations", build(questions, numbers))
