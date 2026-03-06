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

## 9. Open Questions for Discussion

1. **Model upgrade**: Should strategy generation use Sonnet instead of Haiku? Better reasoning but 10x cost. Could use Haiku for simple Q&A and Sonnet for generation.

2. **Prompt caching priority**: Should we implement caching first (quick win, ~50% token savings) or restructure the prompt layers first (bigger change, better architecture)?

3. **Tool routing**: Rules-based (keyword matching) or LLM-based (lightweight classifier) for intent detection?

4. **Document context**: Option A (lazy load), B (relevant section + status), or C (compressed summary)? B is recommended but adds complexity.

5. **Conversation memory**: Simple window + summary, or more sophisticated retrieval (embed messages, retrieve relevant ones)?

6. **Streaming granularity**: Current 10-char chunks from backend. Should we switch to word-level or sentence-level streaming for more natural typewriter effect?

7. **Multi-model orchestration**: Haiku for routing + Sonnet for generation? Or keep single model?
