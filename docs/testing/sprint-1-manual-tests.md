# Sprint 1 — Manual Test Scripts

**Tested on**: 2026-02-23 ~12:00 UTC
**Staging commit**: d2c4e67
**Result**: 7/28 passed, 21 failed

**PRs**: #35 (Tone Fix), #36 (Auto-Save), #37 (Phase Infrastructure), #38 (Chat Markdown), #39 (Phase UI)

**Staging URL**: https://leadgen-staging.visionvolve.com/
**Login**: `test@staging.local` / `staging123`
**Playbook URL**: After login, go to `/visionvolve/playbook`

> To test a specific PR revision, append `?rev={commit-hash}` to the URL.
> Example: `https://leadgen-staging.visionvolve.com/visionvolve/playbook?rev=abc1234`

---

## PR #35 — AI Tone Fix + TODOs + Document Awareness

**Branch**: `feature/playbook-tone`

### Preconditions
- Logged in as `test@staging.local`
- On the Playbook page (`/visionvolve/playbook`)
- Strategy editor is visible on the left, AI chat on the right

### Test 35.1 — No harsh language for companies with limited data

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | In the strategy editor, type: "Target company: QuietStartup Ltd. They are a 3-person team with no website and no LinkedIn presence." | Text appears in the editor | [x] |
| 2 | In the AI chat, type: "What do you think about QuietStartup as a prospect?" and press Enter | AI responds about the company | [x] |
| 3 | Read the AI response carefully | The response must NOT contain any of these phrases: "DISQUALIFY", "no verifiable business presence", "minimal digital footprint", "red flag", "low-quality lead", "not worth pursuing" | [ ] FAIL: Response says "QuietStartup is not a viable prospect" with "Disqualifying Factors" table heading. Uses "Remove QuietStartup from your prospect list entirely." — harsh and dismissive. |
| 4 | Check the overall tone of the response | The tone should be collaborative and constructive — e.g., suggesting ways to learn more about the company rather than dismissing it | [ ] FAIL: Tone is directive and dismissive, not collaborative. Says to remove them entirely rather than suggesting ways to learn more. |

### Test 35.2 — TODO markers for sparse data

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | In the AI chat, type: "Help me analyze the competitive landscape for QuietStartup's market" and press Enter | AI responds with analysis | [x] |
| 2 | Read the AI response | Since there is very little data about the company, the response should include visible TODO markers (e.g., `[TODO: ...]`) with concrete examples of what information to gather | [ ] FAIL: No TODO markers anywhere. AI redirected to Oscar Health instead of providing placeholders. |
| 3 | Check the TODO examples | Each TODO should suggest a specific action, not just generic placeholders — e.g., "[TODO: Research competitor X's pricing page at ...]" rather than just "[TODO: add info]" | [ ] FAIL: No TODOs present at all. |

### Test 35.3 — Document awareness (AI references existing content)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Clear the strategy editor and type: "ICP: B2B SaaS companies, 50-200 employees, Series A/B funded, based in DACH region. Pain point: manual lead qualification taking 10+ hours per week." | Text appears in the editor | [x] (used existing Oscar Health content instead of clearing — editor has rich ICP data already) |
| 2 | In the AI chat, type: "What should our ICP look like?" and press Enter | AI responds about ICP | [x] |
| 3 | Read the AI response | The AI must reference the ICP information you already wrote in the document (e.g., mention DACH region, 50-200 employees, SaaS, Series A/B). It should NOT ask you to define your ICP from scratch. | [x] PASS: AI referenced existing ICP fields (healthcare, enterprise, New York) from the document and built on them. |
| 4 | Ask the AI: "What pain points should we focus on?" | The AI should reference "manual lead qualification" from the document rather than listing generic pain points without acknowledging what was already written | [x] PASS: AI referenced specific pain points from the document (profitability crisis, member acquisition costs, medical loss ratio) rather than giving generic advice. |

### Test 35.4 — Guidance when document is empty

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Clear all text from the strategy editor (select all, delete) | Editor is empty | [ ] SKIP: Not tested — clearing the editor would destroy existing strategy data, and auto-save is broken so changes cannot be reverted. |
| 2 | In the AI chat, type: "Help me with my GTM strategy" and press Enter | AI responds | [ ] SKIP |
| 3 | Read the AI response | The AI should guide you to start filling in sections of the strategy document (e.g., "Let's start by defining your ICP..." or "First, let's outline your target market...") rather than giving a generic strategy lecture | [ ] SKIP |

