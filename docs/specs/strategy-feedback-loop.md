# BL-058: Strategy Feedback Loop — Scoring, Conflict Detection & Gap Analysis

**Status**: Spec'd
**Priority**: Should Have
**Effort**: L
**Depends on**: AGENT (agent-ready chat), BL-055/BL-056 (token cost display)
**Theme**: Playbook Core

---

## Problem Statement

Strategies are created but never evaluated. Users write an ICP section, draft messaging, define channels — but have no way to know if their strategy is good, internally consistent, or missing critical elements. The AI helps create content but never steps back to assess the whole picture.

This is the gap between "AI as content generator" and "AI as proactive strategist." A real CMO would review the strategy, score it on multiple dimensions, catch contradictions, and flag blind spots. Our AI should do the same.

Without evaluation:
- Users don't know which sections need more work
- Internal contradictions go unnoticed (e.g., targeting enterprise but planning only social media outreach)
- Missing sections aren't surfaced until it's too late
- There's no sense of progress — users can't see their strategy improving over time

---

## Scoring Framework

### Dimensions

Each dimension is scored 1-10 with a confidence level and actionable feedback.

| Dimension | What It Measures | Weight |
|-----------|-----------------|--------|
| ICP Clarity | Specificity of ideal customer: industry, size, geography, triggers, disqualifiers | 15% |
| Market Positioning | Clear differentiation from competitors, defensible angle | 10% |
| Channel Strategy | Channels match ICP and personas, cadence defined, realistic for team size | 15% |
| Messaging Strength | Pain-point alignment, value prop clarity, proof points, tone consistency | 15% |
| Competitive Differentiation | Awareness of landscape, clear "why us" vs alternatives | 10% |
| Value Proposition | Specificity, relevance to ICP pain points, quantified outcomes | 10% |
| Feasibility | Realistic for team size, budget, and timeline. Actionable 90-day plan | 10% |
| Completeness | All 8 strategy sections present with substantive content | 15% |

### Scoring Rubric

**ICP Clarity** (example — similar rubric applies to each dimension):

| Score | Criteria |
|-------|----------|
| 1-3 | Vague or missing. "B2B companies" with no specifics. No triggers or disqualifiers defined. |
| 4-6 | Partial. Industry and size defined but geography/triggers/disqualifiers missing or generic. |
| 7-8 | Solid. All ICP dimensions defined with specifics. Some quantification (revenue range, employee count). |
| 9-10 | Exceptional. Highly specific with data-backed triggers, clear disqualifiers, tiered segments, and enrichment-verified signals. |

**Confidence Levels**:
- **High**: Enough data in the strategy to make a definitive assessment
- **Medium**: Partial data; score is an estimate based on available content
- **Low**: Minimal content for this dimension; score is largely inferred

### Overall Score

Weighted average of all dimensions, displayed as both a number (0-100) and a letter grade:

| Grade | Range | Meaning |
|-------|-------|---------|
| A | 85-100 | Strong strategy, ready for execution |
| B | 70-84 | Good foundation, minor gaps to address |
| C | 55-69 | Workable but needs significant improvement |
| D | 40-54 | Weak in multiple areas, major revision needed |
| F | 0-39 | Incomplete or fundamentally flawed |

---

## Conflict Detection

### Conflict Types

