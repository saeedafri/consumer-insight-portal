#!/bin/bash
# The Logs page's machine numbers (api/logs.py metrics): one JSON line every 15 s in logs/machine.log, read from the
# container's own counters, so they match Azure's metrics:
#   cpu_pct         CPU used, % of all CPUs (cgroup cpu.stat; the whole machine's /proc/stat where there is no cgroup)
#   working_set_mb  memory as Azure counts it: used minus inactive file cache
#   anon_mb         the processes' own memory; file_mb the file cache (published files, nginx cache) the kernel frees on demand
#   net_in_kbs / net_out_kbs   bandwidth, KB per second; processes_mb memory per process name
set -u
cg=/sys/fs/cgroup$(awk -F: '$1 == "0" {print $3}' /proc/self/cgroup)   # our own cgroup: the container's, or a VM scope
cg=${cg%/}
own=$(cat /proc/self/cgroup)
cpus=$(nproc)
prev_t=""
while true; do
  t=$(date +%s)
  cpu=$(awk '/^usage_usec/ {print $2}' $cg/cpu.stat 2>/dev/null)
  [ -n "$cpu" ] || cpu=$(awk '/^cpu / {printf "%d", ($2 + $3 + $4 + $7 + $8) * 10000}' /proc/stat)   # 100 Hz ticks to µs
  read -r rx tx < <(awk -F'[: ]+' 'NR > 2 && $2 != "lo" {rx += $3; tx += $11} END {printf "%d %d", rx, tx}' /proc/net/dev)
  if [ -n "$prev_t" ] && [ "$t" -gt "$prev_t" ]; then
    span=$((t - prev_t))
    used=$(cat $cg/memory.current 2>/dev/null || echo 0)
    limit=$(cat $cg/memory.max 2>/dev/null || echo max)
    mine=""   # the processes in our cgroup only: in a container that is all of them
    for p in /proc/[0-9]*; do [ "$(cat $p/cgroup 2>/dev/null)" = "$own" ] && mine="$mine $p/status"; done
    procs=$(awk '/^Name:/ {name = $2} /^VmRSS:/ {mb[name] += $2 / 1024}
      END {for (n in mb) if (mb[n] >= 5) printf "%s\"%s\":%d", (c++ ? "," : ""), n, mb[n]}' $mine /dev/null 2>/dev/null)
    read -r load1 load5 _ < /proc/loadavg
    stat=""; [ -r $cg/memory.stat ] && [ -r $cg/memory.current ] && stat=$cg/memory.stat   # a container's own cgroup
    awk -v used="$used" -v limit="$limit" -v cpu_us=$((cpu - prev_cpu)) -v span="$span" -v cpus="$cpus" \
        -v rx=$((rx - prev_rx)) -v tx=$((tx - prev_tx)) -v l1="$load1" -v l5="$load5" -v procs="$procs" \
        -v disk="$(df -P /srv/cip 2>/dev/null | awk 'NR == 2 {print $5}')" -v time="$(date -u +%FT%TZ)" '
      FILENAME ~ /meminfo/ && /^MemTotal:/ {total = $2 / 1024}
      FILENAME ~ /meminfo/ && /^MemAvailable:/ {free = $2 / 1024}
      FILENAME ~ /meminfo/ && /^MemFree:/ {unused = $2 / 1024}
      FILENAME ~ /meminfo/ && /^AnonPages:/ {host_anon = $2 / 1024}
      FILENAME ~ /meminfo/ && /^Cached:/ {host_file = $2 / 1024}
      FILENAME ~ /meminfo/ && /^Inactive\(file\):/ {host_inactive = $2 / 1024}
      FILENAME ~ /memory.stat/ && $1 == "anon" {anon = $2 / 1048576; cg = 1}
      FILENAME ~ /memory.stat/ && $1 == "file" {file = $2 / 1048576}
      FILENAME ~ /memory.stat/ && $1 == "inactive_file" {inactive = $2 / 1048576}
      END {
        if (!cg || used == 0) {anon = host_anon; file = host_file; inactive = host_inactive; mem = total - unused} else mem = used / 1048576
        printf "{\"time\":\"%s\",\"cpu_pct\":%.1f,\"working_set_mb\":%d,\"anon_mb\":%d,\"file_mb\":%d,\"limit_mb\":%s,", time,
          cpu_us / (span * 1e6 * cpus) * 100, mem - inactive, anon, file, (limit == "max" || limit > 2^50) ? int(total) : int(limit / 1048576)
        printf "\"machine_used_mb\":%d,\"machine_total_mb\":%d,\"net_in_kbs\":%.1f,\"net_out_kbs\":%.1f,", total - free, total, rx / span / 1024, tx / span / 1024
        printf "\"load_1m\":%s,\"load_5m\":%s,\"cpus\":%d,\"disk_used\":\"%s\",\"processes_mb\":{%s}}\n", l1, l5, cpus, disk, procs
      }' /proc/meminfo $stat >> logs/machine.log
  fi
  prev_t=$t prev_cpu=$cpu prev_rx=$rx prev_tx=$tx
  sleep 15
done
