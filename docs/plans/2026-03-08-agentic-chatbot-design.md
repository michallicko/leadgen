# Agentic Chatbot Architecture — Design Document

## Overview
Design for a context-aware chatbot that spans the entire leadgen app. One continuous chat thread, adaptive behavior per page, 3-tier model architecture optimized for cost and quality.

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Chat thread | Single continuous thread across all pages |
| Intent detection | Same thread, new intent → new plan in background, old plan archived |
| Page navigation | Agent suggests via quick action buttons, user clicks |
| Editor versioning | Google Docs style — in-session undo + persisted versions at meaningful boundaries |
| Transparent thinking | Show latest finding (what I learned), collapse history behind toggle |
| Scoring | Two layers: automatic completeness bar + AI quality score per section |
| Fact-checking | Website authoritative, escalate to user only on consensus conflict |
| Discovery flow | Research-first, then targeted questions. Adaptive, not scripted |
| Testing | Two layers: deterministic E2E (Playwright) + non-deterministic quality (Claude Code skill as LLM judge) |
| Agent persona | Senior strategist — asks, doesn't assume. Facts only. |
| Plan abstraction | YAML/JSON configs per page context — defines prompt, tools, rubric, research policy |
| Model routing | Haiku (chat) → Deterministic Planner (LangGraph SM) → Opus (synthesis/scoring) |
| Specialist invocation | Tool call, not separate agent. Receives full context, returns output, stateless. |

## Architecture: Three Tiers

### Tier 1: Chat (Haiku)
- Always-on, handles every message first
- Simple Q&A, data lookups, simple edits, quick actions
- Intent detection and routing
- When planner is active, routes messages to planner
- When planner is idle: keyword fast path for clear cases, Haiku classifies ambiguous messages
- Safety net: if user expresses dissatisfaction with Haiku response, escalates to planner

### Tier 2: Deterministic Planner (LangGraph State Machine)
- Loads plan config for current page context + detected intent
- Executes plan steps as a state machine (not LLM-driven orchestration)
- Manages tool calls: web research, editor writes, scoring
- Interruptible at node boundaries — handles user corrections, stops, redirects
- Assembles structured context for Opus invocations (code, not LLM-summarized)
- Decision points → calls Sonnet only when state machine can't resolve from config (e.g., "research found nothing, what now?")
- Streams transparent thinking events (latest finding + collapsible history)

### Tier 3: Specialist (Opus)
- Called as a tool by the planner, not a separate agent
- Receives full structured context: raw research, relevant user messages, existing sections, scoring rubric, constraints
- Handles: strategy synthesis, quality scoring, complex research synthesis
- Stateless per invocation — all context provided by planner
- Self-scores against the plan's rubric
- Called ~4-5 times per strategy generation (section syntheses + final scoring)

### Flow Diagram

```
User Message
    │
    ▼
┌─────────────────────────────────────┐
│  ROUTER (deterministic + Haiku)     │
│  Planner active? → route to planner │
│  Keyword match? → direct route      │
│  Ambiguous? → Haiku classifies      │
└──────────┬──────────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐  ┌──────────────────────────┐
│  CHAT   │  │  PLANNER (LangGraph SM)  │
│ (Haiku) │  │  - Deterministic steps    │
│ simple  │  │  - Interruptible          │
│ Q&A,    │  │  - Tool orchestration     │
│ lookups │  │  - Decision points → LLM  │
│         │  │  - Context assembly       │
└─────────┘  └────────┬─────────────────┘
                      │ invoke when quality matters
                      ▼
             ┌─────────────────┐
             │  SPECIALIST     │
             │  (Opus)         │
             │  - Full context │
             │  - Self-scoring │
             │  - One-shot     │
             └─────────────────┘
```

## Plan Abstraction

A Plan is a data-driven configuration that defines how the agent behaves in a given context. Plans are not subgraphs — they're config objects consumed by the deterministic planner.

### Plan Schema