| Type | Description | Severity |
|------|-------------|----------|
| ICP vs Channel Mismatch | Targeting enterprise CxOs but planning only social media; targeting SMB but planning account-based marketing | Critical |
| Positioning vs Messaging Tone | Positioning as premium/strategic but messaging uses discount language or transactional tone | Critical |
| Multi-Segment Without Differentiation | ICP defines 3+ distinct segments but messaging/channel strategy doesn't differentiate between them | Warning |
| Budget vs Ambition Gap | 90-day plan targets 100 meetings but channel strategy is single-channel with no automation | Warning |
| Timeline Conflicts | Plan assumes outcomes before prerequisites are complete (e.g., "generate leads in Week 1" when content isn't created until Week 3) | Warning |
| Geography vs Language | Targeting DACH region but all messaging is English-only | Info |
| Persona vs Channel | Key persona is "VP Operations" but no direct outreach channel defined (only content marketing) | Warning |

### Conflict Structure

Each detected conflict includes:
- **type**: One of the types above
- **severity**: critical / warning / info
- **description**: Human-readable explanation
- **evidence**: Direct quotes or section references from the strategy document
- **resolution**: Specific suggestion to resolve the conflict

Example:
```json
{
  "type": "icp_channel_mismatch",
  "severity": "critical",
  "description": "Your ICP targets enterprise CTOs (500+ employees) but your only defined channel is LinkedIn organic posts. Enterprise decision-makers rarely engage with organic content from unknown companies.",
  "evidence": {
    "icp_section": "Company Size: 500+ employees, Target: CTO/VP Engineering",
    "channel_section": "Primary: LinkedIn organic posts"
  },
  "resolution": "Add LinkedIn direct outreach and consider account-based marketing (ABM) with personalized touchpoints. Enterprise sales typically requires 7-12 touches across multiple channels."
}
```

---

## Gap Analysis

### Gap Categories

1. **Missing Sections**: Strategy sections with no content or only placeholder text
2. **Weak Areas**: Sections present but insufficiently developed (e.g., ICP says "B2B companies" with no further specifics)
3. **Unexplored Opportunities**: Based on enrichment data that hasn't been incorporated into the strategy (e.g., company has hiring signals data but strategy doesn't reference timing-based outreach)
4. **Template Comparison**: How complete is this strategy vs the "ideal" 8-section template

### "Complete Strategy" Checklist

Each of the 8 sections (`STRATEGY_SECTIONS` from `playbook_service.py`) has a completeness checklist:

| Section | Required Elements |
|---------|------------------|
| Executive Summary | Objective stated, company context, market context |
| ICP | Industry, company size, geography, triggers, disqualifiers (at least 3 of 5) |
| Buyer Personas | At least 2 personas with titles, pain points, and goals |
| Value Proposition | Core value prop, 2+ proof points, differentiation statement |
| Competitive Positioning | 2+ competitors named, differentiation for each |
| Channel Strategy | Primary + secondary channels, cadence, rationale for channel choice |
| Messaging Framework | Pain-led messaging, 2+ angles, tone defined |
| Success Metrics | At least 2 quantified targets (reply rate, meeting rate, pipeline, timeline) |

### Gap Structure

```json
{
  "type": "missing_section",
  "section": "Competitive Positioning",
  "severity": "high",
  "description": "No competitive positioning section found. Without knowing the competitive landscape, messaging can't differentiate effectively.",
  "suggestion": "Ask the AI: 'Help me map our competitive landscape' — it can use your enrichment data to identify likely competitors."
}
```

---

## Trigger Mechanisms

### User Triggers

1. **UI Button**: "Evaluate Strategy" button in the playbook top bar. Opens the evaluation panel.
2. **Chat Commands**: Natural language triggers:
   - "Score my strategy"
   - "Find conflicts in my strategy"
   - "What's missing from my strategy?"
   - "How can I improve my strategy?"
   - "Rate my ICP section"

### AI Proactive Triggers

The AI suggests running an evaluation when:
- **After initial draft**: Strategy document goes from empty to having 3+ sections filled
- **After major edits**: Document version increases by 3+ since last evaluation
- **Phase transition**: User is about to move from Strategy phase to Contacts phase
- **Explicit gaps visible**: AI detects during chat that a section is weak or missing

Proactive suggestion format (in chat):
> "Your strategy has grown significantly since the last evaluation. Want me to run a quick score check? I'll look at ICP clarity, messaging strength, and flag any conflicts."

### Lightweight Auto-Evaluation

On every strategy save (debounced, max once per 5 minutes):
- Run completeness check only (no LLM call — pure section detection)
- Update a `completeness_score` field on the strategy document
- Display as a subtle progress indicator in the UI

---

## Data Model

### New Table: `strategy_evaluations`

```sql
CREATE TABLE strategy_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    strategy_id UUID NOT NULL REFERENCES strategy_documents(id),
    triggered_by VARCHAR(20) NOT NULL,  -- 'user', 'ai', 'auto'
    trigger_context TEXT,               -- e.g., 'phase_transition', 'chat_command'
    overall_score NUMERIC(5, 2),        -- 0-100
    overall_grade VARCHAR(2),           -- A, B, C, D, F
    scores JSONB NOT NULL DEFAULT '{}', -- per-dimension scores
    conflicts JSONB NOT NULL DEFAULT '[]',
    gaps JSONB NOT NULL DEFAULT '[]',
    strategy_version INTEGER NOT NULL,  -- version of strategy at evaluation time
    credit_cost NUMERIC(10, 2) DEFAULT 0,  -- credits consumed
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_strategy_evaluations_strategy ON strategy_evaluations(strategy_id);
CREATE INDEX idx_strategy_evaluations_tenant ON strategy_evaluations(tenant_id);
```

