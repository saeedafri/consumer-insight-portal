"""etl/weekly_topics.py: the weekly topic screens' figures (Activities & retailers, Spending pressure, Consumer
sentiment & outlook), from small question files built here in the published layout (shared/data/payloads.question_from:
waves [survey_id, date, version], answers [item, code, label], cuts [dim, value], cells w/c/a/n/b)."""
import gzip
import json
import re

import yaml

from etl import weekly_topics
from etl.weekly_topics import build, build_tab

TOTAL, MALE, NOT_SAY = ["total", "Total"], ["gender", "Male"], ["income_band", "Prefer not to answer"]


def question(versions, waves, answers, cuts, cells):
    """A question file: cells as (wave index, cut index, answer index, people, asked)."""
    w, c, a, n, b = (list(x) for x in zip(*cells))
    return {"versions": versions, "waves": waves, "answers": answers, "cuts": cuts, "w": w, "c": c, "a": a, "n": n, "b": b}


def figure(tab, survey, cut, answer):
    """A tab's figure as the screen shows it: 100 n / b, or None."""
    week = next(i for i, x in enumerate(tab["weeks"]) if x[0] == survey)
    group = next((g for g in tab["groups"] if g[0] == week and g[1] == tab["cuts"].index(cut)), None)
    n = group and group[3][tab["answers"].index(answer)]
    return None if n is None else round(100 * n / group[2], 1)


TAB = {"name": "T", "answer": "A", "all": "all", "each": "each", "asked": "asked"}


def test_a_multiple_answer_question_keeps_real_other_answers_and_drops_the_non_answers():
    """D15 on 23 Nov 2026 lists "Other savings / investments" (17.2%): a real answer. "Other (please specify)", "None of
    these" and "Don't know" are no answers. A retailer not offered that week is None, not 0 (multiple-answer files
    store their zeros)."""
    answers = [["Travel", None, "Travel"], ["Other savings / investments", None, "Other savings / investments"],
               ["Other (please specify)", None, "Other (please specify)"], ["None of these", None, "None of these"],
               ["Don't know", None, "Don't know"], ["Real estate", None, "Real estate"]]
    file = question(["Where have you reduced your spending due to higher gas prices?"], [[725, "2026-11-23", 1]], answers, [TOTAL],
                    [(0, 0, 0, 50, 200), (0, 0, 1, 34, 200), (0, 0, 2, 3, 200), (0, 0, 3, 9, 200), (0, 0, 4, 1, 200)])
    tab = build_tab({**TAB, "wording": "reduced your spending"}, [file])
    assert tab["answers"] == ["Travel", "Other savings / investments"]   # Real estate never had a cell: never offered
    assert figure(tab, 725, TOTAL, "Other savings / investments") == 17.0
    assert tab["nets"] == [] and not tab["scale"]


def test_a_scale_sums_its_sides_and_counts_an_answer_nobody_gave_as_zero():
    """CS1: net better = better less worse, in points. Non-binary (4 people) gave no "Somewhat better": the file has no
    cell for it, so better is "Much better" alone; a group nobody answered is None."""
    scale = ["Much worse", "Somewhat worse", "About the same", "Somewhat better", "Much better", "Don't know / not sure"]
    nb = ["gender", "Non-binary / third gender"]
    file = question(["Considering your discretionary income (what is left over…), better or worse?"], [[725, "2026-11-23", 1]],
                    [["", i + 1, label] for i, label in enumerate(scale)], [TOTAL, nb, MALE],
                    [(0, 1, 0, 1, 4), (0, 1, 1, 1, 4), (0, 1, 2, 1, 4), (0, 1, 4, 1, 4),   # Non-binary's cells come first
                     (0, 0, 0, 80, 404), (0, 0, 1, 72, 404), (0, 0, 2, 137, 404), (0, 0, 3, 60, 404), (0, 0, 4, 33, 404), (0, 0, 5, 22, 404)])
    sums = yaml.safe_load((weekly_topics.CONFIG / "weekly_topics.yml").read_text())["outlook"]
    tab = build_tab({**TAB, "wording": "discretionary income", "sums": sums}, [file])
    assert tab["answers"] == ["Net better", "Better", "About the same", "Worse", "Don't know"] and tab["nets"] == ["Net better"]
    assert figure(tab, 725, TOTAL, "Net better") == round(100 * (60 + 33 - 80 - 72) / 404, 1) == -14.6
    assert figure(tab, 725, nb, "Better") == 25.0 and figure(tab, 725, nb, "Net better") == -25.0
    assert MALE not in tab["cuts"]   # no cells: never asked of that group
    assert tab["cuts"] == [TOTAL, nb]   # the file's order (Gen Z before Millennial), not the order cells come in


