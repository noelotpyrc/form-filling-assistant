#!/usr/bin/env bash
# eval_sweep.sh — Run eval_grpo.py across all 6 checkpoints (base, SFT, 4 GRPO).
#
# For each model: start mlx_vlm.server, wait for it, run eval, stop server.
# Produces per-checkpoint preds + summary under tuning/rl/eval_results/.
#
# Usage:
#   ./tuning/rl/eval_sweep.sh                # full 300-case sweep
#   ./tuning/rl/eval_sweep.sh 30             # quick: 30 cases each (sanity)

set -e

NUM_ARG=""
if [ -n "${1:-}" ]; then
  NUM_ARG="--num $1"
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_DIR="$PROJECT_ROOT/python"
RESULTS_DIR="$PROJECT_ROOT/tuning/rl/eval_results"
mkdir -p "$RESULTS_DIR"

PORT=8099  # dedicated eval port (avoid collisions with regular dev servers)
URL="http://localhost:$PORT/v1/chat/completions"

# Model ID → local path mapping
# (Base model is served by mlx_lm with the HF id; everything else is a local path)
declare -a CKPTS=(
  "base|mlx_lm|mlx-community/Qwen3.5-0.8B-4bit"
  "sft|mlx_vlm|$HOME/work/models/qwen35-08b-dspy-format-mlx"
  "grpo-300|mlx_vlm|$HOME/work/models/grpo-merged/mlx-ready/checkpoint-300"
  "grpo-900|mlx_vlm|$HOME/work/models/grpo-merged/mlx-ready/checkpoint-900"
  "grpo-1500|mlx_vlm|$HOME/work/models/grpo-merged/mlx-ready/checkpoint-1500"
  "grpo-1800|mlx_vlm|$HOME/work/models/grpo-merged/mlx-ready/checkpoint-1800"
)

# Models to skip (e.g. already evaluated)
SKIP="${SKIP:-}"

stop_server() {
  local pidfile="/tmp/eval-sweep-${PORT}.pid"
  if [ ! -f "$pidfile" ]; then
    return 0
  fi
  local pid
  pid=$(cat "$pidfile")
  rm -f "$pidfile"

  if ! ps -p "$pid" > /dev/null 2>&1; then
    return 0
  fi

  echo "[server] Stopping pid=$pid (SIGTERM)..."
  kill -TERM "$pid" 2>/dev/null || true

  # Wait up to 10s for graceful exit
  for _ in $(seq 1 10); do
    ps -p "$pid" > /dev/null 2>&1 || break
    sleep 1
  done

  # Force-kill if still alive
  if ps -p "$pid" > /dev/null 2>&1; then
    echo "[server] pid=$pid still alive, sending SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
    sleep 2
  fi

  # Wait for port to fully release
  for _ in $(seq 1 30); do
    lsof -i ":$PORT" > /dev/null 2>&1 || break
    sleep 1
  done

  # Extra pause for MLX/Metal to release memory
  # (MLX holds GPU memory until Python process is fully reaped)
  echo "[server] Sleeping 20s for memory reclaim..."
  sleep 20

  # Report available memory (free + inactive + purgeable; macOS style)
  report_mem
}

# Available memory on macOS = free + inactive + purgeable pages.
# macOS aggressively caches files as "inactive", so raw "free" is misleading.
report_mem() {
  if ! command -v vm_stat > /dev/null 2>&1; then
    return 0
  fi
  local page_size free inactive purgeable used_gb avail_gb
  page_size=$(vm_stat | awk '/page size of/ {print $8}')
  free=$(vm_stat | awk '/Pages free/ {gsub(/\./,"",$3); print $3}')
  inactive=$(vm_stat | awk '/Pages inactive/ {gsub(/\./,"",$3); print $3}')
  purgeable=$(vm_stat | awk '/Pages purgeable/ {gsub(/\./,"",$3); print $3}')
  avail_gb=$(awk -v p="$page_size" -v a="$((free + inactive + purgeable))" \
    'BEGIN {printf "%.2f", (p*a)/1024/1024/1024}')
  echo "[mem] Available: ${avail_gb} GB (free+inactive+purgeable)"
}

