# Agent & Prompt Architecture Design

> Discussion document — March 2026

## 1. Current Architecture

### System Prompt Assembly

Every API call rebuilds the full system prompt from scratch:

```
┌─────────────────────────────────────────────┐
│              SYSTEM PROMPT                   │
│  (~3,000 - 10,000+ tokens per call)         │
├─────────────────────────────────────────────┤
│ A. Critical Rules (static)         ~300 tok │
│ B. Role Definition (static)        ~100 tok │
│ C. 7-Section Structure (static)    ~100 tok │
│ D. Research Workflow (static)      ~200 tok │
│ E. User Objective (dynamic)         ~50 tok │
│ F. Full Strategy Document (dynamic) ~500-5K │
│ G. Section Completeness (dynamic)  ~100 tok │
│ H. Document Awareness (static)     ~400 tok │
│ I. ICP/Personas Rules (static)     ~400 tok │
│ J. Enrichment Data (dynamic)       ~200-2K  │
│ K. Tone/Style/Length (static)      ~1000 tok│
│ L. Phase Instructions (dynamic)    ~800 tok │
│ M. Page Context Hint (dynamic)      ~50 tok │
│ N. Language Override (dynamic)      ~50 tok │
├─────────────────────────────────────────────┤
│ TOTAL STATIC: ~2,500 tokens                 │
│ TOTAL DYNAMIC: ~1,000 - 8,000+ tokens       │
└─────────────────────────────────────────────┘
```

### Per-Call Cost

```
┌──────────────────────────────────────────────────┐
│           EVERY query_with_tools() CALL          │
├──────────────────────────────────────────────────┤
│ System Prompt          3K - 10K tokens           │
│ 24 Tool Schemas        ~2.5K tokens              │
│ Conversation History   up to 20 msgs (~2-4K)     │
│ Current Turn Tools     accumulates per iteration  │
├──────────────────────────────────────────────────┤
│ INPUT TOTAL:           8K - 20K+ tokens per call │
│                                                  │
│ Agent loop: up to 25 iterations per turn         │
│ WORST CASE: 25 × 20K = 500K input tokens/turn   │
└──────────────────────────────────────────────────┘
```

### Agent Execution Flow

```
User Message
    │
    ▼
┌─────────────┐     ┌─────────────────────┐
│ Build System │────▶│   query_with_tools  │◄──────────────┐
│   Prompt     │     │   (Claude Haiku)    │               │
└─────────────┘     └────────┬────────────┘               │
                             │                             │
                    ┌────────┴────────┐                    │
                    │  stop_reason?   │                    │
                    └────────┬────────┘                    │
                   ┌─────────┴─────────┐                   │
                   ▼                   ▼                   │
            tool_use              end_turn                 │
                   │                   │                   │
                   ▼                   ▼                   │
           ┌──────────────┐    ┌──────────────┐           │
           │ Execute Tool │    │ Nudge Check  │           │
           │ (1..N tools) │    │ (sections?)  │           │
           └──────┬───────┘    └──────┬───────┘           │
                  │                   │                    │
                  │            ┌──────┴──────┐            │
                  │            │ Incomplete?  │            │
                  │            └──────┬──────┘            │
                  │           yes     │     no            │
                  │            │      │      │            │
                  ▼            ▼      │      ▼            │
           Append Results   Inject    │   Yield Done      │
           to Messages      Nudge     │   Event           │
                  │            │      │                   │
                  └────────────┴──────┘                   │
                           │                              │
                           └──────────────────────────────┘
                                  (loop)
```

### Frontend ↔ Agent Interaction

```
┌─────────────────┐         ┌─────────────────┐        ┌──────────────┐
│   ChatSidebar   │         │   ChatProvider   │        │  Flask API   │
│   (UI Layer)    │         │   (State Mgmt)   │        │  (Backend)   │
├─────────────────┤         ├─────────────────┤        ├──────────────┤
│                 │         │                 │        │              │
│ User types msg ─┼────────▶│ sendMessage()  ─┼───────▶│ POST /chat   │
│                 │         │                 │        │              │
│                 │         │ SSE callbacks:  │◄───────┤ SSE stream:  │
│ ChatMessages   ◄┼─────────┤  onChunk       │        │  chunk       │
│ (renders msgs)  │         │  onToolStart   │        │  tool_start  │
│                 │         │  onToolResult  │        │  tool_result │
│ WorkingState   ◄┼─────────┤  isThinking    │        │  thinking    │
│ (thinking UI)   │         │  thinkingStatus│        │  research_st │
│                 │         │                 │        │              │
│ StrategyEditor ◄┼─────────┤  onSectionStart│        │  sec_content │
│ (typewriter)    │         │  onSectionChunk│        │  _start/chunk│
│                 │         │  onSectionDone │        │  _done       │
│                 │         │                 │        │              │
│ PhaseTransition◄┼─────────┤  documentChanged│       │  done (with  │
│ (banner)        │         │  (invalidate   │        │   tool_calls)│
│                 │         │   react-query)  │        │              │
└─────────────────┘         └─────────────────┘        └──────────────┘
```