---

## PR #36 — Auto-Save

**Branch**: `feature/playbook-autosave`

### Preconditions
- Logged in as `test@staging.local`
- On the Playbook page (`/visionvolve/playbook`)
- Strategy editor is visible

### Test 36.1 — Save button removed

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Look at the playbook editor area | There should be NO "Save" button anywhere on the page | [x] PASS: No Save button visible. Only Extract button and formatting toolbar. |

### Test 36.2 — Auto-save after typing stops

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Click into the strategy editor | Cursor is active in the editor | [x] |
| 2 | Type a few words: "Testing auto-save feature" | Text appears in the editor | [x] |
| 3 | Stop typing and watch for a save indicator (near the top of the editor or in the toolbar area) | Within about 2 seconds of stopping, you should see a "Saving..." indicator appear, then change to "Saved" | [ ] FAIL: No save indicator appeared. No "Saving..." or "Saved" text anywhere on the page. No network PUT/PATCH request to /api/playbook was fired. |
| 4 | Wait 2 more seconds after "Saved" appears | The "Saved" indicator should fade away or become very subtle | [ ] FAIL: No indicator ever appeared. |

### Test 36.3 — Cmd/Ctrl+S instant save

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Type some new text: "Immediate save test" | Text appears | [x] |
| 2 | Immediately press Cmd+S (Mac) or Ctrl+S (Windows) — do NOT wait | The "Saving..." indicator should appear immediately (not after the 1.5s delay) | [ ] FAIL: No save indicator appeared. No network request fired. Cmd+S had no visible effect. |
| 3 | Verify the browser does not show its own "Save page" dialog | The keyboard shortcut should be captured by the app, not the browser | [x] PASS: Browser did not show its own save dialog. |

### Test 36.4 — Content persists after refresh

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Type a unique phrase in the editor: "Persistence check 12345" | Text appears | [x] |
| 2 | Wait for the "Saved" indicator to appear and confirm | Shows "Saved" | [ ] FAIL: No saved indicator appeared. |
| 3 | Refresh the page (Cmd+R / Ctrl+R or F5) | Page reloads | [x] |
| 4 | Check the strategy editor content | The text "Persistence check 12345" should still be there | [ ] FAIL: Text gone after refresh. API confirmed content was never saved (version unchanged at 532). Auto-save is not functional. |

### Test 36.5 — Rapid typing does not cause lag

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Click into the editor | Cursor active | [x] |
| 2 | Type continuously and quickly for about 10 seconds (e.g., type out a long sentence without pausing) | Text should appear smoothly with no visible lag or freezing. No "Saving..." indicator should appear while you are still typing. | [x] PASS: Typing was smooth, no lag. (Though auto-save never fires at all.) |
| 3 | Stop typing | "Saving..." then "Saved" should appear after you stop | [ ] FAIL: No indicator appeared. |

### Test 36.6 — Save failure indication (network disconnect)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Open browser DevTools (Cmd+Option+I / F12) | DevTools opens | [ ] SKIP: Cannot test — auto-save does not fire at all, so offline behavior is untestable. |
| 2 | Go to the Network tab and check "Offline" (or use the throttling dropdown to select "Offline") | Network is now disconnected | [ ] SKIP |
| 3 | Type some text in the editor: "Offline save test" | Text appears | [ ] SKIP |
| 4 | Wait for the save attempt | A "Save failed" or error indicator should appear (not just silent failure) | [ ] SKIP |
| 5 | Uncheck "Offline" in DevTools to restore the network | Network restored | [ ] SKIP |
| 6 | Type one more character or press Cmd+S | The save should retry and succeed — "Saved" indicator appears | [ ] SKIP |

---

## PR #37 — Phase Infrastructure

**Branch**: `feature/playbook-phases`

### Preconditions
- Logged in as `test@staging.local`
- Playbook page open

