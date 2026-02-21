# Chrome Extension: LinkedIn Send Capability

**Status**: Draft
**Date**: 2026-02-21
**Theme**: AI-Native GTM — Personalized Outreach (Track B)
**Depends on**: Track A (linkedin_send_queue API)
**Parent Spec**: docs/specs/personalized-outreach-campaign.md

## Purpose

Add LinkedIn message and connection request sending to the existing Chrome extension. The extension becomes a "safe send agent" — it pulls approved messages from the platform's linkedin_send_queue API and executes them with human-like timing and conservative rate limiting to prevent account bans.

Today the extension only scrapes Sales Navigator profiles and tracks activity (invites accepted, messages sent/received). This spec adds the inverse capability: consuming a queue of outbound actions and executing them safely through the user's authenticated LinkedIn session.

## Requirements

### Functional Requirements

1. **FR-1: Queue Consumer** — Extension periodically polls the platform API for queued LinkedIn actions (connection requests + messages). Pulls in small batches (5 at a time). Polling interval: 60 seconds when idle, 5 seconds immediately after completing an action (to keep the pipeline flowing during an active session).

2. **FR-2: Connection Request Send** — Extension navigates to the contact's LinkedIn profile, clicks "Connect", optionally adds a personalized note (max 300 chars), and confirms. Reports success/failure back to API. Handles the two LinkedIn connect flows: direct "Connect" button on profile, and "More... → Connect" dropdown variant.

3. **FR-3: Message Send** — Extension navigates to the contact's LinkedIn messaging thread, types the message body with human-like typing speed, and sends. Reports success/failure back to API. Handles both new conversations (via profile → "Message" button) and existing threads (via messaging inbox URL).

4. **FR-4: Rate Limiting Engine** — Enforces daily limits with per-account configuration:
   - Connection requests: default 15/day (conservative), max 25/day (user override)
   - Messages: default 40/day (conservative), max 60/day (user override)
   - Weekly: connection requests capped at 80/week even if daily limits allow more
   - Warmup: new accounts start at 5 requests/day, increase by 3/day each week until reaching configured default
   - Limits reset at midnight in the user's local timezone
   - Counters persist in `chrome.storage.local` (survive browser restarts)

5. **FR-5: Human-Like Timing** — Random delays between actions:
   - Between actions: 45-180 seconds (randomized, Gaussian distribution centered at 90s)
   - Active hours only: 8am-7pm in user's timezone (configurable)
   - No weekend sends (configurable, default off on weekends)
   - Typing simulation: 30-80ms per character with occasional pauses (200-800ms every 8-15 characters)
   - Page dwell time: stay on profile page 3-8 seconds before taking action (simulates reading)
   - Scroll simulation: small random scrolls on profile pages before clicking Connect/Message

6. **FR-6: Safety Circuit Breaker** — Automatically pauses all sending if any of these conditions are detected:
   - LinkedIn shows a warning or restriction banner (detected via known DOM patterns)
   - Connection request acceptance rate drops below 20% (calculated over rolling 50 requests)
   - Profile page returns HTTP error, "page not found", or restricted-access page
   - More than 3 consecutive action failures (reset on next success)
   - Browser tab becomes inactive/hidden for more than 5 minutes (pause until re-focused)
   - Reports pause reason to platform API via `PATCH /api/extension/linkedin-queue/pause`

7. **FR-7: Dashboard Widget** — Small floating widget (bottom-right corner) visible on LinkedIn pages, showing:
   - Current queue depth: "5 invites, 3 messages remaining"
   - Daily usage: "12/15 invites used, 28/40 messages used" (progress bars)
   - Status indicator: Active (green pulse) / Paused (yellow) / Completed (gray) / Error (red)
   - Pause/Resume toggle button
   - Collapse/expand (minimizes to small icon when collapsed)
   - Settings gear icon (opens config panel in extension popup)

8. **FR-8: Status Reporting** — Extension reports back to platform API:
   - Per-action: `PATCH /api/extension/linkedin-queue/{id}` with status (sent/failed/skipped), timestamp, error detail
   - Daily summary: `POST /api/extension/linkedin-queue/daily-summary` with total sent, total failed, acceptance rate, session duration
   - Session heartbeat: `POST /api/extension/linkedin-queue/heartbeat` every 30 seconds while active (so platform knows extension is alive)

9. **FR-9: Action Preview** — Before executing each action, the widget briefly shows what it is about to do: "Connecting with Jane Doe (Acme Corp)..." with a 5-second countdown and a "Skip" button. This gives the user a chance to skip individual actions without pausing the entire queue.

### Non-Functional Requirements