## 2. Problems Identified

### P1: No Prompt Caching
The system prompt is re-sent verbatim on EVERY iteration of the tool loop. Anthropic API supports `cache_control` breakpoints that would cache the static portion across calls. With up to 25 iterations per turn, this wastes ~2,500 static tokens x 25 = 62,500 input tokens that could be cached.

### P2: All 24 Tools Always Sent
Every call includes all 24 tool definitions regardless of context. On the Playbook strategy phase, campaign tools are irrelevant. On the contacts phase, strategy tools are irrelevant. Sending unnecessary tools wastes ~1,000+ tokens and confuses the model.

### P3: Full Document in System Prompt
The entire strategy document is embedded in every system prompt. As the document grows (5,000+ tokens), this dominates the prompt cost. The document is already available via `get_strategy_document` tool -- the AI could fetch it on demand instead.

### P4: No Conversation Summarization
Hard window of 20 messages with no summarization. Early context (decisions, preferences) is lost after 20 messages. No distinction between important context and filler.

### P5: Tool History Lost Between Turns
Previous turn's tool calls are NOT included in conversation history -- only the text response. The AI loses awareness of what tools it already used and what data it already has.

### P6: Static Phase Instructions for All Phases
All 4 phase instruction blocks are included regardless of which phase is active. Only the active phase's instructions are relevant.

### P7: Enrichment Data Always Included
Full enrichment data (~200-2,000 tokens) is included even when the conversation topic doesn't need it (e.g., user asks "make this section shorter").

## 3. Proposed: Layered Prompt Architecture

### Core Idea: Separate static identity from dynamic context

```
┌─────────────────────────────────────────────┐
│  LAYER 0: IDENTITY (cacheable, ~800 tok)    │
│  - Role definition                          │
│  - Critical rules                           │
│  - Response style/tone                      │
│  - Question format rules                    │
│  - Language override                        │
│  [cache_control: ephemeral]                 │
├─────────────────────────────────────────────┤
│  LAYER 1: CAPABILITIES (cacheable, ~1-2K)   │
│  - Tool descriptions (phase-filtered)       │
│  - Tool usage rules                         │
│  - Document editing rules                   │
│  [cache_control: ephemeral]                 │
├─────────────────────────────────────────────┤
│  LAYER 2: CONTEXT (dynamic, ~1-5K)          │
│  - Current phase instructions (1 of 4)      │
│  - Section completeness status              │
│  - User objective                           │
│  - Page context hint                        │
│  - Enrichment summary (compressed)          │
│  - Document excerpt (relevant sections)     │
├─────────────────────────────────────────────┤
│  LAYER 3: CONVERSATION (dynamic, ~1-4K)     │
│  - Summarized older messages                │
│  - Recent messages (last 6-10 verbatim)     │
│  - Previous turn tool results (compressed)  │
└─────────────────────────────────────────────┘
```

### Token Budget Comparison

```
                    CURRENT          PROPOSED
                    -------          --------
System prompt:      3K-10K           800 (cached) + 1-3K dynamic
Tool schemas:       2.5K (all 24)    600-1K (phase-filtered 6-10)
History:            2-4K (raw 20)    1-2K (summarized + recent)
Turn context:       0-5K (tools)     0-3K (compressed)
                    -------          --------
Per-call total:     8-20K            3-7K
25-iteration turn:  200-500K         ~50K (cached) + 75-175K
Savings:            --               50-70% input token reduction
```

### Tool Routing by Phase

```
Phase        Active Tools (send to API)       Omitted
-----        --------------------------       -------
strategy     update_strategy_section          filter_contacts
             append_to_section                create_campaign
             set_extracted_field              assign_to_campaign
             track_assumption                 check_strategy_conflicts
             check_readiness                  get_campaign_summary
             set_icp_tiers                    apply_icp_filters
             set_buyer_personas               get_enrichment_gaps
             web_search                       estimate_enrichment_cost
             research_own_company             start_enrichment
             get_strategy_document            analyze_enrichment_insights
             count_contacts
             count_companies

contacts     list_contacts                    update_strategy_section
             count_contacts                   append_to_section
             filter_contacts                  set_extracted_field
             apply_icp_filters                track_assumption
             get_enrichment_gaps              set_icp_tiers
             estimate_enrichment_cost         set_buyer_personas
             start_enrichment                 web_search
             get_strategy_document            research_own_company
             analyze_enrichment_insights

messages     create_campaign                  update_strategy_section
             filter_contacts                  set_extracted_field
             get_strategy_document            web_search
             list_contacts                    research_own_company
                                              set_icp_tiers / personas

campaign     create_campaign                  update_strategy_section
             assign_to_campaign               set_extracted_field
             check_strategy_conflicts         web_search
             get_campaign_summary             research_own_company
             filter_contacts                  set_icp_tiers / personas
             get_strategy_document
```

