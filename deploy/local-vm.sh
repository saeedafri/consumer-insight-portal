#!/bin/bash
# A local copy of the Azure web app (P0v3: 1 CPU, 4 GB) in a Lima VM, no Docker: the same Debian 13, nginx 1.29 with
# njs, Python 3.13, user cip and deploy/start.sh as the image (deploy/Dockerfile, target app), so its CPU and memory
# numbers are the web app's. Run from the repository root, in this order the first time:
#   bash deploy/local-vm.sh create      # the VM (once)
#   bash deploy/local-vm.sh provision   # nginx, Python, the venv (once, and after requirements.txt changes)
#   bash deploy/local-vm.sh sync        # this checkout and the built website into /srv/cip (after every change)
#   bash deploy/local-vm.sh start       # deploy/start.sh with ~/.config/cip/staging.env; the site on http://127.0.0.1:18080
#   bash deploy/local-vm.sh stop | shell | delete      # output: limactl shell cip1 -- sudo journalctl -u cip -f
# The ETL scheduler is off here (CIP_ETL=off): the Azure web app is the one that loads waves into cip_stg.
set -euo pipefail
VM=cip1
ENV_FILE=${CIP_ENV_FILE:-$HOME/.config/cip/staging.env}
in_vm() { limactl shell "$VM" -- sudo bash -c "$1"; }

case "${1:-}" in
create)
  limactl create --name="$VM" --cpus=1 --memory=4 --disk=10 --vm-type=vz --network=vzNAT --mount-none --containerd=none --tty=false \
    --set '.portForwards=[{"guestPort":8080,"hostPort":18080},{"guestPortRange":[1,65535],"ignore":true}]' template:debian-13
  limactl start "$VM" --tty=false ;;
provision)
  in_vm 'set -e
    apt-get update -qq && apt-get install -y -qq --no-install-recommends curl gnupg ca-certificates python3 python3-venv rsync >/dev/null
    curl -fsSL https://nginx.org/keys/nginx_signing.key | gpg --dearmor -o /usr/share/keyrings/nginx.gpg
    echo "deb [signed-by=/usr/share/keyrings/nginx.gpg] https://nginx.org/packages/mainline/debian trixie nginx" > /etc/apt/sources.list.d/nginx.list
    apt-get update -qq && apt-get install -y -qq nginx nginx-module-njs >/dev/null
    systemctl disable --now nginx >/dev/null 2>&1 || true
    id cip >/dev/null 2>&1 || useradd --system --create-home --uid 10001 cip
    mkdir -p /srv/cip /home/cip/logs /var/cache/nginx/data && chown -R cip /srv/cip /home/cip /var/cache/nginx /var/log/nginx
    nginx -v'
  limactl copy requirements.txt "$VM":/tmp/requirements.txt
  in_vm 'python3 -m venv /opt/venv && /opt/venv/bin/pip install -q --no-cache-dir -r /tmp/requirements.txt
    apt-get install -y -qq --no-install-recommends gcc pkg-config libmariadb-dev python3-dev >/dev/null
    /opt/venv/bin/pip install -q --no-cache-dir mysqlclient==2.3.0 && /opt/venv/bin/python --version' ;;
sync)
  (cd frontend && npm run build >/dev/null) && node deploy/csp_map.mjs frontend/out > /tmp/cip_csp_map.conf
  tar --no-xattrs -czf - api app etl config scripts sql deploy DigiCertGlobalRootG2.crt.pem data/coded requirements.txt \
      -C frontend out -C /tmp cip_csp_map.conf | limactl shell "$VM" -- sudo bash -c '
    set -e; cd /srv/cip && rm -rf web out api app etl config scripts sql deploy && tar -xzf - 2>/dev/null && mv out web
    cp deploy/nginx.conf /etc/nginx/nginx.conf
    cp deploy/cip_proxy.conf deploy/cip_headers.conf deploy/cip_locations.conf deploy/cip_auth.js cip_csp_map.conf /etc/nginx/
    mkdir -p /etc/nginx/logs.d && cp deploy/cip_logs.conf /etc/nginx/logs.d/
    mkdir -p published state && ln -sfn /tmp/cip-keep/logs logs
    chown -R cip /srv/cip/published /srv/cip/state /var/cache/nginx /var/log/nginx /home/cip && chmod -R a+rX /srv/cip /etc/nginx
    sudo -u cip nginx -t 2>&1 | head -1'
  # a running nginx keeps the old files open: start again, as a deploy starts a new container
  if limactl shell "$VM" -- systemctl is-active --quiet cip; then bash "$0" start; fi ;;
start)
  limactl copy "$ENV_FILE" "$VM":/tmp/cip.env
  in_vm 'install -o cip -m 600 /tmp/cip.env /srv/cip/state/cip.env && rm -f /tmp/cip.env /tmp/nginx.pid
    systemctl stop cip 2>/dev/null; systemctl reset-failed cip 2>/dev/null
    # the database is on a private address (10.x) reached through the VPN on the Mac: that traffic goes via the Lima network,
    # which the Mac sends on; the direct vzNAT network (load tests from the Mac) does not pass the VPN
    ip route replace 10.0.0.0/8 via 192.168.5.2 dev eth0 2>/dev/null; true'
  # a transient service: detached, and in its own cgroup as a container is, so machine-log.sh reports the stack, not the VM
  limactl shell "$VM" -- sudo systemd-run --quiet --unit=cip --uid=cip --working-directory=/srv/cip \
    -p MemoryAccounting=yes -p CPUAccounting=yes \
    bash -c 'set -a && . <(grep -E "^[A-Z_]+=" state/cip.env | sed "s/=\(.*\)/=\x27\1\x27/") && set +a
    export PATH=/opt/venv/bin:$PATH APP_ENV=staging CIP_ETL=off WEB_CONCURRENCY='"${WEB_CONCURRENCY:-1}"' CIP_CACHE_MB=32 CIP_BUILD=local-vm \
      CIP_WEB_DIR=/srv/cip/web CIP_PUBLISH_DIR=/srv/cip/published CIP_REVOKED_FILE=/srv/cip/state/revoked.txt \
      CIP_TEAM_STAMP=/srv/cip/state/team.stamp CIP_NGINX_CACHE=/var/cache/nginx/data CIP_NGINX_URL=http://127.0.0.1:8080 \
      CIP_CODED_DIR=/tmp/cip-keep/coded CIP_LOG_DIR=/srv/cip/logs STG_DB_SSL_CA=/srv/cip/DigiCertGlobalRootG2.crt.pem PYTHONDONTWRITEBYTECODE=1
    exec bash deploy/start.sh'
  sleep 8; limactl shell "$VM" -- sh -c 'systemctl is-active cip; sudo journalctl -u cip -n 2 --no-pager -o cat' ;;
stop)
  in_vm 'systemctl stop cip 2>/dev/null; systemctl reset-failed cip 2>/dev/null
    # [x]yz: a pattern that never matches the pkill line itself (for anything started by hand)
    pkill -f "[g]unicorn api.main"; pkill -x nginx; pkill -f "[e]tl.publish"; pkill -f "[m]achine-log.sh"; sleep 1
    { pgrep -af "[g]unicorn api.main|[e]tl.publish"; pgrep -ax nginx; } || echo "stopped"' ;;
shell) limactl shell "$VM" ;;
delete) limactl delete --force "$VM" ;;
*) sed -n '2,11p' "$0"; exit 1 ;;
esac
