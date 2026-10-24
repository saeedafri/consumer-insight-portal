"""The ETL's serving layer (etl/serving.py): finished rows with comparisons, built at the end of each load.

The 2026 Holiday tracker shapes: XM1 went to 'started shopping' only in wave 2 and to everyone in wave 3,
and last year's same week (13 Oct 2025) is hibernated in Forsta until someone reactivates it."""
import json
from datetime import date

import sqlalchemy as sa

from app.data import payloads
from etl import forsta_etl, serving

served = lambda data: json.loads(payloads.encode(data))   # what the API sends


def seed(conn, survey_id, day, qualified, xm1_yes, xm1_base, path=None,
         qtext="Did you make any holiday purchases in the last seven days?"):
    """A verified CSI-US tracker wave with one cubed question (XM1 yes/no), Total and one generation cut."""
    conn.execute(sa.text("INSERT INTO cip_survey (survey_id, forsta_host, forsta_path, title, wave_label, wave_date,"
                         " survey_family, study_type, load_status) VALUES (:s, 'h', :p, 'Tracker', :d, :d, 'CSI-US',"
                         " 'tracker', 'verified')"), {"s": survey_id, "p": path or f"p{survey_id}", "d": day})
    conn.execute(sa.text("INSERT INTO cip_respondent (survey_id, record_no, is_qualified) VALUES (:s, :r, 1)"),
                 [{"s": survey_id, "r": r} for r in range(qualified)])
    qid = conn.execute(sa.text("INSERT INTO cip_question (survey_id, qcode, qtext, qtype) VALUES (:s, 'XM1', :t, 'single')"),
                       {"s": survey_id, "t": qtext}).lastrowid
    for code, n in ((1, xm1_yes), (2, xm1_base - xm1_yes)):
        oid = conn.execute(sa.text("INSERT INTO cip_option (question_id, value_code, value_label) VALUES (:q, :c, :l)"),
                           {"q": qid, "c": code, "l": "Yes" if code == 1 else "No"}).lastrowid
        for dim, value, scale in (("total", "Total", 1), ("generation", "GenZ", 0.1)):
            conn.execute(sa.text("INSERT INTO cip_agg_cell (survey_id, cell_key, question_id, option_id, dim, dim_value,"
                                 " n, base_n) VALUES (:s, :k, :q, :o, :d, :v, :n, :b)"),
                         {"s": survey_id, "k": f"{qid}:{oid}:{dim}", "q": qid, "o": oid, "d": dim, "v": value,
                          "n": round(n * scale), "b": round(xm1_base * scale)})


def rows(engine, survey_id, dim="total"):
    with engine.connect() as conn:
        return {r.option_label: r for r in conn.execute(sa.text(
            "SELECT * FROM srv_result WHERE survey_id = :s AND qcode = 'XM1' AND dim = :d"), {"s": survey_id, "d": dim})}


def test_a_wave_gets_finished_rows_with_its_prior_week_and_honest_flags(csi_db):
    with csi_db.begin() as conn:
        conn.execute(sa.text("INSERT INTO cip_forsta_survey (forsta_path, title, state, last_seen, launched_at)"
                             " VALUES ('selfserve/58f/251000', 'Tracker', 'closed', CURRENT_TIMESTAMP, '2025-10-13 12:00')"))
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)    # asked of 'started' only
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)  # asked of everyone
    assert serving.build_wave(266) == 4 and serving.build_wave(412) == 4
    yes = rows(csi_db, 412)["Yes"]
    assert float(yes.pct) == 30.941 and float(yes.prior_pct) == 61.745 and yes.prior_base_n == 149
    assert yes.flags == "base_changed_prior"                     # 149/401 asked last week, 404/404 now
    assert "small_base" in rows(csi_db, 412, "generation")["Yes"].flags        # GenZ base 40
    with csi_db.connect() as conn:
        wave = conn.execute(sa.text("SELECT prior_survey_id, ly_survey_id, ly_status FROM srv_wave WHERE survey_id = 412")).one()
    assert tuple(wave) == (266, None, "not_loaded")              # last year's week is hibernated: reported, not substituted