## 4. Conversation Context Strategy

### Current: Hard Window

```
Message 1  --+
Message 2    |  DROPPED (lost forever)
...          |
Message 15 --+
Message 16 --- kept (raw)
Message 17 --- kept (raw)
...
Message 35 --- kept (raw, latest)
```

### Proposed: Summarize + Window

```
Messages 1-20:  +----------------------+
                |  SUMMARY (~200 tok)  |
                |  "User wants B2B     |
                |   SaaS strategy.     |
                |   Prefers aggressive |
                |   outbound. Approved |
                |   3-tier ICP."       |
                +----------------------+
Messages 21-28: kept verbatim (recent context)
Message 29:     current user message
```

**Summarization trigger:** When history exceeds 15 messages, summarize oldest 10 into a ~200 token summary. Keep last 8 verbatim. Re-summarize as conversation grows.

**What to preserve in summaries:**
- User decisions and preferences
- Approved strategies/content
- Rejected suggestions
- Key constraints mentioned
- Tool results that inform future decisions

**What to drop:**
- Filler ("looks good", "thanks")
- Intermediate drafts that were replaced
- Tool execution details (keep outcomes only)

## 5. Prompt Caching Strategy

### Anthropic Cache Control

```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": STATIC_SYSTEM_PROMPT,  # ~800 tokens
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": TOOL_RULES,  # ~500 tokens
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": dynamic_context  # changes each call
            }
        ]
    }
]
```

**Cache hit rate:** Within a single turn's tool loop (up to 25 iterations), the static portion would be cached after the first call. Saves ~1,300 tokens x 24 iterations = ~31,200 cached input tokens per turn.

**Between turns:** Cache lives for 5 minutes. If user sends another message within 5 min, static portion is still cached.

## 6. Document Context Optimization

### Current: Full Document Always Included

```
System prompt contains:
--- Current Strategy Document ---
# GTM Strategy Playbook
## Executive Summary
[500 words]
## Value Proposition
[400 words]
## Competitive Positioning
[300 words]
... (all 7 sections, 2000-5000 words total)
--- End ---
```

### Option A: Lazy Load via Tool

Remove document from system prompt entirely. AI calls `get_strategy_document` when it needs to read the document. Trade-off: adds 1 tool call per turn but saves 500-5000 tokens from system prompt.

**Risk:** AI might not call the tool when it should, leading to stale context. Mitigated by explicit instructions.

### Option B: Relevant Sections Only

Include only the section the user is asking about + completeness status for all sections. AI can fetch other sections via tool if needed.

```
--- Strategy Context ---
ACTIVE SECTION: Competitive Positioning
[full content of that section]

OTHER SECTIONS STATUS:
- Executive Summary [COMPLETE - 245 words]
- Value Proposition [COMPLETE - 180 words]
- Channel Strategy [EMPTY]
- Messaging Framework [PARTIAL - 45 words]
- Metrics & KPIs [EMPTY]
- 90-Day Action Plan [EMPTY]
--- End ---
```

### Option C: Compressed Summary + Full on Demand

Include a 200-token summary of the document (key decisions, ICP, positioning) in the system prompt. Full document available via tool.

**Recommended: Option B** -- relevant section + status gives the AI enough context to respond intelligently while keeping prompt lean. Full sections available via tool for cross-referencing.

## 7. UI <-> Agent Interaction Patterns

### Current: Monolithic Handler

```
User clicks Send
    |
    v
ChatProvider.sendMessage()
    |
    v
POST /api/playbook/chat  ---- one endpoint handles everything
    |
    v
build_system_prompt()     ---- one prompt for all scenarios
    |
    v
agent_executor loop       ---- one loop, all tools available
```

### Proposed: Intent-Aware Routing

```
User clicks Send
    |
    v
ChatProvider.sendMessage()
    |
    v
POST /api/playbook/chat
    |
    v
+──────────────+
| Intent Check |  <-- lightweight classifier (or keyword rules)
+──────┬───────+
       |
  +────┴────┬──────────┬──────────┐
  v         v          v          v
Quick     Strategy   Research   Campaign
Answer    Edit       Task       Action
  |         |          |          |
  v         v          v          v
Simple    Edit        Research   Campaign
streaming tools +     tools +    tools +
(no tools) doc ctx    web ctx    contact ctx
```

**Intent categories:**
- **Quick answer**: "What's our ICP?" -- no tools, just reference doc, streaming response
- **Strategy edit**: "Rewrite the positioning section" -- edit tools + doc context
- **Research task**: "Find competitors for Acme" -- web_search + research tools
- **Campaign action**: "Create a campaign for Tier 1" -- campaign + contact tools

**Benefits:**
- Smaller tool sets per intent = cheaper calls + better tool selection
- Targeted context = less noise in the prompt
- Can use different models per intent (Haiku for quick answers, Sonnet for complex edits)

## 8. Design Patterns Summary

