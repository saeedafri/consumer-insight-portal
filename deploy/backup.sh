#!/bin/sh
# The weekly backup on the portal's server (deploy/compose.yml, service backup): the database dump, proven by
# scripts/backup_db.py (every table and row count checked), and a copy of the published files, both written to
# CIP_BACKUP_DIR (a mount of the off-server target IT provides: Azure Files, a Blob mount). CIP_BACKUP_KEEP of each
# are kept. Runs at CIP_BACKUP_AT ("Day@HH:MM" UTC, default Sun 04:30 = 10:00 IST, the Mac's old slot).
set -u
AT=${CIP_BACKUP_AT:-"Sun@04:30"}
TARGET=${CIP_BACKUP_DIR:-/backup}
KEEP=${CIP_BACKUP_KEEP:-4}
cd /srv/cip
once() {
  stamp=$(date -u +%Y%m%d-%H%M)
  CIP_BACKUP_COPY_DIR="$TARGET" python scripts/backup_db.py || return 1
  mkdir -p "$TARGET/published-$stamp" && cp -a "$(readlink -f "${CIP_PUBLISH_DIR:-/srv/cip/published}/current")/." "$TARGET/published-$stamp/" || return 1
  ls -1d "$TARGET"/published-* | sort | head -n -"$KEEP" | xargs -r rm -rf
  ls -1 "$TARGET"/cip_stg-*.sql.gz | sort | head -n -"$KEEP" | xargs -r rm -f
  echo "backup $stamp written to $TARGET"
}
[ "${1:-}" = "now" ] && { once; exit $?; }
while :; do
  [ "$(date -u +%a@%H:%M)" = "$AT" ] && once
  sleep $((60 - $(date -u +%-S)))
done
