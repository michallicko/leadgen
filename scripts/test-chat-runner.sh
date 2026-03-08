#!/bin/bash
# Test chat runner — captures SSE stream from the playbook chat API.
#
# Usage:
#   bash scripts/test-chat-runner.sh [scenario] [api_url] [max_time]
#
# Arguments:
#   scenario  - "onboarding" (default) or "qa"
#   api_url   - Base URL for the API (default: http://localhost:5001)
#   max_time  - Max seconds to wait for response (default: 120)
#
# Output:
#   Prints the path to the captured SSE stream file on the last line.
#   The file contains raw SSE data lines.

set -euo pipefail

SCENARIO="${1:-onboarding}"
API_URL="${2:-http://localhost:5001}"
MAX_TIME="${3:-120}"

# --- Health check ---
if ! curl -sf "$API_URL/api/health" > /dev/null 2>&1; then
  echo "ERROR: API not reachable at $API_URL/api/health"
  echo "Start the dev server first: make dev"
  exit 1
fi

# --- Authenticate ---
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@staging.local","password":"staging123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to authenticate"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "Authenticated successfully"

# --- Build scenario payload ---
TIMESTAMP=$(date +%s)

case "$SCENARIO" in
  onboarding)
    PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'message': 'Generate a complete GTM strategy for unitedarts.cz. Goal: increase market penetration in Czech regions and pilot engagements with DACH event agencies.',
    'page_context': 'playbook'
}))
")
    ;;
  qa)
    PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'message': 'How many contacts do I have?',
    'page_context': 'contacts'
}))
")
    MAX_TIME="${3:-30}"
    ;;
  refinement)
    PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'message': 'Refine the ICP section. We should focus on mid-market companies (50-500 employees) in the creative and events industry, specifically in Prague and Munich.',
    'page_context': 'playbook'
}))
")
    ;;
  *)
    echo "Unknown scenario: $SCENARIO"
    echo "Available: onboarding, qa, refinement"
    exit 1
    ;;
esac

echo "Running scenario: $SCENARIO"
echo "Max time: ${MAX_TIME}s"

# --- Capture SSE stream ---
OUTPUT_FILE="/tmp/test-chat-${SCENARIO}-${TIMESTAMP}.txt"
START_TIME=$(date +%s)

curl -s -N -X POST "$API_URL/api/playbook/chat?stream=true" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Namespace: visionvolve" \
  -d "$PAYLOAD" \
  --max-time "$MAX_TIME" > "$OUTPUT_FILE" 2>&1 || true

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Duration: ${DURATION}s"
echo "SSE stream captured to: $OUTPUT_FILE"

# --- Summary ---
TOTAL_EVENTS=$(grep -c '^data:' "$OUTPUT_FILE" 2>/dev/null || echo 0)
CHUNK_COUNT=$(grep -c '"type":"chunk"' "$OUTPUT_FILE" 2>/dev/null || echo 0)
TOOL_START_COUNT=$(grep -c '"type":"tool_start"' "$OUTPUT_FILE" 2>/dev/null || echo 0)
TOOL_RESULT_COUNT=$(grep -c '"type":"tool_result"' "$OUTPUT_FILE" 2>/dev/null || echo 0)
DONE_COUNT=$(grep -c '"type":"done"' "$OUTPUT_FILE" 2>/dev/null || echo 0)
ERROR_COUNT=$(grep -c '"type":"error"' "$OUTPUT_FILE" 2>/dev/null || echo 0)

echo ""
echo "--- Event Summary ---"
echo "Total events: $TOTAL_EVENTS"
echo "  chunk: $CHUNK_COUNT"
echo "  tool_start: $TOOL_START_COUNT"
echo "  tool_result: $TOOL_RESULT_COUNT"
echo "  done: $DONE_COUNT"
echo "  error: $ERROR_COUNT"

if [ "$ERROR_COUNT" -gt 0 ]; then
  echo ""
  echo "--- Errors ---"
  grep '"type":"error"' "$OUTPUT_FILE" | head -5
fi

# Output file path as last line (for programmatic consumption)
echo ""
echo "$OUTPUT_FILE"