def test_a_reused_code_is_not_compared_with_last_weeks_different_question(csi_db):
    with csi_db.begin() as conn:   # 4 Dec 2023: Q13 was footwear the week before, Cyber Monday this week; both Yes/No
        seed(conn, 134, date(2023, 11, 27), qualified=400, xm1_yes=120, xm1_base=400,
             qtext="Have you purchased any footwear in the past three months?")
        seed(conn, 135, date(2023, 12, 4), qualified=400, xm1_yes=200, xm1_base=400,
             qtext="Did you do any shopping on Cyber Monday this year?")
        seed(conn, 136, date(2023, 12, 11), qualified=400, xm1_yes=190, xm1_base=400,
             qtext="Did you do any shopping on  Cyber Monday this year? (Select one)")   # spacing and instructions only
    for sid in (134, 135, 136):
        serving.build_wave(sid)
    yes = rows(csi_db, 135)["Yes"]
    assert yes.prior_pct is None and yes.flags == "wording_changed_prior"
    assert float(rows(csi_db, 136)["Yes"].prior_pct) == 50.0      # same question, reformatted: still compared
    trend = served(payloads.family_trend("CSI-US", "tracker", "XM1", "generation", "GenZ"))
    assert [w["version"] for w in trend["waves"]] == [1, 2, 2]   # a trend line never joins footwear to Cyber Monday
    assert trend["versions"][0].startswith("Have you purchased any footwear")


def test_loading_last_years_week_fills_this_years_comparison(csi_db):
    with csi_db.begin() as conn:
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(412)
    with csi_db.begin() as conn:                                  # the 2025 week is recovered and loaded
        seed(conn, 230, date(2025, 10, 13), qualified=400, xm1_yes=100, xm1_base=400)
    serving.build_wave(230)
    assert serving.rebuild_dependants(230) == [412]
    assert float(rows(csi_db, 412)["Yes"].ly_pct) == 25.0


def test_the_etl_builds_serving_rows_inside_the_load_and_refreshes_dependants_after(csi_db, monkeypatch):
    from tests.test_forsta_etl import FakeForsta
    calls = []
    monkeypatch.setattr(serving, "build_wave", lambda sid: calls.append(("build", sid)) or 0)
    monkeypatch.setattr(serving, "rebuild_dependants", lambda sid: calls.append(("dependants", sid)) or [])
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert calls == [("build", sid), ("dependants", sid)]


def test_a_real_load_builds_its_serving_rows(csi_db):
    from tests.test_forsta_etl import FakeForsta
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:
        built = conn.execute(sa.text("SELECT rows_built FROM srv_wave WHERE survey_id = :s"), {"s": sid}).scalar()
        stored = conn.execute(sa.text("SELECT COUNT(*) FROM srv_result WHERE survey_id = :s"), {"s": sid}).scalar()
    assert built == stored > 0


def test_a_real_load_stores_answers_whose_two_cuts_add_up_to_its_serving_rows(csi_db):
    from tests.test_forsta_etl import FakeForsta
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:
        stored = conn.execute(sa.text("SELECT COUNT(*) FROM srv_answer WHERE survey_id = :s"), {"s": sid}).scalar()
        # summed over every cut, each count (and every multi base) equals srv_result's Total row (this wave asked no
        # generation question: a cut with no value is not a segment, so srv_result has no generation rows)
        mine = {tuple(r[:4]): r[4] for r in conn.execute(sa.text(
            "SELECT qcode, 'Total', item_id, option_id, COUNT(*) FROM srv_answer WHERE survey_id = :s"
            " GROUP BY qcode, item_id, option_id"), {"s": sid})}
        theirs = conn.execute(sa.text(
            "SELECT qcode, dim_value, item_id, option_id, n, base_n, qtype FROM srv_result"
            " WHERE survey_id = :s AND dim = 'total'"), {"s": sid}).all()
        blank = conn.execute(sa.text("SELECT COUNT(*) FROM srv_result WHERE survey_id = :s AND dim_value = ''"), {"s": sid}).scalar()
    assert blank == 0
    assert stored > 0 and theirs
    for qcode, value, item, option, n, base, qtype in theirs:
        assert mine.get((qcode, value, item, option), 0) == n
        if option == 0:
            assert mine[(qcode, value, 0, 0)] == base


