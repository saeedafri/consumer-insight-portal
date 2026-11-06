"""The Databank's sector tables, computed by the ETL so the portal only has to show them.

Who calls it: etl/publish.py, after it has written every wave's book (api/v1/waves/<id>/book.json.gz) and the
per-question files. build() finds each sector question in the books and takes its exact counts from the question
files (no database); publish() writes one file for every sector, api/v1/sectors.json.gz, which the Sectors screen
(frontend/src/screens/Sectors.tsx) shows as it is. The API route /api/v1/sectors is the fallback when nginx is absent.

Each sector, as the Databank lays it out: one column per survey the sector ran (sectors rotate, so about every 12
weeks, back to 2022), a purchase-rate row (% of all respondents who bought in the category in the past three months),
then one table per tab (retailers, brands, categories), each row an answer's % of the respondents asked (the buyers).

Finding a sector's surveys and questions:
  surveys    tagged with the sector's module since Jul 2025; before that, the survey title names it ("Shopping and
             Spending - inc Dept Stores + …", the rule in config/survey_calendar.yml)
  questions  by code when the wording agrees; older surveys numbered their questions Q1, Q2…, so there by wording. The
             wording also tells reused codes apart: DS1-DS3 ask about drugstores in drugstore weeks and about dollar
             stores in off-price weeks, and M1-M2 were reused for Memorial Day in Mar 2026.
Which sectors and questions: config/sectors.yml. Checked against the Databank page of 6 Nov 2026 (Department stores):
tests/test_sectors.py.
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

from etl import survey_calendar, weekly_report
from etl.weekly_report import Question, first_sentence, margin_of_error, read_questions, read_waves, share

CONFIG = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/sectors.yml (each sector's module, purchase question and tables) plus each module's title rule
    (config/survey_calendar.yml sectors: title), as {module name: regex}."""
    rules = yaml.safe_load((CONFIG / "sectors.yml").read_text(encoding="utf-8"))
    return {**rules, "titles": {s["name"]: s["title"] for s in survey_calendar.load_config()["sectors"]}}


def sector_waves(waves: list[dict], sector: dict) -> list[dict]:
    """The surveys of one sector, oldest first: tagged with its module, or (before tags) titled with it. One per date:
    a parallel panel fielded the same week (titles ending "- RIWI", Dec 2023) is left out."""
    title = re.compile(settings()["titles"][sector["module"]], re.I)
    skip = tuple(settings()["leave_out_titles"])
    found = {}
    for wave in waves:
        tagged = sector["module"] in (wave.get("modules") or [])
        titled = not wave.get("modules") and title.search(wave.get("title") or "")
        if (tagged or titled) and not any(word in (wave.get("title") or "") for word in skip):
            found.setdefault(wave["wave_date"], wave)
    return list(found.values())


def find(book: dict, code: str, sentence: str) -> dict | None:
    """One sector question in a survey's book: by its code when the wording agrees, else by its wording. Open-ended
    answers coded into themes ("— Other (please specify)") repeat the wording and are skipped."""
    asked = [q for q in book["questions"] if "coded" not in q and first_sentence(q["text"]) == sentence]
    return next((q for q in asked if q["id"] == code), asked[0] if asked else None)


def locate(question_file, found: dict | None, survey_id: int) -> tuple[Question, int] | None:
    """The published question file and place of a question found in a survey's book: its exact counts (the book's
    % are rounded, so 40.65 would show as 40.6 where the Databank shows 40.7)."""
    question = question_file(found["id"]) if found else None
    at = question.position(survey_id) if question else None
    return None if at is None else (question, at)