```yaml
id: playbook_onboarding
name: "Playbook Onboarding"
trigger:
  page: playbook
  conditions:
    - no_strategy_exists
    - onboarding_not_completed

persona: "Senior marketing strategist. Research-first. Facts only, no assumptions."

system_prompt_template: |
  You are helping {{company_name}} build a GTM strategy.
  Research their website ({{domain}}) first. Cross-check all external
  findings against the website. Write to the editor section-by-section.
  Ask targeted discovery questions only where research leaves gaps.

tools:
  - web_research
  - update_strategy_section
  - set_extracted_field
  - halt_gate
  - navigate_suggestion
  - score_strategy

research_requirements:
  primary_source: "{{domain}}"
  cross_check_policy: website_authoritative_with_consensus_override

scoring_rubric:
  sections:
    company_profile: { weight: 1.0, criteria: [factual_accuracy, completeness] }
    market_analysis: { weight: 1.5, criteria: [competitive_depth, segment_clarity] }
    icp_definition: { weight: 2.0, criteria: [specificity, actionability] }
    messaging: { weight: 1.5, criteria: [differentiation, persona_alignment] }
  thresholds:
    completeness: 0.8
    quality_min: 3.5

discovery_questions:
  - category: target_market
    when: "market segment unclear from website"
    examples:
      - "Your website shows corporate events and festivals. Which drives more revenue?"
      - "Do you work mostly in Prague or across Czech regions?"
  - category: competitive_position
    when: "competitors not identifiable from research"
    examples:
      - "Who do you lose deals to most often?"

phases:
  - research_company
  - research_market
  - build_strategy
  - review_and_score
```

### Plan Properties
- **Trigger** — page context + conditions determine which plan activates
- **Persona + system prompt** — different per plan, templated with tenant/company data
- **Tool whitelist** — only expose tools relevant to this plan
- **Scoring rubric** — defines what "good" looks like, used by agent self-scoring and QA testing
- **Discovery questions** — a pool, not a script. Agent picks contextually.
- **Research requirements** — primary source, cross-check policy
- **Phases** — internal workflow steps for the deterministic planner

### Initial Plans (v1)
1. `playbook_onboarding` — first-time strategy generation
2. `strategy_refinement` — editing/improving existing strategy
3. `copilot` — fallback for general Q&A and simple tasks

## Context Router & Intent Detection

### Message Routing (when planner is idle)

1. **Keyword fast path** (~60% of messages): Pattern matching routes without LLM
   - Data queries → Chat tier (Haiku)
   - Explicit commands ("rethink ICP", "score my strategy") → Planner
   - Navigation requests → Chat tier generates quick action
2. **Haiku classification** (~40%): For ambiguous messages, Haiku decides chat-tier vs needs-planning
3. **Safety net**: User dissatisfaction with Haiku response → auto-escalate to planner

### Message Routing (when planner is active)

All messages route through the planner. Planner pauses at next node boundary and classifies:
- **Correction** ("we don't do festivals") → update plan context, resume with new info
- **Stop** ("stop, this is wrong") → halt, surface progress, ask what to change
- **Question** ("what did you find?") → Haiku answers from accumulated state, planner stays paused, resumes after
- **Redirect** ("focus on DACH first") → reorder plan steps, resume

### Page Context
- `page_context` sent with every message (existing behavior)
- When planner is idle and page changes, plan trigger conditions re-evaluated
- Active plan persists across page changes unless explicitly cancelled

## Editor Versioning

### Google Docs-Style Model
- **In-session**: Tiptap built-in undo/redo extended to treat AI edits as atomic operations
- **Persisted versions**: Auto-saved at meaningful boundaries:
  - End of an AI editing session (plan completes a section)
  - User manually saves ("snapshot this version")
  - Before a major rewrite (auto-safety-net)
- **Version metadata**: Timestamp, author (user or AI), description (e.g., "AI: Company Profile added")
- **Version browser**: User can view any version, compare side-by-side, restore any version

### Section Conflict Resolution
- When agent writes to a section, subtle "AI writing..." indicator shown
- User can still edit — their edits take priority (user always wins)
- If user edits the section being written, agent pauses, acknowledges: "I see you changed this. Want me to continue from your version?"
- Other sections remain fully editable during agent writes

## Transparent Thinking UX

### Live Status (during agent work)
- Single status bubble in chat showing the **latest finding** (not just activity)
- Example progression:
  - `Reading unitedarts.cz... Found: event production company, Prague-based, 15+ years`
  - `Searching competitors... Found: EventLab, Massive Events in Czech market`
  - `Writing Company Profile to editor...`
- Each finding replaces the previous one (only latest visible)

### After Completion
- Final response replaces the status bubble
- Brief, actionable chat message (not long text — that goes to editor)
- "Show thinking history" toggle reveals the full trail of findings/steps
- Quick actions for next steps (e.g., `[Score strategy]`, `[Go to Contacts →]`)