### `scores` JSONB Structure

```json
{
  "icp_clarity": {
    "score": 7,
    "confidence": "high",
    "explanation": "Well-defined industry (Financial Services) and company size (200-2000 employees). Missing geographic focus and explicit disqualifiers.",
    "suggestion": "Add geographic targeting (you mention DACH in messaging but not in ICP) and define 3-5 disqualifiers to help filter prospects."
  },
  "market_positioning": { ... },
  "channel_strategy": { ... },
  "messaging_strength": { ... },
  "competitive_differentiation": { ... },
  "value_proposition": { ... },
  "feasibility": { ... },
  "completeness": { ... }
}
```

### Changes to `strategy_documents`

Add column:
```sql
ALTER TABLE strategy_documents ADD COLUMN completeness_score SMALLINT DEFAULT 0;
```

Updated on every save (lightweight, no LLM) based on section detection.

---

## Chat Integration

### Chat Tools (Requires AGENT)

| Tool | Description | Trigger |
|------|-------------|---------|
| `evaluate_strategy` | Run full evaluation (all dimensions, conflicts, gaps). Returns structured results. | "Score my strategy", "Evaluate my strategy" |
| `find_conflicts` | Run conflict detection only. Faster, cheaper. | "Find conflicts", "Check for contradictions" |
| `analyze_gaps` | Run gap analysis only. | "What's missing?", "Find gaps" |
| `get_score_history` | Return past evaluations to show improvement over time. | "How has my strategy improved?", "Show score history" |
| `score_section(section_name)` | Score a single dimension in detail. | "Rate my ICP", "How's my messaging?" |

### Tool Response Format

The AI receives structured evaluation data and presents it conversationally:

> **Strategy Score: 72/100 (B)**
>
> **Strongest areas:**
> - ICP Clarity: 8/10 — Well-defined with specific industry, size, and triggers
> - Messaging Strength: 7/10 — Good pain-point alignment with proof points
>
> **Needs work:**
> - Channel Strategy: 4/10 — Only LinkedIn defined, no secondary channels
> - Competitive Positioning: 3/10 — No competitors mentioned
>
> **Conflicts found (1 critical):**
> - Your ICP targets enterprise (500+ employees) but your only channel is LinkedIn organic. Enterprise requires multi-touch outreach.
>
> **Missing:**
> - No Success Metrics section — add reply rate and meeting targets
> - No competitive analysis — shall I help map your competitive landscape?

---

## UI Design

### Evaluation Panel

Triggered by the "Evaluate" button or after an AI evaluation. Slides in as a right panel (replacing or overlaying the chat panel).

**Layout:**

1. **Header**: Overall score (large number + letter grade), evaluated timestamp
2. **Radar Chart**: 8-axis spider chart showing dimension scores (1-10 scale)
3. **Dimension Cards**: Expandable cards for each dimension showing score, confidence badge, explanation, and suggestion
4. **Conflicts Section**: Severity-colored cards (red=critical, yellow=warning, blue=info) with evidence quotes and resolution suggestions
5. **Gaps Checklist**: Section-by-section checklist with check/cross icons and gap descriptions
6. **Trend Chart**: Line chart showing overall score over time (from `strategy_evaluations` history)
7. **Credit Cost**: "This evaluation used X credits" (per BL-056 display rules — credits only, never USD)

### Completeness Indicator (Always Visible)

Small progress ring in the playbook top bar showing `completeness_score` (0-100%). Updates on every save without LLM calls. Clicking it opens the full evaluation panel.

---

## Implementation Approach

### LLM Evaluation Prompt

The evaluation is a single LLM call with the full strategy document + enrichment context. System prompt instructs the model to return structured JSON matching the scores/conflicts/gaps schema.

Key prompt elements:
- Provide the scoring rubric for each dimension
- Include enrichment data as context (so the AI can identify unexplored opportunities)
- Require evidence quotes from the strategy for each score and conflict
- Require actionable, specific suggestions (not "improve your ICP" but "add geographic targeting — you mention DACH in messaging but not in ICP")

### Cost Estimation

