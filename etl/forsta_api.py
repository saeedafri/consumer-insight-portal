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

from typing import Any

from etl import excel_parsers as xp

STATUS = {1: "Terminated", 2: "Overquota", 3: "Qualified", 4: "Partial"}
_KINDS = {"number": "numeric", "float": "numeric", "text": "text", "textarea": "text", "date": "datetime"}


def questions_from_datamap(payload: dict) -> list:
    """One ParsedQuestion per Forsta QUESTION (not per variable), typed the
    way excel_parsers.parse_datamap types the same question."""
    out = []
    for q in payload.get("questions", []):
        variables = q.get("variables") or []
        values = [(int(v["value"]), xp.clean_text(v.get("title") or "")) for v in q.get("values") or []
                  if str(v.get("value", "")).lstrip("-").isdigit()]
        kind = str(q.get("type") or "").lower()
        question = xp.ParsedQuestion(qcode=str(q.get("qlabel") or "")[:50], qtext=xp.clean_text(q.get("qtitle") or ""))
        rows = [(str(v["label"]), xp.clean_text(" — ".join(t for t in (v.get("rowTitle"), v.get("colTitle")) if t)
                                                 or v.get("title") or v["label"]))
                for v in variables if v.get("label")]
        # a variable named apart from its question (q7r1 under q7) is a row of it
        named_apart = len(rows) > 1 or (rows and rows[0][0] != str(q.get("qlabel")))
        if kind == "multiple":
            question.qtype, question.rows, question.options = "multi", rows, values
            question.value_min, question.value_max = 0, 1
        elif kind == "single":
            question.options = values
            if values:
                question.value_min, question.value_max = min(c for c, _ in values), max(c for c, _ in values)
            if named_apart:
                question.qtype, question.rows = "grid_single", rows
            else:
                question.qtype = "single"
        else:
            question.qtype = _KINDS.get(kind, "text")
            if named_apart:
                question.rows = rows
        if question.qcode:
            out.append(question)
    return out


def to_record(api_record: dict[str, Any], questions: list) -> dict[str, Any]:
    """An API record (codes) → the loader's label record. A code the datamap
    does not know is kept as text, never mapped to a guess."""
    rec: dict[str, Any] = {}
    kinds: dict[str, tuple] = {}
    for q in questions:
        options = dict(q.options)
        if q.qtype == "multi":
            for code, label in q.rows:
                kinds[code] = ("multi", label)
        elif q.qtype == "grid_single":
            for code, _ in q.rows:
                kinds[code] = ("coded", options)
        elif q.qtype == "single":
            kinds[q.qcode] = ("coded", options)
    for key, value in api_record.items():
        if value is None or str(value).strip() == "":
            continue
        kind, number = kinds.get(key), _whole(value)
        if key == "status":
            rec[key] = STATUS.get(number, str(value))
        elif kind is None:
            rec[key] = value
        elif kind[0] == "multi":
            if number is not None:
                rec[key] = kind[1] if number == 1 else f"{xp.NO_TO}{kind[1]}"
        else:
            rec[key] = kind[1].get(number, str(value))
    return rec


def _whole(value: Any):
    """3, "3", 3.0 and "3.0" are all code 3; anything else is not a code."""
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return int(number) if number.is_integer() else None
