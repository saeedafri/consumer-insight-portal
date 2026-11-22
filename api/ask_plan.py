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
from api.ask_index import Index

# where a question splits into the things it joins: "among X, Y", "X who Y", "X and Y", "X vs Y", "Y because of X"
SPLIT = re.compile(r",|;|\?|\b(?:among|of people who|of those who|who|and|vs\.?|versus|or|than|between|because of|due to|for)\b", re.I)
PER_PART = 10   # candidates kept per part: the needed question was in a part's top 10 for 124 of 126 plans, top 5 for 121


def parts(question: str) -> list[str]:
    """The question and its pieces of two words or more: "Among GLP-1 users on 16 Nov, what share bought footwear?" gives
    the whole, "GLP-1 users on 16 Nov" and "what share bought footwear"."""
    return [question] + [p.strip() for p in SPLIT.split(question) if p and len(p.strip().split()) >= 2]


def weeks(question: str, ids: dict[str, int]) -> set[int] | None:
    """The survey ids of the weeks a question names ("16 Nov", "the last four weeks"), from Ask's own period reading
    over the tracker's fielded dates; None when it names none (every week may answer)."""
    specs, _ = ask_reader.periods(" ".join(question.lower().replace("’", "'").split()))
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