- Full evaluation: ~2,000-4,000 input tokens (strategy doc + prompt) + ~2,000 output tokens
- Estimated cost: 200-500 credits per evaluation (varies by strategy length and model)
- Single-section scoring: ~50-150 credits
- Conflict-only check: ~100-300 credits
- Gap analysis only: ~100-200 credits (partially rule-based, less LLM)
- Completeness check: 0 credits (pure section detection, no LLM)

---

## User Stories & Acceptance Criteria

### US-1: User triggers strategy evaluation

**Given** a user has a strategy document with content in 3+ sections
**When** they click "Evaluate Strategy" or ask the AI "score my strategy"
**Then** a full evaluation runs and displays:
- Overall score (0-100) with letter grade
- Per-dimension scores with explanations and suggestions
- Conflicts with severity, evidence, and resolution
- Gaps with section references and suggestions
- Credit cost of the evaluation

### US-2: AI proactively suggests evaluation

**Given** a strategy document has been significantly edited (3+ version bumps since last evaluation)
**When** the user sends a chat message
**Then** the AI suggests running an evaluation before responding to the message

### US-3: Score history shows improvement

**Given** a user has run 3+ evaluations over time
**When** they ask "how has my strategy improved?" or view the evaluation panel
**Then** a trend chart shows overall score over time with timestamps

### US-4: Conflict detection catches ICP-channel mismatch

**Given** a strategy with ICP targeting "enterprise companies, 500+ employees"
**And** channel strategy listing only "LinkedIn organic posts"
**When** conflict detection runs
**Then** a critical conflict is flagged with evidence from both sections and a resolution suggesting multi-touch ABM

### US-5: Gap analysis identifies missing sections

**Given** a strategy with 5 out of 8 sections filled
**When** gap analysis runs
**Then** the 3 missing sections are listed with descriptions of what should be in each and offers to help draft them

### US-6: Lightweight completeness updates on save

**Given** the user edits the strategy document
**When** auto-save fires
**Then** the completeness score updates in the top bar without any LLM call or credit cost

### US-7: Single-section deep dive

**Given** a user asks "rate my ICP section"
**When** the section-specific scoring tool runs
**Then** a detailed assessment of just the ICP is returned with score, confidence, specific strengths, weaknesses, and improvement suggestions

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Empty strategy | Return score 0, grade F, all gaps flagged as "missing". Suggest starting with Executive Summary or ICP. |
| Very short strategy (<100 words) | Flag as "too early to evaluate meaningfully." Run completeness check only (free). Suggest filling 3+ sections first. |
| Single section only | Score that section; mark all others as gaps. Overall score reflects heavy incompleteness penalty. |
| Strategy with only placeholder text | Detect `_Fill based on...` and `Define your...` patterns as placeholders, not real content. Score accordingly. |
| No enrichment data | Skip "unexplored opportunities" gap type. Note in evaluation that enrichment research could improve recommendations. |
| Conflicting user preferences vs AI | AI flags but defers to user. "Your channel strategy focuses on cold calling, which differs from the LinkedIn-first approach I'd recommend for this ICP. This is a preference, not a flaw." |
| Rapid re-evaluation (within 1 minute) | Return cached previous evaluation if strategy version hasn't changed. |

---

## Dependencies

| Dependency | Required For | Status |
|-----------|--------------|--------|
| AGENT (agent-ready chat) | Chat tools (`evaluate_strategy`, etc.) | Idea |
| BL-055 (LLM cost logging) | Accurate credit cost tracking for evaluations | Spec'd |
| BL-056 (Token credit system) | Credit cost display in evaluation panel | Spec'd |
| `strategy_documents` table | Already exists | Done |
| `StrategyChatMessage` | Chat integration | Done |
| Enrichment data | Used for "unexplored opportunities" gap detection | Done |

### Phasing

**Phase 1 (No dependencies):**
- Completeness check (rule-based, no LLM, 0 credits)
- `completeness_score` column on `strategy_documents`
- Completeness indicator in top bar
- `strategy_evaluations` table migration

**Phase 2 (Requires LLM, no AGENT):**
- Full evaluation via API endpoint (`POST /api/playbook/evaluate`)
- Evaluation panel UI (radar chart, dimension cards, conflicts, gaps)
- Score history and trend chart

**Phase 3 (Requires AGENT):**
- Chat tools: `evaluate_strategy`, `find_conflicts`, `analyze_gaps`, `get_score_history`, `score_section`
- AI proactive triggers
