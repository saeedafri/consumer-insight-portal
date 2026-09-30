"""Phase 2: linking each wave's questions to canonical concepts.

See docs/superpowers/specs/2026-09-29-survey-platform-design.md §5.2.
"""
from __future__ import annotations

import sqlalchemy as sa

from app.data import harmonise


def test_normalise_text_folds_formatting_and_instructions():
    raw = ("Which, if any,\xa0of these  retailers have you bought from? "
           "Select all that apply or “None of these”")
    assert harmonise.normalise_text(raw) == \
        "which, if any, of these retailers have you bought from"
    assert harmonise.normalise_text("Kohl’sÂ (excluding Sephora)") == \
        "kohl's (excluding sephora)"
    assert harmonise.normalise_text(None) == ""


def test_slug_is_short_and_stable():
    assert harmonise.slug("Amazon.com") == "amazon_com"
    assert harmonise.slug("x" * 99, limit=10) == "x" * 10
    assert harmonise.slug("???") == "x"


def test_concepts_store_their_full_matching_wording(csi_db):
    cols = {c["name"] for c in sa.inspect(csi_db).get_columns("csi_concept")}
    assert "match_text" in cols


def add_wave(engine, wave: str, questions: list[dict]) -> int:
    """Insert a minimal wave. Each question: qcode, qtext, qtype, and
    `answers` (single options / multi items) or `rows` + `answers` (grid);
    `technical=True` marks paradata."""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO csi_survey (forsta_host, forsta_path, title, wave_label,"
            " platform, source_ref) VALUES ('h', 'p', 't', :w, 'forsta', 'p')"), {"w": wave})
        sid = conn.execute(sa.text("SELECT survey_id FROM csi_survey WHERE wave_label = :w"),
                           {"w": wave}).scalar()
        for order, q in enumerate(questions, 1):
            conn.execute(sa.text(
                "INSERT INTO csi_question (survey_id, qcode, qtext, qtype, is_technical,"
                " is_multi, sort_order) VALUES (:s, :c, :t, :y, :tech, :m, :o)"),
                {"s": sid, "c": q["qcode"], "t": q["qtext"], "y": q["qtype"],
                 "tech": int(q.get("technical", False)), "m": int(q["qtype"] == "multi"),
                 "o": order})
            qid = conn.execute(sa.text(
                "SELECT question_id FROM csi_question WHERE survey_id = :s AND qcode = :c"),
                {"s": sid, "c": q["qcode"]}).scalar()
            items = q["answers"] if q["qtype"] == "multi" else q.get("rows", [])
            for i, label in enumerate(items, 1):
                conn.execute(sa.text(
                    "INSERT INTO csi_item (question_id, item_code, item_label, sort_order)"
                    " VALUES (:q, :c, :l, :o)"), {"q": qid, "c": f"{q['qcode']}r{i}", "l": label, "o": i})
            if q["qtype"] != "multi":
                for i, label in enumerate(q.get("answers", []), 1):
                    conn.execute(sa.text(
                        "INSERT INTO csi_option (question_id, value_code, value_label, sort_order)"
                        " VALUES (:q, :v, :l, :o)"), {"q": qid, "v": i, "l": label, "o": i})
    return sid


def maps(engine, sid: int) -> list[tuple]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(sa.text(
            "SELECT q.qcode, m.status, m.method, c.concept_code"
            " FROM csi_concept_map m JOIN csi_question q ON q.question_id = m.question_id"
            " JOIN csi_concept c ON c.concept_id = m.concept_id"
            " WHERE m.survey_id = :s AND m.concept_option_id IS NULL ORDER BY q.sort_order, m.item_id"),
            {"s": sid})]


def count(engine, sql: str) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql)).scalar()


RETAILERS = {"qcode": "q4", "qtype": "multi",
             "qtext": "Which, if any, of these retailers have you bought from? Select all that apply",
             "answers": ["Walmart", "Target", "None of these"]}
GENDER = {"qcode": "D1", "qtype": "single", "qtext": "What is your gender?",
          "answers": ["Male", "Female"]}
LOI = {"qcode": "qtime", "qtype": "numeric", "qtext": "Total Interview Time", "technical": True}


