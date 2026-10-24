#!/bin/sh
# The ETL on the portal's server (deploy/compose.yml, service etl): what the Mac's launchd jobs did (scripts/launchd).
#  - scripts/weekly_forsta.py at each CIP_ETL_RUNS slot, "Day@HH:MM" in UTC (default Mon 12:00 = 17:30 IST, the launch
#    run, and Fri 03:30 = 09:00 IST, the weekly integrity run). On a Monday of config/launch_schedule.yml the script
#    watches for up to 54 h by itself; any other slot is one short run. It takes the ETL lock, so runs never overlap.
#  - scripts/weekly_forsta.py --watchdog every hour at minute 05: a stuck or missing run is reported (etl/notify.py).
#  - logs/*.log rotated past 20 MB, one old copy kept (OPS-07).
set -u
RUNS=${CIP_ETL_RUNS:-"Mon@12:00 Fri@03:30"}
cd /srv/cip
while :; do
  now=$(date -u +%a@%H:%M)
  for slot in $RUNS; do
    [ "$slot" = "$now" ] && python scripts/weekly_forsta.py >> logs/etl-loop.log 2>&1 &
  done
  [ "$(date -u +%M)" = "05" ] && python scripts/weekly_forsta.py --watchdog >> logs/etl-loop.log 2>&1 &
  for f in logs/*.log; do
    [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 20971520 ] && mv "$f" "$f.1"
  done
  sleep $((60 - $(date -u +%-S)))
done