### Pattern 1: Prompt Layering
Separate identity (cacheable) from context (dynamic). Static layers cached across tool iterations. Dynamic layers rebuilt per call with minimal content.

### Pattern 2: Phase-Filtered Tools
Only register tools relevant to the current phase. Reduces schema tokens and eliminates irrelevant tool selection.

### Pattern 3: Lazy Document Loading
Remove full document from system prompt. Include section status + active section only. Full content available via tool call.

### Pattern 4: Conversation Summarization
Summarize old messages, keep recent ones verbatim. Preserve decisions and preferences, drop filler.

### Pattern 5: Intent-Aware Routing
Classify user intent before building prompt. Route to specialized prompt+tool configurations per intent type.

### Pattern 6: Model Selection by Complexity
Use Haiku for quick answers and simple edits. Use Sonnet for complex strategy generation, research synthesis, and multi-tool orchestration.

## 9. Agent Conversation Flow Control

### The Problem: Blind Execution

Currently the agent receives a prompt like "Generate a GTM strategy for acme.com" and runs autonomously for up to 25 tool iterations, making every decision itself. It produces a complete 7-section strategy without ever checking if it's on the right track. This leads to:

- Strategy about the wrong product line (company has 5 products, AI picked one)
- Wrong ICP scope (B2B + B2C company, AI assumed both)
- Generic positioning because AI didn't confirm differentiators
- Wasted tokens on sections that get thrown away after user review

### Proposed: Progressive Confirmation Gates

The agent should decompose work into phases and HALT at critical decision points — moments where a wrong assumption would invalidate everything downstream.

```
User: "Generate a strategy for acme-saas.com"
    │
    ▼
┌─────────────────────────────────────────┐
│  PHASE 1: RESEARCH (autonomous)         │
│  ─ web_search: company website          │
│  ─ research_own_company: deep profile   │
│  ─ Extract: products, markets, team     │
└────────────────┬────────────────────────┘
                 │
    ─────── HALT GATE 1: Company Scope ────────
    │                                          │
    │  "I found Acme has 3 products:           │
    │   1. DataFlow (analytics, $2M ARR)       │
    │   2. QuickSync (integration, $500K)      │
    │   3. CloudVault (storage, $800K)         │
    │                                          │
    │   Strategy for all 3, or focus on one?"  │
    │                                          │
    │  [All products] [DataFlow only]          │
    │  [DataFlow + QuickSync] [Other]          │
    │                                          │
    ────────────────────────────────────────────
                 │
                 ▼ (user picks "DataFlow only")
                 │
┌─────────────────────────────────────────┐
│  PHASE 2: POSITIONING (autonomous)      │
│  ─ Analyze DataFlow competitors         │
│  ─ Draft value proposition              │
│  ─ Define target market segments        │
└────────────────┬────────────────────────┘
                 │
    ─────── HALT GATE 2: ICP Direction ────────
    │                                          │
    │  "Two strong ICP segments emerge:        │
    │   A. VP Ops at mid-market SaaS (200-2K)  │
    │   B. CFO at enterprise fintech (2K+)     │
    │                                          │
    │   Go broad (both) or narrow (one)?"      │
    │                                          │
    │  [Both segments] [Segment A]             │
    │  [Segment B] [Other]                     │
    ────────────────────────────────────────────
                 │
                 ▼ (user picks "Segment A")
                 │
┌─────────────────────────────────────────┐
│  PHASE 3: STRATEGY DRAFT (autonomous)   │
│  ─ Write Executive Summary              │
│  ─ Write ICP tiers (based on Segment A) │
│  ─ Write Positioning                    │
│  ─ Write Channel Strategy               │
└────────────────┬────────────────────────┘
                 │
    ─────── HALT GATE 3: Draft Review ─────────
    │                                          │
    │  "Strategy draft complete. Key choices:  │
    │   ─ Primary channel: LinkedIn outbound   │
    │   ─ Tone: consultative, not salesy       │
    │   ─ Metric target: 5% reply rate         │
    │                                          │
    │   Looks right, or adjust?"               │
    │                                          │
    │  [Looks good, continue] [Adjust tone]    │
    │  [Change channel] [Review full draft]    │
    ────────────────────────────────────────────
                 │
                 ▼
┌─────────────────────────────────────────┐
│  PHASE 4: MESSAGING + ACTION PLAN       │
│  ─ Write Messaging Framework            │
│  ─ Write 90-Day Action Plan             │
│  ─ Set buyer personas                   │
│  ─ Check readiness for Contacts phase   │
└─────────────────────────────────────────┘
```

### Halt Gate Taxonomy

Not every pause is a halt gate. Define clear categories:

```
GATE TYPE         TRIGGER                           EXAMPLE
──────────        ───────                           ───────
Scope Gate        Multiple valid scopes found       "Which product line?"
Direction Gate    Mutually exclusive strategies     "Broad or narrow ICP?"
Assumption Gate   AI made a guess it's unsure about "I assumed B2B only — correct?"
Review Gate       Major deliverable complete        "Strategy draft ready — review?"
Resource Gate     Expensive action about to happen  "Enrichment will cost 450 credits — proceed?"
```

