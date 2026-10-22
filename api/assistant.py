"""Ask CIP: a question in plain words, answered only from the portal's own published figures, every statement cited.

1. Find sources: the question catalogue (api/search.py) gives the matching questions; each one's latest wave figures
   come from the published wave book (the same numbers every screen shows, groups under 30 already hidden).
2. Answer: with Claude credentials (ANTHROPIC_API_KEY, or a profile), Claude writes a short answer from those sources
   only and names the ones it used; code then drops any citation that is not a real source, and an answer left with
   none is "no source". Without credentials the sources themselves are the answer (cited figures, no prose).
Only aggregates (question wording, answer labels, percentages, bases) leave the server; never respondent rows.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable, Optional

log = logging.getLogger("cip.assistant")
MODEL = os.environ.get("CIP_ASSISTANT_MODEL", "claude-opus-5-5")
SOURCES = 5
# words a question is phrased with, not what it is about: they never make a survey question a source on their own
FILLER = set("what which when where whose does many much have about there their they this that with from were would "
             "should could more most some into your people share percent percentage consumers americans many".split())


def topic(text: str) -> set[str]:
    """The words a text is about, cut to five letters so shopped/shopping and tariff/tariffs meet."""
    return {w[:5] for w in re.findall(r"[a-z0-9]{4,}", text.lower()) if w not in FILLER}
SYSTEM = (
    "You answer questions about Coresight Research's US consumer surveys for retail analysts. Use only the numbered "
    "sources given with the question: survey questions with their latest wave's results (unweighted percentages of "
    "qualified US adults who answered, with the base n). Quote figures exactly as given with their source id, e.g. "
    "\"47.5% did some Cyber Monday shopping [S1]\". Say which wave a figure is from. Never compute new percentages, "
    "never estimate, never use outside knowledge. If the sources do not answer the question, set no_source to true and "
    "say briefly what the portal does cover. Keep the answer under 120 words."
)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer", "cited", "no_source"],
          "properties": {"answer": {"type": "string"}, "cited": {"type": "array", "items": {"type": "string"}},
                         "no_source": {"type": "boolean"}}}


def sources(question: str, search: Callable[[str, int], dict], book: Callable[[int], Optional[dict]]) -> list[dict]:
    """The best-matching questions, each with its latest wave's Total figures: [{id, survey_id, wave_date, title,
    qcode, question, base, answers: [[label, pct]], link}]."""
    found = search(question, 12)
    asked = topic(" ".join([question, *found.get("understood", {}).get("expanded", [])]))   # with the search's synonyms
    out = []
    for hit in found["results"]:
        data = book(hit["survey_id"])
        q = data and next((x for x in data["questions"] if x["id"] == hit["qcode"]), None)
        if not q:
            continue
        group = q["groups"][0]
        if not asked & topic(" ".join([q["text"], *(r["label"] for r in group["rows"])])):
            continue             # a loose search match (a word fragment) that shares no topic word with the question
        answers = sorted(([r["label"], r.get("Total")] for r in group["rows"] if r.get("Total") is not None), key=lambda a: -a[1])
        if not answers:          # fewer than 30 people answered: nothing to quote
            continue
        out.append({"id": f"S{len(out) + 1}", "survey_id": hit["survey_id"], "wave_date": data["wave"]["wave_date"],
                    "title": data["wave"]["title"], "qcode": q["id"], "question": q["text"], "base": group["base"],
                    "group": group["label"], "waves": hit["waves"], "answers": answers[:8],
                    "link": f"/w/{hit['survey_id']}/questions/{q['id']}"})
        if len(out) == SOURCES:
            break
    return out


def listing(found: list[dict]) -> str:
    return "\n\n".join(
        f"[{s['id']}] {s['title']}, wave of {s['wave_date']} · {s['qcode']}: {s['question']}"
        + (f" ({s['group']})" if s["group"] else "") + f" · base n={s['base']} · asked in {s['waves']} waves\n"
        + "\n".join(f"  {label}: {pct}%" for label, pct in s["answers"]) for s in found)


def figures_only(found: list[dict]) -> str:
    return "\n".join(f"{s['qcode']} ({s['wave_date']}, n={s['base']}): " + "; ".join(f"{l} {p}%" for l, p in s["answers"][:3])
                     + f" [{s['id']}]" for s in found)


def ask(question: str, search, book, client=None) -> dict:
    """{answer, sources (only the cited ones), no_source, mode}. mode: claude, figures (no credentials or Claude
    unavailable), none (nothing in the portal matched)."""
    question = " ".join(str(question).split())[:500]
    found = sources(question, search, book) if len(question) >= 3 else []
    if not found:
        return {"answer": "No source in the portal answers this. Try other words, or search the question library.",
                "sources": [], "no_source": True, "mode": "none"}
    try:
        import anthropic
        client = client or anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL, max_tokens=2000, system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",   # a declined request is retried server-side
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": f"Sources:\n\n{listing(found)}\n\nQuestion: {question}"}])
        if response.stop_reason == "refusal":
            raise RuntimeError("declined")
        reply = json.loads(next(b.text for b in response.content if b.type == "text"))
    except Exception as exc:                 # no credentials, network, refusal, or unreadable reply: the cited figures
        log.info("Assistant falls back to figures only: %s", type(exc).__name__)
        return {"answer": figures_only(found), "sources": found, "no_source": False, "mode": "figures"}
    known = {s["id"]: s for s in found}
    cited = [known[c] for c in dict.fromkeys(reply.get("cited") or []) if c in known]
    if reply.get("no_source") or not cited:  # an answer that names no real source is not given
        return {"answer": reply.get("answer") if reply.get("no_source") else "No source in the portal answers this.",
                "sources": [], "no_source": True, "mode": "claude"}
    return {"answer": reply["answer"], "sources": cited, "no_source": False, "mode": "claude"}
