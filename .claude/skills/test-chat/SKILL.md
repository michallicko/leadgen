---
name: test-chat
description: Test agentic chatbot conversation quality. Feeds scenarios to the chat API, captures SSE streams, evaluates via LLM judge scoring.
user_invocable: true
---

# Test Chat - Conversation Quality Evaluation

## Usage

Invoke with: `/test-chat [scenario]`
- `/test-chat` -- run all scenarios
- `/test-chat onboarding` -- run playbook onboarding scenario only
- `/test-chat qa` -- run simple Q&A routing scenario only

## What This Does

1. Checks that local servers are running (Flask on port 5001)
2. Authenticates with test user credentials
3. Feeds the scenario to the chat API (`POST /api/playbook/chat`)
4. Captures the full SSE event stream
5. Evaluates the conversation against quality criteria
6. Reports scores and pass/fail verdict

## Step 1: Verify Local Server

Check that the API is running:

```bash
curl -sf http://localhost:5001/api/health > /dev/null 2>&1
```

If not running, tell the user to start it with `make dev`. Do NOT start it yourself.

## Step 2: Authenticate

```bash
TOKEN=$(curl -s -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@staging.local","password":"staging123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

If authentication fails, report the error and stop.

## Step 3: Run Scenario

Use the runner script to capture the SSE stream:

```bash
bash scripts/test-chat-runner.sh <scenario> http://localhost:5001 120
```

The script outputs the path to the captured SSE stream file.

Alternatively, run the curl directly:

```bash
curl -s -N -X POST http://localhost:5001/api/playbook/chat?stream=true \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Namespace: visionvolve" \
  -d '<payload>' \
  --max-time 120
```

## Scenarios

### Scenario: onboarding (PRIMARY)

**Purpose**: Test the full playbook generation flow with research and strategy writing.

**Payload**:
```json
{
  "message": "Generate a complete GTM strategy for unitedarts.cz. Goal: increase market penetration in Czech regions and pilot engagements with DACH event agencies.",
  "page_context": "playbook"
}
```

**Expected behavior**:
- Agent should use tools (web_search, website research) to gather information
- Agent should produce strategy content based on research findings
- Response should include tool_start/tool_result events showing research activity
- Final content should reference specific facts from the company website
- Done event should complete successfully

### Scenario: qa

**Purpose**: Test simple Q&A routing without heavy tool use.

**Payload**:
```json
{
  "message": "How many contacts do I have?",
  "page_context": "contacts"
}
```

**Expected behavior**:
- Fast response (should complete in under 30 seconds)
- May use a data query tool or answer directly
- Response should be concise and factual
- No lengthy strategy generation

## Step 4: Parse SSE Events

Read the captured output file. Each SSE event is a `data: {...}\n\n` line. Parse events by type:

- `chunk` -- text content streaming (has `text` field)
- `tool_start` -- agent initiated a tool call (has `toolCallId`, `toolName`, `input` fields)
- `tool_result` -- tool execution completed (has `toolCallId`, `toolName`, `status`, `summary`, `durationMs` fields)
- `done` -- conversation turn completed (has `messageId`, `toolCalls`, `total_input_tokens`, `total_output_tokens`, `total_cost_usd` fields)
- `error` -- an error occurred (has `message` field)

Count events by type and reconstruct the full assistant message from chunk events.

## Step 5: Evaluate Quality

After parsing the SSE stream, evaluate each criterion by reading the full content and tool activity.

### Evaluation Criteria for Onboarding Scenario

#### 1. Research Grounding (Score 1-5)
- Were tool_start/tool_result events emitted showing research activity?
- Did tool results reference the actual company website (unitedarts.cz)?
- Were company facts in the final content traceable to tool outputs?
- Score 5: Multiple research tools used, findings clearly referenced in content
- Score 3: Some research done but content is generic
- Score 1: No research tools used, or content ignores research findings

#### 2. Cross-Check Rigor (Score 1-5)
- Were multiple sources consulted (website + external search)?
- Were conflicting or complementary findings noted?
- Score 5: Multiple sources cross-referenced, conflicts handled
- Score 3: Single source used but findings are accurate
- Score 1: No cross-checking, content may contain inaccuracies

#### 3. Discovery Quality (Score 1-5)
- Did the agent ask targeted follow-up questions (not generic)?
- Were questions based on research gaps?
- Score 5: Specific questions tied to research findings and strategy gaps
- Score 3: Generic questions that show some understanding
- Score 1: No questions asked, or questions are completely generic

#### 4. Strategy Quality (Score 1-5)
- Is the ICP specific enough to act on (industries, titles, company size)?
- Is competitive positioning differentiated?
- Does the strategy reference real market data?
- Score 5: Actionable ICP, specific positioning, market-grounded
- Score 3: Reasonable strategy but somewhat generic
- Score 1: Completely generic, no specifics from research

#### 5. UX Quality (Score 1-5)
- Was the chat response concise (detailed content in tool outputs, not chat)?
- Did the response complete without errors?
- Was the done event properly formed?
- Score 5: Clean stream, no errors, well-structured response
- Score 3: Some minor issues but functional
- Score 1: Errors, broken stream, or unusable response

### Evaluation Criteria for Q&A Scenario

#### 1. Response Speed (Score 1-5)
- Score 5: Completed in under 5 seconds
- Score 3: Completed in 5-15 seconds
- Score 1: Over 30 seconds or timed out

#### 2. Accuracy (Score 1-5)
- Did the response provide a factual answer?
- Was the data correct (if tool was used to query)?

#### 3. Conciseness (Score 1-5)
- Was the response brief and to the point?
- Score 5: Direct answer in 1-2 sentences
- Score 1: Verbose, unnecessary elaboration

### Thresholds

- **PASS**: All criteria >= 3.5, average >= 4.0
- **WARN**: Any criterion between 3.0-3.5
- **FAIL**: Any criterion < 3.0

## Step 6: Report

Output the quality report in this format:

```
=== CHATBOT QUALITY REPORT ===
Scenario: <scenario name>
Timestamp: <ISO timestamp>

--- Stream Summary ---
Events captured: {total}
  chunk: {N}
  tool_start: {N}
  tool_result: {N}
  done: {N}
  error: {N}
Total tokens: {input_tokens} in / {output_tokens} out
Cost: ${cost_usd}
Duration: {seconds}s

--- Full Assistant Response (first 500 chars) ---
{truncated response text}

--- Tool Activity ---
{For each tool_start/tool_result pair:}
  - {toolName}: {status} ({durationMs}ms) -- {summary}

--- Scores ---
Research Grounding:  {score}/5 -- {one-line reasoning}
Cross-Check Rigor:   {score}/5 -- {one-line reasoning}
Discovery Quality:   {score}/5 -- {one-line reasoning}
Strategy Quality:    {score}/5 -- {one-line reasoning}
UX Quality:          {score}/5 -- {one-line reasoning}

Average: {avg}/5
Verdict: PASS / WARN / FAIL

--- Issues Found ---
- {issue 1}
- {issue 2}

--- Suggestions ---
- {suggestion 1}
- {suggestion 2}
```

## Notes

- The chat API endpoint is `POST /api/playbook/chat` (NOT `/api/v2/chat`)
- Streaming requires either `Accept: text/event-stream` header or `?stream=true` query param
- Authentication uses JWT Bearer token + `X-Namespace: visionvolve` header
- Test credentials: `test@staging.local` / `staging123`
- The onboarding scenario may take 60-120 seconds due to web research
- Each run creates chat messages in the database -- use a unique thread for isolation
- SSE events are `data: {json}\n\n` format (no `event:` field, type is in the JSON payload)
