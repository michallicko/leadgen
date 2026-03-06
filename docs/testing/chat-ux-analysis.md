# Chat UX Analysis — Playbook Page (Staging)

**Date:** 2026-03-04
**Environment:** `https://leadgen-staging.visionvolve.com/visionvolve/playbook`
**User:** `test@staging.local` (super_admin, visionvolve namespace)

---

## 1. What the User Sees in the Chat

The Playbook page (`/visionvolve/playbook`) has a two-panel layout:
- **Left panel:** GTM Strategy contacts table (4,535 contacts with Name, Company, Job Title, Seniority, Score columns)
- **Right panel:** AI Chat embedded panel (heading "AI Chat", ~458px wide, ~698px tall)

The chat panel is composed of:
- **Header:** Green dot + "AI Chat" title. When streaming, shows a pulsing cyan status text (e.g., "Updating strategy...")
- **Message area:** Scrollable list of MessageBubble components with auto-scroll-to-bottom behavior
- **Input area:** Textarea with placeholder text (context-dependent: "Which contacts should we target?" on contacts phase)

### Current Chat State (visionvolve namespace)

The chat has a **massive history** — scrollHeight ~15,000px with ~568px viewport. This means the user must scroll through approximately 26 screens of content. The chat contains:

1. **Old thread messages** from previous sessions about Oscar Health strategy testing
2. Multiple "Strategy generation started..." placeholders (hidden onboarding trigger prompts)
3. Tool call cards (web_search, get_strategy_document, update_strategy_section) with green checkmarks and timings
4. AI responses mixed with research progress cards
5. **Three identical user messages:** "Hello, what can you help me with?" at 10:11, 10:14, and 10:55 AM — suggesting the user was confused about whether the chat was responding

### The "Strategy generation started..." Message

This message is a **hidden user message placeholder**. When the user triggers strategy generation through onboarding, the frontend sends a long prompt like:

```
Generate a complete GTM strategy playbook for my company (domain.com).
GTM objective: [description]. Primary challenge: [challenge].
Use the company research data provided in your context...
```

The `ChatMessages` component detects messages starting with "Generate a complete GTM strategy" (or messages with `extra.hidden = true`) and renders them as a condensed italic placeholder: "Strategy generation started..." instead of showing the full internal prompt text. This is correct behavior — the internal prompt should not leak into the UI.

### What Follows the Last "Strategy generation started..."

After the last trigger at the bottom of the chat history:

1. **"Strategy generation started..."** — italic placeholder for hidden onboarding prompt
2. **Tool call card group:** web_search (5.4s), web_search (5.0s), web_search (9.9s), get_strategy_document (3ms) — all with green checkmarks and "Expand all" link
3. **AI response bubble:** "Perfect. Your document is empty — I'm building it from scratch. Here's your complete GTM playbook:" (10:11 AM)
4. **User message:** "Hello, what can you help me with?" (10:11 AM)
5. **User message:** "Hello, what can you help me with?" (10:14 AM)
6. **User message:** "Hello, what can you help me with?" (10:55 AM)
7. (End of chat — no AI response to these messages visible)

---

## 2. Thinking Indicator Placement Analysis

### Current Implementation

The ThinkingIndicator is placed in the ChatMessages component **after all persisted messages** and **before in-flight tool calls and the streaming bubble**:

```
[persisted messages]
[ThinkingIndicator — shown when isThinking=true]
[In-flight ToolCallCardList]
[StreamingBubble]
```

File: `/Users/michal/git/leadgen-pipeline/frontend/src/components/chat/ChatMessages.tsx` (lines 445-456)

### Potential Issues

1. **ThinkingIndicator appears below all history:** Since messages are rendered first, then the indicator, it correctly appears at the bottom of the scrollable area. The auto-scroll (`scrollRef.current.scrollTop = scrollRef.current.scrollHeight`) should keep it visible. This placement is actually correct for the standard flow.

2. **Header-level status during streaming:** The PlaybookChat header (line 60-66 of PlaybookChat.tsx) shows `thinkingStatus` text only when `isStreaming` is true. During the initial "thinking" phase (before any chunks arrive), `isStreaming` may be true but `streamingText` empty — so the header shows the status while the ThinkingIndicator dot shows in the message area. This is a reasonable dual indicator.

3. **No dedicated thinking indicator visible in the screenshot:** In the current state (no active streaming), the chat just shows the last messages. The ThinkingIndicator only appears during active AI processing. There is no issue with placement per se — the indicator is conditional and correctly positioned at the bottom of the message stream.

4. **Potential gap:** Between sending a message and the ThinkingIndicator appearing, there could be a brief moment where nothing is shown (the user message appears, but no response indicator). This depends on how quickly the SSE connection establishes and sets `isThinking=true`.

