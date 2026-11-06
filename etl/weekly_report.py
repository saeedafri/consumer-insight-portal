"""The weekly "US Consumer Survey Insights" report, computed by the ETL so the portal only has to show it.

Who calls it: etl/publish.py, after it has written the per-question files (one per question, every wave and cut with
exact counts). build() reads those files (no database), adds the shopper profiles (one database query), and the
publish step writes one report file per recent weekly-tracker wave: api/v1/waves/<id>/report.json.gz. The portal's
Report screen (frontend/src/screens/Report.tsx) reads that file as it is; nothing is calculated when someone opens it.

What is in a report, in the order of the PDF report it reproduces (checked against the 3 Nov 2026 report: every
number matched to 0.1 point, see tests/test_weekly_report.py):
  three_points   the three biggest significant moves of the week ("Three Data Points To Watch")
  sentiment      net better (better minus worse) for personal finances and the economy: weekly, four-week average,
                 by income group, with the change over a year
  tables         13-week tables (four-week averages) for food and nonfood retailers, categories bought in store and
                 online, and activities, with the one-week and three-month changes and which ones are significant
  profiles       each retailer's shoppers: average age and household income, over the 13 weeks
  methodology    respondents per week and the margin of error, weekly and four-week
  events         news events to mark on the sentiment chart (config/news_events.yml)

The rules the report uses, all in config/weekly_report.yml: which question is which section, the three income groups,
and the words that make an answer positive or negative for a net score.
"""
from __future__ import annotations

import gzip
import json
import math
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import bindparam, text

from shared.core.database import get_engine

CONFIG = Path(__file__).resolve().parents[1] / "config"
ROLLING = 4      # weeks in a rolling average
TABLE_WEEKS = 13  # weeks shown in a table: the latest and the 12 before ("three-month change" = 12 weeks back)
YEAR = 52        # weeks back for the change over a year
NEAR_DAYS = 3    # a wave fielded off its Monday (e.g. Tue 3 Sep 2024) still counts as that week
Z_95 = 1.959964  # two-sided 95 %


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/weekly_report.yml: the sections, the income groups and the net-score words."""
    return yaml.safe_load((CONFIG / "weekly_report.yml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def news_events() -> list[dict]:
    """config/news_events.yml: dated news the research team marks on the sentiment chart."""
    events = yaml.safe_load((CONFIG / "news_events.yml").read_text(encoding="utf-8")) or []
    return [{**event, "date": str(event["date"])} for event in events]   # YAML reads 2026-03-09 as a date: kept as text


class Question:
    """One published question file (shared/data/payloads.question_from), indexed for quick look-ups: the number of
    respondents who gave each answer, and the base, for every wave and cut."""

    def __init__(self, file: dict):
        self.qcode = file["qcode"]
        self.ids = [w[0] for w in file["waves"]]
        self.dates = [w[1] for w in file["waves"]]
        self.days = [date.fromisoformat(d) for d in self.dates]   # parsed once: wave_of runs thousands of times
        self.labels = [answer[2] or answer[0] for answer in file["answers"]]
        self.cuts = {(dim, value): i for i, (dim, value) in enumerate(file["cuts"])}
        self.count, self.base = {}, {}
        for w, c, a, n, b in zip(file["w"], file["c"], file["a"], file["n"], file["b"]):
            self.count[(w, c, a)] = n or 0   # n is empty under the privacy minimum: counted as none
            self.base[(w, c)] = b

    def wave_of(self, day: str) -> int | None:
        """The wave fielded nearest to `day` (within NEAR_DAYS), or None when no wave asked the question that week."""
        target = date.fromisoformat(day)
        gaps = [(abs((d - target).days), i) for i, d in enumerate(self.days)]
        gap, nearest = min(gaps, default=(NEAR_DAYS + 1, None))
        return nearest if gap <= NEAR_DAYS else None

    def position(self, survey_id: int) -> int | None:
        """This question's place for one wave, by its id: two waves can share a date (two panels in one week)."""
        return self.ids.index(survey_id) if survey_id in self.ids else None

    def counts(self, wave: int, cuts: list[int], answers: list[int]) -> tuple[int, int]:
        """(respondents who gave any of `answers`, base) in one wave, over one or several cuts added together."""
        base = sum(self.base.get((wave, c), 0) for c in cuts)
        return sum(self.count.get((wave, c, a), 0) for c in cuts for a in answers), base


def share(question: Question, wave: int | None, cuts: list[int], answers: list[int]) -> float | None:
    """The % of respondents in `wave` (one week) who gave one of `answers`; None when that week did not ask it."""
    if wave is None:
        return None
    n, base = question.counts(wave, cuts, answers)
    return 100 * n / base if base else None