def test_first_wave_seeds_one_confirmed_concept_per_question(csi_db):
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER, LOI])
    assert harmonise.harmonise_survey(sid) == \
        {"exact": 0, "changed": 0, "similar": 0, "new": 2, "skipped": 0}
    assert [m[:2] for m in maps(csi_db, sid)] == [("q4", "confirmed"), ("D1", "confirmed")]
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_option") == 5   # 3 retailers + 2 genders


def test_identical_question_confirms_to_the_same_concept(csi_db):
    a = add_wave(csi_db, "2026-09-21", [RETAILERS])
    harmonise.harmonise_survey(a)
    reformatted = dict(RETAILERS, qtext="Which,\xa0if any, of these retailers have you bought from?")
    b = add_wave(csi_db, "2026-09-28", [dict(reformatted, answers=["Target", "Walmart"])])
    assert harmonise.harmonise_survey(b)["exact"] == 1       # a dropped answer does not block
    assert maps(csi_db, a)[0][3] == maps(csi_db, b)[0][3]
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 1
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map WHERE concept_option_id IS NOT NULL") == 3 + 2


def test_an_added_answer_waits_for_review(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [RETAILERS]))
    b = add_wave(csi_db, "2026-09-28", [dict(RETAILERS, answers=["Walmart", "Target", "Costco"])])
    assert harmonise.harmonise_survey(b)["changed"] == 1
    with csi_db.connect() as conn:
        status, evidence = conn.execute(sa.text(
            "SELECT status, evidence FROM csi_concept_map WHERE survey_id = :s"), {"s": b}).one()
    assert status == "proposed" and "adds: costco" in evidence
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {b}") == 1


def test_reworded_question_is_proposed_unrelated_one_is_new(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER]))
    b = add_wave(csi_db, "2026-09-28", [
        dict(RETAILERS, qtext="Which, if any, of these retailers have you purchased from?"),
        {"qcode": "BT1", "qtype": "single", "answers": ["Yes", "No"],
         "qtext": "Have you purchased any beauty products in the past three months?"}])
    assert harmonise.harmonise_survey(b) == \
        {"exact": 0, "changed": 0, "similar": 1, "new": 1, "skipped": 0}
    assert [m[:3] for m in maps(csi_db, b)] == \
        [("q4", "proposed", "similar_text"), ("BT1", "confirmed", "exact_text")]


def test_grid_rows_are_concepts_sharing_a_group(csi_db):
    grid = {"qcode": "BT14", "qtype": "grid_single", "rows": ["Amazon.com", "Walmart"],
            "qtext": "How do you feel about each retailer?", "answers": ["Positive", "Negative"]}
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [grid]))
    b = add_wave(csi_db, "2026-09-28", [dict(grid, rows=["Amazon.com", "Walmart", "Target"])])
    assert harmonise.harmonise_survey(b) == \
        {"exact": 2, "changed": 0, "similar": 0, "new": 1, "skipped": 0}
    assert count(csi_db, "SELECT COUNT(DISTINCT concept_group) FROM csi_concept") == 1
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 3


def test_harmonise_twice_changes_nothing(csi_db):
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER])
    harmonise.harmonise_survey(sid)
    before = count(csi_db, "SELECT COUNT(*) FROM csi_concept_map")
    assert harmonise.harmonise_survey(sid)["skipped"] == 2
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map") == before


def test_two_identical_questions_in_one_wave_get_two_concepts(csi_db):
    q3 = dict(RETAILERS, qcode="q5")
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, q3])
    assert harmonise.harmonise_survey(sid)["new"] == 2
    assert count(csi_db, "SELECT COUNT(DISTINCT concept_id) FROM csi_concept_map") == 2


def test_long_wording_still_matches_exactly(csi_db):
    long_q = dict(GENDER, qcode="HX1", qtext="Looking back, " + "how did your spending compare " * 12)
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [long_q]))
    b = add_wave(csi_db, "2026-09-28", [long_q])
    assert len(long_q["qtext"]) > 255
    assert harmonise.harmonise_survey(b)["exact"] == 1


def test_text_question_confirms_on_wording_alone(csi_db):
    verbatim = {"qcode": "BT3r17oe", "qtype": "text", "qtext": "Where do you discover beauty? - Other"}
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [verbatim]))
    assert harmonise.harmonise_survey(add_wave(csi_db, "2026-09-28", [verbatim]))["exact"] == 1


import pytest

from app.data import repository


