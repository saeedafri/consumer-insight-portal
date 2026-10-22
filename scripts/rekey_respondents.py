"""Once, after CIP_RESPONDENT_SALT is set: rekey every stored respondent_key (a plain sha256 of the panel id) to the
keyed hash new loads write (etl/records.respondent_key). One transaction; a marker in cip_load_state stops a
second run from hashing twice.

    python scripts/rekey_respondents.py
"""
import hashlib
import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.database import bulk_insert, get_engine  # noqa: E402

MARKER = "respondent_key_salted"


def main() -> int:
    salt = os.getenv("CIP_RESPONDENT_SALT", "")
    if not salt:
        print("CIP_RESPONDENT_SALT is not set: nothing done")
        return 1
    with get_engine("etl").begin() as conn:
        if conn.execute(text("SELECT 1 FROM cip_load_state WHERE feed_name = :m"), {"m": MARKER}).scalar():
            print("Already rekeyed: nothing done")
            return 0
        rows = conn.execute(text("SELECT respondent_id, respondent_key FROM cip_respondent WHERE respondent_key IS NOT NULL")).all()
        conn.execute(text("CREATE TEMPORARY TABLE tmp_rekey (respondent_id BIGINT UNSIGNED PRIMARY KEY, k CHAR(64) NOT NULL)"))
        bulk_insert(conn, "tmp_rekey", ("respondent_id", "k"),
                    ((rid, hmac.new(salt.encode(), key.encode(), hashlib.sha256).hexdigest()) for rid, key in rows))
        changed = conn.execute(text("UPDATE cip_respondent r JOIN tmp_rekey t USING (respondent_id) SET r.respondent_key = t.k")).rowcount
        conn.execute(text("INSERT INTO cip_load_state (feed_name, last_status) VALUES (:m, :s)"), {"m": MARKER, "s": f"{changed} rows"})
    print(f"Rekeyed {changed} of {len(rows)} respondents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
