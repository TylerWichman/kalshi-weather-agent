#!/usr/bin/env bash
# Relay: dispatch workflows at exact UTC times without depending on GitHub's cron,
# which has started scheduled jobs hours late (2026-09-25, twice). A dispatched run
# starts within about a minute.
#
# The job sleeps until each fire time in $FIRES, dispatches that line's workflow, and
# before its own time limit dispatches its successor ($RELAY_WORKFLOW, after=<last fire>)
# so the chain keeps itself going. The successor skips fire times <= after, so nothing
# fires twice. A fire time is never older than 20 min when it goes out.
#
# It only decides WHEN existing jobs start. It never changes what they do.
#
# Env: FIRES (lines "HH:MM workflow.yml key=value ..."), AFTER (epoch s), RELAY_WORKFLOW,
#      RUN_MIN (minutes to live, default 320), DISPATCH (command, default "gh workflow run").
set -euo pipefail
start=$(date +%s)
end=$((start + ${RUN_MIN:-320} * 60))
last=${AFTER:-0}
DISPATCH=${DISPATCH:-"gh workflow run"}

at() {  # at <epoch> <HH:MM> [days] -> epoch of HH:MM UTC on that epoch's UTC date (+days)
  date -u -d "$(date -u -d "@$1" +%F) $2 UTC + ${3:-0} day" +%s
}

next_fire() {  # earliest fire time after $last and not older than 20 min
  local now=$1 best="" t
  while read -r hm wf args; do
    [ -z "${hm:-}" ] && continue
    for d in 0 1; do
      t=$(at "$now" "$hm" "$d")
      if [ "$t" -gt "$last" ] && [ "$t" -ge $((now - 1200)) ]; then
        if [ -z "$best" ] || [ "$t" -lt "$best" ]; then best=$t; fi
      fi
    done
  done <<< "$FIRES"
  echo "$best"
}

fire() {  # dispatch every line scheduled at exactly $1
  local t=$1 flags
  while read -r hm wf args; do
    [ -z "${hm:-}" ] && continue
    if [ "$(at "$t" "$hm")" -eq "$t" ]; then
      flags=()
      for kv in $args; do flags+=(-f "$kv"); done
      echo "$(date -u +%FT%TZ) dispatch $wf $args"
      $DISPATCH "$wf" "${flags[@]}" || echo "  dispatch FAILED: $wf"
    fi
  done <<< "$FIRES"
}

while :; do
  now=$(date +%s)
  t=$(next_fire "$now")
  if [ -z "$t" ] || [ "$t" -gt "$end" ]; then
    [ "$end" -gt "$now" ] && { echo "nothing due before hand-over; sleeping $(( (end - now) / 60 )) min"; sleep $((end - now)); }
    break
  fi
  if [ "$t" -gt "$now" ]; then
    echo "sleeping until $(date -u -d "@$t" +%FT%TZ)"
    sleep $((t - now))
  fi
  fire "$t"
  last=$t
done
echo "$(date -u +%FT%TZ) handing over to the next relay run (after=$last)"
$DISPATCH "$RELAY_WORKFLOW" -f after="$last"