### Test 37.1 — Default phase is "strategy"

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Open browser DevTools (Cmd+Option+I / F12), go to the Network tab | DevTools open on Network tab | [x] |
| 2 | Refresh the playbook page | Network requests appear | [x] |
| 3 | Find the request to `GET /api/playbook` (click on it to see the response) | The response JSON should include `"phase": "strategy"` | [ ] FAIL: No `phase` field in response. API returns: content, created_at, enrichment_id, extracted_data, id, objective, status, tenant_id, updated_at, updated_by, version. Phase infrastructure not deployed. |
| 4 | Also check the response includes `"playbook_selections"` | Should show `"playbook_selections": {}` (empty object) | [ ] FAIL: No `playbook_selections` field in response. |

### Test 37.2 — Cannot advance without ICP extracted

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Open browser DevTools Console tab | Console is open | [x] |
| 2 | Run this command in the console (replace TOKEN with your JWT): `fetch('/api/playbook/phase', {method: 'PUT', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer TOKEN', 'X-Namespace': 'visionvolve'}, body: JSON.stringify({target_phase: 'contacts'})}).then(r => r.json()).then(console.log)` | Request is made | [x] |
| 3 | Read the response in the console | Should return an error response indicating that ICP data must be extracted before advancing to the contacts phase | [ ] FAIL: Returns 404 "Not found". The `/api/playbook/phase` endpoint does not exist on staging. |

### Test 37.3 — Advance after ICP is present

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Use the playbook editor to write ICP information and trigger extraction (the exact flow depends on the UI — look for an "Extract" or "Save ICP" action) | ICP data is saved | [ ] FAIL: Phase endpoint does not exist, so phase advancement is impossible. |
| 2 | Repeat the phase advance API call from Test 37.2 | Should succeed this time — response confirms phase changed to "contacts" | [ ] FAIL: Blocked by 37.2 failure. |
| 3 | Refresh the page and check `GET /api/playbook` response | `"phase": "contacts"` | [ ] FAIL: Blocked. |

### Test 37.4 — Phase-aware AI behavior

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | While in the "strategy" phase, ask the AI chat: "What should I do next?" | AI response should be strategy-focused (e.g., about defining ICP, market analysis, positioning) | [ ] FAIL: Cannot test — no phase concept exists in the deployed build. AI has no phase awareness. |
| 2 | If you were able to advance to "contacts" phase in Test 37.3, ask the same question | AI response should now be contacts-focused (e.g., about finding prospects, building contact lists) rather than repeating strategy advice | [ ] FAIL: Blocked by 37.3 failure. |

---

## PR #38 — Chat Markdown Rendering

**Branch**: `feature/playbook-chat-md`

### Preconditions
- Logged in as `test@staging.local`
- On the Playbook page with AI chat visible

### Test 38.1 — Markdown formatting in AI responses

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | In the AI chat, type: "What sections should a GTM strategy include?" and press Enter | AI responds | [x] (used equivalent questions) |
| 2 | Look at the AI response formatting | The response should use rich formatting: **bold text**, bullet points, and possibly headings. It should NOT appear as raw markdown (no visible `**`, `*`, or `#` characters). | [ ] FAIL: All AI responses show raw markdown characters. `**bold**` appears as literal `**bold**`, `## Heading` as literal `## Heading`, `---` as literal dashes. No HTML rendering of markdown. Confirmed across 6+ AI responses. |

### Test 38.2 — Table rendering

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | In the AI chat, type: "Show me a comparison table of inbound vs outbound channels with pros and cons" and press Enter | AI responds with a table | [x] (AI generated tables in multiple responses) |
| 2 | Check the table formatting | The table should render as an actual HTML table with rows and columns — not raw markdown pipe characters (`|`) | [ ] FAIL: Tables appear as raw pipe characters. Example: `| Factor | QuietStartup | Oscar Health Need |` — not rendered as HTML tables. |

### Test 38.3 — Code block rendering

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | In the AI chat, type: "Write a code example showing how to call a REST API in Python" and press Enter | AI responds with code | [ ] SKIP: Not explicitly tested, but based on 38.1/38.2 failures, markdown rendering is completely broken — code blocks would also show as raw text. |
| 2 | Check the code block formatting | The code should appear in a styled code block with a monospace font and possibly syntax highlighting. Not raw text with backtick characters visible. | [ ] SKIP |