1. **NFR-1: Stealth** — Extension actions must be indistinguishable from manual user behavior. No rapid-fire actions, no direct LinkedIn API calls, no browser automation markers (`navigator.webdriver` must be false). DOM interactions use native click/keyboard events, not synthetic dispatches.

2. **NFR-2: Resilience** — Extension handles LinkedIn UI changes gracefully. DOM selectors use a tiered strategy: (1) `data-test-id` attributes, (2) `aria-label` patterns, (3) CSS class name patterns, (4) text content matching. Each selector tier is tried in order. Selector definitions are stored in a separate config file for easy updates without code changes.

3. **NFR-3: Battery/Performance** — Extension must not significantly impact browser performance when idle. No busy loops. Polling uses `chrome.alarms` API (min 1-minute granularity) rather than `setInterval`. Background service worker wakes only for alarms and message events.

4. **NFR-4: Privacy** — Extension only accesses LinkedIn pages (host permission: `*://*.linkedin.com/*`). No data leaves the browser except via the authenticated platform API (`leadgen.visionvolve.com`). No third-party analytics or tracking.

5. **NFR-5: Manifest V3 Compliance** — All functionality must work within Manifest V3 constraints: service worker (not persistent background page), no remote code execution, declarative content scripts.

## Architecture

### Queue Consumer Pattern

```
Platform API                    Chrome Extension
---------------------           ----------------
linkedin_send_queue    <----    GET /api/extension/linkedin-queue?limit=5
                                    |
                                Store in local queue (chrome.storage.local)
                                    |
                                Pick next action
                                    |
                                Navigate to LinkedIn profile/messaging
                                    |
                                Dwell on page (3-8s, random scroll)
                                    |
                                Preview in widget (5s countdown)
                                    |
                                Execute action (connect/message)
                                    |
                                Wait (typing simulation for messages)
                                    |
linkedin_send_queue    <----    PATCH /api/extension/linkedin-queue/{id}
                                    |
                                Wait (45-180s random delay)
                                    |
                                Check rate limits + safety
                                    |
                                If under limits AND safe --> loop to next action
                                If over limits --> pause until next active window
                                If safety triggered --> pause + report reason
```

### Extension Components

```
extension/
  manifest.json                    # Manifest V3 config
  service-worker.js                # Background: alarms, message routing, API calls
  content-scripts/
    linkedin-executor.js           # Content script: DOM interaction on LinkedIn pages
    widget.js                      # Floating status widget (injected into LinkedIn pages)
    widget.css                     # Widget styles (shadow DOM isolated)
  popup/
    popup.html                     # Extension popup (settings, status overview)
    popup.js                       # Popup logic
  lib/
    queue-manager.js               # Queue polling, local storage, retry logic
    action-executor.js             # Navigate + execute connect/message actions
    rate-limiter.js                # Daily/weekly counters, warmup schedule
    timing-engine.js               # Human-like delays, active hours, typing sim
    safety-monitor.js              # Circuit breaker, warning detection
    selector-config.js             # LinkedIn DOM selectors (tiered fallbacks)
    api-client.js                  # Platform API communication (auth, queue, reporting)
  config/
    defaults.json                  # Default rate limits, timing params, active hours
```

**Component responsibilities:**

1. **QueueManager** (`queue-manager.js`) — Polls platform API on alarm intervals, stores fetched actions in `chrome.storage.local`, manages local queue ordering (FIFO within priority: connection requests before messages), handles claim/release semantics, retries failed fetches with exponential backoff.

2. **ActionExecutor** (`action-executor.js`) — Receives an action from QueueManager, instructs the content script to navigate to the target URL, waits for page load, then dispatches the appropriate DOM interaction sequence (connect flow or message flow). Returns success/failure/skip result.

3. **RateLimiter** (`rate-limiter.js`) — Maintains counters in `chrome.storage.local` keyed by date and week number. Checks before each action whether daily/weekly limits allow it. Manages warmup schedule (account age in weeks, escalating daily cap). Exposes `canExecute()` and `recordExecution()` methods.

4. **TimingEngine** (`timing-engine.js`) — Generates randomized delays using Gaussian distribution. Manages active hours window (checks current time against configured range). Provides `waitBetweenActions()`, `typeCharacter()`, `dwellOnPage()`, and `isActiveWindow()` methods. Uses `chrome.alarms` for scheduling future actions rather than holding timers in memory.

5. **SafetyMonitor** (`safety-monitor.js`) — Content script companion that watches the LinkedIn DOM for warning banners, restriction notices, and error states. Maintains a rolling window of action results for acceptance rate calculation. Triggers circuit breaker (pauses queue) and reports reason to platform. Exposes `isSafe()` check called before each action.

