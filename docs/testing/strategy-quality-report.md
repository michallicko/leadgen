# Strategy Creation Quality Assessment Report

**Date**: 2026-03-08
**Branch**: staging
**Environment**: Local dev (Flask 5001, Vite 5173)
**Test User**: test@staging.local

## Executive Summary

The chat-based strategy creation flow has a **critical defect**: the SSE streaming path works at the API level but fails silently when invoked from the React chat UI. User messages are sent and displayed, but the AI never responds through the UI. The API itself is functional -- both SSE and JSON endpoints return correct responses when called directly.

## Test Results

### What Works

| Test | Status | Details |
|------|--------|---------|
| Login | PASS | JWT auth works correctly |
| Playbook page loads | PASS | "GTM Strategy" heading, editor, tabs all render |
| Chat sidebar opens | PASS | Toggle button, Cmd+K, sidebar expansion all work |
| SSE API (direct fetch) | PASS | Status 200, `text/event-stream`, 2 events (chunk + done) in 5ms |
| JSON API (direct fetch) | PASS | Status 201, `application/json`, complete assistant response |
| User messages render | PASS | Messages typed in textarea appear as user bubbles in chat |
| Workflow suggestions | PASS | "Review Messages", "Continue Enrichment" chips visible |
| Phase transition banner | PASS | "Enrichment complete" banner with "Select Contacts" action |
| Progress strip | PASS | Strategy > Contacts > Enrich > Messages > Campaign pipeline |
| Editor | PASS | TipTap editor loads with toolbar (B/I/H1-H3/Bullet/etc.) |

### What Fails

| Test | Status | Details |
|------|--------|---------|
| Chat UI sends + receives | **FAIL** | User message appears, but NO AI response is rendered |
| Thinking/streaming indicator | **FAIL** | No pulse animation, no "Thinking..." text after message send |
| Strategy document population | **FAIL** | Editor shows only "Testing save indicator" (22 chars) -- AI never wrote to it |
| Conversation continuity | **FAIL** | Cannot test -- no first response to follow up on |
| Tool call cards | **FAIL** | 0 tool call cards visible (AI never invoked tools) |

## Root Cause Analysis

### The Disconnect

The SSE streaming endpoint (`POST /api/playbook/chat` with `Accept: text/event-stream`) works correctly when called via direct `fetch()` from the browser context:
- Returns `200 OK` with `Content-Type: text/event-stream`
- Emits proper SSE events: `data: {"text": "...", "type": "chunk"}` and `data: {"type": "done", ...}`
- Response time: ~5 seconds

But when the same endpoint is called via the React `ChatProvider.sendMessage()` -> `useSSE.startStream()` path:
- The user message is displayed as an optimistic bubble
- The `isThinking` state is set to `true` in React state
- **However**: no streaming indicator appears in the DOM after 2 seconds
- No SSE events are processed
- No AI response is ever rendered
- After 90+ seconds, the chat remains unchanged

### Likely Causes

1. **SSE stream silently fails**: The `fetch()` call in `useSSE.startStream()` may be throwing an error caught by the try/catch that calls `callbacks.onError()`, which resets state but shows no user-visible error. The `onError` handler in ChatProvider sets `streamingText = ''` and clears `optimisticMessages`, but the user message was already persisted server-side, so it shows up on refetch.

2. **Duplicate user messages**: The same message appears twice in the chat, suggesting:
   - First copy: optimistic message added by React state
   - Second copy: server-side persisted message from the `chatQuery.refetch()` after stream ends
   - The deduplication logic (`serverContents` set comparison) fails because the content matches are based on exact string equality, but the timing or format differs

3. **AbortController conflict**: The `useSSE` hook creates a new `AbortController` and aborts the previous one on each call. If React strict mode double-invokes effects, the first stream could be aborted by the second.

4. **Vite proxy SSE buffering**: The Vite dev proxy at `/api` -> `http://localhost:5001` may buffer SSE responses. Vite uses `http-proxy` which can interfere with chunked transfer encoding. The direct `fetch()` test worked because it also goes through the same proxy, so this is less likely but possible if the timing/headers differ.

## Performance Data

| Metric | Value |
|--------|-------|
| SSE API response (direct) | ~5ms to complete stream |
| JSON API response (direct) | ~2s full response |
| Chat UI response | Never (timeout after 90s+) |
| LLM input tokens | ~5,700-6,300 per call |
| LLM output tokens | ~44-242 per call |
| LLM cost per call | $0.005-0.006 |

## UI Quality Assessment

### Positive
- Clean, dark-themed UI with consistent spacing and typography
- Chat sidebar with proper collapsed/expanded states
- Workflow progress strip gives good visual context
- Phase transition banners are contextual and actionable
- Suggestion chips provide guided next actions
- TipTap editor with full toolbar for manual editing
- Sub-tabs (Strategy Overview, ICP Tiers, Buyer Personas) for organized content

### Issues
- **Critical**: No error feedback when chat fails -- user sees nothing happen
- **Major**: Duplicate user messages in chat history
- **Minor**: Chat doesn't auto-scroll to bottom when new messages appear
- **Minor**: Strategy document shows test content ("Testing save indicator") -- should be empty or have placeholder

## Content Quality (from Direct API Tests)

The AI responds in Czech (user's language preference), which is correct behavior. Responses are:
- Context-aware (references the user's talent booking agency project)
- Concise (one-paragraph responses with clear options)
- Formatted with markdown (bold, arrows, emoji)
- Fast (~2-5 seconds)

When working, the AI correctly identifies the user's domain and offers relevant strategy options.

## Screenshots

| File | Description |
|------|-------------|
| `01-playbook-loaded.png` | Playbook page with editor and "Testing save indicator" |
| `02-chat-open.png` | Chat sidebar expanded with workflow suggestions |
| `03-after-2s.png` | After sending message -- user messages visible, no AI response, shows previous direct-API response at top |
| `04-after-wait.png` | After 90s timeout -- unchanged from 03 |
| `05-scrolled-top.png` | Top of chat showing earlier messages |

## Recommendations

1. **P0 -- Fix the SSE streaming in ChatProvider**: Add error logging/UI feedback in the `useSSE.startStream()` error path. Currently errors are silently swallowed. Add a visible error toast or retry mechanism.

2. **P0 -- Debug the sendMessage flow**: Add console.log at each step of the `sendMessage` -> `startStream` pipeline to identify where the stream breaks (fetch call, response parsing, event dispatch, or React state update).

3. **P1 -- Fix duplicate user messages**: The deduplication logic in `ChatProvider.allMessages` needs to handle the case where both optimistic and server messages exist.

4. **P2 -- Add error states to chat UI**: When the SSE stream fails, show an error message like "Failed to get response. Click to retry." instead of silently doing nothing.

5. **P2 -- Auto-scroll chat**: Ensure chat scrolls to bottom when new messages appear.

## Test Script

The Playwright test is saved at `frontend/e2e/strategy-creation.spec.ts`. To run:

```bash
cd frontend && npx playwright test e2e/strategy-creation.spec.ts --reporter=list
```

Note: Requires local dev servers running (`make dev`).
