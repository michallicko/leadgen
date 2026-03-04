# Sprint 9: Playbook UX Fixes + GTM Restructuring

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical playbook bugs (strategy generation, prompt leaks, editor), improve UX (markdown rendering, animations, navigation), and restructure the playbook from ICP-centric to GTM Strategy.

**Architecture:** 5 parallel tracks organized by file/component boundaries. Track 1 (backend orchestration) is the critical path — strategy generation and chat intelligence. Tracks 2-5 are frontend-heavy and fully parallel.

**Tech Stack:** Flask + SQLAlchemy (backend), React + TypeScript + TipTap (frontend), Claude API with tool use, SSE streaming, Playwright (E2E)

---

## Table of Contents

1. [Track 1 — Strategy Generation & Chat Intelligence](#track-1--strategy-generation--chat-intelligence)
2. [Track 2 — Onboarding Flow](#track-2--onboarding-flow)
3. [Track 3 — Strategy Editor & Rich Content](#track-3--strategy-editor--rich-content)
4. [Track 4 — Navigation & Naming](#track-4--navigation--naming)
5. [Track 5 — Playbook Restructuring](#track-5--playbook-restructuring)
6. [Dependency Map](#dependency-map)
7. [Testing Strategy](#testing-strategy)
8. [Sprint Sizing & Team Plan](#sprint-sizing--team-plan)

---

## Track 1 — Strategy Generation & Chat Intelligence

**Items:** BL-212, BL-110, BL-211, BL-202, BL-203
**Engineer(s):** 1-2 (backend-focused, one can split to BL-203 frontend)
**Critical path:** Yes — BL-212 fixes the core strategy generation flow.

### Task 1.1: BL-212 — Fix Strategy Generation + Animation

**Problem:** Strategy generation produces tiny, truncated content because of a 150-word system prompt limit and a 4096 max_tokens cap. The AI researches but then produces minimal output. No live animation shows progress during document writing.

**Files to modify:**
- `api/services/playbook_service.py` (line 415-416 — 150-word limit)
- `api/services/anthropic_client.py` (line 168 — max_tokens=4096)
- `api/services/agent_executor.py` (lines 133-360 — agentic loop, continuation logic)
- `api/routes/playbook_routes.py` (lines 1696-1830 — SSE generator)
- `frontend/src/providers/ChatProvider.tsx` (lines 226-327 — SSE event handling)
- `frontend/src/components/playbook/StrategyEditor.tsx` (lines 221-240 — content sync)

#### Step 1: Remove 150-word limit from system prompt

**File:** `api/services/playbook_service.py`
**Line:** 415-416

**Current code (line 415-416):**
```python
"2. MAXIMUM 150 words per response unless the user explicitly asks for "
"more detail. Use bullet points, not paragraphs.",
```

**Replace with:**
```python
"2. Write comprehensive, well-structured content. Use markdown formatting "
"with headers, bullet points, and tables where appropriate. Be thorough.",
```

**Test:** `make test-changed` — verify no tests depend on the "150 words" wording.

#### Step 2: Increase max_tokens from 4096 to 8192

**File:** `api/services/anthropic_client.py`
**Line:** 168

**Current code:**
```python
def query_with_tools(
    self,
    messages,
    system_prompt,
    tools,
    max_tokens=4096,
    ...
```

**Change:** `max_tokens=4096` -> `max_tokens=8192`

**Rationale:** 4096 output tokens is ~3000 words. A complete 9-section strategy with tables and bullet points can easily exceed this. 8192 gives enough room for all sections in a single turn.

#### Step 3: Add continuation logic for strategy generation

**File:** `api/services/agent_executor.py`
**After line 268** (after the "no tool calls, we're done" block)

The problem: After the AI finishes research tools (web_search), it sometimes returns with stop_reason="end_turn" but has NOT called `update_strategy_section`. The loop exits prematurely.

**Add a continuation check between the "no tool use" block and the "append assistant message" block.**

At the end of the `if stop_reason != "tool_use" or not tool_use_blocks:` block (line 242-268), before the `return` on line 268, insert logic:

```python
# Check if this is a strategy generation turn that hasn't written
# sections yet. If so, inject a follow-up nudge instead of returning.
strategy_tools_used = any(
    e.tool_name in ("update_strategy_section", "append_to_section")
    for e in tool_executions
)
research_tools_used = any(
    e.tool_name == "web_search" for e in tool_executions
)

if research_tools_used and not strategy_tools_used and iteration < 3:
    # AI researched but didn't write. Nudge it to proceed.
    nudge = (
        "You have completed your research. Now proceed to write the "
        "strategy sections. Call update_strategy_section for each of "
        "the 9 sections with specific, researched content. Start now."
    )
    if final_text:
        yield SSEEvent(type="chunk", data={"text": final_text})
    messages.append({"role": "assistant", "content": content_blocks})
    messages.append({"role": "user", "content": nudge})
    continue  # Re-enter the agentic loop
```

**Important:** This requires restructuring the `if` block so it doesn't `return` immediately. Wrap the existing return path inside an `else` clause or add the check before the return.

#### Step 4: Add SSE events for live section updates

**File:** `api/services/agent_executor.py`
**After tool_result SSE event** (line 344-356)

When a `update_strategy_section` or `append_to_section` tool completes successfully, emit an additional SSE event:

```python
# Emit section_update event for live document animation
if (
    tool_name in ("update_strategy_section", "append_to_section")
    and not exec_record.is_error
    and exec_record.output
):
    yield SSEEvent(
        type="section_update",
        data={
            "section": exec_record.output.get("section", ""),
            "content": exec_record.output.get("content_preview", ""),
            "action": "update" if tool_name == "update_strategy_section" else "append",
        },
    )
```

**File:** `api/routes/playbook_routes.py`
**In the `generate()` function** (line 1696-1830), add handling for the new event type:

After the `elif sse_event.type == "tool_result":` block (line 1721-1724), add:

```python
elif sse_event.type == "section_update":
    yield "data: {}\n\n".format(
        json.dumps(sse_event.data | {"type": "section_update"})
    )
```

#### Step 5: Frontend — Handle section_update SSE events

**File:** `frontend/src/providers/ChatProvider.tsx`

In the SSE event handler configuration (around line 225), the `sse.startStream()` call needs a new event handler. The SSE utility (`useSSE` hook or equivalent) needs to route `section_update` events.

Check how the SSE parser works — likely in `frontend/src/hooks/useSSE.ts` or `frontend/src/utils/sse.ts`. Add parsing for `type: "section_update"` events.

In `ChatProvider.tsx`, add a new state or callback:

```typescript
onSectionUpdate: (event) => {
  // Invalidate the strategy document query so StrategyEditor refreshes
  queryClient.invalidateQueries({ queryKey: ['strategy-document'] })
},
```

**File:** `frontend/src/components/playbook/StrategyEditor.tsx`

The existing content sync effect (lines 221-240) already handles server content changes via `lastServerContentRef`. When the strategy document query is invalidated, React Query will refetch, the `content` prop will update, and the `useEffect` will push it into TipTap. No additional changes needed here — the existing mechanism is correct.

**Optional enhancement:** Add a subtle typing cursor animation when content is being streamed. This can be a CSS class `animate-cursor-blink` on the editor wrapper when `isStreaming` is true.

#### Step 6: Verify and test

```bash
# Run unit tests for changed files
cd /Users/michal/git/leadgen-pipeline
make test-changed

# Manual test (requires make dev running):
# 1. Go to Playbook page
# 2. Trigger strategy generation via onboarding
# 3. Verify: AI researches (web_search calls visible)
# 4. Verify: AI writes sections (update_strategy_section calls visible)
# 5. Verify: Strategy editor shows content progressively
# 6. Verify: Final document has 9 complete sections with >150 words each
```

**Commit:**
```
feat(BL-212): fix strategy generation — remove 150-word limit, increase max_tokens, add continuation logic and live section updates
```

---

### Task 1.2: BL-110 — Agent Proactive Research

**Problem:** The AI jumps straight to writing sections without first presenting research findings. Users can't verify or guide the AI's understanding before it writes.

**Files to modify:**
- `api/services/playbook_service.py` (line 423-435 — system prompt assembly)

#### Step 1: Add "Research Phase" instruction to system prompt

**File:** `api/services/playbook_service.py`
**After line 435** (after the "reference specific sections" instruction)

Add a new instruction block:

```python
"",
"RESEARCH WORKFLOW — When asked to generate or update strategy sections:",
"1. RESEARCH PHASE: Use web_search to gather data about the company, "
"market, competitors, and industry trends. Present a brief summary "
"(3-5 bullet points) of key findings to the user.",
"2. WRITING PHASE: After research, proceed to write/update sections "
"using update_strategy_section. Reference specific findings.",
"3. VALIDATION: After writing, briefly summarize what you wrote and "
"ask if any sections need adjustment.",
"",
"When researching, form hypotheses first: 'Based on {domain}, I expect "
"to find...' then validate with web_search. This shows your reasoning.",
```

**Note:** This naturally pairs with BL-212's continuation logic. The AI will research first (triggering web_search), present findings (text output), then on the continuation nudge, proceed to write sections.

#### Step 2: Test

```bash
make test-changed

# Manual test:
# 1. Trigger strategy generation
# 2. Verify: AI first calls web_search 2-3 times
# 3. Verify: AI presents research findings as bullet points
# 4. Verify: AI then proceeds to write sections
```

**Commit:**
```
feat(BL-110): add research-first workflow to strategy generation system prompt
```

---

### Task 1.3: BL-211 — Token Cost Tracking Across All Turns

**Problem:** Token costs may not be accurately aggregated across all turns in the agentic loop. The `execute_agent_turn` generator accumulates tokens in `total_input_tokens` and `total_output_tokens`, but Perplexity (web_search) costs are logged separately in `search_tools.py:97-108` and may be double-counted or missed.

**Files to verify/modify:**
- `api/services/agent_executor.py` (lines 164-167, 218-227 — token accumulation)
- `api/services/search_tools.py` (lines 97-108 — Perplexity cost logging)
- `api/routes/playbook_routes.py` (lines 1778-1790 — final log_llm_usage call)
- `api/services/budget.py` (lines 81-97 — credit deduction)
- `api/services/llm_logger.py` — the `log_llm_usage` function

#### Step 1: Audit the current token flow

**Current flow:**
1. `agent_executor.py:164-167` initializes `total_input_tokens = 0`, `total_output_tokens = 0`
2. Each Claude API call (line 218-227) adds tokens from `response.usage`
3. `search_tools.py:97-108` calls `log_llm_usage` independently for Perplexity
4. `playbook_routes.py:1778-1790` calls `log_llm_usage` with the Claude totals

**Potential issue:** Perplexity costs are logged in step 3 AND the overall turn cost is logged in step 4, but they use different providers ("perplexity" vs the default Claude model). This is actually CORRECT — they are separate providers. The issue is whether the budget deduction double-counts.

#### Step 2: Verify budget deduction path

**File:** `api/services/llm_logger.py`

Read this file and check if `log_llm_usage` calls `consume_credits` from `budget.py`. If yes, confirm that both Claude and Perplexity calls go through the same credit consumption path.

**File:** `api/services/budget.py` (lines 81-97)

Verify `consume_credits` correctly deducts from the tenant's budget for each call.

#### Step 3: Add Perplexity token tracking to the agent turn summary

Currently, the `done` SSE event only includes Claude API tokens. Add Perplexity tokens too.

**File:** `api/services/agent_executor.py`

Add tracking for external tool costs. After each tool execution (line 332), check if the tool returned cost metadata:

```python
# Aggregate external tool costs (e.g., Perplexity search)
if exec_record.output and isinstance(exec_record.output, dict):
    ext_tokens = exec_record.output.get("_token_usage", {})
    if ext_tokens:
        # Track separately for transparency
        # These are already logged by the tool handler itself
        pass  # Cost tracking is handled per-tool — no double-count
```

Actually, the architecture is correct: Perplexity tokens are logged by `search_tools.py` directly, and Claude tokens are logged by `playbook_routes.py`. They use different `operation` values ("agent_web_search" vs "playbook_chat"). The budget system sums all operations per tenant.

**The fix needed:** Ensure the `done` event data includes a breakdown for the frontend to display:

```python
# In the done event data dict, add:
"external_tool_costs": [
    {
        "tool_name": e.tool_name,
        "provider": "perplexity" if e.tool_name == "web_search" else None,
    }
    for e in tool_executions
    if e.tool_name == "web_search" and not e.is_error
],
```

#### Step 4: Test

```bash
make test-changed

# Manual test:
# 1. Trigger strategy generation
# 2. Check LLM usage table: should have entries for both "playbook_chat" and "agent_web_search"
# 3. Check namespace budget: credits deducted for both Claude and Perplexity calls
# 4. No double-counting — each API call logged exactly once
```

**Commit:**
```
fix(BL-211): verify and document token cost tracking across agentic turns — no double-counting, add external cost metadata to done event
```

---

### Task 1.4: BL-202 — Chat Tracks Strategy Gaps

**Problem:** The chat agent doesn't know which strategy sections are empty or incomplete. It can't proactively guide the user to fill gaps.

**Files to modify:**
- `api/services/playbook_service.py` (system prompt assembly, after line 458)
- `api/services/strategy_tools.py` (line 26-36 — KNOWN_SECTIONS list)

#### Step 1: Add gap analysis to system prompt

**File:** `api/services/playbook_service.py`
**After line 458** (after the "End of Current Strategy" block)

Add a section completeness analysis:

```python
# Analyze section completeness for gap tracking
from .strategy_tools import KNOWN_SECTIONS

section_status = []
for section_name in KNOWN_SECTIONS:
    # Check if section heading exists in content
    heading_pattern = "## {}".format(section_name)
    if heading_pattern in content:
        # Find the section content between this heading and the next
        idx = content.index(heading_pattern)
        next_heading = content.find("\n## ", idx + len(heading_pattern))
        if next_heading == -1:
            section_content = content[idx + len(heading_pattern):]
        else:
            section_content = content[idx + len(heading_pattern):next_heading]

        # Count non-empty lines (excluding the heading itself)
        lines = [l.strip() for l in section_content.strip().split("\n") if l.strip()]
        word_count = sum(len(l.split()) for l in lines)

        if word_count < 20:
            section_status.append("- {} [NEEDS WORK — only {} words]".format(section_name, word_count))
        elif word_count < 80:
            section_status.append("- {} [PARTIAL — {} words]".format(section_name, word_count))
        else:
            section_status.append("- {} [COMPLETE — {} words]".format(section_name, word_count))
    else:
        section_status.append("- {} [EMPTY — not yet written]".format(section_name))

if section_status:
    parts.extend([
        "",
        "STRATEGY COMPLETENESS STATUS:",
        "\n".join(section_status),
        "",
        "Prioritize helping the user fill EMPTY and NEEDS WORK sections. "
        "When appropriate, proactively suggest: 'Your [section] section "
        "needs attention. Shall I draft it based on our research?'",
    ])
```

#### Step 2: Test

```bash
make test-changed

# Manual test:
# 1. Create a playbook with some empty sections
# 2. Open chat and type "What should I work on?"
# 3. Verify: AI references the empty/incomplete sections
# 4. Verify: AI suggests filling specific sections
```

**Commit:**
```
feat(BL-202): add strategy section gap analysis to chat system prompt — AI proactively guides users to fill empty sections
```

---

### Task 1.5: BL-203 — Context-Aware Chat Placeholder

**Problem:** The chat input always shows "Ask about your strategy..." regardless of what the user needs to do next.

**Files to modify:**
- `frontend/src/components/chat/ChatInput.tsx` (line 49 — default placeholder)
- `frontend/src/pages/playbook/PlaybookPage.tsx` (where ChatInput is used)
- `api/routes/playbook_routes.py` (add `chat_placeholder` to playbook state endpoint)

#### Step 1: Backend — Add chat_placeholder to playbook state

**File:** `api/routes/playbook_routes.py`

Find the endpoint that returns the strategy document state (likely a GET endpoint). Add a `chat_placeholder` field computed from document state:

```python
def _compute_placeholder(doc):
    """Derive chat placeholder from document state."""
    if not doc.content or not doc.content.strip():
        return "Describe your target market and GTM objective..."

    from .strategy_tools import KNOWN_SECTIONS
    content = doc.content or ""
    empty_sections = []
    for s in KNOWN_SECTIONS:
        if "## {}".format(s) not in content:
            empty_sections.append(s)

    if len(empty_sections) > 5:
        return "Tell the AI what to research about your market..."
    elif empty_sections:
        return "Ask about {} or refine your strategy...".format(empty_sections[0])
    else:
        return "Ask about your GTM strategy or request changes..."
```

Add `"chat_placeholder": _compute_placeholder(doc)` to the endpoint response.

#### Step 2: Frontend — Use dynamic placeholder

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx`

Where `ChatInput` (or `PlaybookChat`) is rendered, pass the `placeholder` prop from the document state query:

```typescript
<ChatInput
  onSend={sendMessage}
  isStreaming={isStreaming}
  placeholder={documentData?.chat_placeholder ?? 'Ask about your strategy...'}
/>
```

#### Step 3: Test

```bash
make test-changed

# Manual test:
# 1. New playbook (empty) → placeholder says "Describe your target market..."
# 2. After initial generation (some sections filled) → placeholder shows first empty section
# 3. Complete playbook → placeholder says "Ask about your GTM strategy..."
```

**Commit:**
```
feat(BL-203): context-aware chat placeholder — dynamically updates based on document completeness
```

---

## Track 2 — Onboarding Flow

**Items:** BL-208, BL-207, BL-206
**Engineer(s):** 1 (full-stack, frontend-leaning)
**Dependencies:** BL-206 benefits from BL-212's research integration but can start immediately.

### Task 2.1: BL-208 — Fix System Prompt Leak in Chat History

**Problem:** When onboarding triggers strategy generation, the crafted prompt (visible at `PlaybookPage.tsx:523-542`) is saved as a user message and displayed in the chat history. This exposes internal instructions to the user.

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (lines 523-542 — onboarding trigger message)
- `api/routes/playbook_routes.py` (lines 1436-1446 — message saving)
- `frontend/src/components/chat/ChatMessages.tsx` (line 191, 375 — system message filtering)

#### Step 1: Mark onboarding trigger as hidden

**Option A (preferred): Add a `hidden` flag to the message.**

**File:** `api/routes/playbook_routes.py`
In the chat endpoint where the user message is saved (lines 1437-1446), check if the message contains the onboarding trigger signature. If so, mark it as hidden:

```python
# Detect onboarding trigger messages (system-generated, not user-typed)
is_onboarding_trigger = message_text.startswith("Generate a complete GTM strategy")

user_msg = StrategyChatMessage(
    tenant_id=tenant_id,
    document_id=doc.id,
    role="user",
    content=message_text,
    page_context=page_context,
    created_by=user_id,
    extra={"hidden": True} if is_onboarding_trigger else None,
)
```

**File:** `frontend/src/components/chat/ChatMessages.tsx`

The filter at line 375 already excludes system messages:
```typescript
const displayMessages = messages.filter((m) => m.role !== 'system')
```

Extend it to also exclude hidden messages:
```typescript
const displayMessages = messages.filter(
  (m) => m.role !== 'system' && !m.extra?.hidden
)
```

**Option B (alternative): Send as role "system" instead of "user".**

In `PlaybookPage.tsx:523-542`, instead of calling `sendMessage()` (which creates a user message), call a dedicated `triggerGeneration()` function that sends the prompt as a system instruction, not a user message.

**Recommendation:** Use Option A — it's less invasive and the hidden flag is useful for other auto-triggered messages in the future.

#### Step 2: Show a friendly placeholder instead

After hiding the raw prompt, add a visible "Strategy generation started" system message:

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx` (line 542)

After `sendMessage(parts.join(' '))`, add an optimistic message:

```typescript
// Show a friendly message instead of the raw prompt
setOptimisticMessages([{
  id: 'onboarding-trigger',
  role: 'user',
  content: `Generate a GTM strategy for ${primaryDomain}. Objective: ${payload.description}`,
  created_at: new Date().toISOString(),
}])
```

Wait — this conflicts with the hidden flag approach. Better approach: the backend saves two messages — one hidden (the full prompt) and one visible (a summary). Or, simply truncate the displayed message.

**Simplest approach:** In `ChatMessages.tsx`, for messages with `extra.hidden`, show a condensed version:

```typescript
// In MessageBubble component (line 187)
if (message.extra?.hidden) {
  return (
    <div className="text-xs text-text-muted italic py-2">
      Strategy generation started...
    </div>
  )
}
```

#### Step 3: Test

```bash
make test-changed

# Manual test:
# 1. Go through onboarding flow
# 2. Submit GTM objective
# 3. Verify: Chat does NOT show the raw "Generate a complete GTM strategy..." prompt
# 4. Verify: Chat shows a friendly "Strategy generation started..." message
# 5. Verify: AI response still works correctly (the hidden message is still sent to the API)
```

**Commit:**
```
fix(BL-208): hide system prompt leak in chat — onboarding trigger messages marked hidden, show condensed summary instead
```

---

### Task 2.2: BL-207 — Editable Domain in Onboarding

**Problem:** The domain badge in onboarding is read-only. Users can't correct a wrong auto-detected domain.

**Files to modify:**
- `frontend/src/components/playbook/PlaybookOnboarding.tsx` (lines 57-93 — domain display)

#### Step 1: Replace static badge with editable input

**File:** `frontend/src/components/playbook/PlaybookOnboarding.tsx`

Replace the read-only domain display (lines 73-93) with an editable text input:

```typescript
// Add state for editable domain
const [domain, setDomain] = useState(tenant?.domain || '')

// In the JSX, replace the static badge:
{/* Auto-detected domain — editable */}
<div className="mb-4">
  <label htmlFor="pb-domain" className="block text-xs font-medium text-text-muted mb-1">
    Company domain
  </label>
  <div className="flex items-center gap-2">
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-accent-cyan flex-shrink-0"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
    <input
      id="pb-domain"
      type="text"
      value={domain}
      onChange={(e) => setDomain(e.target.value)}
      placeholder="yourcompany.com"
      className="flex-1 px-3 py-1.5 text-sm rounded-md bg-surface-alt border border-border-solid text-text focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20"
    />
  </div>
</div>
```

#### Step 2: Pass edited domain to onGenerate

**File:** `frontend/src/components/playbook/PlaybookOnboarding.tsx`

Update `handleSubmit` (line 42-55) to use the editable domain:

```typescript
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault()
  if (!isValid || isGenerating) return

  // Use the user-edited domain (or fallback to tenant domain)
  const primaryDomain = domain.trim() || tenant?.domain || ''
  const domains = primaryDomain ? [primaryDomain] : []

  onGenerate({
    domains,
    description: objective.trim(),
    challenge_type: 'auto',
  })
}
```

#### Step 3: Test

```bash
make test-changed

# Manual test:
# 1. Go to onboarding
# 2. Verify: domain field is pre-filled with tenant domain
# 3. Edit the domain to a different value
# 4. Submit → Verify: AI researches the edited domain, not the original
```

**Commit:**
```
feat(BL-207): make domain editable in onboarding — users can correct auto-detected domain before strategy generation
```

---

### Task 2.3: BL-206 — Auto-Research on Onboarding

**Problem:** Users have to wait for the chat to finish before any research happens. Background research should start immediately when they submit the onboarding form.

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (lines 518-548 — onboarding handler)
- `api/routes/playbook_routes.py` (add a background research endpoint)
- `api/services/research_service.py` (existing research service)

#### Step 1: Add background research trigger endpoint

**File:** `api/routes/playbook_routes.py`

Add a new endpoint that triggers background domain research:

```python
@bp.route("/strategy/research", methods=["POST"])
@require_auth
def trigger_research():
    """Trigger background research for a domain.

    Runs web searches and caches results so the chat agent
    has context before the user starts chatting.
    """
    tenant_id = request.tenant_id
    data = request.get_json() or {}
    domain = data.get("domain", "")

    if not domain:
        return jsonify({"error": "domain required"}), 400

    # Run research in the request context (not background thread)
    # This is fast enough for a synchronous call (~2-5 seconds)
    from .services.research_service import research_domain
    results = research_domain(tenant_id, domain)

    return jsonify({"status": "ok", "results": results})
```

**Note:** Check if `research_service.py` already has a `research_domain` function. If not, create one that wraps 2-3 Perplexity searches and caches results in `StrategyDocument.extracted_data` or a new cache field.

#### Step 2: Frontend — Fire research on onboarding submit

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx`

In the `handleGenerate` callback (around line 500), fire the research endpoint in parallel with the chat message:

```typescript
// Trigger background research immediately
const researchPromise = fetch(`/api/strategy/research`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Namespace': namespace,
  },
  body: JSON.stringify({ domain: primaryDomain }),
})

// Don't await — let it run in background while chat starts
researchPromise.catch((err) => console.warn('Background research failed:', err))

// Then send the chat message as before
sendMessage(parts.join(' '))
```

#### Step 3: Test

```bash
make test-changed

# Manual test:
# 1. Open network tab in browser
# 2. Submit onboarding form
# 3. Verify: Two requests fire — /api/strategy/research AND the SSE chat stream
# 4. Verify: Research endpoint completes in ~3-5 seconds
# 5. Verify: Chat agent benefits from cached research (faster section writing)
```

**Commit:**
```
feat(BL-206): auto-research on onboarding — triggers background domain research immediately on form submit
```

---

## Track 3 — Strategy Editor & Rich Content

**Items:** BL-205, BL-124, BL-209, BL-123
**Engineer(s):** 1 (frontend, TipTap expertise)
**Dependencies:** None — fully parallel with all other tracks.

### Task 3.1: BL-205 — Complex Object Selection & Deletion in TipTap

**Problem:** Tables and Mermaid diagrams in the TipTap editor can't be selected as a whole block or deleted easily. Backspace/Delete doesn't work on selected block nodes.

**Files to modify:**
- `frontend/src/components/playbook/StrategyEditor.tsx` (lines 178-209 — TipTap extensions)
- `frontend/src/components/playbook/MermaidBlock.tsx` (lines 176-257 — Mermaid NodeView)
- New file: `frontend/src/components/playbook/BlockToolbar.tsx` (hover toolbar component)

#### Step 1: Add node selection support to TipTap

**File:** `frontend/src/components/playbook/StrategyEditor.tsx`

The TipTap Table extension (line 188-193) already supports table functionality. Verify that `@tiptap/extension-table` allows node-level selection. If not, configure it:

```typescript
Table.configure({
  resizable: false,
  allowTableNodeSelection: true, // Enable whole-table selection
}),
```

#### Step 2: Add hover toolbar for complex blocks

**File:** Create `frontend/src/components/playbook/BlockToolbar.tsx`

```typescript
/**
 * Floating toolbar that appears when hovering over complex blocks
 * (tables, diagrams). Shows a delete button.
 */
import { useCallback } from 'react'
import type { Editor } from '@tiptap/react'

interface BlockToolbarProps {
  editor: Editor
  nodePos: number
  nodeSize: number
}

export function BlockToolbar({ editor, nodePos, nodeSize }: BlockToolbarProps) {
  const handleDelete = useCallback(() => {
    editor.chain().focus().deleteRange({ from: nodePos, to: nodePos + nodeSize }).run()
  }, [editor, nodePos, nodeSize])

  return (
    <div className="absolute -top-8 right-0 flex items-center gap-1 bg-surface border border-border-solid rounded-md shadow-sm px-1.5 py-0.5 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        type="button"
        onClick={handleDelete}
        className="p-1 text-text-muted hover:text-error rounded transition-colors"
        title="Delete block"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      </button>
    </div>
  )
}
```

#### Step 3: Wrap Mermaid NodeView with hover toolbar

**File:** `frontend/src/components/playbook/MermaidBlock.tsx` (line 216-257)

Add the `BlockToolbar` to the `MermaidNodeView` component. Wrap the `NodeViewWrapper` in a `group` div for hover detection:

```typescript
// In MermaidNodeView, add:
import { BlockToolbar } from './BlockToolbar'

// In the JSX:
<NodeViewWrapper className="mermaid-block my-4 rounded-lg border border-border-solid overflow-hidden bg-surface-alt/30 relative group">
  {isEditable && (
    <BlockToolbar
      editor={editor}
      nodePos={getPos()}
      nodeSize={node.nodeSize}
    />
  )}
  {/* ... existing content ... */}
</NodeViewWrapper>
```

#### Step 4: Handle Backspace/Delete on selected block nodes

TipTap should handle this natively when `allowTableNodeSelection` is true. Test and verify. If not working, add a keyboard handler:

**File:** `frontend/src/components/playbook/StrategyEditor.tsx`

Add a custom extension or keyboard shortcut handler:

```typescript
import { Extension } from '@tiptap/core'

const BlockDelete = Extension.create({
  name: 'blockDelete',
  addKeyboardShortcuts() {
    return {
      Backspace: ({ editor }) => {
        const { $from } = editor.state.selection
        if ($from.parent.type.name === 'table' || $from.parent.type.name === 'codeBlock') {
          return editor.commands.deleteSelection()
        }
        return false
      },
      Delete: ({ editor }) => {
        const { $from } = editor.state.selection
        if ($from.parent.type.name === 'table' || $from.parent.type.name === 'codeBlock') {
          return editor.commands.deleteSelection()
        }
        return false
      },
    }
  },
})
```

Add `BlockDelete` to the extensions array in `StrategyEditor.tsx:179`.

#### Step 5: Test

```bash
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Create a strategy with a table (via AI or manual markdown)
# 2. Click on the table → verify whole-table selection works
# 3. Press Backspace → verify table is deleted
# 4. Create a Mermaid diagram
# 5. Hover over diagram → verify trash icon appears
# 6. Click trash → verify diagram is deleted
```

**Commit:**
```
feat(BL-205): enable whole-block selection and deletion for tables and diagrams in strategy editor
```

---

### Task 3.2: BL-124 — Sticky Format Toolbar

**Problem:** The editor toolbar scrolls out of view when editing long documents.

**Files to modify:**
- `frontend/src/components/playbook/strategy-editor.css` (toolbar styles)
- `frontend/src/components/playbook/StrategyEditor.tsx` (line 244 — Toolbar wrapper)

#### Step 1: Make toolbar sticky

**File:** `frontend/src/components/playbook/StrategyEditor.tsx` (line 244)

Change the Toolbar wrapper:

```typescript
{editable && (
  <div className="sticky top-0 z-10 bg-surface border-b border-border-solid">
    <Toolbar editor={editor} />
  </div>
)}
```

**Or** in `strategy-editor.css`, add:

```css
.strategy-editor .toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border-solid);
}
```

#### Step 2: Test

```bash
# Manual test:
# 1. Open strategy editor with long content
# 2. Scroll down
# 3. Verify: toolbar stays visible at top
# 4. Verify: toolbar doesn't overlap with other sticky elements (nav, etc.)
```

**Commit:**
```
feat(BL-124): make strategy editor toolbar sticky — stays visible when scrolling long documents
```

---

### Task 3.3: BL-209 — Markdown Rendering in Tool Call Cards

**Problem:** Tool call result cards display raw markdown text instead of rendered markdown. Links, headers, bold text, and lists show as plain text.

**Files to modify:**
- `frontend/src/components/playbook/ToolCallCard.tsx` (lines 299-377 — FormattedValue, lines 379-423 — HumanFormattedDetail)
- `frontend/package.json` — verify `react-markdown` is a dependency

#### Step 1: Check react-markdown availability

`react-markdown` is already used in `ChatMessages.tsx` (confirmed by grep). No need to add it as a dependency.

#### Step 2: Add markdown detection and rendering to FormattedValue

**File:** `frontend/src/components/playbook/ToolCallCard.tsx`

In the `FormattedValue` component (line 300-377), modify the string rendering section (lines 313-316):

```typescript
// String — detect markdown and render appropriately
if (typeof value === 'string') {
  // Check if string contains markdown syntax
  const hasMarkdown = /[*_#\[\]`|>-]/.test(value) && value.length > 50

  if (hasMarkdown) {
    return (
      <div className="text-xs text-text-muted leading-relaxed prose prose-sm prose-invert max-w-none">
        <ReactMarkdown>{value}</ReactMarkdown>
      </div>
    )
  }

  return <p className="text-xs text-text-muted leading-relaxed m-0">{value}</p>
}
```

Add the import at the top of the file:
```typescript
import ReactMarkdown from 'react-markdown'
```

#### Step 3: Add markdown rendering to HumanFormattedDetail values

The `HumanFormattedDetail` component (line 379-423) delegates to `FormattedValue`, which now handles markdown. No additional changes needed in `HumanFormattedDetail` itself.

#### Step 4: Style the markdown within tool cards

Add CSS to ensure markdown renders well in the small card context:

```css
/* In the component or a shared CSS file */
.tool-card-markdown {
  font-size: 0.75rem;
  line-height: 1.5;
}
.tool-card-markdown h1,
.tool-card-markdown h2,
.tool-card-markdown h3 {
  font-size: 0.8rem;
  font-weight: 600;
  margin: 0.5em 0 0.25em;
}
.tool-card-markdown a {
  color: var(--color-accent-cyan);
  text-decoration: underline;
}
.tool-card-markdown ul,
.tool-card-markdown ol {
  padding-left: 1.25rem;
  margin: 0.25em 0;
}
```

#### Step 5: Test

```bash
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Trigger a web_search tool call (via chat)
# 2. Expand the tool call card
# 3. Verify: Links are clickable, headers are styled, bold text is bold
# 4. Verify: Short plain text strings are NOT processed as markdown
```

**Commit:**
```
feat(BL-209): render markdown in tool call cards — links, headers, lists, and formatted text display correctly
```

---

### Task 3.4: BL-123 — Mermaid Diagram Rendering

**Problem:** Mermaid diagrams may not render correctly or consistently in the strategy editor.

**Files to verify/modify:**
- `frontend/src/components/playbook/MermaidBlock.tsx` (lines 176-257 — already implemented)

#### Step 1: Audit current implementation

The `MermaidBlock.tsx` already has:
- `MermaidRenderer` component (renders SVG from mermaid code)
- `MermaidNodeView` component (NodeView with source/preview toggle)
- Source code editing toggle (lines 228-236)

**Check if mermaid library is properly initialized:**

Look for the mermaid initialization call (usually `mermaid.initialize()`). Verify it's called before any rendering attempts.

#### Step 2: Fix any rendering issues

Common issues:
1. **Theme mismatch:** Mermaid uses a light theme by default. Ensure dark theme configuration:
   ```typescript
   mermaid.initialize({
     theme: 'dark',
     themeVariables: {
       primaryColor: 'var(--color-accent)',
       primaryTextColor: 'var(--color-text)',
       lineColor: 'var(--color-border-solid)',
     },
   })
   ```

2. **Re-render on content change:** If the mermaid code changes but the diagram doesn't update, add a `key` prop or force re-render:
   ```typescript
   <MermaidRenderer key={code} code={code} ... />
   ```

3. **Error handling:** If mermaid syntax is invalid, show the error message instead of a blank block. Check if `MermaidRenderer` has error handling.

#### Step 3: Test

```bash
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Add a mermaid code block to the strategy editor
# 2. Verify: Diagram renders as SVG
# 3. Toggle "Source" button → verify code is editable
# 4. Toggle "Preview" → verify diagram updates
# 5. Enter invalid mermaid syntax → verify error message shows (not blank)
```

**Commit:**
```
fix(BL-123): verify and fix mermaid diagram rendering — ensure dark theme, error handling, and content re-rendering
```

---

## Track 4 — Navigation & Naming

**Items:** BL-197, BL-125, BL-112
**Engineer(s):** 1 (frontend, UI)
**Dependencies:** None — fully parallel.

### Task 4.1: BL-197 — Rename "ICP Playbook" to "GTM Strategy"

**Problem:** The app still uses "ICP Playbook" naming, but the product has evolved to a broader GTM Strategy tool.

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (line 676 — `ICP Playbook`)
- `frontend/src/components/layout/AppNav.tsx` (line 36, 42 — `Playbook` / `ICP Summary`)
- `frontend/src/pages/playbook/PlaybookPage.tsx` (line 99 — `Extract ICP` button label)
- Global search for other occurrences

#### Step 1: Search for all occurrences

```bash
cd /Users/michal/git/leadgen-pipeline
grep -rn "ICP Playbook\|ICP Summary\|playbook.*label\|Playbook.*label" frontend/src/ --include="*.tsx" --include="*.ts"
```

#### Step 2: Rename in PlaybookPage.tsx

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx`
**Line 676:**
```typescript
// Change:
ICP Playbook
// To:
GTM Strategy
```

**Line 99:**
```typescript
// Change:
strategy: { label: 'Extract ICP', pendingLabel: 'Extracting...' },
// To:
strategy: { label: 'Analyze Market', pendingLabel: 'Analyzing...' },
```

#### Step 3: Rename in AppNav.tsx

**File:** `frontend/src/components/layout/AppNav.tsx`
**Line 36:**
```typescript
// Change:
label: 'Playbook',
// To:
label: 'GTM Strategy',
```

**Line 42:**
```typescript
// Change:
pages: [{ id: 'playbook', label: 'ICP Summary', path: 'playbook', minRole: 'viewer' }],
// To:
pages: [{ id: 'playbook', label: 'Strategy Overview', path: 'playbook', minRole: 'viewer' }],
```

**Note:** Keep `path: 'playbook'` unchanged — URL paths should stay stable to avoid breaking bookmarks.

#### Step 4: Search for remaining references

```bash
grep -rn "ICP" frontend/src/ --include="*.tsx" --include="*.ts" | grep -v "node_modules" | grep -iv "import\|type\|interface"
```

Update any user-visible strings that say "ICP" to use "GTM Strategy" or "Ideal Customer Profile" (the full name) depending on context.

#### Step 5: Test

```bash
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Check sidebar nav → should show "GTM Strategy"
# 2. Click into playbook page → header should say "GTM Strategy"
# 3. Check page title in browser tab
# 4. Verify no broken references
```

**Commit:**
```
refactor(BL-197): rename ICP Playbook to GTM Strategy throughout the frontend
```

---

### Task 4.2: BL-125 — Consistent Top Navigation

**Problem:** The gear dropdown and user menu in AppNav are not logically organized.

**Files to modify:**
- `frontend/src/components/layout/AppNav.tsx`

#### Step 1: Audit current nav structure

Read `AppNav.tsx` fully to understand the current dropdown structure.

#### Step 2: Restructure dropdowns

Group menu items logically:

**User dropdown (avatar/name):**
1. Profile / Account
2. Credits & Usage (BL-112 — see below)
3. ---
4. Sign Out

**Settings dropdown (gear icon):**
1. Team Members (namespace admin only)
2. API Keys (namespace admin only)
3. ---
4. Admin Panel (super_admin only)

#### Step 3: Test

```bash
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Click user avatar → verify dropdown items
# 2. Click gear icon → verify dropdown items
# 3. As viewer role → verify admin-only items are hidden
# 4. As namespace admin → verify correct items show
```

**Commit:**
```
refactor(BL-125): reorganize top navigation dropdowns — logical grouping of user and settings menus
```

---

### Task 4.3: BL-112 — Credits Link in User Dropdown

**Problem:** Users can't easily find the credits/usage page.

**Files to modify:**
- `frontend/src/components/layout/AppNav.tsx` (user dropdown)

#### Step 1: Add Credits link

**File:** `frontend/src/components/layout/AppNav.tsx`

In the user dropdown menu, add a "Credits & Usage" item:

```typescript
<DropdownItem
  onClick={() => navigate(`/${namespace}/credits`)}
  icon={<CoinIcon />}
>
  Credits & Usage
</DropdownItem>
```

If there's no dedicated credits page yet, link to whatever existing page shows token usage.

#### Step 2: Test

```bash
# Manual test:
# 1. Click user avatar
# 2. Verify "Credits & Usage" link is visible
# 3. Click it → verify it navigates to the correct page
```

**Commit:**
```
feat(BL-112): add Credits & Usage link to user dropdown menu
```

---

## Track 5 — Playbook Restructuring

**Items:** BL-198, BL-199, BL-201
**Engineer(s):** 1-2 (full-stack, data modeling + React)
**Dependencies:** BL-201 depends on BL-198.

### Task 5.1: BL-198 — ICP Tiers Tab

**Problem:** ICP tier definitions are buried in the strategy document as freeform text. They need a structured, dedicated tab for easy editing and AI extraction.

**Files to modify:**
- `api/models.py` (new model or use `extracted_data` JSONB field)
- `api/routes/playbook_routes.py` (new endpoints for tiers CRUD)
- `frontend/src/pages/playbook/PlaybookPage.tsx` (add tab navigation)
- New file: `frontend/src/components/playbook/IcpTiersTab.tsx`

#### Step 1: Design the data model

**Option A (preferred): Use `StrategyDocument.extracted_data` JSONB field.**

The `extracted_data` field already stores structured ICP data (see `strategy_tools.py:39-50`). Add a `tiers` key:

```python
# In extracted_data:
{
  "icp": { "industries": [...], ... },
  "tiers": [
    {
      "id": "tier-1",
      "name": "Tier 1 - Platinum",
      "description": "Enterprise SaaS companies with 500+ employees...",
      "criteria": [
        { "field": "employees", "operator": ">=", "value": "500" },
        { "field": "industry", "operator": "in", "value": ["SaaS", "Enterprise Software"] },
      ],
      "fit_score_min": 80,
      "fit_score_max": 100,
    },
    // ... more tiers
  ],
}
```

**Option B: New model (ICPTier).**

Only use this if tiers need their own versioning, audit trail, or relationships. For Sprint 9, Option A is simpler.

#### Step 2: Backend — Add tier CRUD endpoints

**File:** `api/routes/playbook_routes.py`

```python
@bp.route("/strategy/tiers", methods=["GET"])
@require_auth
def get_tiers():
    """Get ICP tier definitions."""
    tenant_id = request.tenant_id
    doc = _get_or_create_document(tenant_id)
    tiers = (doc.extracted_data or {}).get("tiers", [])
    return jsonify({"tiers": tiers})


@bp.route("/strategy/tiers", methods=["PUT"])
@require_auth
def update_tiers():
    """Update ICP tier definitions."""
    tenant_id = request.tenant_id
    data = request.get_json() or {}
    tiers = data.get("tiers", [])

    doc = _get_or_create_document(tenant_id)
    extracted = doc.extracted_data or {}
    extracted["tiers"] = tiers
    doc.extracted_data = extracted
    db.session.commit()

    return jsonify({"status": "ok", "tiers": tiers})
```

#### Step 3: Frontend — Add tab navigation to PlaybookPage

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx`

Add tab navigation below the header (after line 677):

```typescript
const [activeTab, setActiveTab] = useState<'strategy' | 'tiers' | 'personas'>('strategy')

// In JSX, after the header:
<div className="flex gap-1 border-b border-border-solid mb-3">
  <TabButton active={activeTab === 'strategy'} onClick={() => setActiveTab('strategy')}>
    Strategy Document
  </TabButton>
  <TabButton active={activeTab === 'tiers'} onClick={() => setActiveTab('tiers')}>
    ICP Tiers
  </TabButton>
  <TabButton active={activeTab === 'personas'} onClick={() => setActiveTab('personas')}>
    Buyer Personas
  </TabButton>
</div>

{/* Tab content */}
{activeTab === 'strategy' && (
  <StrategyEditor ... />
)}
{activeTab === 'tiers' && (
  <IcpTiersTab tenantId={tenantId} />
)}
{activeTab === 'personas' && (
  <BuyerPersonasTab tenantId={tenantId} />
)}
```

#### Step 4: Frontend — Create IcpTiersTab component

**File:** Create `frontend/src/components/playbook/IcpTiersTab.tsx`

```typescript
/**
 * ICP Tiers Tab — structured tier definitions with inline editing.
 * Tiers are stored in StrategyDocument.extracted_data.tiers
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../utils/api'

interface TierCriterion {
  field: string
  operator: string
  value: string
}

interface IcpTier {
  id: string
  name: string
  description: string
  criteria: TierCriterion[]
  fit_score_min: number
  fit_score_max: number
}

export function IcpTiersTab({ tenantId }: { tenantId: string }) {
  // Fetch tiers from API
  const { data, isLoading } = useQuery({
    queryKey: ['icp-tiers', tenantId],
    queryFn: () => api.get('/strategy/tiers'),
  })

  const tiers: IcpTier[] = data?.tiers || []

  // ... render tier cards with inline editing
  // Each tier is a card with:
  // - Name (editable heading)
  // - Description (editable textarea)
  // - Criteria list (add/remove rows)
  // - Fit score range slider
  // - Delete button

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">ICP Tiers</h2>
        <button className="btn btn-sm btn-primary">Add Tier</button>
      </div>

      {isLoading ? (
        <div className="text-text-muted text-sm">Loading tiers...</div>
      ) : tiers.length === 0 ? (
        <EmptyState />
      ) : (
        tiers.map((tier) => <TierCard key={tier.id} tier={tier} />)
      )}
    </div>
  )
}
```

#### Step 5: AI auto-extraction of tiers

Add a tool in `strategy_tools.py` that the AI can call to set tier data:

```python
# In strategy_tools.py, add to the TOOL_DEFINITIONS list:
ToolDefinition(
    name="set_icp_tiers",
    description="Set structured ICP tier definitions from strategy analysis.",
    input_schema={
        "type": "object",
        "properties": {
            "tiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "criteria": {"type": "array"},
                        "fit_score_min": {"type": "number"},
                        "fit_score_max": {"type": "number"},
                    },
                },
            },
        },
        "required": ["tiers"],
    },
    handler=set_icp_tiers,
)
```

#### Step 6: Test

```bash
make test-changed
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Go to playbook page → verify tabs appear (Strategy Document, ICP Tiers, Buyer Personas)
# 2. Click "ICP Tiers" tab → verify empty state or existing tiers display
# 3. Click "Add Tier" → verify inline form appears
# 4. Edit tier name, description, criteria → verify changes save
# 5. Ask AI to "extract ICP tiers from the strategy" → verify AI uses set_icp_tiers tool
```

**Commit:**
```
feat(BL-198): add ICP Tiers tab — structured tier definitions with inline editing and AI extraction
```

---

### Task 5.2: BL-199 — Buyer Personas Tab

**Problem:** Buyer personas are scattered in the strategy document text. They need a dedicated, structured tab.

**Files to modify:**
- `api/routes/playbook_routes.py` (personas CRUD endpoints)
- `api/services/strategy_tools.py` (AI persona extraction tool)
- New file: `frontend/src/components/playbook/BuyerPersonasTab.tsx`

#### Step 1: Design data structure

**In `StrategyDocument.extracted_data`:**

```python
{
  "personas": [
    {
      "id": "persona-1",
      "name": "The Technical Buyer",
      "role_title": "CTO / VP Engineering",
      "pain_points": ["Legacy system integration", "Team scalability"],
      "goals": ["Reduce technical debt", "Ship faster"],
      "preferred_channels": ["LinkedIn", "Technical blogs"],
      "messaging_hooks": ["ROI on engineering time", "Case studies from similar stack"],
      "tier_ids": ["tier-1", "tier-2"],  # linked to ICP tiers
    },
  ],
}
```

#### Step 2: Backend endpoints

**File:** `api/routes/playbook_routes.py`

```python
@bp.route("/strategy/personas", methods=["GET"])
@require_auth
def get_personas():
    tenant_id = request.tenant_id
    doc = _get_or_create_document(tenant_id)
    personas = (doc.extracted_data or {}).get("personas", [])
    return jsonify({"personas": personas})


@bp.route("/strategy/personas", methods=["PUT"])
@require_auth
def update_personas():
    tenant_id = request.tenant_id
    data = request.get_json() or {}
    personas = data.get("personas", [])

    doc = _get_or_create_document(tenant_id)
    extracted = doc.extracted_data or {}
    extracted["personas"] = personas
    doc.extracted_data = extracted
    db.session.commit()

    return jsonify({"status": "ok", "personas": personas})
```

#### Step 3: Frontend — BuyerPersonasTab component

**File:** Create `frontend/src/components/playbook/BuyerPersonasTab.tsx`

Each persona renders as a card with:
- Avatar/icon (derived from role)
- Name + Role/Title (editable)
- Pain Points (tag list, editable)
- Goals (tag list, editable)
- Preferred Channels (checkbox group)
- Messaging Hooks (bullet list, editable)
- Linked ICP Tiers (multi-select)

#### Step 4: AI persona generation tool

**File:** `api/services/strategy_tools.py`

```python
def set_buyer_personas(args: dict, ctx: ToolContext) -> dict:
    """Handler for set_buyer_personas tool."""
    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "no document found"}

    personas = args.get("personas", [])

    # Validate and assign IDs
    for i, p in enumerate(personas):
        if not p.get("id"):
            p["id"] = "persona-{}".format(i + 1)

    extracted = doc.extracted_data or {}
    extracted["personas"] = personas
    doc.extracted_data = extracted

    _bump_version(doc)
    db.session.commit()

    return {"status": "ok", "count": len(personas)}
```

Register as a tool definition with appropriate schema.

#### Step 5: Test

```bash
make test-changed
cd /Users/michal/git/leadgen-pipeline/frontend && npx tsc --noEmit

# Manual test:
# 1. Click "Buyer Personas" tab → verify empty state
# 2. Ask AI "Generate buyer personas based on my strategy" → verify persona cards populate
# 3. Edit a persona → verify changes save
# 4. Add/remove a persona → verify CRUD works
```

**Commit:**
```
feat(BL-199): add Buyer Personas tab — structured persona cards with AI generation and inline editing
```

---

### Task 5.3: BL-201 — Remove "Extract ICP" Button / Continuous Extraction

**Problem:** The manual "Extract ICP" button (line 99) is a user friction point. ICP extraction should happen automatically as the strategy document is updated.

**Files to modify:**
- `frontend/src/pages/playbook/PlaybookPage.tsx` (line 99 — remove Extract ICP)
- `api/routes/playbook_routes.py` (add auto-extraction trigger on document save)
- `api/services/strategy_tools.py` (extraction logic)

**Dependencies:** Requires BL-198 (tier structure exists to extract into).

#### Step 1: Remove the Extract ICP button

**File:** `frontend/src/pages/playbook/PlaybookPage.tsx`

**Line 99:**
```typescript
// Remove or replace:
strategy: { label: 'Extract ICP', pendingLabel: 'Extracting...' },
// With:
strategy: { label: 'Review Strategy', pendingLabel: 'Loading...' },
```

If the button triggers extraction, replace its handler with a simpler action (e.g., scroll to ICP tiers tab or trigger a document review).

#### Step 2: Add auto-extraction on document save

**File:** `api/routes/playbook_routes.py`

In the strategy document save endpoint, add a background extraction trigger:

```python
# After document content is saved:
def _trigger_auto_extraction(doc_id, tenant_id):
    """Extract structured data from strategy document content.

    Called asynchronously after document saves. Uses the AI to extract
    tiers, personas, and ICP criteria from freeform strategy text.
    """
    # This could be a celery task or a simple synchronous extraction
    # For Sprint 9, start with synchronous (fast enough for current doc sizes)
    doc = StrategyDocument.query.get(doc_id)
    if not doc or not doc.content:
        return

    # Simple regex-based extraction for tiers
    # (AI-based extraction is already handled by set_icp_tiers tool)
    # Here we detect if the content mentions tiers but extracted_data is empty
    content = doc.content or ""
    extracted = doc.extracted_data or {}

    if "Tier" in content and not extracted.get("tiers"):
        # Flag for AI extraction on next chat interaction
        extracted["_needs_tier_extraction"] = True
        doc.extracted_data = extracted
        db.session.commit()
```

#### Step 3: Update system prompt to trigger extraction proactively

**File:** `api/services/playbook_service.py`

In the system prompt assembly, check for the extraction flag:

```python
# Check if auto-extraction is needed
extracted = document.extracted_data or {}
if extracted.get("_needs_tier_extraction"):
    parts.extend([
        "",
        "IMPORTANT: The strategy document mentions ICP tiers but they haven't "
        "been extracted into structured format yet. When appropriate, call "
        "set_icp_tiers to extract tier definitions from the document content.",
    ])
```

#### Step 4: Test

```bash
make test-changed

# Manual test:
# 1. Verify "Extract ICP" button is removed from playbook page
# 2. Write strategy content that mentions tiers
# 3. Save the document
# 4. Open chat → verify AI proactively extracts tiers
# 5. Check ICP Tiers tab → verify tiers populated
```

**Commit:**
```
feat(BL-201): remove manual Extract ICP button — continuous auto-extraction of tiers and personas from strategy content
```

---

## Dependency Map

```
Track 1 (BL-212 — Strategy Gen Fix)
  └──→ Track 2 (BL-206 uses improved research from BL-212)
  └──→ Track 1 (BL-110 builds on BL-212's system prompt changes)

Track 1 (BL-203 — Context Placeholders)
  └──→ Track 5 (context-aware prompts need tab structure from BL-198)

Track 3 (BL-205, BL-124, BL-209, BL-123) — NO dependencies, fully parallel

Track 4 (BL-197, BL-125, BL-112) — NO dependencies, fully parallel

Track 5:
  BL-198 (ICP Tiers) — can start immediately
  BL-199 (Buyer Personas) — can start immediately (parallel with BL-198)
  BL-201 (Remove Extract ICP) — depends on BL-198 (needs tier structure to extract into)
```

### Execution Order

```
PARALLEL START:
├── Track 1: BL-212 → BL-110 → BL-211 → BL-202 → BL-203
├── Track 2: BL-208 → BL-207 → BL-206 (BL-206 waits for BL-212 research service)
├── Track 3: BL-205 + BL-124 + BL-209 + BL-123 (all parallel within track)
├── Track 4: BL-197 + BL-125 + BL-112 (all parallel within track)
└── Track 5: BL-198 + BL-199 → BL-201

SERIAL DEPENDENCIES:
1. BL-212 must complete before BL-110 (same file: system prompt)
2. BL-212 must complete before BL-206 (research service integration)
3. BL-198 must complete before BL-201 (tier structure needed)
4. BL-203 frontend should sync with BL-198 tab structure
```

---

## Testing Strategy

### Unit Tests (per track)

```bash
# Track 1 — Backend changes
make test-changed   # Tests touching playbook_service, agent_executor, anthropic_client

# Track 2 — Onboarding
make test-changed   # Tests for playbook_routes onboarding endpoints

# Track 3 — Frontend only
cd frontend && npx tsc --noEmit   # TypeScript check

# Track 4 — Frontend only
cd frontend && npx tsc --noEmit

# Track 5 — Full-stack
make test-changed   # Tests for new tier/persona endpoints
cd frontend && npx tsc --noEmit
```

### Integration Tests (after all tracks merge)

```bash
make test           # Full unit test suite
cd frontend && npm run lint  # ESLint
```

### E2E Tests (sprint completion)

After all PRs merge to staging:
```bash
make test-e2e       # Full Playwright suite against staging
```

### Manual Test Script

Create `docs/testing/sprint-9-manual-tests.md` with:
1. Strategy generation produces 9 complete sections (BL-212)
2. AI researches before writing (BL-110)
3. System prompt not visible in chat (BL-208)
4. Domain editable in onboarding (BL-207)
5. Tool call cards render markdown (BL-209)
6. Tables/diagrams deletable in editor (BL-205)
7. Toolbar stays visible on scroll (BL-124)
8. Navigation says "GTM Strategy" (BL-197)
9. Credits link in user menu (BL-112)
10. ICP Tiers tab works (BL-198)
11. Buyer Personas tab works (BL-199)
12. No "Extract ICP" button (BL-201)

---

## Sprint Sizing & Team Plan

| Role | Agent Count | Responsibility |
|------|-------------|---------------|
| **PM** | 1 | Scope validation, acceptance criteria review |
| **EM** | 1 | Architecture review, code review on all PRs |
| **PD** | 1 | UX review of Tracks 2-5, consistency check |
| **QA** | 1 | Sprint E2E tests, staging verification |
| **Engineer 1** | 1 | Track 1 (backend-heavy, critical path) |
| **Engineer 2** | 1 | Track 2 + Track 4 (onboarding + nav, smaller scope) |
| **Engineer 3** | 1 | Track 3 (TipTap/editor specialist) |
| **Engineer 4** | 1 | Track 5 (data modeling + tab components) |

**Total:** 8 agents (4 engineers + 4 support roles)
**Estimated duration:** 2-3 sessions
**Sprint type:** Large

### Git Branch Plan

```
staging
├── feature/bl-212-strategy-generation   (Track 1, items 1-3)
├── feature/bl-202-chat-intelligence     (Track 1, items 4-5)
├── feature/bl-208-onboarding-fixes      (Track 2, all items)
├── feature/bl-205-editor-rich-content   (Track 3, all items)
├── feature/bl-197-gtm-rename            (Track 4, all items)
└── feature/bl-198-playbook-tabs         (Track 5, all items)
```

6 feature branches, 6 PRs to staging. Merge all, then deploy once, test once.

### Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| BL-212 continuation logic causes infinite loops | High | MAX_TOOL_ITERATIONS already caps at 25; add `iteration < 3` guard on continuation nudge |
| TipTap block selection breaks existing editing | Medium | Test thoroughly with existing content; add feature flag if needed |
| Auto-extraction triggers on every save (performance) | Medium | Add debounce + changed-content check; only extract when content actually changed |
| Mermaid rendering in dark mode broken | Low | Test with design system theme; mermaid has dark theme option |
| Tab navigation breaks mobile layout | Low | Test responsive layout; tabs should collapse to dropdown on mobile |
