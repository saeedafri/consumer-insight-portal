"""Post-deploy and weekly canary: is the portal up, serving the latest wave, and on time. Read-only; exits 1 on a problem.

    python scripts/canary.py http://127.0.0.1:8001 [--login /auth/dev-login?next=/]

Checks: /healthz is 200 and serving waves; the latest wave's book loads with questions; the latest wave is not older
than the last Monday wave (a delayed weekly load); the published files are as new as the serving tables; and how many
question-wording changes still wait for an analyst (harmonisation proposals). It prints and exits; it sends nothing.
"""
import argparse
import http.cookiejar
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta

from sqlalchemy import text

from app.core.database import get_engine


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--login", default="/auth/dev-login?next=/", help="a URL that sets the session cookie")
    ap.add_argument("--late-days", type=int, default=2, help="days after a Monday the weekly wave may still be missing")
    a = ap.parse_args()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    get = lambda path: json.loads(opener.open(a.base + path, timeout=20).read())
    problems = []
    try:
        health = get("/healthz")
        opener.open(a.base + a.login, timeout=20).read()
        waves = get("/api/v1/waves")
        waves = waves if isinstance(waves, list) else waves["waves"]
        latest = max(waves, key=lambda w: (w["wave_date"], w["survey_id"]))
        book = get(f"/api/v1/waves/{latest['survey_id']}/book")
    except Exception as exc:
        print(f"FAIL the portal did not answer: {exc}")
        return 1
    if not health.get("serving_waves"):
        problems.append("healthz reports no serving waves")
    if not book.get("questions"):
        problems.append(f"latest wave {latest['survey_id']} has no questions")
    today = date.today()
    monday = today - timedelta(days=today.weekday())   # this week's Monday
    due = monday if (today - monday).days >= a.late_days else monday - timedelta(days=7)
    newest = date.fromisoformat(str(latest["wave_date"])[:10])
    if newest < due - timedelta(days=6):
        problems.append(f"weekly wave late: newest wave is {newest}, expected one fielded in the week of {due}")
    with get_engine("app").connect() as conn:
        built = conn.execute(text("SELECT MAX(built_at) FROM srv_wave")).scalar()
        proposed = conn.execute(text("SELECT COUNT(*) FROM cip_concept_map WHERE status = 'proposed'")).scalar()
        dashboards = conn.execute(text("SELECT MAX(published_at) FROM cip_dash_published")).scalar()
    published = datetime.fromisoformat(health["published"]) if health.get("published") else None
    if built and published and published < built - timedelta(minutes=30):
        problems.append(f"published files ({published}) are older than the serving tables ({built}): run etl.publish")
    print(f"latest wave {latest['survey_id']} ({newest}), {len(book['questions'])} questions · serving built {built} · "
          f"published {health.get('published')} · dashboards {dashboards} · {proposed} wording changes waiting for an analyst")
    for p in problems:
        print("FAIL", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