---

## 3. Does Research Actually Scrape the Company Website?

**YES.** The research pipeline is implemented in `/Users/michal/git/leadgen-pipeline/api/services/research_service.py` and it performs a genuine three-step research process:

### Step 1: Website Fetch & Parse (`fetch_website()`)

- Fetches the company's homepage via HTTPS (with HTTP fallback)
- Parses HTML using BeautifulSoup to extract: title, meta description, visible body text, and internal links
- Finds and fetches up to 3 relevant subpages matching patterns: `/about`, `/team`, `/products`, `/services`, `/solutions`, etc.
- Combines all text from homepage + subpages into `all_text` (truncated to 6000 chars per page)
- Includes SSRF protection (rejects private IPs, localhost, link-local addresses)
- User-Agent: Chrome 131.0 on macOS

### Step 2: Perplexity Web Search (`run_web_search()`)

- Uses Perplexity `sonar-pro` model with the website content as context
- The search prompt includes the extracted website text as "ground truth"
- Asks Perplexity to find supplementary business intelligence: competitors, funding, news, hiring signals, revenue data, leadership team, tech stack, etc.
- Returns structured JSON with 25+ fields (industry, employees, revenue, competitors, etc.)
- Temperature: 0.2 (factual), max tokens: 1200, recency filter: "year"

### Step 3: AI Synthesis via Claude (`run_synthesis()`)

- Uses Anthropic `claude-sonnet-4-5-20250929` to synthesize website content + Perplexity search results
- Produces structured intelligence: executive brief, AI opportunities, pain hypothesis, quick wins, pitch framing, competitor analysis
- Temperature: 0.3, max tokens: 4000

### Step 4: Save to Database

- Updates the Company table (name, industry, size, revenue, HQ, etc.)
- Saves L1 enrichment (triage notes, pre-score, confidence)
- Saves L2 enrichment (company intel, AI opportunities, pain hypothesis, quick wins, pitch framing, revenue trend)
- Saves profile enrichment (key products, customer segments, competitors, tech stack, leadership team, certifications)
- Saves signal enrichment (digital initiatives, hiring signals, AI adoption level, growth indicators)
- Saves market enrichment (recent news, funding history)
- Sets company status to "enriched_l2" on success

### Important: This is NOT the n8n pipeline

The docstring at the top of `research_service.py` explicitly states:

> Replaces the L1 (Perplexity sonar) + L2 (Perplexity + Anthropic synthesis) two-step enrichment with a single, domain-first research pipeline

This is a **pure Python** implementation that runs in a background thread within the Flask API. It does NOT use n8n workflows for the Playbook's self-research flow. The n8n pipeline (Orchestrator workflow `N00qr21DCnGoh32D`) is still used for batch contact/company enrichment in the Radar module.

---

## 4. What the AI Has Access To When Generating Strategy

When the chat endpoint (`/api/playbook/chat`) processes a message, it builds a system prompt with the following data:

### System Prompt Construction (`build_system_prompt()`)

File: `/Users/michal/git/leadgen-pipeline/api/services/playbook_service.py` (line 478)

The system prompt is built from these data sources:

#### A. Base Instructions (always present)
- Critical rules: no negative language about companies, comprehensive writing, no filler phrases
- Role: "{company_name}'s fractional CMO" — sharp, concise, action-biased
- 7-section playbook structure (Executive Summary through 90-Day Action Plan)
- Research workflow instructions
- Document awareness rules (reference existing content, use tools to edit)
- Tool use mandates (must call `update_strategy_section`, never just describe changes)
- ICP Tiers & Buyer Personas tool instructions (`set_icp_tiers`, `set_buyer_personas`)
- Tone rules (extensive — never dismissive, always constructive)
- Response length limits (150 words default, 400 if user asks for detail)
- Style rules (brief, direct, no fluff, lead with recommendation)
- No internal reasoning in chat
- One question at a time

#### B. User's Stated Objective (if set)
- Comes from `document.objective`, set during onboarding

#### C. Existing Strategy Document Content
- Full markdown content of the current strategy document
- Section completeness analysis: each section marked as COMPLETE/PARTIAL/NEEDS WORK/EMPTY with word counts

#### D. Enrichment/Research Data (if available)
- Formatted by `_format_enrichment_for_prompt()` into labeled sections:
  - COMPANY PROFILE: name, industry, category, size, revenue, HQ
  - COMPANY OVERVIEW: company_intel, company_overview
  - PRODUCTS & TECHNOLOGY: key_products, tech_stack
  - MARKET & COMPETITION: customer_segments, competitors
  - PAIN POINTS & OPPORTUNITIES: pain_hypothesis, ai_opportunities, quick_wins
  - STRATEGIC POSITIONING: pitch_framing, revenue_trend
  - INDUSTRY CONTEXT: industry_pain_points
  - PROOF POINTS: relevant_case_study
  - SIGNALS: digital_initiatives, hiring_signals, ai_adoption_level, growth_indicators
  - NEWS & FUNDING: recent_news, funding_history