def rolling(values: list[float | None]) -> float | None:
    """The four-week rolling average: the mean of the four weekly %s, as the PDF report computes it (checked: this
    matches its tables more often than pooling the four weeks' respondents; the two never differ by more than 0.1)."""
    return sum(values) / len(values) if len(values) == ROLLING and None not in values else None


def significant(changes: list[tuple[int, int, int, int]]) -> list[bool]:
    """Which changes are real: a two-proportion z-test of each (n1, base1, n2, base2), then the Benjamini-Hochberg
    correction over all the changes of one table at 5 %, the portal's rule everywhere (the PDF's highlights match it:
    in the 26 Oct 2026 food table, Dollar Tree's +3.2 is not significant while Family Dollar's +3.5 is)."""
    p_values = []
    for n1, b1, n2, b2 in changes:
        if not b1 or not b2:
            p_values.append(1.0)
            continue
        pooled = (n1 + n2) / (b1 + b2)
        se = math.sqrt(pooled * (1 - pooled) * (1 / b1 + 1 / b2))
        z = abs(n2 / b2 - n1 / b1) / se if se else 0.0
        p_values.append(math.erfc(z / math.sqrt(2)))
    ranked = sorted(range(len(p_values)), key=lambda i: p_values[i])
    passing, total = set(), len(p_values)
    for rank, i in enumerate(ranked, start=1):   # the largest rank whose p fits under rank/total * 5 %, and all before it
        if p_values[i] <= rank / total * 0.05:
            passing = set(ranked[:rank])
    return [i in passing for i in range(total)]


def window(question: Question, end: int, weeks: int) -> list[int | None]:
    """The waves of the `weeks` weeks ending at wave `end`: each week its nearest wave (a week not asked is None), so a
    missing week never shifts the others. The last week is always `end` itself."""
    last = date.fromisoformat(question.dates[end])
    found = [question.wave_of((last - timedelta(weeks=weeks - 1 - k)).isoformat()) for k in range(weeks - 1)]
    return found + [end]


def table(question: Question, end: int) -> dict:
    """A 13-week table, as in the PDF report: per answer the four-week rolling average for each of the 13 weeks, the
    one-week change (of the four-week averages), the three-month change (latest against 12 weeks before), and which
    changes are significant. One-week moves are tested on single weeks (this week against last), three-month moves on
    the four weeks of each window, respondents pooled. Rows: biggest first, "None of these"-style answers left out."""
    total = [question.cuts[("total", "Total")]]
    waves = window(question, end, TABLE_WEEKS + ROLLING - 1)    # 16 weeks: the first table week needs three before it
    dates = [question.dates[w] if w is not None else None for w in waves[ROLLING - 1:]]
    rows, week_tests, quarter_tests = [], [], []
    skip = tuple(settings()["leave_out_answers"])
    for a, label in enumerate(question.labels):
        # an answer this week's survey did not offer (the code once meant another question, kept in the file) is left out
        if label.lower().startswith(skip) or waves[-1] is None or (waves[-1], total[0], a) not in question.count:
            continue
        weekly = [share(question, w, total, [a]) for w in waves]
        values = [rolling(weekly[k:k + ROLLING]) for k in range(TABLE_WEEKS)]
        if values[-1] is None:
            continue
        rows.append({"label": label, "values": [None if v is None else round(v, 1) for v in values],
                     "week_change": None if values[-2] is None else round(values[-1] - values[-2], 1),
                     "quarter_change": None if values[0] is None else round(values[-1] - values[0], 1)})
        this_week, last_week = (question.counts(w, total, [a]) if w is not None else (0, 0) for w in (waves[-1], waves[-2]))
        week_tests.append((*last_week, *this_week))
        first = [question.counts(w, total, [a]) for w in waves[:ROLLING] if w is not None]
        latest = [question.counts(w, total, [a]) for w in waves[-ROLLING:] if w is not None]
        quarter_tests.append((sum(n for n, _ in first), sum(b for _, b in first),
                              sum(n for n, _ in latest), sum(b for _, b in latest)))
    for row, week_sig, quarter_sig in zip(rows, significant(week_tests), significant(quarter_tests)):
        row["week_significant"], row["quarter_significant"] = week_sig, quarter_sig and row["quarter_change"] is not None
    rows.sort(key=lambda r: -r["values"][-1])
    return {"dates": dates, "rows": rows}


def answers_for(question: Question, words: list[str]) -> list[int]:
    """The answers whose wording contains one of `words` ("better", "more"…): one side of a net score."""
    return [a for a, label in enumerate(question.labels) if any(w in label.lower() for w in words)]


