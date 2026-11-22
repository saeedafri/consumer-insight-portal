"""The expected answers of Ask's hard test set (scripts/ask_hard.yml), worked out from the raw weekly survey files alone.

Each case in ask_hard.yml carries a plan: what is counted (ask), among whom (among), split by what (by), over which
weeks, and the operation (share, top, chain, counts). This script reads the raw Excel exports (one row per respondent,
one column per answer: what Forsta gives the data team) with pandas, runs each plan with plain counting, and writes the
figures into the case's `expect`. Nothing here uses Ask's own code, so the test cannot agree with Ask by sharing a bug.

Run by hand when cases are added (the raw files are not in the repo):
    python scripts/ask_hard_truth.py ~/Downloads/Collab/ask-benchmark scripts/ask_hard.yml
Read by scripts/ask_hard.py, which scores Ask against the figures. Written 22 Nov 2026 (step 1 of the Ask rebuild).

A plan's share is of those asked the question (and in its group); `base: all` makes it a share of everyone.

A condition, in a plan:
    {q: XM3, is: [Still shopping, Finished shopping]}   a single-choice answer (a label's start is enough)
    {q: D28, is: [ChatGPT]}                             a select-all item chosen
    {q: D28, any: true}                                 any item chosen but a "none of these" one
    {q: q6, item: Utilities, is: [Notable increase]}    one row of a grid
    {q: D2, between: [18, 34]}                          a number (age)
    {either: [...]}, {both: [...]}, {not: {...}}        combined
"""
import glob
import html
import math
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

NONE_LIKE = re.compile(r"^(none of|have not|i have not|haven't|did not|do not|i do not|not used)", re.I)


def clean(text) -> str:
    return " ".join(html.unescape(str(text)).replace("\xa0", " ").split())


def load(folder: Path) -> dict:
    """Each raw wave by its fielded date: its rows and, per question code, its columns and kind."""
    waves = {}
    for path in sorted(glob.glob(str(folder / "Coresight US weekly survey *.xlsx"))):
        date = re.search(r"(\d{4}-\d{2}-\d{2})", path)[1]
        data, questions = pd.read_excel(path, "Data"), pd.read_excel(path, "Questions")
        codes: dict = {}
        for _, row in questions.iterrows():
            entry = codes.setdefault(str(row["Question code"]), {"multi": "select all" in str(row["Type"]), "columns": {}})
            column = row["Column"]
            if re.search(r"oe$", column.split(": ", 1)[0]):   # an "Other (please specify)" typed text: not an answer, and
                continue                                      # it shares its tick box's label (it hid D28's Other)
            entry["columns"][clean(column.split(": ", 1)[1]) if ": " in column else ""] = column
        waves[date] = {"data": data, "codes": codes}
    return waves


def mask(wave: dict, cond: dict) -> tuple[pd.Series, pd.Series]:
    """(true, asked) for one condition in one wave: who meets it, and who was asked the questions it reads."""
    data = wave["data"]
    if "either" in cond or "both" in cond:
        parts = [mask(wave, c) for c in cond.get("either") or cond["both"]]
        true = parts[0][0].copy()
        for t, _ in parts[1:]:
            true = true | t if "either" in cond else true & t
        asked = parts[0][1].copy()
        for _, a in parts[1:]:
            asked = asked & a
        return true & asked, asked
    if "not" in cond:
        true, asked = mask(wave, cond["not"])
        return ~true & asked, asked
    entry = wave["codes"][cond["q"]]
    columns = entry["columns"]
    if "item" in cond:   # a grid row: one single-choice column
        columns = {k: v for k, v in columns.items() if k.lower().startswith(cond["item"].lower())}
    asked = data[list(columns.values())].notna().any(axis=1)
    if "between" in cond:
        low, high = cond["between"]
        values = pd.to_numeric(data[next(iter(columns.values()))].astype(str).str.replace(r"(?i)under\s*\d+", "", regex=True)
                               .str.extract(r"(\d+)")[0], errors="coerce")   # "70 or more" is 70; "Under 18" is no adult age
        return values.between(low, high) & asked, asked
    if entry["multi"]:
        wanted = [v for k, v in columns.items() if not NONE_LIKE.match(k)] if cond.get("any") else \
                 [v for k, v in columns.items() if any(k.lower().startswith(w.lower()) for w in cond["is"])]
        if not wanted:
            raise KeyError(f"{cond}: no column matches; columns are {list(columns)[:12]}")
        return (data[wanted] == 1).any(axis=1) & asked, asked
    values = data[next(iter(columns.values()))].map(lambda v: clean(v) if pd.notna(v) else None)
    if cond.get("any"):
        return values.notna(), asked
    labels = set(values.dropna())
    if not any(any(l.lower().startswith(w.lower()) for l in labels) for w in cond["is"]):
        raise KeyError(f"{cond}: no answer matches; answers are {sorted(labels)[:12]}")
    return values.map(lambda v: v is not None and any(v.lower().startswith(w.lower()) for w in cond["is"])), asked


