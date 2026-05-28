#!/bin/bash
# batch-sim.sh — Run all persona × profile × form combinations
#
# Usage:
#   ./scripts/batch-sim.sh              # 3 runs per combo (default, tops up)
#   ./scripts/batch-sim.sh 5            # 5 runs per combo (tops up)
#   ./scripts/batch-sim.sh 1 northfield # 1 run, northfield only
#   ./scripts/batch-sim.sh --fresh 5    # 5 NEW runs per combo (ignores existing)
#
# Features:
#   - Runs each session individually (failure isolation)
#   - By default, tops up to N runs per combo (skips if already have enough)
#   - --fresh flag: always runs N new sessions, ignoring existing count
#   - Logs progress and errors to sims/batch.log
#   - Shows which combo failed if interrupted
#
# Output: sims/sim-{form}-{persona}-{profile}-{timestamp}.jsonl

FRESH=false
if [ "$1" = "--fresh" ]; then
  FRESH=true
  shift
fi

RUNS=${1:-3}
FORM_FILTER=${2:-}

# Config
PERSONAS="jane alex maria"
PROFILES="thorough impatient confused corrector returning"
if [ -n "$FORM_FILTER" ]; then
  FORMS="$FORM_FILTER"
else
  FORMS="northfield westbrook patient"
fi

LOGFILE="sims/batch.log"
mkdir -p sims

# Count combos
FORM_COUNT=$(echo $FORMS | wc -w | tr -d ' ')
PERSONA_COUNT=$(echo $PERSONAS | wc -w | tr -d ' ')
PROFILE_COUNT=$(echo $PROFILES | wc -w | tr -d ' ')
TOTAL=$((FORM_COUNT * PERSONA_COUNT * PROFILE_COUNT * RUNS))

echo "═══════════════════════════════════════════════════════"
echo " Batch Simulation"
echo " Forms: $FORMS"
echo " Personas: $PERSONAS"
echo " Profiles: $PROFILES"
echo " Runs per combo: $RUNS $([ "$FRESH" = "true" ] && echo "(FRESH)" || echo "(top-up)")"
echo " Sampling: weighted (40/35/25)"
echo " Prompt mode: split-prompt"
echo " Total sessions: $TOTAL"
echo " Log: $LOGFILE"
echo "═══════════════════════════════════════════════════════"
echo ""

echo "$(date -Iseconds) Batch started: $TOTAL sessions" >> "$LOGFILE"

COMPLETED=0
SKIPPED=0
FAILED=0
SESSION_NUM=0

for form in $FORMS; do
  for persona in $PERSONAS; do
    for profile in $PROFILES; do
      # Check how many runs already exist for this combo
      COMBO="${form}-${persona}-${profile}"
      EXISTING=$(ls -1 sims/sim-${COMBO}-*.jsonl 2>/dev/null | wc -l | tr -d ' ')

      if [ "$FRESH" = "true" ]; then
        NEEDED=$RUNS
      else
        NEEDED=$((RUNS - EXISTING))
      fi

      if [ "$NEEDED" -le 0 ]; then
        SKIPPED=$((SKIPPED + RUNS))
        echo "  [skip] $COMBO — already has $EXISTING runs (need $RUNS)"
        echo "$(date -Iseconds) SKIP $COMBO ($EXISTING/$RUNS exist)" >> "$LOGFILE"
        continue
      fi

      for run in $(seq 1 $NEEDED); do
        SESSION_NUM=$((SESSION_NUM + 1))
        if [ "$FRESH" = "true" ]; then
          RUN_LABEL="$COMBO fresh run $run/$RUNS"
        else
          RUN_LABEL="$COMBO run $((EXISTING + run))/$RUNS"
        fi
        echo ""
        echo "── [$SESSION_NUM/$TOTAL] $RUN_LABEL ──"
        echo "$(date -Iseconds) START $RUN_LABEL" >> "$LOGFILE"

        if npm run e2e:sim -- --form "$form" --persona "$persona" --profile "$profile" --sampling weighted --split-prompt 2>&1; then
          COMPLETED=$((COMPLETED + 1))
          echo "$(date -Iseconds) OK    $RUN_LABEL" >> "$LOGFILE"
        else
          FAILED=$((FAILED + 1))
          echo "$(date -Iseconds) FAIL  $RUN_LABEL (exit=$?)" >> "$LOGFILE"
          echo ""
          echo "  [FAILED] $RUN_LABEL — continuing to next..."
        fi
      done
    done
  done
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo " Batch complete"
echo " Completed: $COMPLETED"
echo " Skipped:   $SKIPPED (already had enough runs)"
echo " Failed:    $FAILED"
echo " Logs in:   sims/"
echo "═══════════════════════════════════════════════════════"

echo "$(date -Iseconds) Batch done: completed=$COMPLETED skipped=$SKIPPED failed=$FAILED" >> "$LOGFILE"

# Summary
echo ""
echo "Session count by combo:"
ls -1 sims/sim-*.jsonl 2>/dev/null | \
  sed 's/.*sim-//' | sed 's/-[0-9T].*$//' | sort | uniq -c | sort -rn

# Show any combos that are short
echo ""
echo "Combos still needing runs:"
SHORT=0
for form in $FORMS; do
  for persona in $PERSONAS; do
    for profile in $PROFILES; do
      COMBO="${form}-${persona}-${profile}"
      COUNT=$(ls -1 sims/sim-${COMBO}-*.jsonl 2>/dev/null | wc -l | tr -d ' ')
      if [ "$COUNT" -lt "$RUNS" ]; then
        echo "  $COMBO: $COUNT/$RUNS"
        SHORT=$((SHORT + 1))
      fi
    done
  done
done
if [ "$SHORT" -eq 0 ]; then
  echo "  None — all combos have $RUNS runs!"
fi