6. **StatusWidget** (`widget.js`) — Injected into LinkedIn pages via content script. Renders in a Shadow DOM container to avoid style conflicts. Shows real-time queue status, daily usage bars, and pause/resume control. Communicates with service worker via `chrome.runtime.sendMessage`.

7. **SelectorConfig** (`selector-config.js`) — Centralized LinkedIn DOM selector definitions with tiered fallbacks. Each action (click Connect, type message, click Send) has an array of selector strategies tried in order. Updated independently when LinkedIn changes its UI. Versioned so the platform API can report which selector version the extension is using.

### State Machine (per action)

```
                                    +---> skipped (user clicked Skip in preview)
                                    |
queued --> claimed --> navigating --> previewing --> executing --> sent
                          |              |              |
                          v              v              v
                       nav_failed    skipped       exec_failed
                          |                            |
                          v                            v
                       (retry count < 2?)          (retry count < 2?)
                          |    |                      |    |
                         yes   no                    yes   no
                          |    |                      |    |
                          v    v                      v    v
                       queued  failed              queued  failed
```

**State transitions:**
- `queued` -- Extension pulls from API, stores locally
- `claimed` -- Extension marks action as in-progress (prevents duplicate pull)
- `navigating` -- Browser tab is navigating to target LinkedIn URL
- `previewing` -- Widget shows action preview with countdown
- `executing` -- DOM interaction in progress (clicking, typing)
- `sent` -- Action completed successfully, reported to API
- `failed` -- Action failed after max retries, reported to API
- `skipped` -- User manually skipped, or action not applicable (already connected, profile not found)

### Data Flow: API Integration

The extension consumes and reports to the Track A API endpoints defined in the parent spec:

**Consume:**
```
GET /api/extension/linkedin-queue?limit=5
Authorization: Bearer {jwt_token}

Response:
[
  {
    "id": "uuid",
    "action_type": "connection_request" | "message",
    "linkedin_url": "https://www.linkedin.com/in/janedoe/",
    "body": "Hi Jane, I noticed your work on...",
    "contact_name": "Jane Doe",
    "contact_company": "Acme Corp",
    "campaign_name": "AI Community Invites"
  }
]
```

**Report:**
```
PATCH /api/extension/linkedin-queue/{id}
Authorization: Bearer {jwt_token}

Body:
{
  "status": "sent" | "failed" | "skipped",
  "error": "selector_not_found" | "profile_not_found" | "already_connected" | null,
  "executed_at": "2026-02-21T14:23:45Z",
  "selector_version": "2026-02-21",
  "duration_ms": 12400
}
```

**Heartbeat:**
```
POST /api/extension/linkedin-queue/heartbeat
Authorization: Bearer {jwt_token}

Body:
{
  "status": "active" | "paused" | "idle",
  "queue_depth": 5,
  "daily_counts": {
    "connection_requests": { "sent": 12, "limit": 15 },
    "messages": { "sent": 28, "limit": 40 }
  },
  "pause_reason": null | "daily_limit" | "circuit_breaker" | "outside_hours" | "user_paused"
}
```

### Authentication

The extension reuses the same JWT authentication as the dashboard:
- User logs into the platform via the extension popup (same credentials)
- JWT access token stored in `chrome.storage.local` (encrypted)
- Refresh token used to rotate access tokens automatically
- `X-Namespace` header included on all API calls for tenant resolution
- Token expiry triggers automatic refresh; if refresh fails, extension pauses and prompts re-login

## Acceptance Criteria

- [ ] **AC-1**: Given 10 approved LinkedIn connection requests in the queue, when the extension is active during business hours, then it sends all 10 with random 45-180s delays between each, completing in approximately 15-30 minutes.
- [ ] **AC-2**: Given the daily limit is 15 connection requests and 12 have been sent today, when 5 more are queued, then only 3 are sent and 2 remain queued for the next active window.
- [ ] **AC-3**: Given LinkedIn shows a "you've reached your weekly invitation limit" banner, when the SafetyMonitor detects it, then it pauses all sending, reports the reason to the platform API, and the widget shows "Paused: LinkedIn limit detected."
- [ ] **AC-4**: Given an account with warmup enabled and in its first week, when the warmup schedule is active, then daily connection request limit is 5 and increases by 3 each subsequent week until reaching the configured default.
- [ ] **AC-5**: Given the extension is active at 11pm (outside configured active hours of 8am-7pm), then no actions are executed and the widget shows "Paused: Outside active hours. Resuming at 8:00 AM."
- [ ] **AC-6**: Given a message action, when the extension types the message, then it simulates human typing speed (30-80ms/char) with occasional pauses (200-800ms every 8-15 chars), and the total typing time for a 200-character message is approximately 10-20 seconds.
- [ ] **AC-7**: Given the extension preview shows "Connecting with Jane Doe (Acme Corp)..." with a 5s countdown, when the user clicks "Skip", then the action is marked `skipped` in the API and the extension moves to the next queued action.
- [ ] **AC-8**: Given 4 consecutive connection request failures (e.g., profile pages returning errors), when the SafetyMonitor threshold (3 consecutive failures) is exceeded, then the circuit breaker triggers, all sending pauses, and the reason is reported to the platform.
- [ ] **AC-9**: Given the browser is closed while 3 actions remain in the local queue, when the browser reopens and the extension starts, then it resumes from the remaining queued actions without re-fetching already-claimed actions from the API.
- [ ] **AC-10**: Given the extension is running and the user manually sends a LinkedIn connection request outside the extension, when the activity tracker detects it, then the manual send counts toward the daily limit.

