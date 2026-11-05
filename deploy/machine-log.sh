#!/bin/bash
# The Logs page's machine numbers (api/logs.py metrics): one JSON line every 15 s in logs/machine.log, from the
# container's own counters, so they match Azure's metrics:
#   cpu_pct / cores_used  CPU used: % of the CPUs we may use (the cgroup quota, else nproc) and in whole cores
#   working_set_mb        memory as Azure counts it: used minus inactive file cache
#   anon_mb / file_mb     the processes' own memory / the file cache (published files, nginx cache) freed on demand
#   net_in_kbs / net_out_kbs  bandwidth, KB per second; processes_mb memory per process name; source: where it was read
# Where the numbers come from is found once and written to logs/container.log: cgroup v2 (a VM scope, most containers),
# cgroup v1 (App Service's older layout), or, with neither, our own processes summed (never the whole host).
set -u
own=$(cat /proc/self/cgroup)
v2=/sys/fs/cgroup$(awk -F: '$1 == "0" {print $3}' /proc/self/cgroup); v2=${v2%/}
v1m=/sys/fs/cgroup/memory
v1c=$(ls -d /sys/fs/cgroup/cpuacct /sys/fs/cgroup/cpu,cpuacct 2>/dev/null | head -1)
if [ -r "$v2/memory.current" ]; then
  source=cgroup2
  read -r quota period < "$v2/cpu.max" 2>/dev/null || quota=max
elif [ -r "$v1m/memory.usage_in_bytes" ]; then
  source=cgroup1
  quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null || echo -1); period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null || echo 100000)
  [ "$quota" -gt 0 ] 2>/dev/null || quota=max
else
  source=processes; quota=max
fi
if [ "$quota" != max ]; then cpus=$(awk -v q="$quota" -v p="$period" 'BEGIN {printf "%.2f", q / p}'); else cpus=$(nproc); fi
echo "$(date -u +%FT%TZ) machine-log.sh: numbers from $source, CPUs we may use: $cpus (nproc $(nproc), quota $quota)" >> logs/container.log

mine() {   # the status files of the processes in our cgroup: in a container, all of them
  for p in /proc/[0-9]*; do [ "$(cat $p/cgroup 2>/dev/null)" = "$own" ] && echo "$p"; done
}
cpu_now() {   # CPU used so far, in µs
  case $source in
    cgroup2) awk '/^usage_usec/ {print $2}' "$v2/cpu.stat" ;;
    cgroup1) awk '{printf "%d", $1 / 1000}' "$v1c/cpuacct.usage" 2>/dev/null || echo 0 ;;
    *) for p in $(mine); do cat $p/stat 2>/dev/null; done | awk -v hz="$(getconf CLK_TCK)" '{sub(/.*\) /, ""); t += $12 + $13} END {printf "%d", t / hz * 1e6}' ;;
  esac
}
prev_t=""
while true; do
  t=$(date +%s)
  cpu=$(cpu_now); cpu=${cpu:-0}
  read -r rx tx < <(awk -F'[: ]+' 'NR > 2 && $2 != "lo" {rx += $3; tx += $11} END {printf "%d %d", rx, tx}' /proc/net/dev)
  if [ -n "$prev_t" ] && [ "$t" -gt "$prev_t" ]; then
    span=$((t - prev_t))
    case $source in
      cgroup2) used=$(cat "$v2/memory.current"); limit=$(cat "$v2/memory.max"); stat="$v2/memory.stat" ;;
      cgroup1) used=$(cat "$v1m/memory.usage_in_bytes"); limit=$(cat "$v1m/memory.limit_in_bytes"); stat="$v1m/memory.stat" ;;
      *) used=0; limit=max; stat="" ;;
    esac
    statuses=$(mine | sed 's|$|/status|')
    procs=$(awk '/^Name:/ {name = $2} /^VmRSS:/ {mb[name] += $2 / 1024}
      END {for (n in mb) if (mb[n] >= 5) printf "%s\"%s\":%d", (c++ ? "," : ""), n, mb[n]}' $statuses /dev/null 2>/dev/null)
    rss=$(awk '/^RssAnon:/ {a += $2} END {printf "%d", a / 1024}' $statuses /dev/null 2>/dev/null)
    read -r load1 load5 _ < /proc/loadavg
    awk -v used="$used" -v limit="$limit" -v cpu_us=$((cpu - prev_cpu)) -v span="$span" -v cpus="$cpus" -v rss="$rss" \
        -v rx=$((rx - prev_rx)) -v tx=$((tx - prev_tx)) -v l1="$load1" -v l5="$load5" -v procs="$procs" -v source="$source" \
        -v disk="$(df -P /srv/cip 2>/dev/null | awk 'NR == 2 {print $5}')" -v time="$(date -u +%FT%TZ)" '
      FILENAME ~ /meminfo/ && /^MemTotal:/ {total = $2 / 1024}
      FILENAME ~ /meminfo/ && /^MemAvailable:/ {free = $2 / 1024}
      FILENAME ~ /meminfo/ && /^Cached:/ {host_file = $2 / 1024}
      FILENAME ~ /memory.stat/ && ($1 == "anon" || $1 == "total_rss") {anon = $2 / 1048576}
      FILENAME ~ /memory.stat/ && ($1 == "file" || $1 == "total_cache") {file = $2 / 1048576}
      FILENAME ~ /memory.stat/ && ($1 == "inactive_file" || $1 == "total_inactive_file") {inactive = $2 / 1048576}
      END {
        cores = cpu_us / (span * 1e6); pct = cores / cpus * 100; if (pct > 100) pct = 100   # whole-second clock
        if (source == "processes") {mem = rss; anon = rss; file = host_file; inactive = 0} else mem = used / 1048576
        printf "{\"time\":\"%s\",\"source\":\"%s\",\"cpu_pct\":%.1f,\"cores_used\":%.2f,\"working_set_mb\":%d,\"anon_mb\":%d,\"file_mb\":%d,", time,
          source, pct, cores, mem - inactive, anon, file
        printf "\"limit_mb\":%d,\"machine_used_mb\":%d,\"machine_total_mb\":%d,\"net_in_kbs\":%.1f,\"net_out_kbs\":%.1f,",
          (limit == "max" || limit > 2^50) ? total : limit / 1048576, total - free, total, rx / span / 1024, tx / span / 1024
        printf "\"load_1m\":%s,\"load_5m\":%s,\"cpus\":%s,\"disk_used\":\"%s\",\"processes_mb\":{%s}}\n", l1, l5, cpus, disk, procs
      }' /proc/meminfo $stat >> logs/machine.log
  fi
  prev_t=$t prev_cpu=$cpu prev_rx=$rx prev_tx=$tx
  sleep 15
done
