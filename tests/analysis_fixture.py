"""Deterministic, synthetic survey data for repository analysis tests."""
from __future__ import annotations

from sqlalchemy import text


def seed_analysis_data(engine) -> None:
    """Seed two synthetic waves with the published counts asserted by tests."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cip_survey
                    (survey_id, forsta_host, forsta_path, title, survey_family,
                     wave_label, platform, source_ref, load_status)
                VALUES
                    (1, 'synthetic.invalid', 'synthetic/wave-1', 'Synthetic Wave 1',
                     'CSI-US', '2026-09-21', 'forsta', 'synthetic/wave-1', 'verified'),
                    (2, 'synthetic.invalid', 'synthetic/wave-2', 'Synthetic Wave 2',
                     'CSI-US', '2026-09-28', 'forsta', 'synthetic/wave-2', 'verified')
                """
            )
        )

        questions = [
            (101, 1, "BN1", "BNPL usage", "single", 0, 1),
            (102, 1, "DP1", "Department-store buyer", "single", 0, 2),
            (103, 1, "GP1", "GLP-1 usage", "single", 0, 3),
            (104, 1, "q4", "Retailer shopped", "multi", 1, 4),
            (105, 1, "DP2", "Routed department-store question", "multi", 1, 5),
            (201, 2, "BT8", "Beauty products", "multi", 1, 1),
            (202, 2, "HX1", "Holiday behavior", "single", 0, 2),
            (203, 2, "BT14", "Retailer ratings", "grid_single", 0, 3),
        ]
        conn.execute(
            text(
                """
                INSERT INTO cip_question
                    (question_id, survey_id, qcode, qtext, qtype, is_multi, sort_order)
                VALUES
                    (:question_id, :survey_id, :qcode, :qtext, :qtype, :is_multi, :sort_order)
                """
            ),
            [
                {
                    "question_id": qid,
                    "survey_id": sid,
                    "qcode": qcode,
                    "qtext": qtext,
                    "qtype": qtype,
                    "is_multi": is_multi,
                    "sort_order": order,
                }
                for qid, sid, qcode, qtext, qtype, is_multi, order in questions
            ],
        )

        items = [
            (1041, 104, "q4r1", "Walmart", 1),
            (1042, 104, "q4r2", "Target", 2),
            (1051, 105, "DP2r1", "Macy's", 1),
            (2011, 201, "BT8r1", "Mascara", 1),
            (2012, 201, "BT8r2", "Other beauty product", 2),
            (2031, 203, "BT14r1", "Retailer A", 1),
            (2032, 203, "BT14r2", "Retailer B", 2),
        ]
        conn.execute(
            text(
                """
                INSERT INTO cip_item
                    (item_id, question_id, item_code, item_label, sort_order)
                VALUES (:item_id, :question_id, :item_code, :item_label, :sort_order)
                """
            ),
            [
                {
                    "item_id": item_id,
                    "question_id": qid,
                    "item_code": code,
                    "item_label": label,
                    "sort_order": order,
                }
                for item_id, qid, code, label, order in items
            ],
        )

        option_labels = {
            101: ["Yes", "No", "Maybe", "Never"],
            102: ["Yes", "No"],
            103: ["Yes", "No"],
            202: [f"Holiday option {code}" for code in range(1, 8)],
            203: ["Poor", "Average", "Excellent"],
        }
        options = []
        option_id = 1
        for question_id, labels in option_labels.items():
            for value_code, label in enumerate(labels, 1):
                options.append(
                    {
                        "option_id": option_id,
                        "question_id": question_id,
                        "value_code": value_code,
                        "value_label": label,
                        "sort_order": value_code,
                    }
                )
                option_id += 1
        conn.execute(
            text(
                """
                INSERT INTO cip_option
                    (option_id, question_id, value_code, value_label, sort_order)
                VALUES (:option_id, :question_id, :value_code, :value_label, :sort_order)
                """
            ),
            options,
        )

        fields = [
            (1011, 1, 101, None, "BN1"),
            (1021, 1, 102, None, "DP1"),
            (1031, 1, 103, None, "GP1"),
            (1041, 1, 104, 1041, "q4r1"),
            (1042, 1, 104, 1042, "q4r2"),
            (1051, 1, 105, 1051, "DP2r1"),
            (2011, 2, 201, 2011, "BT8r1"),
            (2012, 2, 201, 2012, "BT8r2"),
            (2021, 2, 202, None, "HX1"),
            (2031, 2, 203, 2031, "BT14r1"),
            (2032, 2, 203, 2032, "BT14r2"),
        ]
        conn.execute(
            text(
                """
                INSERT INTO cip_field
                    (field_id, survey_id, question_id, item_id, field_name, value_type)
                VALUES (:field_id, :survey_id, :question_id, :item_id, :field_name, 'code')
                """
            ),
            [
                {
                    "field_id": fid,
                    "survey_id": sid,
                    "question_id": qid,
                    "item_id": item_id,
                    "field_name": name,
                }
                for fid, sid, qid, item_id, name in fields
            ],
        )

        wave1 = [
            {
                "respondent_id": respondent_id,
                "survey_id": 1,
                "record_no": respondent_id,
                "generation": (
                    "GenZ" if respondent_id <= 54
                    else "Millennial" if respondent_id <= 213
                    else "GenX"
                ),
            }
            for respondent_id in range(1, 405)
        ]
        wave2 = [
            {
                "respondent_id": 1000 + record_no,
                "survey_id": 2,
                "record_no": record_no,
                "generation": "GenX",
            }
            for record_no in range(1, 404)
        ]
        respondents = wave1 + wave2
        conn.execute(
            text(
                """
                INSERT INTO cip_respondent
                    (respondent_id, survey_id, record_no, status_code, status_label, is_qualified)
                VALUES (:respondent_id, :survey_id, :record_no, 3, 'Qualified', 1)
                """
            ),
            respondents,
        )
        conn.execute(
            text(
                """
                INSERT INTO cip_profile (respondent_id, survey_id, generation)
                VALUES (:respondent_id, :survey_id, :generation)
                """
            ),
            respondents,
        )

        answers = []

        def answer(respondent_id: int, survey_id: int, field_id: int, code: int) -> None:
            answers.append(
                {
                    "respondent_id": respondent_id,
                    "survey_id": survey_id,
                    "field_id": field_id,
                    "value_code": code,
                }
            )

        dp1_yes = (
            set(range(1, 55))
            | set(range(55, 143))
            | set(range(214, 264))
            | set(range(324, 354))
        )
        for respondent_id in range(1, 405):
            answer(
                respondent_id,
                1,
                1011,
                1 if respondent_id <= 133 else 2 if respondent_id <= 381 else 3 if respondent_id <= 392 else 4,
            )
            answer(respondent_id, 1, 1021, 1 if respondent_id in dp1_yes else 2)
            answer(respondent_id, 1, 1031, 1 if respondent_id <= 71 else 2)
            answer(respondent_id, 1, 1041, 1 if respondent_id <= 241 else 0)
            answer(respondent_id, 1, 1042, 1 if respondent_id % 2 == 0 else 0)
            if respondent_id in dp1_yes:
                answer(respondent_id, 1, 1051, 1 if 55 <= respondent_id <= 70 else 0)

        for record_no in range(1, 404):
            respondent_id = 1000 + record_no
            answer(respondent_id, 2, 2021, ((record_no - 1) % 7) + 1)
            if record_no <= 264:
                answer(respondent_id, 2, 2012, 1 if record_no % 2 else 0)
            if record_no <= 83:
                answer(respondent_id, 2, 2011, 1 if record_no <= 40 else 0)
            if record_no <= 120:
                answer(respondent_id, 2, 2031, ((record_no - 1) % 3) + 1)
            if record_no <= 80:
                answer(respondent_id, 2, 2032, ((record_no - 1) % 3) + 1)

        conn.execute(
            text(
                """
                INSERT INTO cip_answer
                    (respondent_id, survey_id, field_id, value_code, value_label)
                VALUES (:respondent_id, :survey_id, :field_id, :value_code, NULL)
                """
            ),
            answers,
        )
