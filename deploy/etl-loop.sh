#!/bin/sh
# The ETL scheduler inside the portal's container (started by deploy/start.sh): the jobs that used to run on a Mac on a timer.
#  - scripts/weekly_forsta.py at each CIP_ETL_RUNS slot, "Day@HH:MM" in UTC. Default: Mon 12:00 (17:30 IST), the launch
#    run, which on a Monday of config/launch_schedule.yml watches the new wave for up to 54 h and loads it when its
#    fieldwork ends; and 03:30 (09:00 IST) every day, a short run that loads any other survey that closed (annual, ad hoc)
#    within a day; Friday's also runs the integrity check. Each run takes the ETL lock, so runs never overlap.
#  - scripts/weekly_forsta.py --once every 30 minutes: one check, so a closed survey loads within 30 minutes whatever
#    stopped the watch (a deploy restarts the container and every process in it).
#  - python -m etl.sharepoint_china once IT's access is set: new China survey weeks from SharePoint. Within a minute of
#    a webhook or Power Automate call (api/ingest.py leaves data/sharepoint.wanted); otherwise every 10 minutes, or
#    hourly as a safety net once those calls are set up (CIP_SP_WEBHOOK_SECRET). --subscribe renews the webhook daily.
#  - scripts/weekly_forsta.py --watchdog every hour at minute 05: a stuck or missing run is reported (etl/notify.py).
#  - python -m etl.fieldwork once, two minutes after each start: Forsta's records of every survey still missing one.
#  - logs/*.log and *.jsonl past 20 MB are packed into logs/archive/ as .zip and kept for good (deploy/archive-log.py).
set -u
RUNS=${CIP_ETL_RUNS:-"Mon@12:00 Mon@03:30 Tue@03:30 Wed@03:30 Thu@03:30 Fri@03:30 Sat@03:30 Sun@03:30"}
cd /srv/cip
# Forsta's records of every survey (etl/fieldwork.py) caught up once per start, after the published files are restored:
# a deploy never leaves the Fieldwork screen empty until the next scheduled run. Read-only GETs, lowest priority.
( sleep 120 && nice -n 15 python -m etl.fieldwork >> logs/fieldwork.log 2>&1 ) &
# the SharePoint webhook created or renewed once the API answers (Graph checks the address first), then daily
[ -n "${CIP_SP_WEBHOOK_URL:-}" ] && ( sleep 150 && python -m etl.sharepoint_china --subscribe >> logs/sharepoint.log 2>&1 ) &
while :; do
  now=$(date -u +%a@%H:%M)
  slotted=no
  for slot in $RUNS; do
    if [ "$slot" = "$now" ]; then slotted=yes; python scripts/weekly_forsta.py >> logs/etl-loop.log 2>&1 & fi
  done
  # every 30 minutes a single check: the scheduler itself starts it, so a deploy that kills a running watch costs at
  # most 30 minutes (9 Nov 2026: a killed watch left wave 261100 for the next morning). While the watch runs, the
  # check finds the lock taken and stops at once; in a scheduled run's minute it is skipped, so it never takes the
  # lock from Monday's watch.
  [ "$slotted" = no ] && case "$(date -u +%M)" in 00|30) python scripts/weekly_forsta.py --once >> logs/etl-loop.log 2>&1 & ;; esac
  [ "$(date -u +%M)" = "05" ] && python scripts/weekly_forsta.py --watchdog >> logs/etl-loop.log 2>&1 &
  # the China survey's SharePoint folder every 10 minutes (etl/sharepoint_china.py), off the Forsta minutes; only once IT's
  # access is set (CIP_SP_CLIENT_ID): a pass that finds nothing new is ~60 small Graph reads and no database write
  if [ -n "${CIP_SP_CLIENT_ID:-}" ]; then
    every="02 12 22 32 42 52"; [ -n "${CIP_SP_WEBHOOK_SECRET:-}" ] && every="02"   # told by calls: the timer is a safety net
    if [ -f data/sharepoint.wanted ] || case " $every " in *" $(date -u +%M) "*) true ;; *) false ;; esac; then
      rm -f data/sharepoint.wanted   # any number of calls in the minute make one pass
      nice -n 15 python -m etl.sharepoint_china >> logs/sharepoint.log 2>&1 &
    fi
    [ -n "${CIP_SP_WEBHOOK_URL:-}" ] && [ "$(date -u +%H:%M)" = "03:17" ] && python -m etl.sharepoint_china --subscribe >> logs/sharepoint.log 2>&1 &
  fi
  for f in logs/*.log logs/*.jsonl; do   # past 20 MB: packed into logs/archive/*.zip for good, the live file emptied
    [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 20971520 ] && python deploy/archive-log.py "$f" >> logs/container.log 2>&1
  done
  sleep $((60 - $(date -u +%-S)))
done