def row(label: str, when: str, n: int, base: int, group: str | None = None) -> dict:
    out = {"when": when, "label": label, "pct": round(100 * n / base, 1) if base else None, "n": int(n), "base": int(base)}
    return {**out, "group": group} if group else out


def answers_of(wave: dict, code: str) -> list[str]:
    """A question's answers in survey order: its items (select-all) or its answers as given."""
    entry = wave["codes"][code]
    if entry["multi"]:
        return list(entry["columns"])
    values = wave["data"][next(iter(entry["columns"].values()))].dropna().map(clean)
    return list(dict.fromkeys(values))


def run(plan: dict, waves: dict) -> list[dict]:
    """The expected rows of one plan: a share, a top list, the steps of a chain, or each answer's count."""
    when = [str(w) for w in plan["waves"]]   # YAML reads 2026-11-16 as a date
    pooled = plan.get("per") == "pooled"
    groups = [(None, None)]
    if "by" in plan:
        by = plan["by"]
        if "groups" in by:
            groups = list(by["groups"].items())
        else:
            groups = [(a, {"q": by["q"], "is": [a]}) for a in answers_of(waves[when[-1]], by["q"])
                      if not re.match(r"prefer not", a, re.I)]
    out = []
    buckets = [("pooled", when)] if pooled else [(w, [w]) for w in when]
    op = plan.get("op", "share")
    for label_when, dates in buckets:
        for group, group_cond in groups:
            totals: dict = {}
            for date in dates:
                wave = waves[date]
                among = pd.Series(True, index=wave["data"].index)
                if "among" in plan:
                    true, _ = mask(wave, plan["among"])
                    among &= true
                if group_cond:
                    true, _ = mask(wave, group_cond)
                    among &= true
                if op == "share":
                    true, asked = mask(wave, plan["ask"])
                    key = plan.get("say", "share")
                    n, b = totals.get(key, (0, 0))
                    base = among if plan.get("base") == "all" else asked & among   # "of all respondents", not those asked
                    totals[key] = (n + int((true & among).sum()), b + int(base.sum()))
                elif op in ("top", "counts"):
                    code = plan["ask"]["q"]
                    for answer in answers_of(wave, code):
                        if NONE_LIKE.match(answer) and op == "top":
                            continue
                        true, asked = mask(wave, {"q": code, "is": [answer]})
                        n, b = totals.get(answer, (0, 0))
                        totals[answer] = (n + int((true & among).sum()), b + int((asked & among).sum()))
                elif op == "chain":
                    reached = among
                    for number, step in enumerate(plan["steps"], 1):
                        true, asked = mask(wave, step)
                        n, b = totals.get(step.get("say", f"step {number}"), (0, 0))
                        totals[step.get("say", f"step {number}")] = (n + int((true & reached).sum()), b + int(reached.sum()))
                        reached = reached & true
            rows = [row(label, label_when, n, b, group) for label, (n, b) in totals.items()]
            if op == "top":
                rows = sorted(rows, key=lambda r: -(r["pct"] or 0))[: plan.get("top", 5)]
            out += rows
    if op == "share" and len(out) == 2 and plan.get("test"):   # two weeks or two groups: the change and its test
        (a, b) = out
        p1, p2 = a["n"] / a["base"], b["n"] / b["base"]
        pooled_p = (a["n"] + b["n"]) / (a["base"] + b["base"])
        z = (p2 - p1) / math.sqrt(pooled_p * (1 - pooled_p) * (1 / a["base"] + 1 / b["base"]))
        out.append({"label": "change", "points": round(100 * (p2 - p1), 1), "p": round(math.erfc(abs(z) / math.sqrt(2)), 3)})
    return out


def main(folder: str, cases_path: str) -> None:
    waves = load(Path(folder).expanduser())
    path = Path(cases_path)
    cases = yaml.safe_load(path.read_text())
    for case in cases:
        if "plan" in case:
            case["expect"] = run(case["plan"], waves)
    header = "".join(line for line in path.read_text().splitlines(keepends=True) if line.startswith("#"))
    path.write_text(header + yaml.safe_dump(cases, sort_keys=False, allow_unicode=True, width=140))
    print(f"{sum('plan' in c for c in cases)} plans worked out, {sum('refuse' in c for c in cases)} refusals")


if __name__ == "__main__":
    main(*sys.argv[1:3])