def build(books: dict[int, dict], waves: list[dict], question_file) -> dict:
    """Every sector of config/sectors.yml from the tracker's waves (oldest first), their books (by survey_id) to find
    each question, and `question_file` (code -> Question or None) for its counts. A sector's columns: its surveys that
    asked any of its questions."""
    skip = tuple(weekly_report.settings()["leave_out_answers"])
    sectors = []
    for sector in settings()["sectors"]:
        purchase = sector.get("purchase")
        codes = [*([purchase["question"]] if purchase else []), *sector["tables"].values()]
        surveys = [w for w in sector_waves(waves, sector) if w["survey_id"] in books]
        tagged = [w for w in surveys if w.get("modules")]
        if not tagged:
            continue
        sentences = {}   # each question's wording, as the newest tagged survey asked it
        for code in codes:
            asked = [q for w in tagged for q in books[w["survey_id"]]["questions"] if q["id"] == code]
            if asked:
                sentences[code] = first_sentence(asked[-1]["text"])
        found = [{code: find(books[w["survey_id"]], code, sentence) for code, sentence in sentences.items()} for w in surveys]
        keep = [k for k, questions in enumerate(found) if any(questions.values())]
        surveys, found = [surveys[k] for k in keep], [found[k] for k in keep]
        if not surveys:   # none of its questions found (a code mistyped in the config): the other sectors still publish
            continue

        def table(code: str) -> dict:
            """One tab: each answer's % per survey, biggest in the newest first, and the respondents asked per survey.
            An answer spelled differently over the years ("Dillards", "Dillard's") is one row, under its newest label."""
            rows: dict[str, list[float | None]] = {}
            labels: dict[str, str] = {}
            bases = []
            for k, (wave, questions) in enumerate(zip(surveys, found)):
                hit = locate(question_file, questions.get(code), wave["survey_id"])
                if hit is None:
                    bases.append(None)
                    continue
                question, at = hit
                bases.append(question.counts(at, question.total, [])[1])
                for a in question.offered(at):
                    label, value = question.labels[a], share(question, at, question.total, [a])
                    if value is not None and not label.lower().startswith(skip):
                        key = re.sub(r"[^a-z0-9]", "", label.lower())
                        rows.setdefault(key, [None] * len(found))[k] = round(value, 1)
                        labels[key] = label
            latest_first = sorted(rows.items(), key=lambda row: [-(v if v is not None else -1) for v in reversed(row[1])])
            return {"rows": [{"label": labels[key], "values": values} for key, values in latest_first], "bases": bases}

        bought = None
        if purchase:
            bought = {"label": purchase["label"], "values": []}
            for wave, questions in zip(surveys, found):
                hit = locate(question_file, questions.get(purchase["question"]), wave["survey_id"])
                value = None
                if hit:
                    question, at = hit
                    value = share(question, at, question.total,
                                  [a for a in question.offered(at) if question.codes[a] in purchase["codes"]])
                bought["values"].append(None if value is None else round(value, 1))
        sectors.append({
            "name": sector["name"],
            "waves": [{"survey_id": w["survey_id"], "date": w["wave_date"], "respondents": w["qualified_n"]} for w in surveys],
            "purchase": bought,
            "tables": [{"title": title, "question": code, **table(code)} for title, code in sector["tables"].items()],
            "margin": margin_of_error(min((w["qualified_n"] for w in surveys if w["qualified_n"]), default=0)),   # the Databank's "±5 %, 95 % confidence"
        })
    return {"sectors": sectors}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py once the wave books and question files are written: api/v1/sectors.json.gz from them
    (no database). Returns the bytes written."""
    family, study = weekly_report.settings()["family"], weekly_report.settings()["study_type"]
    waves = read_waves(out, family, study)
    wanted = {w["survey_id"] for sector in settings()["sectors"] for w in sector_waves(waves, sector)}
    books = {}
    for survey_id in wanted:
        path = out / "api/v1/waves" / str(survey_id) / "book.json.gz"
        if path.exists():
            books[survey_id] = json.loads(gzip.decompress(path.read_bytes()))

    @lru_cache(maxsize=None)
    def question_file(code: str) -> Question | None:   # read once, only the codes the sectors use
        return read_questions(out / "api/v1/questions" / family / study, [code]).get(code)
    return write(out / "api/v1/sectors", build(books, waves, question_file))