### When to HALT vs Continue

```
HALT when:                              CONTINUE when:
──────────                              ──────────────
Decision invalidates downstream work    Decision is easily reversible
Multiple valid options, no clear winner Single obvious path forward
User preference matters (tone, scope)   Factual/technical choice
Expensive operation ahead               Low-cost operation
First time encountering this decision   Same decision was made before
```

### Implementation: Halt Gate Protocol

The agent needs a structured way to halt. Two approaches:

**Option A: Tool-Based Halts**

Add a `request_user_decision` tool:
```json
{
  "name": "request_user_decision",
  "description": "Pause execution and ask the user to choose between options. Use at critical decision points where the wrong choice would waste significant work.",
  "input_schema": {
    "type": "object",
    "properties": {
      "question": {"type": "string", "description": "Clear question for the user"},
      "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": "2-4 concrete options the user can pick"
      },
      "context": {"type": "string", "description": "Brief context for why this matters"},
      "gate_type": {
        "type": "string",
        "enum": ["scope", "direction", "assumption", "review", "resource"]
      }
    },
    "required": ["question", "options", "context", "gate_type"]
  }
}
```

When the AI calls this tool, the executor:
1. Yields the question as a special SSE event (`decision_request`)
2. Stops the agent loop
3. Frontend shows the question with option buttons
4. User's choice is sent as the next message
5. Agent resumes with the decision as context

**Option B: Prompt-Instructed Halts**

No new tool — instruct the AI in the system prompt to stop and ask:
```
HALT GATE RULES:
When you encounter these situations, STOP generating and ask the user:
1. SCOPE: You found multiple products/business lines → ask which to focus on
2. DIRECTION: Two valid ICP segments → ask broad or narrow
3. ASSUMPTION: You're guessing about market/industry → verify
4. REVIEW: You completed a major section → ask if direction is right

Format halt questions as:
- One sentence context
- The question
- 3-4 clickable options (format as numbered list)

After asking, STOP. Do not continue until the user responds.
```

**Recommended: Option A (tool-based)** — more reliable. Prompt-only halts are easy for the AI to skip, especially with Haiku. A tool call forces a real pause in the executor loop.

### Frontend: Decision Request UI

When a `decision_request` SSE event arrives:

```
┌─────────────────────────────────────────┐
│  🔍 Research Complete                    │
│                                         │
│  Acme has 3 product lines. Which        │
│  should the strategy focus on?          │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ DataFlow (analytics, $2M ARR)  │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ All products                    │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ DataFlow + QuickSync           │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ Other...                        │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

Render as interactive buttons in the chat. User clicks one → sent as next message → agent resumes.

### Communication Framework for Discussing Chat Interactions

When designing agent interactions, use this shared vocabulary:

```
TERM              MEANING
────              ───────
Turn              One user message → full agent response (may include tool loops)
Gate              A decision point where the agent pauses for user input
Phase             A block of autonomous work between gates
Scope             What the strategy covers (product, market, geography)
Direction         Strategic choice (broad/narrow, aggressive/conservative)
Assumption        Something the AI guessed — needs verification
Deliverable       A concrete output (section draft, ICP definition, action plan)
Confirmation      User approves a deliverable or direction
Rejection         User sends back a deliverable for revision
Pivot             User changes scope or direction mid-flow
```

### Task Decomposition Rules

The agent should break a large request into phases with gates:

```
USER REQUEST               DECOMPOSITION
────────────               ─────────────
"Generate strategy"        Research → [Scope Gate] → Position → [Direction Gate]
                          → Draft → [Review Gate] → Finalize

"Find contacts"           Review ICP → [Assumption Gate: ICP correct?]
                          → Filter → [Review Gate: sample looks right?]
                          → Full list

"Create campaign"         Select contacts → [Scope Gate: how many?]
                          → Draft messages → [Review Gate: tone right?]
                          → Schedule

