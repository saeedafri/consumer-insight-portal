#!/bin/sh
# The ETL scheduler inside the portal's container (started by deploy/start.sh): the jobs that used to run on a Mac on a timer.
#  - scripts/weekly_forsta.py at each CIP_ETL_RUNS slot, "Day@HH:MM" in UTC. Default: Mon 12:00 (17:30 IST), the launch
#    run, which on a Monday of config/launch_schedule.yml watches the new wave for up to 54 h and loads it when its
#    fieldwork ends; and 03:30 (09:00 IST) every day, a short run that loads any other survey that closed (annual, ad hoc)
#    within a day; Friday's also runs the integrity check. Each run takes the ETL lock, so runs never overlap.
#  - scripts/weekly_forsta.py --watchdog every hour at minute 05: a stuck or missing run is reported (etl/notify.py).
#  - logs/*.log and *.jsonl past 20 MB are packed into logs/archive/ as .zip and kept for good (deploy/archive-log.py).
set -u
RUNS=${CIP_ETL_RUNS:-"Mon@12:00 Mon@03:30 Tue@03:30 Wed@03:30 Thu@03:30 Fri@03:30 Sat@03:30 Sun@03:30"}
cd /srv/cip
while :; do
  now=$(date -u +%a@%H:%M)
  for slot in $RUNS; do
    [ "$slot" = "$now" ] && python scripts/weekly_forsta.py >> logs/etl-loop.log 2>&1 &
  done
  [ "$(date -u +%M)" = "05" ] && python scripts/weekly_forsta.py --watchdog >> logs/etl-loop.log 2>&1 &
  for f in logs/*.log logs/*.jsonl; do   # past 20 MB: packed into logs/archive/*.zip for good, the live file emptied
    [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 20971520 ] && python deploy/archive-log.py "$f" >> logs/container.log 2>&1
  done
  sleep $((60 - $(date -u +%-S)))
done