def net(question: Question, wave: int | None, cuts: list[int]) -> float | None:
    """Net better (or net more): % with a positive answer minus % with a negative one, in one week."""
    words = settings()["net_words"]
    up, down = answers_for(question, words["positive"]), answers_for(question, words["negative"])
    plus, minus = share(question, wave, cuts, up), share(question, wave, cuts, down)
    return None if plus is None or minus is None else plus - minus


def income_cuts(question: Question) -> dict[str, list[int]]:
    """The report's three income groups (<$50K, $50K to <$100K, $100K+), each the portal's finer bands added together."""
    return {group: [question.cuts[("income_band", band)] for band in bands if ("income_band", band) in question.cuts]
            for group, bands in settings()["income_groups"].items()}


def sentiment(question: Question, end: int) -> dict:
    """Net better for one sentiment question over the past year: weekly, four-week average, and the four-week average
    by income group, each income line with its change against a year before (the PDF's "Down 17.9 PPTs year over year")."""
    waves = window(question, end, YEAR + ROLLING)    # 56 weeks: 53 four-week averages, the first exactly a year back
    groups = {"Total": [question.cuts[("total", "Total")]], **income_cuts(question)}
    shown = waves[ROLLING - 1:]
    out = {"dates": [question.dates[w] if w is not None else None for w in shown], "lines": {}}
    for group, cuts in groups.items():
        weekly = [net(question, w, cuts) for w in waves]
        four = [rolling(weekly[k:k + ROLLING]) for k in range(len(shown))]
        last = four[-1]
        out["lines"][group] = {"weekly": [None if v is None else round(v, 1) for v in weekly[ROLLING - 1:]],
                               "four_week": [None if v is None else round(v, 1) for v in four],
                               "year_change": None if last is None or four[0] is None else round(last - four[0], 1)}
    return out


def three_points(tables: list[dict]) -> list[dict]:
    """The three biggest significant three-month moves of the week, at most one per table so the three tell three
    different stories: the PDF's "Three Data Points To Watch This Week"."""
    best = []
    for data in tables:
        moves = [r for r in data["rows"] if r["quarter_significant"]]
        if moves:
            row = max(moves, key=lambda r: abs(r["quarter_change"]))
            best.append({"section": data["name"], "label": row["label"], "change": row["quarter_change"],
                         "from": row["values"][0], "to": row["values"][-1],
                         "from_date": data["dates"][0], "to_date": data["dates"][-1]})
    return sorted(best, key=lambda p: -abs(p["change"]))[:3]


def margin_of_error(base: int) -> float:
    """The largest margin of error of a % at 95 % for `base` respondents (at 50 %): ±4.9 points for 400, ±2.4 for 1,600."""
    return round(100 * Z_95 * math.sqrt(0.25 / base), 1) if base else 0.0


def methodology(waves: list[dict], end_date: str) -> dict:
    """Respondents per week for the year to `end_date`, newest first, and the margins of error the report states."""
    weeks = [{"date": w["wave_date"], "respondents": w["qualified_n"]} for w in waves
             if w["wave_date"] <= end_date][-YEAR:][::-1]
    smallest = min((w["respondents"] for w in weeks[:ROLLING]), default=0)
    return {"weeks": weeks, "weekly_margin": margin_of_error(smallest), "four_week_margin": margin_of_error(smallest * ROLLING)}


_PROFILE_ROWS = """
    SELECT c.survey_id, q.qcode, COALESCE(i.item_label, o.value_label) AS label, SUM(c.n) AS n,
           SUM(c.sum_age_mid) AS age_sum, SUM(c.n_age_mid) AS age_n,
           SUM(c.sum_income_mid_k) AS income_sum, SUM(c.n_income_mid) AS income_n
      FROM cip_question q
      JOIN cip_agg_cell c ON c.question_id = q.question_id AND c.survey_id = q.survey_id
      LEFT JOIN cip_item i ON i.item_id = c.item_id        -- a multi-select answer (a retailer) is an item
      LEFT JOIN cip_option o ON o.option_id = c.option_id  -- a single-choice answer is an option
     WHERE q.survey_id IN :ids AND q.qcode IN :codes AND c.dim = 'total' AND c.cohort_id IS NULL
     GROUP BY c.survey_id, q.qcode, COALESCE(i.item_label, o.value_label)"""


