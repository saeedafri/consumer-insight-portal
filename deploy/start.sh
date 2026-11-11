#!/bin/bash
# The whole portal in one container, for Azure App Service (one container, one port: 8080). nginx serves the site and
# the published files and caches answers, in front of the API (gunicorn on 127.0.0.1:8000), and the ETL scheduler
# (deploy/etl-loop.sh) runs beside them at low priority. If nginx, the API or the scheduler stops, the container stops
# and App Service starts a fresh one; its health check (/healthz) also replaces a container that stops answering.
set -u
cd /srv/cip
# What must survive restarts and deploys lives in /home/cip (App Service keeps /home): logs/ (with the ETL heartbeat, so
# no "no run for a week" alarm after each deploy) and the open-ended answers' coding (CIP_CODED_DIR, read by publish).
# /tmp/cip-keep leads there; a /home this user cannot write: a folder in the container instead, lost at restart
if mkdir -p /home/cip/logs /home/cip/coded 2>/dev/null && [ -w /home/cip/coded ]; then
  ln -sfn /home/cip /tmp/cip-keep
  # each publish also keeps one tar of its files here, so a new image restores them in seconds instead of rebuilding
  # every wave (6 min at 100 % CPU on one core, 5 Nov 2026); a Blob URL set in the settings wins
  export CIP_PUBLISH_BACKUP_URL="${CIP_PUBLISH_BACKUP_URL:-/home/cip/published-backup}"
else
  echo "start.sh: /home is not writable for uid $(id -u): logs and coding kept in the container until it restarts" >&2
  mkdir -p /tmp/cip-local/logs /tmp/cip-local/coded && ln -sfn /tmp/cip-local /tmp/cip-keep
fi
cp -n data/coded/*.json /tmp/cip-keep/coded/ 2>/dev/null   # the coding done before this server (in the image), never over newer
# Published files live on the container's own disk: fast, and App Service's /home share (SMB) cannot hold the hard
# links publish uses between versions. After a restart or a new image they come back from the backup
# (CIP_PUBLISH_BACKUP_URL: /home/cip/published-backup or a Blob URL) in seconds; with no backup yet, a full publish
# rebuilds them and the API answers from the database meanwhile.
if [ ! -e "$CIP_PUBLISH_DIR/current" ]; then
  backup="${CIP_PUBLISH_BACKUP_URL:-}"
  { { [ -n "$backup" ] && { [ "${backup#/}" = "$backup" ] || [ -f "$backup/latest" ]; } && python -m etl.publish --restore --wait 21600; } || nice -n 10 python -m etl.publish; } >> logs/publish-start.log 2>&1 &
fi
ulimit -n "$(ulimit -Hn)"   # the default 1,024 open files caps a worker near a thousand connections
nginx -g 'daemon off;' &
nginx_pid=$!
# the API's output goes both to App Service's log stream and to logs/api.log (the admins' Logs page). One worker: on one
# CPU a second adds no capacity (first-time cross-tabs 912/s with one, 990/s with two) and costs ~110 MB (6 Nov 2026)
gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w "${WEB_CONCURRENCY:-1}" -b 127.0.0.1:8000 \
  --timeout 30 --graceful-timeout 20 --forwarded-allow-ips 127.0.0.1 --no-control-socket 2>&1 | tee -a logs/api.log &
api_pid=$!
watched="$nginx_pid $api_pid"
if [ "${CIP_ETL:-on}" = on ]; then   # CIP_ETL=off: a second web app of the same image that only serves
  nice -n 10 sh deploy/etl-loop.sh &
  watched="$watched $!"
fi
bash deploy/machine-log.sh &   # the Logs page's machine numbers every 15 s; not watched: if it stops, the site carries on
echo "$(date -u +%FT%TZ) start.sh: started nginx and the API, ETL scheduler ${CIP_ETL:-on} (build ${CIP_BUILD:-unknown})" | tee -a logs/container.log
wait -n $watched
echo "$(date -u +%FT%TZ) start.sh: a process stopped (exit $?); stopping the container so App Service restarts it" | tee -a logs/container.log >&2
exit 1
