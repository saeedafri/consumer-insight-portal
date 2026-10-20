#!/bin/sh
# Server CPU % and memory once a second with an epoch timestamp, for matching to user_mix.py's step windows.
#   sh docker_stats.sh cip-api cip-mysql > stats.log
while :; do
  docker stats --no-stream --format "{{.Name}} {{.CPUPerc}} {{.MemUsage}}" "$@" | sed "s/^/$(date +%s) /"
done
