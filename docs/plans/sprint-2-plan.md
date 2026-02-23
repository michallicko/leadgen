# Sprint 2 Plan

**Date**: 2026-02-23
**Theme**: Make the AI a Real Strategist (Agent + Persistent Chat + First Tools)
**Goal**: Transform the playbook chat from a passive chatbot into an agent that persists across pages, uses tools, and directly edits the strategy document.

---

## Sprint 1 Recap

Sprint 1 delivered the playbook foundation. 5 PRs are open and awaiting merge to staging:

| ID | Title | Status | PR |
|----|-------|--------|-----|
| TONE | AI Tone Fix + TODOs + Doc Awareness | PR Open | #35 |
| PB-035 | Auto-Save (Debounced) | PR Open | #36 |
| PB-001 | Phase Infrastructure (Migration+Model+API) | PR Open | #37 |
| CHAT-MD | Chat Markdown Rendering + Conciseness | PR Open | #38 |
| PB-006 | Phase UI (Routing+Stepper+TopBar) | PR Open | #39 |

**Sprint 1 verdict**: Foundation is solid. Phases, auto-save, markdown chat, tone rules — the playbook skeleton is built. Now we need to give the AI brain and hands.

---

## Sprint 2 Items (6 items, build order)

### 1. AGENT — Agent-Ready Chat (Tool Use Architecture)
- **Priority**: Must Have | **Effort**: M | **Status**: Idea
- **Dependencies**: None
- **Rationale**: The single biggest enabler in the entire backlog. Unblocks 8+ items across Sprint 2 and 3. Without this, the AI is just a text generator. With this, it becomes an agent that can take actions.
- **Build first**: Everything else in Sprint 2 depends on this.

### 2. PERSIST — Persistent App-Wide Chat (Marketing Strategist)
- **Priority**: Must Have | **Effort**: L | **Status**: Idea
- **Dependencies**: None (can build in parallel with AGENT)
- **Rationale**: Currently the chat resets on page navigation. The vision requires an always-available strategist that remembers context. This is the #1 usability gap — users lose conversation context every time they switch pages.
- **Can start immediately**: No dependency on AGENT. Build the persistence layer (DB, API, sliding panel, Cmd+K) while AGENT is being built.

### 3. WRITE — Chat Writes/Updates Strategy Doc Directly
- **Priority**: Must Have | **Effort**: M | **Status**: Idea
- **Dependencies**: AGENT
- **Rationale**: The first and most impactful tool to wire up. The vision says "the AI does the work, the founder approves." If the AI can't write to the doc, the founder is still doing busywork. This is the tool that makes the Strategy phase feel magical.
- **Build after AGENT**: Needs the tool-use architecture to register and execute strategy editing tools.

### 4. BL-054 (Phase 1 only) — Chat Access to Self-Company Enrichment Data
- **Priority**: Must Have | **Effort**: S (Phase 1 only, no AGENT dep) | **Status**: Spec'd
- **Dependencies**: None for Phase 1
- **Rationale**: The AI currently lacks context about the user's own company when giving strategy advice. Phase 1 is a quick win — expand the system prompt with L2 enrichment fields and add the self-company fallback. No tool-use needed. This makes every chat response more relevant immediately.
- **Spec ready**: Full spec at `docs/specs/chat-enrichment-access.md`. Phase 1 is explicitly marked as having no dependencies.

### 5. BL-055 — LLM Cost Logging & Breakdown Dashboard
- **Priority**: Should Have | **Effort**: M | **Status**: Spec'd
- **Dependencies**: None
- **Rationale**: With AGENT adding more LLM calls (tool execution loops, multi-turn), cost visibility becomes critical. This instruments all call sites and builds the admin dashboard. It's also a prerequisite for BL-056 (token credit system) which is essential for multi-tenant billing.
- **Spec ready**: Full spec at `docs/specs/llm-cost-tracking.md`. Can build in parallel with AGENT/PERSIST.

### 6. THINK — Transparent AI Thinking (Tool Calls, Reasoning)
- **Priority**: Must Have | **Effort**: M | **Status**: Idea
- **Dependencies**: AGENT
- **Rationale**: Once the AI starts using tools, users need to see what's happening. "Searching contacts...", "Updating strategy..." — without this, tool use feels like a black box. This is the UX counterpart to AGENT.
- **Build after AGENT + WRITE**: The thinking UI needs actual tool calls to display. Build this last so there are real tools to visualize.

---

## Build Sequence (Dependency Chain)

