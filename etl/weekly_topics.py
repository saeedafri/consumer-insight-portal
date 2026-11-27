"""The weekly topic screens' figures, computed by the ETL so the screens only draw (the manager's roadmap of 27 Nov 2026):
Activities & retailers, Spending pressure and Consumer sentiment & outlook (frontend/src/screens/Weekly.tsx).

Who calls it: etl/publish.py write_views, after the per-question files are written, at every publish and after a
restore. It reads only those files (api/v1/questions/CSI-US/tracker/<code>.json.gz: every week and group with exact
counts, no database) and writes one file per topic, api/v1/weekly/<topic>.json.gz, which nginx sends
(deploy/cip_locations.conf) and the API serves as a fallback (api/main.py weekly_topic).

Each tab is one question under its codes, a week counted only when asked with the tab's wording. Its answers are every
answer given (a multiple-answer question), `sums` of a scale's answers, or each row of a grid added up by `rows`. A
figure is people: n of the b asked, in that week and group; a net's n is people on the plus side less those on the
minus side, so it can be negative, and the screen divides by b. A single-answer question stores no count for an answer
nobody gave, so a sum counts it 0 once the group answered that week; a multiple-answer question stores its zeros, so a
missing count there is an answer not offered that week. Which topics, codes, wordings and words: config/weekly_topics.yml.
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/weekly_topics.yml."""
    return yaml.safe_load((CONFIG / "weekly_topics.yml").read_text(encoding="utf-8"))


def answer_key(item: str, label: str) -> str:
    """An answer as the screens name it: its label, or "row: label" for a grid's row (Utilities: Notable increase), as
    api/ask_figures.py names them."""
    return f"{item}: {label}" if item and item != label else item or label


def counts(files: list[dict], wording: str) -> tuple[dict, dict, dict]:
    """The question files' cells over the weeks asked with `wording`: people[(survey_id, cut, answer)], asked[(survey_id,
    cut)] and the weeks {survey_id: date}. Two files holding one week (a code's file and the one it borrowed the week
    from) hold the same counts."""
    pattern = re.compile(wording, re.I)
    people, asked, weeks = {}, {}, {}
    for file in files:
        kept = [bool(pattern.search(file["versions"][w[2] - 1] or "")) for w in file["waves"]]
        for i, w in enumerate(file["waves"]):
            if kept[i]:
                weeks[w[0]] = w[1]
        for w, c, a, n, b in zip(file["w"], file["c"], file["a"], file["n"], file["b"]):
            if kept[w] and n is not None and b:
                item, _, label = file["answers"][a]
                group = (file["waves"][w][0], tuple(file["cuts"][c]))
                people[(*group, answer_key(item, label))] = n
                asked[group] = b
    return people, asked, weeks


def parts(tab: dict, answers: list[str]) -> list[tuple[str, list[str], list[str], list[str]]]:
    """Each answer of the tab as (name, the answers it counts, those it takes off, the answers that show its group was
    asked it): a multiple-answer question's own answers less the non-answers, a scale's sums, or a grid's rows."""
    def match(pattern: str | None, among: list[str]) -> list[str]:
        return [a for a in among if pattern and re.search(pattern, a, re.I)]
    if "sums" in tab:
        return [(s["name"], match(s["plus"], answers), match(s.get("minus"), answers), answers) for s in tab["sums"]]
    if "rows" in tab:
        rows = dict.fromkeys(a.rsplit(": ", 1)[0] for a in answers if ": " in a)
        found = []
        for row in rows:
            own = [a for a in answers if a.startswith(f"{row}: ")]
            scale = [a[len(row) + 2:] for a in own]
            found.append((row, [f"{row}: {s}" for s in match(tab["rows"]["plus"], scale)],
                          [f"{row}: {s}" for s in match(tab["rows"].get("minus"), scale)], own))
        return found
    skip = re.compile(settings()["leave_out"], re.I)
    return [(a, [a], [], [a]) for a in answers if not skip.search(a.strip())]


def tab_figures(tab: dict, files: list[dict]) -> dict:
    """One tab as the screen draws it: its words, its answers (nets named), the weeks newest first, the groups, and per
    week and group the people asked and each answer's people (None: not asked of that group that week)."""
    people, asked, weeks = counts(files, tab["wording"])
    answers = list(dict.fromkeys(answer for *_, answer in people))
    shown = parts(tab, answers)
    leave = settings().get("leave_out_groups") or {}
    cuts = [cut for cut in dict.fromkeys(cut for _, cut in asked)
            if not (cut[0] in leave and re.search(leave[cut[0]], cut[1], re.I))]
    order = sorted(weeks, key=lambda survey: weeks[survey], reverse=True)
    week_at, cut_at = {s: i for i, s in enumerate(order)}, {c: i for i, c in enumerate(cuts)}
    groups = []
    for (survey, cut), base in asked.items():
        if cut not in cut_at:
            continue
        def figure(plus, minus, own):
            if not any((survey, cut, a) in people for a in own):
                return None
            return sum(people.get((survey, cut, a), 0) for a in plus) - sum(people.get((survey, cut, a), 0) for a in minus)
        groups.append([week_at[survey], cut_at[cut], base, [figure(*part[1:]) for part in shown]])
    groups.sort(key=lambda g: (g[0], g[1]))
    return {**{k: tab[k] for k in ("name", "answer", "all", "each", "asked")},
            "answers": [name for name, *_ in shown], "nets": [name for name, _, minus, _ in shown if minus],
            "scale": "sums" in tab,   # a scale keeps its order; other answers are ranked on screen
            "weeks": [[s, weeks[s]] for s in order], "cuts": [list(c) for c in cuts], "groups": groups}


def build(read_files) -> dict:
    """Every topic of config/weekly_topics.yml, from `read_files` (code -> its published question files)."""
    return {key: {"title": topic["title"], "lede": topic["lede"],
                  "tabs": [tab_figures(tab, [f for code in tab["codes"] for f in read_files(code)]) for tab in topic["tabs"]]}
            for key, topic in settings()["topics"].items()}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views: api/v1/weekly/<topic>.json.gz for every topic, from the question files of
    the version being built (no database). Returns the bytes written."""
    folder = out / "api/v1/questions" / settings()["family"] / settings()["study_type"]
    spellings: dict[str, list[Path]] = {}   # every spelling of a code: the server's disk tells q1 from Q1, a Mac's does not
    for path in folder.iterdir() if folder.is_dir() else []:
        spellings.setdefault(path.name.lower(), []).append(path)

    @lru_cache(maxsize=None)
    def read_files(code: str) -> tuple[dict, ...]:   # each file read once, though tabs share it (Q6: three)
        return tuple(json.loads(gzip.decompress(p.read_bytes())) for p in spellings.get(f"{code.lower()}.json.gz", []))
    return sum(write(out / "api/v1/weekly" / key, topic) for key, topic in build(read_files).items())