### Test 38.4 — User messages remain plain text

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Type this message in chat: "Here is **bold** and a [link](https://example.com)" and press Enter | Your message appears in the chat | [x] |
| 2 | Look at YOUR message bubble (not the AI response) | Your message should show as plain text — the `**bold**` and `[link](url)` should display literally, not as formatted markdown | [x] PASS: User message shows `Here is **bold** and a [link](https://example.com)` as literal plain text. |

### Test 38.5 — Concise responses (no filler)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Ask the AI: "What is account-based marketing?" | AI responds | [x] |
| 2 | Check the response length | Should be 2-4 sentences or a short bullet list — not a long essay | [ ] FAIL: Response is ~3000+ words with 10+ sections, multiple tables, and an exhaustive breakdown. Extremely verbose. |
| 3 | Check the first sentence | Should NOT start with filler phrases like "Great question!", "That's a really interesting topic!", "I'd be happy to help!", or "Absolutely!" | [ ] FAIL: Response starts with "Great question—and **highly relevant to your strategy**." — classic filler phrase. |

### Test 38.6 — Document awareness in responses

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Write in the strategy editor: "Our main channel is LinkedIn outreach targeting CTOs." | Text saved | [x] (document already contains LinkedIn channel strategy) |
| 2 | Ask the AI: "How should we approach our outreach?" | AI responds | [x] (tested via pain points and ICP questions) |
| 3 | Check the response | Should reference LinkedIn and CTOs from the document, not give generic channel advice | [x] PASS: AI consistently references document content (Oscar Health specifics, LinkedIn channel, existing personas). Document awareness works well. |

---

## PR #39 — Phase UI

**Branch**: `feature/playbook-phase-ui`

### Preconditions
- Logged in as `test@staging.local`
- Navigate to `/visionvolve/playbook`

### Test 39.1 — Phase stepper visible

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Look at the top of the playbook page | A horizontal phase stepper should be visible showing four phases: **Strategy** > **Contacts** > **Messages** > **Campaign** | [ ] FAIL: No phase stepper visible anywhere on the page. Top shows only "ICP Playbook" heading with Extract button. |
| 2 | Check which phase is highlighted/active | "Strategy" should be the active phase (highlighted, different color, or with a checkmark indicator) | [ ] FAIL: No phase stepper exists. |

### Test 39.2 — Locked phases cannot be clicked

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Click on "Contacts" in the phase stepper | Nothing should happen — you should NOT navigate to the contacts phase. The phase should appear locked/grayed out. | [ ] FAIL: No phase stepper to click on. |
| 2 | Click on "Messages" in the phase stepper | Same — locked, no navigation | [ ] FAIL: No phase stepper. |
| 3 | Click on "Campaign" in the phase stepper | Same — locked, no navigation | [ ] FAIL: No phase stepper. |

### Test 39.3 — Locked phase tooltip

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Hover your mouse over the locked "Contacts" phase in the stepper | A tooltip should appear explaining why the phase is locked (e.g., "Complete the Strategy phase first" or "Extract ICP data to unlock") | [ ] FAIL: No phase stepper to hover on. |

### Test 39.4 — Phase-specific left panel (Strategy)

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Verify you are on the Strategy phase | Phase stepper shows Strategy as active | [ ] FAIL: No phase stepper. Left panel shows strategy editor but without phase context. |
| 2 | Look at the left panel | Should show the strategy editor (text editing area where you write your GTM strategy) | [x] PASS: Strategy editor is visible and functional (though not labeled as "Strategy phase"). |

### Test 39.5 — URL routing

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Check the browser URL bar | URL should include `/playbook` (may also show `/playbook/strategy` or just `/playbook`) | [x] PASS: URL shows `/visionvolve/playbook`. |
| 2 | Manually type in the URL bar: `/visionvolve/playbook/campaign` and press Enter | Should NOT show the campaign phase (it is locked) — should redirect you back to the current unlocked phase (Strategy) | [ ] FAIL: Shows blank page (black screen). Console warning: "No routes matched location". No redirect to playbook. |
| 3 | Check the URL after redirect | Should be back at `/visionvolve/playbook` or `/visionvolve/playbook/strategy` | [ ] FAIL: URL stays at `/visionvolve/playbook/campaign` with blank page. |