def profile_cells(survey_ids: list[int]) -> list[dict]:
    """The cube's age and income midpoints of each retailer's shoppers, per wave: one database query for all the
    recent waves (etl/cube.py stores them; nothing else showed them until now)."""
    if not survey_ids:
        return []
    query = text(_PROFILE_ROWS).bindparams(bindparam("ids", expanding=True), bindparam("codes", expanding=True))
    with get_engine("app").connect() as conn:
        codes = list(settings()["profile_questions"])
        return [dict(row) for row in conn.execute(query, {"ids": survey_ids, "codes": codes}).mappings()]


def profiles(cells: list[dict], survey_ids: set[int]) -> list[dict]:
    """Each retailer's shoppers over the waves in `survey_ids` (13 weeks): average age and average household income
    ($ thousands), largest shopper base first, per profile question (the Databank's "US Retailers' Shopper Profiles")."""
    sums: dict[tuple[str, str], list[float]] = {}
    for cell in cells:
        if cell["survey_id"] in survey_ids:
            total = sums.setdefault((cell["qcode"], cell["label"]), [0, 0, 0, 0, 0])
            for i, key in enumerate(("n", "age_sum", "age_n", "income_sum", "income_n")):
                total[i] += float(cell[key] or 0)
    skip = tuple(settings()["leave_out_answers"])
    out: dict[str, list[dict]] = {}
    for (qcode, label), (n, age_sum, age_n, income_sum, income_n) in sums.items():
        if label.lower().startswith(skip) or not age_n or not income_n:
            continue
        out.setdefault(qcode, []).append({"label": label, "shoppers": int(n), "age": round(age_sum / age_n),
                                          "income_k": round(income_sum / income_n)})
    return [{"title": title, "rows": sorted(out[qcode], key=lambda r: -r["shoppers"])}
            for qcode, title in settings()["profile_questions"].items() if out.get(qcode)]


def publish(out: Path, write) -> int:
    """Called by etl/publish.py once the question files are written: one report file per recent weekly-tracker wave,
    api/v1/waves/<id>/report.json.gz, from the question files in `out` (no database) plus the shopper profiles (one
    query). Returns the bytes written."""
    family, study = settings()["family"], settings()["study_type"]
    folder = out / "api/v1/questions" / family / study
    codes = {*(s["question"] for s in settings()["sections"]), *settings()["sentiment"].values()}
    questions = {code: Question(json.loads(gzip.decompress((folder / f"{code}.json.gz").read_bytes()))) for code in codes
                 if (folder / f"{code}.json.gz").exists()}   # read and indexed once, for all the reports
    waves = sorted((w for w in json.loads(gzip.decompress((out / "api/v1/waves.json.gz").read_bytes()))
                    if w["survey_family"] == family and w["study_type"] == study), key=lambda w: w["wave_date"])
    recent = waves[-settings()["recent_waves"]:]
    cells = profile_cells([w["survey_id"] for w in waves[-(len(recent) + TABLE_WEEKS - 1):]])
    size = 0
    for wave in recent:
        at = waves.index(wave)
        last_13 = {w["survey_id"] for w in waves[max(0, at - TABLE_WEEKS + 1):at + 1]}   # this wave and the 12 before
        report = build(questions, waves, wave["survey_id"], profiles(cells, last_13))
        if report:
            size += write(out / "api/v1/waves" / str(wave["survey_id"]) / "report", report)
    # a wave that is no longer recent loses its report (publish reuses unchanged wave folders, report included)
    keep = {str(w["survey_id"]) for w in recent}
    for old in (out / "api/v1/waves").glob("*/report.json.gz"):
        if old.parent.name not in keep:
            old.unlink()
    return size


def build(questions: dict[str, Question], waves: list[dict], survey_id: int,
          shopper_profiles: list[dict] | None = None) -> dict | None:
    """The whole report for one weekly-tracker wave, from its family's indexed question files (by question code) and
    the family's waves (oldest first). A table whose question the wave did not ask is left out; None when no table
    remains."""
    wave = next((w for w in waves if w["survey_id"] == survey_id), None)
    if wave is None:
        return None
    tables = []
    for section in settings()["sections"]:
        question = questions.get(section["question"])
        end = question.position(survey_id) if question else None
        if end is not None:
            tables.append({**section, **table(question, end)})
    feeling = {}
    for name, code in settings()["sentiment"].items():
        end = questions[code].position(survey_id) if code in questions else None
        if end is not None:
            feeling[name] = sentiment(questions[code], end)
    if not tables:
        return None
    return {"survey_id": survey_id, "wave_date": wave["wave_date"], "three_points": three_points(tables),
            "sentiment": feeling, "tables": tables, "profiles": shopper_profiles or [],
            "methodology": methodology(waves, wave["wave_date"]), "events": news_events()}
