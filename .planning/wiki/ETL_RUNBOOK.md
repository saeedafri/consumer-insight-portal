# Weekly wave runbook (Monday Forsta load)

## What runs by itself
`scripts/weekly_forsta.py` runs under launchd (`scripts/launchd/com.coresight.cip-forsta-etl.plist`) at 17:30 IST on each planned Monday (dates from `config/launch_schedule.yml`) and Friday 09:00 IST. On a planned Monday it posts a Teams heads-up, then re-runs every 30 minutes until the week's wave is loaded and closed in Forsta, or `WATCH_HOURS` pass.

One run: discover surveys (Forsta, GET only) -> load each closed, readable, unloaded one -> verify -> harmonise -> build the serving cube -> search index -> re-check publications. Log: `logs/forsta-etl.log`; errors as JSON lines in `logs/forsta-etl-errors.jsonl`.

A wave loads once its quota is reached or `FIELD_HOURS` after launch, and reloads when Forsta closes it. It writes `cip_stg` only, never Forsta, never `dwh_stg`.

## Alerts and the watchdog
- Every failure (a wave that did not load, the database or Forsta unreachable, a crash, a stop signal) posts to the team's Teams channel (`TEAMS_WEBHOOK_URL`) and emails `config/notify.yml` `failure` (default: the ETL developer). The same failure is told once per 6 hours.
- A run writes `logs/etl-heartbeat.json` as it goes, promising its next sign of life.
- `com.coresight.cip-etl-watchdog` (launchd, hourly, `scripts/weekly_forsta.py --watchdog`) tells the team when that promise is broken: a run that was killed or lost to sleep, a planned Monday whose run never started, or no run for 8 days. On 21 Oct 2026 the Monday watch was cut off after its 19:00 check with no error; this is what now catches that.
- Integrity (after a load, and on Fridays) also reports a planned tracker week (`config/launch_schedule.yml`) still missing 4 days after its Monday.
- A metric alert that fires goes to Teams and, by email, to the person who set it.

## Exit codes
| Code | Meaning | Do |
|---|---|---|
| 0 | everything due is loaded and verified | nothing |
| 1 | a wave failed to load or verify | read the error log, re-run `python scripts/weekly_forsta.py` |
| 2 | Forsta rejected the key, or the schema is behind the code | fix the key in `.env`, or `python scripts/init_db.py` |
| 3 | loaded, but a published number moved | compare the old and new files, decide, `python -m etl.publish --rollback` if wrong |
| 4 | database unreachable after 4 tries | check Azure firewall / VPN, re-run |
| 5 | integrity check found something it could not heal | `python -m etl.forsta_etl --reconcile`, then read `etl/integrity.py` output |

## By hand
```
python -m etl.forsta_etl --discover          # list surveys Forsta has
python -m etl.forsta_etl --due               # load what is due
python -m etl.forsta_etl --survey <id>       # one survey
python -m etl.serving --wave <survey_id>     # rebuild one wave's serving cube (--missing, --all, --jobs N)
python -m etl.publish                        # write the files the API serves; swaps atomically, keeps last 3
python -m etl.publish --rollback             # back to the previous published version
python scripts/weekly_forsta.py --watchdog   # what the hourly watchdog checks, by hand
python scripts/rekey_respondents.py          # once, after CIP_RESPONDENT_SALT is added to .env
```

## After a load: check
1. `python scripts/canary.py http://127.0.0.1:8000` prints the latest wave, publish time and pending wording changes; it exits 1 on a late weekly wave or a stale publish. It sends nothing.
2. Open the portal, pick the new wave, confirm the base size and the headline question look sane.
3. `/healthz` returns 200 with `serving_waves` and `published`.

## Analyst task: wording changes
New or reworded questions arrive as `proposed` links in `cip_concept_map` (3,771 today). A proposal trends nothing until an analyst confirms it, so a changed question is never joined to an old one by accident.

## Never
- Stop or restart the live API or the tunnel to load a wave: publishing swaps files and the API picks them up by version.
- Touch Forsta except GET.