def test_crosstab_shows_tiny_cells_flags_small_ones_and_pools_weeks_by_answer(csi_db):
    from api import main
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    rid = iter(range(1, 10_000))
    with csi_db.begin() as conn:
        option = {(s, l): o for s, l, o in conn.execute(sa.text(
            "SELECT survey_id, option_label, option_id FROM srv_result WHERE qcode = 'XM1' AND dim = 'total'"))}
        answers = []
        for sid, generation, gender, yes, no in ((412, "GenZ", "Female", 2, 2), (412, "Boomer", "Male", 20, 20),
                                                 (412, "Boomer", "Female", 15, 45), (412, "", "Female", 1, 0),
                                                 (266, "GenZ", "Female", 10, 10)):
            for label, count in (("Yes", yes), ("No", no)):
                answers += [{"s": sid, "o": option[(sid, label)], "r": next(rid), "g": generation, "x": gender}
                            for _ in range(count)]
        conn.execute(sa.text("INSERT INTO srv_answer (survey_id, qcode, item_id, option_id, respondent_id, generation,"
                             " gender) VALUES (:s, 'XM1', 0, :o, :r, :g, :x)"), answers)
    read = lambda weeks: served(payloads.crosstab(412, "XM1", ("generation", "gender"), weeks))
    one = read(1)
    yes = {(v1, v2): dict(zip(one["columns"], r)) for r in one["rows"] for v1, v2 in [r[:2]] if r[3] == 1}
    tiny = yes[("GenZ", "Female")]
    assert (tiny["n"], tiny["pct"], tiny["base_n"], tiny["flags"]) == (2, 50.0, 4, "small_base")   # 4 people: shown, flagged
    assert (yes[("Boomer", "Male")]["pct"], yes[("Boomer", "Male")]["flags"]) == (50.0, "small_base")
    assert (yes[("Boomer", "Female")]["pct"], yes[("Boomer", "Female")]["flags"]) == (25.0, "")
    assert all(r[0] for r in one["rows"]) and one["weeks"] == 1 and one["warnings"] == []
    two = read(2)
    pooled = next(dict(zip(two["columns"], r)) for r in two["rows"] if r[:2] == ["GenZ", "Female"] and r[3] == 1)
    assert (pooled["n"], pooled["base_n"], pooled["flags"]) == (12, 24, "small_base")   # ids differ, answers pooled; 24 is shown
    with csi_db.connect() as conn:   # the API's published path: cut tables written as JSON, paired in memory
        waves = payloads.pool(conn, 412, 2)
        parts = {sid: served(part) for (sid, _), part in payloads.question_cuts(conn, [266, 412], "XM1").items()}
    assert served(payloads.crosstab_from(412, "XM1", ("generation", "gender"), waves, parts)) == two
    assert [w["survey_id"] for w in two["waves"]] == [412, 266]
    assert two["warnings"] == ["base_changed_within_pool"]       # XM1 asked of 149/401, then 404/404


def test_the_book_gives_any_wave_in_the_dashboards_shape_and_the_picker_lists_it(csi_db):
    from api import main
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    book = served(payloads.book(412))
    assert book["columns"] == ["Total", "Male", "Female", "Gen Z", "Millennial", "Gen X", "Boomer"]
    assert book["n"]["Total"] == 404 and book["wave"]["wave_date"] == "2026-10-12"
    (question,) = book["questions"]                              # XM1, single choice: one group, a row per answer
    assert (question["id"], question["type"], len(question["groups"])) == ("XM1", "single", 1)
    yes = next(r for r in question["groups"][0]["rows"] if r["label"] == "Yes")
    assert (yes["Total"], yes["prior"], yes["Gen Z"], "Male" in yes) == (30.9, 61.7, 30.0, False)
    assert yes["flags"] == "base_changed_prior" and question["groups"][0]["base"] == 404
    picker = served(payloads.waves({}))
    assert [w["survey_id"] for w in picker] == [412, 266] and picker[0]["prior_survey_id"] == 266


