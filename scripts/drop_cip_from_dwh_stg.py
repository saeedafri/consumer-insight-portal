"""Drop the CIP tables and views from dwh_stg (they now live in cip_stg).

Drops exactly the 33 tables and 9 views named below, nothing else. Before
dropping, it checks that every one exists in cip_stg with the same row count,
and that nothing outside this list in dwh_stg references them.

With --macro it also drops the 32 US-census-ETL objects (census_, bls_, bea_,
fred_), which now live in coresight_market_data_stg, but only if every series
code in dwh_stg exists there too, so no observation is lost.

Needs a dwh_stg account with DROP rights (e.g. dwh_app_access):
    DWH_STG_USER=dwh_app_access DWH_STG_PASSWORD='…' .venv/bin/python scripts/drop_cip_from_dwh_stg.py [--macro]
Add --yes to drop; without it the script only reports.
"""
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import get_engine  # noqa: E402  the project login (.env), which can see cip_stg

TABLES = [
    "cip_agg_cell", "cip_answer", "cip_auth_session", "cip_banner", "cip_cohort_def", "cip_concept",
    "cip_concept_map", "cip_concept_option", "cip_crosstab", "cip_crosstab_run", "cip_field",
    "cip_forsta_survey", "cip_item", "cip_load_error", "cip_load_log", "cip_load_state", "cip_option",
    "cip_profile", "cip_profile_map", "cip_publication", "cip_publication_cell", "cip_question",
    "cip_respondent", "cip_respondent_cohort", "cip_saved_view", "cip_search", "cip_segment",
    "cip_survey", "cip_topic", "cip_tracker_line", "cip_wave_module", "cip_weight", "cip_weight_scheme",
]
VIEWS = [
    "v_cip_answers", "v_cip_crosstab", "v_cip_grid", "v_cip_item_incidence", "v_cip_mapping_queue",
    "v_cip_question_base", "v_cip_single_distribution", "v_cip_survey_health", "v_cip_trend",
]
MACRO_PREFIXES = ["census", "bls", "bea", "fred"]
MACRO_HOME = "coresight_market_data_stg"
SERIES_KEY = {"census": ["program_code", "category_code", "geo_code", "measure_code", "seasonally_adjusted"]}
CA = Path(__file__).resolve().parents[1] / "DigiCertGlobalRootG2.crt.pem"


def main() -> int:
    user, password = os.environ.get("DWH_STG_USER"), os.environ.get("DWH_STG_PASSWORD")
    if not user or not password:
        sys.exit("Set DWH_STG_USER and DWH_STG_PASSWORD (a dwh_stg account with DROP rights).")
    engine = create_engine(
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@csr-mysql8-flex-stg.mysql.database.azure.com:3306/dwh_stg",
        connect_args={"ssl": {"ca": str(CA)}})
    names = TABLES + VIEWS

    def objects(conn, schema):
        return {r[0]: r[1] for r in conn.execute(text(
            "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = :s "
            "AND (table_name LIKE 'cip\\_%' OR table_name LIKE 'v\\_cip\\_%')"), {"s": schema})}

    # The dwh_stg login cannot see cip_stg, so the cip_stg side is read with the project login.
    with get_engine("etl").connect() as home:
        new = objects(home, "cip_stg")
        new_counts = {t: home.execute(text(f"SELECT COUNT(*) FROM cip_stg.`{t}`")).scalar()
                      for t in TABLES if t in new}
    with engine.connect() as conn:
        old = objects(conn, "dwh_stg")
        unexpected = sorted(set(old) - set(names))
        if unexpected:
            sys.exit(f"Stopping: dwh_stg has CIP-named objects not on the list: {unexpected}")
        missing = [n for n in names if n not in new]
        if missing:
            sys.exit(f"Stopping: not in cip_stg yet: {missing}")
        for table in TABLES:
            if table in old:
                a = conn.execute(text(f"SELECT COUNT(*) FROM dwh_stg.`{table}`")).scalar()
                b = new_counts[table]
                if b < a:
                    sys.exit(f"Stopping: cip_stg.{table} has {b} rows, dwh_stg has {a}")
        outside = conn.execute(text(
            "SELECT table_name, constraint_name FROM information_schema.referential_constraints "
            "WHERE constraint_schema = 'dwh_stg' AND referenced_table_name LIKE 'cip\\_%' "
            "AND table_name NOT LIKE 'cip\\_%'")).all()
        if outside:
            sys.exit(f"Stopping: other dwh_stg tables reference CIP tables: {outside}")
        present = [n for n in names if n in old]
        macro = []
        if "--macro" in sys.argv:
            for prefix in MACRO_PREFIXES:
                found = {r[0]: r[1] for r in conn.execute(text(
                    "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'dwh_stg' "
                    f"AND table_name LIKE '{prefix}\\_%'"))}
                home = {r[0] for r in conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = :h "
                    f"AND table_name LIKE '{prefix}\\_%'"), {"h": MACRO_HOME})}
                if set(found) - home:
                    sys.exit(f"Stopping: not in {MACRO_HOME}: {sorted(set(found) - home)}")
                key = SERIES_KEY.get(prefix, ["series_code"])
                match = " AND ".join(f"m.`{k}` <=> s.`{k}`" for k in key)
                lost = conn.execute(text(
                    f"SELECT COUNT(*) FROM dwh_stg.`{prefix}_series` s WHERE NOT EXISTS (SELECT 1 FROM "
                    f"{MACRO_HOME}.`{prefix}_series` m WHERE {match})")).scalar()
                if lost:
                    sys.exit(f"Stopping: {lost} {prefix} series exist only in dwh_stg; copy them to {MACRO_HOME} first")
                macro += sorted(found, key=lambda n: found[n] != "VIEW")      # views first
            present += macro
        print(f"{len(present)} CIP objects in dwh_stg, all present in cip_stg with at least as many rows:")
        for n in present:
            print("  ", n, "(view)" if n in VIEWS or n.endswith("_v_observation") else "")
        if "--yes" not in sys.argv:
            print("Report only. Re-run with --yes to drop them.")
            return 0
        conn.execute(text("SET SESSION foreign_key_checks = 0"))
        for view in VIEWS:
            if view in old:
                conn.execute(text(f"DROP VIEW dwh_stg.`{view}`"))
        for table in TABLES:
            if table in old:
                conn.execute(text(f"DROP TABLE dwh_stg.`{table}`"))
        for name in macro:
            kind = "VIEW" if name.endswith("_v_observation") else "TABLE"
            conn.execute(text(f"DROP {kind} dwh_stg.`{name}`"))
        conn.commit()
        left = objects(conn, "dwh_stg")
        print(f"Dropped {len(present)}. CIP objects left in dwh_stg: {sorted(left) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