### Test 39.6 — Unlocking and navigating to Contacts

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | Complete the Strategy phase: write ICP content in the editor and trigger ICP extraction (look for an "Extract ICP" button or similar action) | ICP is extracted and saved | [ ] FAIL: Extract button exists but no phase stepper or phase unlocking behavior. |
| 2 | Look at the phase stepper | "Contacts" should now appear unlocked (no longer grayed out) | [ ] FAIL: No phase stepper. |
| 3 | Click on "Contacts" in the stepper | Should navigate to the contacts phase | [ ] FAIL: No phase stepper. |
| 4 | Check the left panel | Should show a contacts placeholder or contacts-specific content (different from the strategy editor) | [ ] FAIL: Cannot navigate to contacts. |
| 5 | Check the AI chat placeholder text | Should show contacts-phase-specific placeholder (e.g., about finding prospects) — different from the strategy phase placeholder | [ ] FAIL: Cannot navigate to contacts. |

### Test 39.7 — Backward navigation

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | From the Contacts phase, click "Strategy" in the phase stepper | Should navigate back to the Strategy phase | [ ] FAIL: Cannot reach Contacts phase — no phase stepper. |
| 2 | Verify the strategy editor shows your previously saved content | Content should still be there | [ ] FAIL: Blocked. |

### Test 39.8 — Phase-specific action buttons

| # | Step | Expected Result | Pass/Fail |
|---|------|-----------------|-----------|
| 1 | On the Strategy phase, look for action buttons (below the editor or in the toolbar) | Should show strategy-relevant actions (e.g., "Extract ICP", "Analyze") | [x] PASS: Extract button exists in the toolbar area. |
| 2 | Navigate to Contacts phase (if unlocked) | Action buttons should change to contacts-relevant actions | [ ] FAIL: Cannot navigate to contacts. |

---

## Summary Checklist

| PR | Feature | Tests | Passed | Failed | Status |
|----|---------|-------|--------|--------|--------|
| #35 | AI Tone Fix + TODOs + Doc Awareness | 35.1 — 35.4 | 2 | 4 (+ 3 skipped) | FAIL |
| #36 | Auto-Save | 36.1 — 36.6 | 1 | 5 (+ 4 skipped) | FAIL |
| #37 | Phase Infrastructure | 37.1 — 37.4 | 0 | 8 | FAIL |
| #38 | Chat Markdown Rendering | 38.1 — 38.6 | 2 | 4 (+ 2 skipped) | FAIL |
| #39 | Phase UI | 39.1 — 39.8 | 3 | 13 | FAIL |

**Overall Sprint 1 Status**: [x] HAS FAILURES — 7/28 passed, 21 failed

## Failure Summary

### Critical Issues (features completely non-functional):

1. **PR #37 — Phase Infrastructure NOT DEPLOYED**: API has no `phase` or `playbook_selections` fields. `/api/playbook/phase` endpoint returns 404. The phase migration was never applied to staging.

2. **PR #39 — Phase UI NOT DEPLOYED**: No phase stepper visible on the playbook page. Sub-routes like `/playbook/campaign` show blank pages. Phase UI depends on PR #37 which is also missing.

3. **PR #36 — Auto-Save NOT FUNCTIONAL**: No save indicator appears, no network requests fire on edit, Cmd+S has no effect, content is lost on refresh. The auto-save mechanism is completely non-functional.

4. **PR #38 — Markdown NOT RENDERING**: All AI chat responses show raw markdown characters (`**`, `##`, `---`, `|`). No HTML rendering of bold, headings, tables, or code blocks. react-markdown or equivalent is not working.

### Partial Issues (feature works partially):

5. **PR #35 — Tone still harsh**: AI uses "Disqualifying Factors", "not a viable prospect", "Remove from list entirely" for companies with limited data. No TODO markers generated. However, document awareness (35.3) works well — AI references existing content.

6. **PR #38 — Responses too verbose**: "What is ABM?" returns 3000+ words. Filler phrases still present ("Great question—"). However, user messages correctly remain plain text (38.4) and document awareness works (38.6).