def test_an_answer_nobody_in_a_group_chose_shows_zero_not_blank(csi_db):
    with csi_db.begin() as conn:   # the cube keeps no cell for an answer nobody gave: Gen Z's "No" here
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
        conn.execute(sa.text("DELETE FROM cip_agg_cell WHERE survey_id = 412 AND dim = 'generation' AND cell_key LIKE '%:2:%'"))
    serving.build_wave(412)
    (group,) = served(payloads.book(412))["questions"][0]["groups"]
    no = next(r for r in group["rows"] if r["label"] == "No")
    assert (no["Total"], no["Gen Z"], "Male" in no) == (69.1, 0.0, False)   # Gen Z was asked: 0 %; no Male cut at all


def test_trend_follows_a_question_across_its_family_and_search_finds_it(csi_db):
    from api import main
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    trend = served(payloads.trend(412, "XM1", "total", "Total"))
    assert [w["survey_id"] for w in trend["waves"]] == [266, 412]
    yes = next(s for s in trend["series"] if s["label"] == "Yes")
    assert yes["pct"] == [61.7, 30.9] and yes["base"] == [149, 404]
    index = main._load_catalogue()
    (hit,) = index.search("holiday seven")["results"]
    assert (hit["qcode"], hit["waves"], hit["survey_id"], hit["last"]) == ("XM1", 2, 412, "2026-10-12")
    assert index.search("Yes")["results"][0]["qcode"] == "XM1"          # found by an answer label


def test_the_result_cache_stays_under_its_byte_cap(monkeypatch):
    import asyncio
    from api import main
    monkeypatch.setattr(main, "RESULTS", main.OrderedDict())
    monkeypatch.setattr(main, "CACHED_BYTES", 0)
    monkeypatch.setattr(main, "CACHE_BYTES", 3_000)
    for i in range(10):
        asyncio.run(main._cached(("k", i), lambda i: main._json({"pad": "x" * 500, "i": i}), i))
    assert main.CACHED_BYTES <= 3_000 and ("k", 9) in main.RESULTS and ("k", 0) not in main.RESULTS


def test_the_question_file_holds_every_wave_and_cut_with_its_versions(csi_db):
    with csi_db.begin() as conn:
        seed(conn, 134, date(2023, 11, 27), qualified=400, xm1_yes=120, xm1_base=400,
             qtext="Have you purchased any footwear in the past three months?")
        seed(conn, 135, date(2023, 12, 4), qualified=400, xm1_yes=200, xm1_base=400,
             qtext="Did you do any shopping on Cyber Monday this year?")
        seed(conn, 136, date(2023, 12, 11), qualified=400, xm1_yes=190, xm1_base=400,
             qtext="Did you do any shopping on Cyber Monday this year?")
    for sid in (134, 135, 136):
        serving.build_wave(sid)
    data = served(payloads.question("CSI-US", "tracker", "XM1"))
    assert data["waves"] == [[134, "2023-11-27", 1], [135, "2023-12-04", 2], [136, "2023-12-11", 2]]
    assert data["versions"][1] == "Did you do any shopping on Cyber Monday this year?"
    assert data["answers"] == [["", 1, "Yes"], ["", 2, "No"]] and data["cuts"] == [["total", "Total"], ["generation", "GenZ"]]
    cells = list(zip(data["w"], data["c"], data["a"], data["n"], data["b"]))
    assert (2, 0, 0, 190, 400) in cells and (1, 1, 0, 20, 40) in cells and len(cells) == 12


def test_rebuilding_a_wave_keeps_its_answers_for_two_cut_crosstabs(csi_db):
    from tests.test_forsta_etl import FakeForsta
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    count = lambda: csi_db.connect().execute(sa.text("SELECT COUNT(*) FROM srv_answer WHERE survey_id = :s"), {"s": sid}).scalar()   # noqa: E731
    before = count()
    serving.build_wave(sid)                       # its srv_wave row is replaced, which cascades to srv_answer
    assert before > 0 and count() == before