```
Week 1 (parallel tracks):
  Track A: AGENT (tool-use architecture)
  Track B: PERSIST (persistent chat + sliding panel)
  Track C: BL-054 Phase 1 (enrichment data in system prompt)
  Track D: BL-055 (LLM cost instrumentation + dashboard)

Week 2 (sequential, after AGENT merges):
  WRITE (strategy doc editing tools — first real tool on AGENT)
  THINK (tool call visualization UI — needs real tools to display)
```

Items 1-2 and 3-4 can run on parallel worktrees. Items 5-6 depend on AGENT being merged first.

---

## What Sprint 2 Enables for Sprint 3

With AGENT + PERSIST + WRITE + THINK in place, Sprint 3 can deliver the high-value items that are currently blocked:

| Sprint 3 Candidate | Why it's unblocked |
|--------------------|--------------------|
| BL-052 — Contact Filtering & Campaign Management | Needs AGENT for `filter_contacts`, `create_campaign` tools |
| BL-053 — Echo Task List | Needs AGENT for `add_task`, `suggest_tasks` tools |
| BL-054 Phase 2 — On-Demand Enrichment Data | Needs AGENT for `get_company_research` tool |
| SEARCH — Chat Internet Access | Needs AGENT for `search_web` tool |
| ANALYZE — Contacts/Companies Analyzer | Needs AGENT for `search_contacts`, `analyze_companies` tools |
| ONBOARD — Smart Onboarding | Needs WRITE for auto-generating first draft |

Sprint 2 is the foundation sprint that turns the AI from passive to active. Sprint 3 is where users start seeing the AI do real work autonomously across all phases.

---

## Capacity and Risk

**Total effort**: 2M + 1L + 1S + 1M + 1M = roughly 3-4 developer-weeks of work

**Risks**:
1. **AGENT scope creep**: The tool-use loop is the critical path. Keep the initial tool registry small (3-5 tools). Don't try to wire up all tools in Sprint 2 — just `update_strategy_body`, `set_field`, `get_strategy`.
2. **PERSIST complexity**: The sliding panel + React Context + message persistence is a lot of frontend. Consider shipping a simpler version (page-level persistence first, then global sidebar).
3. **SSE streaming for THINK**: Server-Sent Events for tool call visualization is technically tricky. If SSE is hard, ship with polling first and upgrade later.

**Mitigations**:
- AGENT and PERSIST have no dependencies — start both on day 1
- BL-054 Phase 1 and BL-055 are independent quick wins — can be assigned to separate worktrees
- WRITE and THINK are sequential but focused — each is a clean feature on top of AGENT

---

## Items Deprioritized or Removed

### Removed
- **PB-037 (Intelligent Auto-Extraction)**: Redundant. The chat now handles ICP extraction on-demand through conversation. Auto-extraction from document text is over-engineering when the AI can just ask the user directly.

### Moved to Backlog (from Sprint 2/3)
- **ONBOARD**: Was Sprint 3. Still Sprint 3, but depends on WRITE which is now Sprint 2. Correctly sequenced.
- **BL-049 (Playbook Auto-Save)**: Duplicate of PB-035 which is already in Sprint 1. The BL-049 item is redundant.

### Deprioritized (Backlog, no sprint)
- **COLLAB / PB-036 (Real-Time Collaboration)**: Nice to have but not revenue-critical. Single-founder tool doesn't need multi-user editing yet.
- **VOICE / BL-047 (Voice Dialog Mode)**: Cool but premature. Focus on text-based agent first.
- **LANG (Namespace Language Settings)**: Low priority. English-first is fine for MVP.
- **VERSION (Strategy Version History)**: Auto-save + WRITE versioning covers basic needs. Full version UI is Sprint 4+.
- **N8N-RM (Remove n8n)**: Important for infra health but doesn't add user value. Defer until the Python pipeline engine (BL-015) is further along.
- **BL-056 (Token Credit System)**: Depends on BL-055. Sprint 3 at earliest.

---

## Sprint 2 Summary

| # | ID | Title | Effort | Deps | Track |
|---|-----|-------|--------|------|-------|
| 1 | AGENT | Agent-Ready Chat (Tool Use Architecture) | M | None | Week 1 |
| 2 | PERSIST | Persistent App-Wide Chat | L | None | Week 1 |
| 3 | BL-054 | Chat Access to Enrichment Data (Phase 1) | S | None | Week 1 |
| 4 | BL-055 | LLM Cost Logging & Dashboard | M | None | Week 1 |
| 5 | WRITE | Chat Writes Strategy Doc | M | AGENT | Week 2 |
| 6 | THINK | Transparent AI Thinking | M | AGENT | Week 2 |

**Sprint 2 delivers**: An AI that persists across pages, uses tools to edit the strategy doc, shows its thinking process, has full context about the user's company, and tracks its own costs. The founder opens the playbook and has a real strategist, not a chatbot.
