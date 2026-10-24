"""Open-ended answers coded into themes, so a typed-in question can be charted like any other.

Each wave's open-ended questions (qtype 'text': "Other, please specify" boxes and free questions) are coded once and
kept in data/coded/<survey_id>.json: per question, its themes and each respondent's theme. The book then shows the
question as one more chart (app/data/payloads.book): the share of those who wrote something, by theme, for Total,
gender and generation. Verbatims themselves never leave this file.

Two coders:
  claude     with Claude credentials (ANTHROPIC_API_KEY): Claude reads the answers and names up to 8 themes
  frequency  otherwise: the same answer written by two or more people (after tidying spelling, case and near
             misses) is a theme; "n/a", "nothing" and the like are one theme; the rest are "Other answers"

A coded question is not coded again unless its answers change. Run after each load (scripts/weekly_forsta.py) and
once for the history:

    python -m etl.open_ends --wave 415
    python -m etl.open_ends --all
"""
from __future__ import annotations

import argparse
import difflib
import json
import logging
import os
import re
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from app.core.database import get_engine

log = logging.getLogger("cip.open_ends")
ROOT = Path(os.environ.get("CIP_CODED_DIR") or Path(__file__).resolve().parents[1] / "data/coded")
MODEL = os.environ.get("CIP_CODING_MODEL", "claude-haiku-5-5")
MAX_THEMES = 8
NOTHING = "Nothing / not sure"
OTHER = "Other answers"
EMPTY = re.compile(r"^(n/?a|na|none|nothing|no|nope|idk|i don'?t know|don'?t know|dont know|not sure|unsure|no idea|"
                   r"-+|\.+|x+|\?+|no comment|nothing else|none of the above|nil|null)$")
PRIVATE = re.compile(r"\S+@\S+|\+?\d[\d\s().-]{6,}\d")   # emails and phone numbers never reach a theme or Claude

VERBATIMS = """
    SELECT q.qcode, a.respondent_id, a.value_text
      FROM cip_answer a
      JOIN cip_field f ON f.field_id = a.field_id AND f.survey_id = :s
      JOIN cip_question q ON q.question_id = f.question_id AND q.qtype = 'text' AND q.is_technical = 0
      JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
     WHERE a.survey_id = :s AND a.value_text IS NOT NULL AND TRIM(a.value_text) <> ''"""


def tidy(answer: str) -> str:
    return " ".join(re.sub(r"[^\w\s'/&+-]", " ", PRIVATE.sub(" ", answer).lower()).split())


def by_frequency(answers: list[str]) -> tuple[list[str], list[int]]:
    """Themes = answers two or more people gave (near misses merged); returns (themes, each answer's theme index)."""
    keys = [tidy(a) for a in answers]
    counts = Counter(k for k in keys if k and not EMPTY.match(k))
    canon: dict[str, str] = {}
    for key, _ in counts.most_common():   # the commonest spelling of a near-identical answer names it
        close = difflib.get_close_matches(key, list(dict.fromkeys(canon.values())), n=1, cutoff=0.85)
        canon[key] = close[0] if close else key
    sizes = Counter(canon[k] for k in keys if k in canon)
    themes = [key for key, n in sizes.most_common() if n >= 2][:MAX_THEMES * 2]
    labels = [key[:1].upper() + key[1:] for key in themes]
    has_empty = any(not k or EMPTY.match(k) for k in keys)
    names = labels + ([NOTHING] if has_empty else []) + [OTHER]
    codes = []
    for k in keys:
        if not k or EMPTY.match(k):
            codes.append(names.index(NOTHING))
        elif canon.get(k) in themes:
            codes.append(themes.index(canon[k]))
        else:
            codes.append(len(names) - 1)
    used = sorted(set(codes))   # drop a theme nobody landed in ("Other answers" when every answer repeats)
    return [names[i] for i in used], [used.index(c) for c in codes]


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["themes", "codes"],
          "properties": {"themes": {"type": "array", "items": {"type": "string"}},
                         "codes": {"type": "array", "items": {"type": "integer"}}}}


def by_claude(question: str, answers: list[str], client) -> tuple[list[str], list[int]]:
    """Claude names up to MAX_THEMES themes and puts each answer in one; anything malformed raises."""
    listing = "\n".join(f"{i}. {PRIVATE.sub('[removed]', a)[:300]}" for i, a in enumerate(answers))
    response = client.messages.create(
        model=MODEL, max_tokens=8000,
        system=(f"You code survey verbatims. Name at most {MAX_THEMES} short themes (2-5 words, plain English) that "
                f"cover the answers, then give each answer's theme index in order. Use '{NOTHING}' for blank or "
                f"don't-know answers and '{OTHER}' for answers that fit no theme. Never quote a person."),
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"Question: {question}\n\nAnswers:\n{listing}"}])
    reply = json.loads(next(b.text for b in response.content if b.type == "text"))
    themes, codes = [str(t)[:80] for t in reply["themes"]], [int(c) for c in reply["codes"]]
    if len(codes) != len(answers) or not themes or any(not 0 <= c < len(themes) for c in codes):
        raise ValueError("Claude's coding does not cover every answer")
    return themes, codes


def claude_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def code_wave(survey_id: int, client=None) -> int:
    """Code the wave's open-ended questions whose answers changed since last time; returns questions coded."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(VERBATIMS), {"s": survey_id}).all()
        wording = dict(conn.execute(text("SELECT qcode, qtext FROM cip_question WHERE survey_id = :s AND qtype = 'text'"),
                                    {"s": survey_id}).all())
    path = ROOT / f"{survey_id}.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    asked: dict[str, list] = {}
    for qcode, rid, answer in rows:
        asked.setdefault(qcode, []).append((rid, answer))
    client = client if client is not None else claude_client()
    coded = 0
    for qcode, given in asked.items():
        signature = len(given), sum(len(a) for _, a in given)
        if done.get(qcode, {}).get("signature") == list(signature):
            continue
        answers = [a for _, a in given]
        method = "frequency"
        themes, codes = by_frequency(answers)
        if client is not None:
            try:
                themes, codes = by_claude(wording.get(qcode, qcode), answers, client)
                method = "claude"
            except Exception as exc:   # no credit, network, a malformed reply: the frequency coding stands
                log.warning("Claude could not code %s %s (%s); coded by frequency", survey_id, qcode, type(exc).__name__)
        done[qcode] = {"method": method, "signature": list(signature), "themes": themes,
                       "codes": {str(rid): c for (rid, _), c in zip(given, codes)}}
        coded += 1
    if coded:
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(done))
        tmp.replace(path)
    return coded


def coded(survey_id: int) -> dict:
    """The wave's coded questions ({} when none): {qcode: {method, themes, codes: {respondent_id: theme index}}}."""
    path = ROOT / f"{survey_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Code open-ended answers into themes (data/coded)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="every served wave")
    group.add_argument("--wave", type=int, help="one survey_id")
    args = ap.parse_args()
    with get_engine("app").connect() as conn:
        ids = [args.wave] if args.wave else [r[0] for r in conn.execute(text("SELECT survey_id FROM srv_wave ORDER BY wave_date"))]
    client = claude_client()
    log.info("Coding %d wave(s) %s", len(ids), "with Claude" if client else "by frequency (no ANTHROPIC_API_KEY)")
    total = sum(code_wave(sid, client) for sid in ids)
    log.info("Coded %d question(s)", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