## Edge Cases

1. **LinkedIn UI redesign** — ActionExecutor uses tiered selector strategies (data-test-id, aria-label, class patterns, text content). Falls back through all tiers. If all selectors fail, reports `selector_not_found` error with the page URL and selector version for debugging. Does NOT retry with the same selectors (would just fail again).

2. **Profile page not found** — Contact may have deleted or deactivated their LinkedIn account. Extension detects "page not found" or profile-not-available patterns. Skips action, reports `profile_not_found` to API. Platform can mark the contact's LinkedIn URL as stale.

3. **Already connected** — Extension detects "Message" button instead of "Connect" on the profile page. Skips the connection request, reports `already_connected`. If there is also a message action queued for this contact, it proceeds normally.

4. **Connection note exceeds 300 characters** — LinkedIn enforces a 300-char limit on connection request notes. Extension truncates at word boundary before 300 chars, appending "..." if truncated. Logs a warning in the action report.

5. **Browser closed mid-action** — If the browser closes while an action is in `executing` state, it remains `claimed` in the local queue. On restart, the extension checks the `claimed` action: if less than 10 minutes old, it retries (navigates fresh); if older, it releases back to `queued` state.

6. **Multiple LinkedIn tabs open** — Extension operates in exactly one tab at a time. The first LinkedIn tab to become active claims the "executor" lock (stored in `chrome.storage.session`). Other tabs show the widget in read-only mode. If the active tab closes, the next LinkedIn tab can claim the lock.

7. **User manually sends during extension session** — The existing activity tracker already monitors messages sent and invites accepted. The RateLimiter reads these activity counts and subtracts them from the daily limit. This means if a user manually sends 5 connection requests, the extension's remaining daily budget decreases by 5.

8. **LinkedIn login session expires** — Extension detects LinkedIn login page redirect during navigation. Pauses all actions, shows "LinkedIn session expired — please log in" in the widget. Resumes automatically when it detects a valid LinkedIn session.

9. **Slow/unstable network** — API calls use exponential backoff (1s, 2s, 4s, max 30s). DOM interactions wait for page load with a 15-second timeout. If navigation times out, the action is retried up to 2 times before being marked failed.