def proposal(engine) -> tuple[int, int, int, int]:
    """A wave whose q4 adds 'Costco' -> (survey_id, question_id, concept_id, first_survey_id)."""
    first = add_wave(engine, "2026-09-21", [RETAILERS])
    harmonise.harmonise_survey(first)
    sid = add_wave(engine, "2026-09-28", [dict(RETAILERS, answers=["Walmart", "Costco"])])
    harmonise.harmonise_survey(sid)
    with engine.connect() as conn:
        qid, cid = conn.execute(sa.text(
            "SELECT question_id, concept_id FROM csi_concept_map WHERE survey_id = :s"), {"s": sid}).one()
    return sid, qid, cid, first


def test_confirm_adds_the_new_answer_and_records_the_reviewer(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    harmonise.confirm(sid, qid, None, cid, "analyst@coresight.com")
    with csi_db.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT status, reviewed_by FROM csi_concept_map WHERE survey_id = :s"
            " AND concept_option_id IS NULL"), {"s": sid}).one()
    assert tuple(row) == ("confirmed", "analyst@coresight.com")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_option WHERE option_code = 'costco'") == 1
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}"
                         " AND concept_option_id IS NOT NULL") == 2


def test_confirm_can_point_at_a_different_concept(csi_db):
    sid, qid, cid, first = proposal(csi_db)
    other = add_wave(csi_db, "2026-08-01", [dict(RETAILERS, qcode="q9", qtext="Where did you shop?")])
    harmonise.harmonise_survey(other)
    with csi_db.connect() as conn:
        other_cid = conn.execute(sa.text(
            "SELECT concept_id FROM csi_concept_map WHERE survey_id = :s"
            " AND concept_option_id IS NULL"), {"s": other}).scalar()
    harmonise.confirm(sid, qid, None, other_cid, "analyst@coresight.com")
    assert maps(csi_db, sid)[0][3] == maps(csi_db, other)[0][3] != maps(csi_db, first)[0][3]


def test_keep_separate_creates_a_new_concept(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    new_cid = harmonise.keep_separate(sid, qid, None, "analyst@coresight.com")
    assert new_cid != cid
    assert maps(csi_db, sid)[0][:3] == ("q4", "confirmed", "manual")


def test_reject_leaves_the_question_untrended(csi_db):
    sid, qid, _, _ = proposal(csi_db)
    harmonise.reject(sid, qid, None, "analyst@coresight.com")
    assert maps(csi_db, sid)[0][1] == "rejected"
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}"
                         " AND concept_option_id IS NOT NULL") == 0