#### E. Research Wait Mechanism (Critical)
- **The chat endpoint waits up to 45 seconds** for research to complete before building the system prompt
- If research status is "in_progress", it polls every 2 seconds
- This ensures the AI has research data even when research was fired in parallel with the first chat message
- After 45 seconds, proceeds with partial data

#### F. Phase-Specific Instructions
- Appended based on current playbook phase (strategy, contacts, messages, campaigns, enrich, import)

#### G. Page-Context Hints
- If user is on a different page (contacts, companies, messages, campaigns), adds contextual hints

#### H. Language
- If tenant has a non-English language setting, instructions to respond in that language

### Available Tools During Chat

The AI has access to these tools via the agent executor:

1. **`get_strategy_document`** — Read current document content and extracted data
2. **`update_strategy_section`** — Replace content of a named H2 section
3. **`append_to_section`** — Append to a section without replacing
4. **`set_extracted_field`** — Set structured data in extracted_data JSONB
5. **`track_assumption`** — Record/update strategic assumptions
6. **`check_readiness`** — Evaluate phase transition readiness
7. **`set_icp_tiers`** — Set structured ICP tier definitions
8. **`set_buyer_personas`** — Set structured buyer persona definitions
9. **`web_search`** — Search the internet via Perplexity sonar API (max 3 per turn)

### The `web_search` Tool

File: `/Users/michal/git/leadgen-pipeline/api/services/search_tools.py`

- Uses Perplexity `sonar` model (not `sonar-pro` — lighter/cheaper than research)
- 10-second timeout, no retries
- Max query length: 500 chars
- Rate limited: 3 calls per turn (enforced by agent executor)
- Returns: `{answer, citations, summary}`
- Used for **ad-hoc research during chat** — different from the upfront domain-first research in research_service.py

---

## 5. Summary of Findings

### What Works Well
- The hidden onboarding prompt is correctly masked as "Strategy generation started..."
- Research pipeline genuinely fetches and scrapes the company website (homepage + subpages)
- Research data is comprehensive: website scraping + Perplexity business intelligence + Claude synthesis
- The 45-second wait mechanism ensures the AI has research data for the first response
- Tool call cards show execution status and timing (web_search 5.4s, etc.)
- Progress events from research are saved as chat messages with is_research_progress flag

### Potential Issues
1. **Massive chat history (15,000px):** The visionvolve namespace has an extremely long chat history from old testing sessions. New users would not see this, but for testing/demo purposes this is a poor experience. There is no "clear history" or "start new thread" button visible in the Playbook chat (though there is one in the global Cmd+K chat panel).

2. **Three unanswered "Hello" messages:** The user sent "Hello, what can you help me with?" three times (10:11, 10:14, 10:55) with no visible AI response. This could indicate:
   - The SSE streaming connection dropped or the API errored silently
   - The messages were sent but the AI response was lost
   - The chat scrolled but responses are hidden above the visible area

3. **Research fires in parallel with first chat message:** The onboarding flow (`handleOnboardGenerate`) fires `triggerResearch.mutate()` and `sendMessage()` simultaneously. The chat endpoint then waits up to 45 seconds for research to complete. During this wait, the user sees no feedback in the chat (the ThinkingIndicator would only appear once the SSE connection is established, which happens after the HTTP request is made — but the HTTP request itself is blocked waiting for research).

4. **No "New Thread" button in Playbook chat:** The global ChatPanel (Cmd+K) has a "Start new conversation" button, but the inline PlaybookChat does not expose this. Old messages accumulate indefinitely.

5. **Phase mismatch:** The page shows the "contacts" phase (contacts table + "Which contacts should we target?" placeholder) but the old chat messages are from the "strategy" phase. The chat thread spans phase transitions, which may confuse users.

---

## Screenshots

| File | Description |
|------|-------------|
| `docs/testing/chat-ux-screenshot.png` | Chat panel scrolled to last "Strategy generation started..." with tool calls and messages |
| `docs/testing/chat-ux-screenshot-viewport.png` | Default viewport when landing on Playbook page |
| `docs/testing/chat-ux-screenshot-top.png` | Chat scrolled to show top of visible thread |
| `docs/testing/chat-ux-screenshot-bottom.png` | Chat scrolled to bottom with latest user messages |