10. **Connection request without "Connect" button visible** — Some profiles show "Follow" instead of "Connect" (creator mode, or LinkedIn's own restrictions). Extension checks for both "Connect" and "More... > Connect". If neither is found, reports `connect_not_available` and skips.

11. **Rate limit counters corrupted** — If `chrome.storage.local` data is corrupted or cleared, RateLimiter initializes fresh counters at zero. This is conservative: in the worst case the user sends slightly more than intended for one day, but the safety monitor still catches LinkedIn-side warnings.

12. **Extension update mid-session** — Chrome may reload the service worker on extension update. All in-flight state is in `chrome.storage.local` (persistent) and `chrome.storage.session` (tab lock). The service worker re-initializes from stored state on wake.

## Open Questions

1. **Extension tech stack** — Is the current extension built with Manifest V3 or V2? What framework (vanilla JS, React, Svelte)? This determines how the send capability is integrated (new content scripts vs. extending existing ones).

2. **LinkedIn selector resilience** — Should we invest in a visual/AI-based approach (e.g., screenshot + OCR to find buttons) for long-term resilience, or is tiered DOM selector matching sufficient? The AI approach is more robust but adds complexity and latency.

3. **Account warmup data** — How do we determine if a LinkedIn account is "new" for warmup purposes? Options: (a) user self-reports account age in settings, (b) extension reads profile creation date from LinkedIn, (c) warmup starts from the moment the user first enables the send feature.

4. **Manual send counting** — The extension already tracks "messages sent" and "invites accepted" activity. Can we reliably distinguish manual sends from extension-triggered sends to avoid double-counting? Or should we count all sends regardless of source?

5. **Sales Navigator vs. regular LinkedIn** — The extension currently scrapes Sales Navigator. Does the send capability need to work within Sales Navigator pages, or only on regular LinkedIn (`linkedin.com/in/...`)? The DOM structure differs significantly between the two.

6. **Extension distribution** — Is the extension distributed via Chrome Web Store (public/unlisted) or side-loaded? This affects Manifest V3 compliance requirements and review policies around automated LinkedIn interaction.

7. **Multi-owner support** — If multiple team members use the extension on the same tenant, does each person's extension pull only their own queue (filtered by `owner_id`), or can a manager's extension process another owner's queue?

## Dependencies

- **Track A**: `linkedin_send_queue` table and extension API endpoints (`GET /api/extension/linkedin-queue`, `PATCH /api/extension/linkedin-queue/{id}`) must be built and deployed first
- **Existing Extension**: Current scraping + activity tracking codebase provides the foundation (host permissions, content script injection, authentication flow)
- **LinkedIn**: No API dependency — all interaction via browser DOM. LinkedIn's Terms of Service should be reviewed for automated messaging policies
- **Platform Auth**: Extension reuses JWT auth from the dashboard; token refresh flow must support extension context (no redirect-based refresh)

## Out of Scope

- InMail sending (premium LinkedIn feature, different UI flow and pricing model)
- LinkedIn group messaging
- LinkedIn post engagement (likes, comments, shares)
- Reply monitoring / conversation thread management (requires separate spec)
- Multi-account management (one LinkedIn account per browser profile)
- Sales Navigator-specific send flows (regular LinkedIn only for v1)
- Automated follow-up sequences (extension executes single actions; sequencing is platform-side)
- Mobile LinkedIn app integration

## Implementation Notes

### Phased Rollout

Given the risk profile (LinkedIn account bans), implementation should be phased:

**Phase 1 — Connection Requests Only**
- Implement queue consumer + connection request flow
- Conservative limits: 10/day default, no warmup override
- Manual pause only (no auto-resume)
- Validate with 2-3 test accounts over 2 weeks

**Phase 2 — Message Send**
- Add message typing simulation
- Add existing-thread detection
- Increase connection request limits to 15/day default

**Phase 3 — Full Automation**
- Warmup schedule
- Auto-resume after active hours
- Daily summary reporting
- Widget polish and settings panel

### LinkedIn DOM Interaction Patterns

Connection request flow (typical):
```
1. Navigate to linkedin.com/in/{username}
2. Wait for profile page load (detect name element)
3. Scroll down slightly (50-150px, random)
4. Wait 3-8 seconds (dwell time)
5. Find "Connect" button (tiered selectors)
   - If not found, check "More..." dropdown
   - If still not found, report connect_not_available
6. Click "Connect"
7. If note dialog appears:
   - Click "Add a note"
   - Wait 1-2 seconds
   - Type note with human-like timing
   - Click "Send"
8. If no note dialog (direct connect):
   - Click "Send" on the confirmation
9. Verify success (connection request pending indicator)
10. Report result to API
```

Message send flow (typical):
```
1. Navigate to linkedin.com/in/{username}
2. Wait for profile page load
3. Dwell 3-5 seconds
4. Click "Message" button
5. Wait for message compose overlay/page
6. Click into message input field
7. Type message with human-like timing (30-80ms/char, pauses)
8. Wait 1-3 seconds after finishing typing
9. Click "Send" button
10. Verify message appears in thread
11. Report result to API
```

### Rate Limiter Storage Schema

```json
{
  "rateLimits": {
    "config": {
      "dailyConnections": 15,
      "dailyMessages": 40,
      "weeklyConnections": 80,
      "warmupEnabled": true,
      "warmupStartDate": "2026-02-21",
      "activeHoursStart": "08:00",
      "activeHoursEnd": "19:00",
      "weekendEnabled": false
    },
    "counters": {
      "2026-02-21": {
        "connections": { "sent": 12, "failed": 1, "manual": 2 },
        "messages": { "sent": 28, "failed": 0, "manual": 5 }
      }
    },
    "weeklyCounters": {
      "2026-W08": {
        "connections": 58
      }
    },
    "safetyState": {
      "consecutiveFailures": 0,
      "paused": false,
      "pauseReason": null,
      "rollingAcceptanceRate": 0.45,
      "rollingWindow": []
    }
  }
}
```