def test_a_decision_cannot_be_made_twice(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    harmonise.confirm(sid, qid, None, cid, "a@coresight.com")
    with pytest.raises(ValueError, match="not awaiting review"):
        harmonise.keep_separate(sid, qid, None, "b@coresight.com")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 1


def test_queue_lists_only_open_proposals(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    uncached = getattr(repository.mapping_queue, "__wrapped__", repository.mapping_queue)
    queue = uncached()
    assert list(queue.qcode) == ["q4"] and "costco" in queue.evidence.iloc[0]
    harmonise.confirm(sid, qid, None, cid, "a@coresight.com")
    assert uncached().empty


import os

from etl import run_pipeline


def test_harmonise_all_runs_oldest_wave_first(csi_db):
    late = add_wave(csi_db, "2026-09-28", [RETAILERS])
    early = add_wave(csi_db, "2026-09-21", [dict(RETAILERS, answers=["Walmart"])])
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE csi_survey SET wave_date = wave_label"))
    result = harmonise.harmonise_all()
    assert list(result) == ["2026-09-21", "2026-09-28"]
    assert result["2026-09-28"]["changed"] == 1          # it adds Target + None of these
    assert maps(csi_db, early)[0][1] == "confirmed" and maps(csi_db, late)[0][1] == "proposed"


@pytest.mark.skipif(not os.getenv("CSI_TEST_RAW"), reason="set CSI_TEST_RAW")
def test_loading_a_wave_harmonises_it(csi_db):
    run_pipeline.ingest_excel(os.environ["CSI_TEST_RAW"], None, "2026-09-21")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 101
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map"
                         " WHERE status = 'proposed'") == 0


# ── fixes from the final review ───────────────────────────────────────────
def test_a_stale_read_cannot_settle_an_already_settled_unit(csi_db, monkeypatch):
    """Two analysts: B's page was loaded before A confirmed. Even when B's own
    status check is stale, the write itself must refuse."""
    sid, qid, cid, _ = proposal(csi_db)
    harmonise.confirm(sid, qid, None, cid, "a@coresight.com")
    real = harmonise._open_unit

    def stale(conn, survey_id, question_id, item_id):        # B's check saw 'proposed'
        return next(u for u in harmonise._units(conn, survey_id)
                    if u.question_id == question_id and u.item_id == item_id)
    monkeypatch.setattr(harmonise, "_open_unit", stale)
    with pytest.raises(ValueError, match="not awaiting review"):
        harmonise.reject(sid, qid, None, "b@coresight.com")
    monkeypatch.setattr(harmonise, "_open_unit", real)
    assert maps(csi_db, sid)[0][1] == "confirmed"


def test_keep_separate_sticks_for_the_next_wave(csi_db):
    sid, qid, _, _ = proposal(csi_db)                       # wave 2 adds Costco
    kept = harmonise.keep_separate(sid, qid, None, "a@coresight.com")
    wave3 = add_wave(csi_db, "2026-10-05", [dict(RETAILERS, answers=["Walmart", "Costco"])])
    assert harmonise.harmonise_survey(wave3)["exact"] == 1
    with csi_db.connect() as conn:
        assert conn.execute(sa.text(
            "SELECT concept_id FROM csi_concept_map WHERE survey_id = :s"
            " AND concept_option_id IS NULL"), {"s": wave3}).scalar() == kept


def test_instructions_are_removed_only_where_they_trail():
    n = harmonise.normalise_text
    assert n("Please select your age group") == "please select your age group"
    assert n("Select one retailer you trust most") == "select one retailer you trust most"
    assert n("Which brands? Select all that apply - Other (please specify)") == \
        "which brands - other (please specify)"
    assert n("Which brands? Select up to three") == "which brands"


def test_matching_uses_the_mapped_wording_not_stale_stored_text(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [GENDER]))
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE csi_concept SET match_text = 'stale rule output'"))
    assert harmonise.harmonise_survey(add_wave(csi_db, "2026-09-28", [GENDER]))["exact"] == 1


def test_a_concept_used_in_the_wave_cannot_take_a_second_question(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER]))
    sid = add_wave(csi_db, "2026-09-28", [
        GENDER, dict(RETAILERS, qtext="Which, if any, of these retailers have you purchased from?")])
    harmonise.harmonise_survey(sid)                         # D1 exact, q4 similar -> proposed
    with csi_db.connect() as conn:
        d1_cid = conn.execute(sa.text(
            "SELECT m.concept_id FROM csi_concept_map m JOIN csi_question q USING (question_id)"
            " WHERE m.survey_id = :s AND q.qcode = 'D1' AND m.concept_option_id IS NULL"),
            {"s": sid}).scalar()
        q4 = conn.execute(sa.text(
            "SELECT question_id FROM csi_question WHERE survey_id = :s AND qcode = 'q4'"),
            {"s": sid}).scalar()
    with pytest.raises(ValueError, match="already used"):
        harmonise.confirm(sid, q4, None, d1_cid, "a@coresight.com")
    offered = getattr(repository.concept_list, "__wrapped__", repository.concept_list)("single", sid)
    assert d1_cid not in set(offered.concept_id)


def test_a_new_concept_costs_the_same_round_trips_whatever_its_answer_count(csi_db):
    """Over the India–Azure link each round trip is ~250 ms; per-option
    INSERT + SELECT made the first back-fill take 21 minutes."""
    def statements_for(wave: str, qtext: str, answers: int) -> int:
        sid = add_wave(csi_db, wave, [dict(RETAILERS, qtext=qtext,
                                           answers=[f"Retailer {i}" for i in range(answers)])])
        seen = []
        listener = lambda *args: seen.append(1)
        sa.event.listen(csi_db, "before_cursor_execute", listener)
        harmonise.harmonise_survey(sid)
        sa.event.remove(csi_db, "before_cursor_execute", listener)
        return len(seen)

    few = statements_for("2026-09-21", "Where do you buy groceries?", 5)
    many = statements_for("2026-09-28", "Where do you buy furniture?", 40)
    assert few == many <= 20
