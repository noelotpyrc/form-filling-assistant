#!/bin/bash
# serve-models.sh — Start MLX model servers for local inference
#
# Usage:
#   ./scripts/serve-models.sh smollm     # SmolLM2-360M on port 8081
#   ./scripts/serve-models.sh qwen       # Qwen3.5-0.8B on port 8082
#   ./scripts/serve-models.sh qwen-4b    # Qwen3.5-4B on port 8083
#   ./scripts/serve-models.sh qwen-sft   # Qwen3.5-0.8B SFT (format) on port 8084 (mlx_vlm)
#   ./scripts/serve-models.sh compare    # Original 0.8B + SFT side-by-side
#   ./scripts/serve-models.sh both       # SmolLM2 + Qwen 0.8B
#   ./scripts/serve-models.sh stop       # Stop all model servers
#
# Test:
#   curl http://localhost:8081/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model": "smollm", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}'

PYTHON_DIR="$(cd "$(dirname "$0")/.." && pwd)/python"

SMOLLM_MODEL="mlx-community/SmolLM2-360M-Instruct"
SMOLLM_PORT=8081

QWEN_MODEL="mlx-community/Qwen3.5-0.8B-4bit"
QWEN_PORT=8082

QWEN_4B_MODEL="mlx-community/Qwen3.5-4B-4bit"
QWEN_4B_PORT=8083

QWEN_SFT_MODEL="$HOME/work/models/qwen35-08b-dspy-format-mlx"
QWEN_SFT_PORT=8084

start_model() {
  local name=$1
  local model=$2
  local port=$3
  local server_module=${4:-mlx_lm}  # default to mlx_lm, override for VLM

  # Check if already running
  if lsof -i ":$port" -sTCP:LISTEN > /dev/null 2>&1; then
    echo "[$name] Already running on port $port"
    return
  fi

  echo "[$name] Starting on port $port..."
  echo "[$name] Model: $model"
  echo "[$name] Server: $server_module"
  cd "$PYTHON_DIR" && uv run python -m "$server_module" server \
    --model "$model" \
    --port "$port" \
    > "/tmp/mlx-${name}.log" 2>&1 &
  local pid=$!
  echo $pid > "/tmp/mlx-${name}.pid"

  # Wait for server to be ready
  local retries=0
  while ! curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; do
    retries=$((retries + 1))
    if [ $retries -ge 60 ]; then
      echo "[$name] Failed to start (timeout). Check /tmp/mlx-${name}.log"
      return 1
    fi
    sleep 1
  done
  echo "[$name] Ready at http://localhost:$port"
}

stop_all() {
  for name in smollm qwen qwen-4b qwen-sft; do
    local pidfile="/tmp/mlx-${name}.pid"
    if [ -f "$pidfile" ]; then
      local pid=$(cat "$pidfile")
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "[$name] Stopped (pid $pid)"
      fi
      rm "$pidfile"
    fi
  done
}

case "${1:-both}" in
  smollm)
    start_model "smollm" "$SMOLLM_MODEL" "$SMOLLM_PORT"
    ;;
  qwen)
    start_model "qwen" "$QWEN_MODEL" "$QWEN_PORT"
    ;;
  qwen-4b)
    start_model "qwen-4b" "$QWEN_4B_MODEL" "$QWEN_4B_PORT"
    ;;
  both)
    start_model "smollm" "$SMOLLM_MODEL" "$SMOLLM_PORT"
    start_model "qwen" "$QWEN_MODEL" "$QWEN_PORT"
    ;;
  qwen-sft)
    start_model "qwen-sft" "$QWEN_SFT_MODEL" "$QWEN_SFT_PORT" "mlx_vlm"
    ;;
  compare)
    start_model "qwen" "$QWEN_MODEL" "$QWEN_PORT"
    start_model "qwen-sft" "$QWEN_SFT_MODEL" "$QWEN_SFT_PORT" "mlx_vlm"
    ;;
  stop)
    stop_all
    ;;
  *)
    echo "Usage: $0 {smollm|qwen|qwen-4b|qwen-sft|compare|both|stop}"
    exit 1
    ;;
esac
