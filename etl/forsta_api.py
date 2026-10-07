"""The Forsta API, adapted to the loader the Excel path already proves.

The Excel export we load today is in LABEL format ("Yes", "NO TO: Gone to a
bar", status "Qualified"); the API returns CODES (2, 0, status 3). Rather than
a second loader, API records are turned into the label records the proven one
consumes — so an API wave gives exactly the numbers the Excel wave gives.

    datamap: {"questions": [{"qlabel", "qtitle", "type", "variables": [{"label", "rowTitle"}],
                             "values": [{"value", "title"}]}]}
    data:    [{"record", "uuid", "status": 3, "date", "q2r1": 1, "hq1": 2, …}]

(Decipher API v1 shapes; to confirm on the first call with a working key.)
"""
from __future__ import annotations

import html
from typing import Any

from etl import records as xp

STATUS = {1: "Terminated", 2: "Overquota", 3: "Qualified", 4: "Partial"}
# Never stored (spec D7), whatever the datamap says: the browser string, the
# link, the session, the device fingerprint, the IP and the raw panel id (kept
# only as respondent_key, a hash).
PERSONAL = {"userAgent", "url", "session", "dcua", "ipAddress", "RID"}
_KINDS = {"number": "numeric", "float": "numeric", "text": "text", "textarea": "text", "date": "datetime"}


def _title(value: Any) -> str:
    return xp.clean_text(html.unescape(str(value or "")))


def _values(question: dict) -> list[tuple[int, str]]:
    """Answer codes and labels: on the question, or — in about a third of the
    real datamaps — only on its variables."""
    raw = question.get("values") or next((v["values"] for v in question.get("variables") or [] if v.get("values")), [])
    return [(int(v["value"]), _title(v.get("title"))) for v in raw if str(v.get("value", "")).lstrip("-").isdigit()]


def questions_from_datamap(payload: dict) -> list:
    """One ParsedQuestion per Forsta QUESTION (not per variable), typed the
    way the loader expects:

      * "Other (specify)" text variables (q1r2oe, vosr15oe) become their own
        text questions — never rows or scale points;
      * flags carry through: t = technical (qtime, conditions), v = derived
        (vos, vbrowser) — and Forsta's "- NORMALIZED" copy of a grid is derived;
      * a single-choice grid whose answers have no titles is a bipolar grid:
        code 1 = the row's left statement, code 2 = its right statement (taken
        from the NORMALIZED copy's `_r` variable).
    """
    questions = payload.get("questions", [])
    right_of = {v["label"]: _title(v.get("rowTitle")) for q in questions for v in q.get("variables") or []
                if str(v.get("label", "")).endswith("_r")}
    out = []
    for q in questions:
        label, title = str(q.get("qlabel") or "")[:50], _title(q.get("qtitle"))
        kind = str(q.get("type") or "").lower()
        flags = tuple(q.get("flags") or ())
        if title.upper().endswith("- NORMALIZED") and "v" not in flags:
            flags += ("v",)
        variables = [v for v in q.get("variables") or [] if v.get("label") and v["label"] not in PERSONAL]
        if not variables or label in PERSONAL:
            continue
        other = [v for v in variables if kind != "text" and str(v.get("type")) == "text"]
        main = [v for v in variables if v not in other]
        rows = [(str(v["label"]), _title(" — ".join(t for t in (v.get("rowTitle"), v.get("colTitle")) if t)
                                         or v.get("title") or v["label"])) for v in main]
        named_apart = len(rows) > 1 or (rows and rows[0][0] != label)
        values = _values(q)
        question = xp.ParsedQuestion(qcode=label, qtext=title, flags=flags)
        if kind == "multiple":
            question.qtype, question.rows, question.options = "multi", rows, values
            question.value_min, question.value_max = 0, 1
        elif kind == "single":
            question.options = values
            if values:
                question.value_min, question.value_max = min(c for c, _ in values), max(c for c, _ in values)
            question.qtype = "grid_single" if named_apart else "single"
            if named_apart:
                question.rows = rows
            if named_apart and values and not any(t for _, t in values):
                question.options = [(1, "Left statement"), (2, "Right statement")]
                for v, (code, left) in zip(main, rows):
                    row = v.get("row") or code[len(label):]
                    question.bipolar[code] = (left, right_of.get(f"{label}_norm{row}_r"))
        else:
            question.qtype = _KINDS.get(kind, "text")
            if named_apart:
                question.rows = rows
        if question.qcode:
            out.append(question)
        for v in other:
            out.append(xp.ParsedQuestion(
                qcode=str(v["label"])[:50], qtype="text", flags=flags,
                qtext=f"{title} — {_title(v.get('rowTitle')) or 'Other'} (please specify)"))
    return out


def whole(value: Any):
    """3, "3", 3.0 and "3.0" are all code 3; anything else is not a code."""
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return int(number) if number.is_integer() else None