## Quality Scoring

### Two Layers

**1. Completeness (automatic)**
- Progress bar: "6/8 sections filled"
- Tracked by the planner deterministically (section exists + non-empty)
- Always visible in the UI

**2. Quality (AI-evaluated)**
- Per-section score (1-5) with specific feedback
- Evaluated against the plan's scoring rubric
- Example: "Market Analysis: 4/5 — strong competitive positioning, missing regional pricing data"
- Triggered: automatically after each section write, and on user request
- Scored by Opus (quality evaluation is a synthesis task)

### Scoring Flow
1. Planner completes a section → invokes Opus with section content + rubric
2. Opus returns: score, reasoning, improvement suggestions
3. Score displayed in editor sidebar next to the section
4. User can ask "score my strategy" → full evaluation of all sections

## Research & Fact-Checking Pipeline

### Research-First Flow
1. **Read primary source** (company website) — extract products, services, team, positioning
2. **Write confirmed facts** to editor immediately (don't wait for full research)
3. **Research market** — competitors, segment, trends (Perplexity/web search)
4. **Cross-check** all external findings against website content
5. **Conflict resolution**:
   - Website vs. single external source → trust website
   - Website vs. multiple agreeing external sources → halt gate to user
6. **Discovery questions** — ask only where research left genuine gaps

### Cross-Check Policy: website_authoritative_with_consensus_override
- Company's own website is the default authority for: products, services, team, location, positioning
- External sources are authority for: market data, competitor info, industry trends
- Conflict: if 3+ external sources agree on something the website contradicts, surface to user via halt gate
- All findings tagged with source in thinking history

## Testing Framework

### Layer 1: Deterministic E2E (Playwright)
- UI renders correctly (chat, editor, quick actions, version browser)
- SSE events arrive in correct order
- Quick actions trigger navigation
- Editor updates reflect agent writes
- Version snapshots are created and browsable
- Pass/fail, repeatable, runs in CI

### Layer 2: Conversation Quality (Claude Code Skill)
- `/test-chat` skill that runs from terminal
- Calls the API directly, feeds a scenario (company + goal)
- Captures the full SSE stream
- Evaluates via LLM judge:
  - Did it research the website first?
  - Did it cross-check findings?
  - Did it ask discovery questions (not assume)?
  - Is the strategy output high quality? (scored against rubric)
  - Were quick actions offered appropriately?
  - Was transparent thinking shown correctly?
- Multiple runs to account for non-determinism
- Flag significant quality drops as regressions

### Test Scenarios (initial)
1. **Playbook onboarding**: unitedarts.cz + "increase market penetration in Czech regions + pilot DACH agencies"
2. **Strategy refinement**: Existing strategy → user asks to rethink ICP
3. **Mid-plan interruption**: Start onboarding → user corrects a fact mid-research
4. **Simple Q&A**: "How many contacts do I have?" (should stay in chat tier)

## Cost Profile

| Component | Model | Est. cost per strategy |
|-----------|-------|----------------------|
| Chat routing | Haiku | ~$0.02 (20 exchanges) |
| Planner orchestration | Code (free) + Sonnet ~2 decision points | ~$0.02 |
| Strategy synthesis | Opus × 4-5 sections | ~$0.50-0.80 |
| Quality scoring | Opus × 1 full evaluation | ~$0.15 |
| **Total** | | **~$0.70-1.00** |

vs. Opus-for-everything: ~$5-10 per strategy

## What This Replaces
- Current: single LangGraph graph with intent → subgraph routing, one model for everything
- New: 3-tier model routing with plan configs, deterministic planner, Opus for synthesis

## What Stays
- ChatProvider (app-level, single thread)
- Page context sent with every message
- SSE streaming + AG-UI events
- Tiptap editor with typewriter streaming
- Halt gate UI for user decisions

## Migration Path
1. Plan abstraction + deterministic planner (refactor existing pipeline.py)
2. Haiku chat tier (extract simple Q&A from current single-model path)
3. Opus specialist integration (add as tool callable by planner)
4. Editor versioning (new feature, standalone)
5. Transparent thinking UX (refactor existing THINK feature)
6. Quality scoring (new feature)
7. Research pipeline with cross-checking (enhance existing research subgraph)
8. Testing framework (new Claude Code skill + Playwright specs)