def test_a_grid_adds_up_each_row_and_a_reused_code_counts_only_its_own_weeks():
    """Q6 held food retailers until Jun 2026 and expenses from Jul 2026: the food week is left out. Utilities up =
    notable + significant increase (149 + 79 of 404 = 56.4%, staging's rounded 36.9 + 19.6); net = up less down."""
    scale = ["Significant decrease", "Notable decrease", "No meaningful change", "Notable increase", "Significant increase"]
    answers = [["Utilities", i + 1, s] for i, s in enumerate(scale)] + [["Walmart", None, "Walmart"]]
    file = question(["Which, if any, of these retailers have you bought any FOOD products from in the past two weeks?",
                     "In the last twelve months, how have your expenses changed in each of the following categories?"],
                    [[515, "2026-06-29", 1], [725, "2026-11-23", 2]], answers, [TOTAL, NOT_SAY],
                    [(0, 0, 5, 250, 400), (1, 0, 0, 14, 404), (1, 0, 1, 14, 404), (1, 0, 2, 148, 404), (1, 0, 3, 149, 404),
                     (1, 0, 4, 79, 404), (1, 1, 3, 2, 5)])
    up = build_tab({**TAB, "wording": "how have your expenses changed", "rows": {"plus": "increase"}}, [file])
    net = build_tab({**TAB, "wording": "how have your expenses changed", "rows": {"plus": "increase", "minus": "decrease"}}, [file])
    assert [w[0] for w in up["weeks"]] == [725] and up["answers"] == ["Utilities"]
    assert figure(up, 725, TOTAL, "Utilities") == 56.4 and figure(net, 725, TOTAL, "Utilities") == 49.5
    assert net["nets"] == ["Utilities"]
    assert NOT_SAY not in up["cuts"]   # household income's "Prefer not to answer" is no group (25 Nov 2026)


def test_two_files_of_one_question_join_by_wording_newest_week_first():
    """Activities: Q3 from Aug 2022 to Dec 2023, Q1 otherwise; both files can hold a borrowed week, with the same counts."""
    wording = "Which, if any, of these have you done in the past two weeks?"
    met = [["Met up with friends", None, "Met up with friends"]]
    q1 = question([wording], [[725, "2026-11-23", 1], [100, "2023-06-05", 1]], met, [TOTAL], [(0, 0, 0, 242, 404), (1, 0, 0, 230, 400)])
    q3 = question([wording], [[100, "2023-06-05", 1], [90, "2023-05-29", 1]], met, [TOTAL], [(0, 0, 0, 230, 400), (1, 0, 0, 228, 400)])
    tab = build_tab({**TAB, "wording": "have you done in the past two weeks"}, [q1, q3])
    assert [w[0] for w in tab["weeks"]] == [725, 100, 90]
    assert figure(tab, 725, TOTAL, "Met up with friends") == 59.9 and figure(tab, 90, TOTAL, "Met up with friends") == 57.0


def test_every_topic_is_a_menu_and_every_tab_is_complete():
    """config/weekly_topics.yml: each topic's key is a feature of config/access.yml (its menu and address), and each tab
    names its codes, a wording that compiles, its words and one way of reading its answers."""
    topics = weekly_topics.settings()["topics"]
    features = yaml.safe_load((weekly_topics.CONFIG / "access.yml").read_text())["features"]
    assert set(topics) == {"activities", "spending", "sentiment"} and set(topics) <= set(features)
    for topic in topics.values():
        assert topic["title"] and topic["lede"]
        for tab in topic["tabs"]:
            assert tab["codes"] and re.compile(tab["wording"]) and all(tab[k] for k in ("name", "answer", "all", "each", "asked"))
            assert not ("sums" in tab and "rows" in tab)
    built = build(lambda code: ())   # no files yet (a fresh install): every topic still publishes, empty
    assert all(tab["weeks"] == [] and tab["groups"] == [] for topic in built.values() for tab in topic["tabs"])


def test_publish_reads_a_code_in_any_spelling_and_writes_one_file_per_topic(tmp_path):
    """The server's disk tells q1 from Q1 (the Mac's does not): config's Q1 is read from a file spelled q1."""
    folder = tmp_path / "api/v1/questions/CSI-US/tracker"
    folder.mkdir(parents=True)
    met = [["Met up with friends", None, "Met up with friends"]]
    file = question(["Which, if any, of these have you done in the past two weeks?"], [[725, "2026-11-23", 1]], met, [TOTAL], [(0, 0, 0, 242, 404)])
    (folder / "q1.json.gz").write_bytes(gzip.compress(json.dumps(file).encode()))
    written = {}
    assert weekly_topics.publish(tmp_path, lambda path, data: written.setdefault(path.name, data) and 1) == 3
    activities = written["activities"]["tabs"][0]
    assert set(written) == {"activities", "spending", "sentiment"} and figure(activities, 725, TOTAL, "Met up with friends") == 59.9