start_server() {
  local server_mod=$1
  local model=$2
  echo "[server] Starting $server_mod with $model on port $PORT..."
  cd "$PYTHON_DIR" && uv run python -m "$server_mod" server \
    --model "$model" \
    --port "$PORT" \
    > "/tmp/eval-sweep-${PORT}.log" 2>&1 &
  local pid=$!
  echo "$pid" > "/tmp/eval-sweep-${PORT}.pid"

  # Wait for ready
  for _ in $(seq 1 180); do
    # Detect early exit (OOM, init failure, etc.)
    if ! ps -p "$pid" > /dev/null 2>&1; then
      echo "[server] ERROR: process died during startup"
      tail -30 "/tmp/eval-sweep-${PORT}.log"
      return 1
    fi
    if curl -s "http://localhost:$PORT/v1/models" > /dev/null 2>&1; then
      echo "[server] Ready (pid=$pid)"
      return 0
    fi
    sleep 1
  done
  echo "[server] ERROR: did not become ready within 180s"
  tail -30 "/tmp/eval-sweep-${PORT}.log"
  return 1
}

trap 'stop_server' EXIT

echo "═══════════════════════════════════════════════════════════════════"
echo "GRPO Eval Sweep"
echo "═══════════════════════════════════════════════════════════════════"
echo "Checkpoints: ${#CKPTS[@]}"
echo "Output:      $RESULTS_DIR"
echo "Port:        $PORT"
[ -n "$NUM_ARG" ] && echo "Limit:       $NUM_ARG"
echo

for entry in "${CKPTS[@]}"; do
  NAME="${entry%%|*}"
  REST="${entry#*|}"
  SERVER_MOD="${REST%%|*}"
  MODEL="${REST#*|}"

  if [[ ",$SKIP," == *",$NAME,"* ]]; then
    echo "[skip] $NAME (in SKIP list)"
    continue
  fi

  echo
  echo "───────────────────────────────────────────────────────────────────"
  echo "Evaluating: $NAME  (server: $SERVER_MOD)"
  echo "Model:      $MODEL"
  echo "───────────────────────────────────────────────────────────────────"

  stop_server

  # Pre-flight memory check (M1 Pro 16GB — require ≥ 6 GB available before loading a 1.6 GB model)
  if command -v vm_stat > /dev/null 2>&1; then
    for attempt in 1 2 3; do
      page_size=$(vm_stat | awk '/page size of/ {print $8}')
      free=$(vm_stat | awk '/Pages free/ {gsub(/\./,"",$3); print $3}')
      inactive=$(vm_stat | awk '/Pages inactive/ {gsub(/\./,"",$3); print $3}')
      purgeable=$(vm_stat | awk '/Pages purgeable/ {gsub(/\./,"",$3); print $3}')
      avail_gb=$(awk -v p="$page_size" -v a="$((free + inactive + purgeable))" \
        'BEGIN {printf "%.2f", (p*a)/1024/1024/1024}')
      echo "[preflight] Available: ${avail_gb} GB (attempt $attempt)"
      if awk "BEGIN {exit !($avail_gb >= 6.0)}"; then
        break
      fi
      echo "[preflight] ⚠️  Low memory, sleeping 30s more..."
      sleep 30
    done
  fi

  start_server "$SERVER_MOD" "$MODEL" || { echo "Skipping $NAME due to server error"; continue; }

  cd "$PYTHON_DIR" && uv run python "$PROJECT_ROOT/tuning/rl/eval_grpo.py" \
    --url "$URL" \
    --model-path "$MODEL" \
    --checkpoint-name "$NAME" \
    --output "$RESULTS_DIR" \
    $NUM_ARG

  stop_server
done

echo
echo "═══════════════════════════════════════════════════════════════════"
echo "SWEEP COMPLETE"
echo "═══════════════════════════════════════════════════════════════════"
echo "Results under: $RESULTS_DIR"
ls -la "$RESULTS_DIR"/summary_*.json 2>/dev/null
echo
echo "To generate comparison report:"
echo "  uv run python tuning/rl/eval_report.py --results $RESULTS_DIR"
