#!/usr/bin/env bash
#
# test-ask-user.sh — Automated diagnostic for AskUserQuestion pipeline
#
# Builds the web app, starts servers, sends a test request,
# captures all logs, and prints a diagnostic summary.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="/tmp/ffa-test-ask-user-$$"
mkdir -p "$LOG_DIR"

MOCK_PORT=3001
WEB_PORT=3004

echo "═══════════════════════════════════════════════════"
echo "  AskUserQuestion Pipeline Diagnostic"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Log dir: $LOG_DIR"
echo ""

# ── Cleanup on exit ──
cleanup() {
  echo ""
  echo "── Cleaning up ──"
  # Kill background processes
  [ -n "${MOCK_PID:-}" ] && kill "$MOCK_PID" 2>/dev/null && echo "Killed mock server (PID $MOCK_PID)"
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null && echo "Killed web app (PID $WEB_PID)"
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT

# ── Step 1: Check if ports are free ──
echo "── Step 1: Checking ports ──"
for port in $MOCK_PORT $WEB_PORT; do
  if lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "⚠️  Port $port is already in use. Kill the process first:"
    lsof -i :$port -sTCP:LISTEN
    echo ""
    echo "Run: kill \$(lsof -t -i :$port)"
    exit 1
  fi
done
echo "✓ Ports $MOCK_PORT and $WEB_PORT are free"
echo ""

# ── Step 2: Build (using tsx for dev, no build needed) ──
echo "── Step 2: Build check ──"
echo "Using tsx (dev mode) — no compile step needed"
echo ""

# ── Step 3: Start mock masters server ──
echo "── Step 3: Starting mock masters server (port $MOCK_PORT) ──"
cd "$PROJECT_ROOT"
npx tsx packages/mock-masters/src/index.ts > "$LOG_DIR/mock-server.log" 2>&1 &
MOCK_PID=$!
echo "PID: $MOCK_PID"

# Wait for mock server to be ready
for i in $(seq 1 20); do
  if curl -s "http://localhost:$MOCK_PORT" > /dev/null 2>&1; then
    echo "✓ Mock server ready"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "✗ Mock server failed to start. Logs:"
    cat "$LOG_DIR/mock-server.log"
    exit 1
  fi
  sleep 0.5
done
echo ""

# ── Step 4: Start web app ──
echo "── Step 4: Starting web app (port $WEB_PORT) ──"
cd "$PROJECT_ROOT"
npx tsx packages/web-app/src/index.ts > "$LOG_DIR/web-app.log" 2>&1 &
WEB_PID=$!
echo "PID: $WEB_PID"

# Wait for web app to be ready
for i in $(seq 1 20); do
  if curl -s "http://localhost:$WEB_PORT" > /dev/null 2>&1; then
    echo "✓ Web app ready"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "✗ Web app failed to start. Logs:"
    cat "$LOG_DIR/web-app.log"
    exit 1
  fi
  sleep 0.5
done
echo ""

# ── Step 5: Create a session ──
echo "── Step 5: Creating chat session ──"
SESSION_RESPONSE=$(curl -s -X POST "http://localhost:$WEB_PORT/api/sessions" \
  -H "Content-Type: application/json")
echo "Response: $SESSION_RESPONSE"

SESSION_ID=$(echo "$SESSION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null || echo "")
if [ -z "$SESSION_ID" ]; then
  echo "✗ Failed to create session"
  exit 1
fi
echo "✓ Session ID: $SESSION_ID"
echo ""

# ── Step 6: Send test message and capture SSE stream ──
echo "── Step 6: Sending test message (this may take 30-120s) ──"
echo "Message: 'Help me fill out the application at http://localhost:$MOCK_PORT'"
echo ""
echo "Streaming SSE response to $LOG_DIR/sse-response.txt ..."
echo "(Timeout: 120 seconds)"
echo ""

# Use curl to read the SSE stream. The stream ends when the server closes the connection (on 'done' event).
curl -s -N -X POST "http://localhost:$WEB_PORT/api/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"message\": \"Help me fill out the application at http://localhost:$MOCK_PORT\"}" \
  --max-time 120 \
  > "$LOG_DIR/sse-response.txt" 2>&1 || true

echo ""
echo "═══════════════════════════════════════════════════"
echo "  DIAGNOSTIC RESULTS"
echo "═══════════════════════════════════════════════════"
echo ""

# ── Analyze SSE response ──
echo "── SSE Events Received ──"
if [ -f "$LOG_DIR/sse-response.txt" ]; then
  # Extract event types from SSE format (lines starting with "event: ")
  echo "Event types:"
  grep "^event: " "$LOG_DIR/sse-response.txt" | sort | uniq -c | sort -rn || echo "(no events found)"
  echo ""

  # Check for ask_user event specifically
  if grep -q "^event: ask_user" "$LOG_DIR/sse-response.txt"; then
    echo "✅ ask_user SSE event FOUND!"
    echo ""
    echo "ask_user event data:"
    grep -A1 "^event: ask_user" "$LOG_DIR/sse-response.txt" | grep "^data: " | head -5
  else
    echo "❌ ask_user SSE event NOT found in response"
  fi
  echo ""

  # Check for tool_use events (which tool names appear?)
  echo "── Tool Use Events ──"
  grep "^event: tool_use" -A1 "$LOG_DIR/sse-response.txt" | grep "^data: " | while read -r line; do
    echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin.buffer); print(f'  tool: {d.get(\"name\",\"?\")}  input_keys: {list(d.get(\"input\",{}).keys()) if isinstance(d.get(\"input\"),dict) else type(d.get(\"input\")).__name__}')" 2>/dev/null || echo "  (parse error: $line)"
  done
  echo ""

  # Show text content (first 500 chars)
  echo "── Text Content (first 500 chars) ──"
  grep "^event: text" -A1 "$LOG_DIR/sse-response.txt" | grep "^data: " | while read -r line; do
    echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin.buffer).get('text','')[:200])" 2>/dev/null || true
  done | head -20
  echo ""
else
  echo "✗ No SSE response file found"
fi

# ── Analyze server logs ──
echo "── Server Logs (claude-cli events) ──"
if [ -f "$LOG_DIR/web-app.log" ]; then
  grep "\[claude-cli\]" "$LOG_DIR/web-app.log" || echo "(no claude-cli log lines)"
  echo ""

  echo "── AskUserQuestion Detection ──"
  if grep -q "AskUserQuestion detected" "$LOG_DIR/web-app.log"; then
    echo "✅ AskUserQuestion WAS detected by interception code"
    grep "AskUserQuestion detected" "$LOG_DIR/web-app.log"
  else
    echo "❌ AskUserQuestion was NOT detected"
    echo ""
    echo "Checking if any tool_use events mention AskUserQuestion:"
    grep -i "askuser" "$LOG_DIR/web-app.log" || echo "(none)"
  fi
  echo ""

  echo "── Full Server Log ──"
  cat "$LOG_DIR/web-app.log"
else
  echo "✗ No web app log file found"
fi

echo ""
echo "── Raw SSE Response (full) ──"
cat "$LOG_DIR/sse-response.txt" 2>/dev/null || echo "(empty)"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Files saved in: $LOG_DIR"
echo "═══════════════════════════════════════════════════"