"Improve positioning"     Read current → [Assumption Gate: what's wrong?]
                          → Revise → [Review Gate]
```

### Gate Frequency Guideline

```
Too few gates:    AI runs for 3 minutes, produces wrong strategy → waste
Too many gates:   AI asks 10 questions before writing anything → annoying
Sweet spot:       2-4 gates per major task, 0-1 for minor edits

TASK SIZE         GATES
─────────         ─────
Full strategy     3-4 (scope, direction, draft review, final review)
Section rewrite   1 (review gate after draft)
Quick edit        0 (just do it)
Research task     1 (scope gate: what to research)
Campaign create   2 (scope gate, message review)
```

## 10. Framework Evaluation: Build vs Adopt

### Current Custom Stack

```
┌──────────────────────────────────────────┐
│           CURRENT ARCHITECTURE           │
├──────────────────────────────────────────┤
│  Flask Route                             │
│    └─ playbook_service.build_system_prompt│
│    └─ agent_executor.execute_agent_turn  │
│         └─ requests.post(anthropic API)  │
│         └─ tool_registry.execute()       │
│         └─ SSE yield (custom generator)  │
├──────────────────────────────────────────┤
│  Lines of code:     ~800 (executor+tools)│
│  External deps:     requests, flask      │
│  Observability:     None                 │
│  Streaming:         Custom SSE generator │
│  State machine:     Implicit (loop+nudge)│
│  Halt gates:        Not implemented      │
│  Multi-model:       Not implemented      │
│  Prompt caching:    Not implemented      │
└──────────────────────────────────────────┘
```

### Option A: Stay Custom + Incremental Improvements

Keep the current architecture, add features incrementally:

```
WHAT TO ADD              EFFORT    BENEFIT
──────────               ──────    ───────
Prompt caching           2 hours   50% token savings
Phase-filtered tools     4 hours   Better tool selection
request_user_decision    1 day     Halt gates
Conversation summary     1 day     Better context mgmt
Intent classifier        2 days    Smarter routing
LangSmith-like tracing   3-5 days  Observability
Multi-model routing      1 day     Cost optimization
```

**Total: ~2 weeks to match framework features.**

**Pros:**
- Zero migration risk
- Full control, no abstractions
- SSE streaming already works
- No new dependencies
- You understand every line

**Cons:**
- You maintain everything yourself
- No community patterns to follow
- Observability is DIY (fragile, incomplete)
- State machine logic stays implicit
- Halt gates need custom protocol
- Testing agent flows is manual

### Option B: LangGraph + LangSmith

LangGraph is LangChain's graph-based agent framework. It models agent flows as directed graphs with typed state, conditional edges, and built-in interrupts.

```
┌──────────────────────────────────────────┐
│          LANGGRAPH ARCHITECTURE          │
├──────────────────────────────────────────┤
│                                          │
│  StateGraph                              │
│    ├─ Node: research                     │
│    │   └─ tools: [web_search,            │
│    │              research_own_company]   │
│    │   └─ model: claude-haiku            │
│    │                                     │
│    ├─ Edge: research → scope_gate        │
│    │   └─ interrupt(decision_request)    │
│    │                                     │
│    ├─ Node: draft_strategy               │
│    │   └─ tools: [update_strategy_section│
│    │              set_icp_tiers, ...]    │
│    │   └─ model: claude-sonnet           │
│    │                                     │
│    ├─ Edge: draft → review_gate          │
│    │   └─ interrupt(review_request)      │
│    │                                     │
│    ├─ Node: finalize                     │
│    │   └─ tools: [check_readiness]       │
│    │   └─ model: claude-haiku            │
│    │                                     │
│    └─ Conditional Edge: phase_router     │
│        └─ strategy → contacts → msgs    │
│                                          │
├──────────────────────────────────────────┤
│  LangSmith (cloud observability)         │
│    ├─ Trace every node execution         │
│    ├─ Token cost per step                │
│    ├─ Latency heatmaps                   │
│    ├─ Prompt versioning + A/B testing    │
│    ├─ Replay + debug failed runs         │
│    └─ Evaluation datasets                │
└──────────────────────────────────────────┘
```

#### LangGraph Agent Flow (replacing agent_executor.py)

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   research    │  ← web_search, research_own_company
                 │  (Haiku 4.5)  │
                 └───────┬───────┘
                         │
                    ┌────┴────┐
                    │ Found   │
                    │ multiple│──── yes ────┐
                    │ scopes? │             │
                    └────┬────┘             ▼
                     no  │          ┌──────────────┐
                         │          │  INTERRUPT:  │
                         │          │  scope_gate  │
                         │          │  (user picks)│
                         │          └──────┬───────┘
                         │                 │
                         ▼◄────────────────┘
                 ┌───────────────┐
                 │   position    │  ← analyze competitors, draft VP
                 │ (Sonnet 4.6)  │
                 └───────┬───────┘
                         │
                    ┌────┴────┐
                    │ Multiple│
                    │  ICP    │──── yes ────┐
                    │ options?│             │
                    └────┬────┘             ▼
                     no  │          ┌──────────────┐
                         │          │  INTERRUPT:  │
                         │          │direction_gate│
                         │          │  (user picks)│
                         │          └──────┬───────┘
                         │                 │
                         ▼◄────────────────┘
                 ┌───────────────┐
                 │    draft      │  ← update_strategy_section ×7
                 │ (Sonnet 4.6)  │    set_icp_tiers, set_personas
                 └───────┬───────┘
                         │
                         ▼
                 ┌──────────────┐
                 │  INTERRUPT:  │
                 │ review_gate  │
                 │ (user reviews│
                 │  draft)      │
                 └──────┬───────┘
                        │
                        ▼
                 ┌───────────────┐
                 │   finalize    │  ← check_readiness, messaging
                 │  (Haiku 4.5)  │
                 └───────┬───────┘
                         │
                         ▼
                    ┌─────────┐
                    │  DONE   │
                    └─────────┘
```

#### LangGraph Halt Gates (interrupt)

LangGraph has BUILT-IN interrupt support:

```python
from langgraph.graph import StateGraph, interrupt

def scope_gate(state):
    """Pause and ask user which product to focus on."""
    products = state["research_results"]["products"]
    if len(products) > 1:
        # This pauses the graph and sends options to the user
        decision = interrupt({
            "question": f"Found {len(products)} products. Focus on which?",
            "options": [p["name"] for p in products],
            "gate_type": "scope"
        })
        state["scope"] = decision
    return state
```

The graph pauses at `interrupt()`, serializes state, and resumes when the user responds. No custom protocol needed.

#### LangSmith Observability

What you'd get for free:

```
┌─────────────────────────────────────────────────┐
│  LangSmith Trace View                           │
├─────────────────────────────────────────────────┤
│                                                 │
│  Run: "Generate strategy for acme.com"          │
│  Duration: 47.2s | Tokens: 28,450 | Cost: $0.08 │
│                                                 │
│  ┌─ research (Haiku)          8.2s   4,200 tok  │
│  │  ├─ web_search             2.1s              │
│  │  └─ research_own_company   5.8s              │
│  │                                              │
│  ├─ scope_gate (interrupt)   12.0s   (waiting)  │
│  │  └─ User chose: "DataFlow only"              │
│  │                                              │
│  ├─ position (Sonnet)        11.3s   8,900 tok  │
│  │  └─ update_strategy_section ×2               │
│  │                                              │
│  ├─ direction_gate (interrupt) 8.1s  (waiting)  │
│  │  └─ User chose: "Segment A"                  │
│  │                                              │
│  └─ draft (Sonnet)           15.6s  15,350 tok  │
│     ├─ update_strategy_section ×5               │
│     ├─ set_icp_tiers                            │
│     └─ set_buyer_personas                       │
│                                                 │
│  [Replay] [Compare] [Export] [Evaluate]         │
└─────────────────────────────────────────────────┘
```

Features:
- **Trace tree**: see every node, tool call, and LLM invocation
- **Token costs**: per-step and cumulative
- **Latency**: identify bottlenecks
- **Prompt playground**: test prompt changes against real conversations
- **Evaluation**: run test datasets against new prompt versions
- **Comparison**: A/B test Haiku vs Sonnet on same inputs

#### Migration Path: Custom → LangGraph

```
PHASE   WHAT                              EFFORT   RISK
─────   ────                              ──────   ────
  1     Add langgraph + langsmith deps    1 hour   None
  2     Wrap existing tools as LG tools   4 hours  Low
  3     Model agent_executor as graph     2 days   Medium
  4     Wire SSE streaming to LG events   1 day    Medium
  5     Add interrupt nodes (halt gates)  1 day    Low
  6     Connect LangSmith tracing         2 hours  None
  7     Phase-filtered tool routing       4 hours  Low
  8     Multi-model nodes                 4 hours  Low
  9     Remove old executor code          2 hours  None
─────                                     ──────
TOTAL                                     ~1 week
```

Phase 1-2 are non-breaking — old code keeps working. Phase 3 is the main migration. Phases 4-9 can be done incrementally.

**Pros:**
- Halt gates built in (`interrupt()`)
- Observability out of the box (LangSmith)
- Graph visualization of agent flow
- State management with typed schemas
- Multi-model routing per node
- Community patterns for common agent architectures
- Replay/debug failed conversations
- Prompt versioning and A/B testing

**Cons:**
- New dependency (langchain-core, langgraph, langsmith)
- Abstraction overhead — LangChain has deep class hierarchies
- SSE streaming needs rewiring (LangGraph uses async iterators, not generators)
- Learning curve for graph concepts
- LangSmith is a paid cloud service ($39/mo dev, usage-based for prod)
- Framework updates can break things
- Less control over exact API call format

### Option C: Anthropic Agent SDK (claude_agent_sdk)

Anthropic's own lightweight agent framework. Thinner than LangGraph, Anthropic-native.

```
┌──────────────────────────────────────────┐
│       ANTHROPIC AGENT SDK                │
├──────────────────────────────────────────┤
│  Agent(                                  │
│    model="claude-sonnet-4-6",            │
│    tools=[tool1, tool2, ...],            │
│    system_prompt="...",                   │
│    max_turns=25,                          │
│  )                                       │
│                                          │
│  result = agent.run("Generate strategy") │
│                                          │
│  # Streaming via callbacks               │
│  for event in agent.stream(...):         │
│    if event.type == "tool_use": ...      │
│    if event.type == "text": ...          │
├──────────────────────────────────────────┤
│  Lines to replace executor:   ~100       │
│  Halt gates:        Not built in         │
│  Multi-model:       Manual               │
│  Observability:     Basic callbacks      │
│  State machine:     No (simple loop)     │
│  Graph viz:         No                   │
└──────────────────────────────────────────┘
```

**Pros:**
- Minimal abstraction — thin wrapper around Messages API
- Native Anthropic support (prompt caching, tool use, streaming)
- ~100 lines to replace executor
- No LangChain dependency bloat
- Easy to understand and debug

**Cons:**
- No halt gates (same problem as current custom code)
- No observability platform (DIY tracing)
- No graph-based flow control
- No multi-model routing
- Simple loop, not a state machine — doesn't solve the architectural needs
- Relatively new, less community patterns

### Recommendation

```
┌─────────────────────────────────────────────────────────┐
│                    DECISION MATRIX                       │
├──────────────┬──────────┬───────────┬───────────────────┤
│ Criterion    │ Custom   │ LangGraph │ Agent SDK         │
├──────────────┼──────────┼───────────┼───────────────────┤
│ Halt gates   │ Build ⚠️  │ Built in ✅│ Build ⚠️           │
│ Observability│ DIY 🔴   │ LangSmith✅│ DIY 🔴            │
│ Multi-model  │ Build ⚠️  │ Built in ✅│ Manual ⚠️          │
│ Migration    │ None ✅  │ ~1 week ⚠️ │ ~2 days ✅        │
│ Complexity   │ Grows 🔴 │ Managed ✅ │ Grows 🔴          │
│ Control      │ Full ✅  │ Good ✅   │ Full ✅            │
│ Lock-in      │ None ✅  │ Medium ⚠️ │ Anthropic-only ⚠️ │
│ Cost         │ Free ✅  │ LangSmith$│ Free ✅            │
│ Future-proof │ Manual 🔴│ Active ✅  │ Early stage ⚠️    │
├──────────────┼──────────┼───────────┼───────────────────┤
│ SCORE        │ 5/9      │ 7/9      │ 5/9               │
└──────────────┴──────────┴───────────┴───────────────────┘
```

**Recommended: LangGraph + LangSmith**

The deciding factors:
1. **Halt gates** are your #1 architectural need — LangGraph has them built in
2. **Observability** is critical as the agent grows — LangSmith is the best-in-class tracing platform
3. **Multi-model routing** (Haiku for Q&A, Sonnet for generation) is trivial in LangGraph
4. **Migration is manageable** — ~1 week, can be done incrementally

The lock-in risk is real but mitigable — LangGraph tools are standard Python functions, easily portable. The main lock-in is LangSmith for tracing, but you can self-host LangSmith OSS or switch to OpenTelemetry later.

### Hybrid Approach (if lock-in is a concern)

```
KEEP CUSTOM:             ADOPT FROM LANGGRAPH:
────────────             ─────────────────────
Flask routes             StateGraph for agent flow
SSE streaming adapter    interrupt() for halt gates
Tool implementations     LangSmith for tracing
Prompt templates         Conditional edges for routing
                         Typed state schemas
```

Wrap LangGraph inside your existing Flask route. Your SSE generator yields events from LangGraph's async iterator. Tools stay as plain Python functions — just registered with LangGraph's `@tool` decorator. The migration is internal — no API changes, no frontend changes.

## 11. Open Questions for Discussion

1. **Model upgrade**: Should strategy generation use Sonnet instead of Haiku? Better reasoning but 10x cost. Could use Haiku for simple Q&A and Sonnet for generation.

2. **Prompt caching priority**: Should we implement caching first (quick win, ~50% token savings) or restructure the prompt layers first (bigger change, better architecture)?

3. **Tool routing**: Rules-based (keyword matching) or LLM-based (lightweight classifier) for intent detection?

4. **Document context**: Option A (lazy load), B (relevant section + status), or C (compressed summary)? B is recommended but adds complexity.

5. **Conversation memory**: Simple window + summary, or more sophisticated retrieval (embed messages, retrieve relevant ones)?

6. **Streaming granularity**: Current 10-char chunks from backend. Should we switch to word-level or sentence-level streaming for more natural typewriter effect?

7. **Multi-model orchestration**: Haiku for routing + Sonnet for generation? Or keep single model?

8. **Halt gate implementation**: Tool-based (`request_user_decision`) or prompt-instructed? Tool-based is more reliable but requires backend + frontend changes.

9. **Gate frequency**: How many confirmation gates per strategy generation? 3-4 recommended, but user may want faster autonomous runs for subsequent strategies.

10. **Decision persistence**: Should user decisions at gates be remembered for future strategies? (e.g., "always focus on primary product only")

11. **LangSmith cost**: At scale (1000 conversations/month), LangSmith costs ~$100-300/mo. Worth it for observability, or build lightweight tracing?

12. **Migration timing**: Adopt LangGraph now (before halt gates) or after implementing halt gates custom (then migrate)?

13. **Self-hosted vs cloud LangSmith**: LangSmith OSS can be self-hosted but lacks some features. Start with cloud, consider self-hosting later?
