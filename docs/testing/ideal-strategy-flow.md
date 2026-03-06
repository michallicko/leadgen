# Ideal Strategy Generation Flow -- Step-by-Step Screenplay

> **Purpose**: This document scripts the ideal user experience from the moment the user
> clicks "Get Started" on the onboarding form through to a fully populated strategy
> document with ICP tiers, buyer personas, and a Strategic Brief in chat.
>
> **Company used**: unitedarts.cz (event production company expanding into Germany)
> **Objective entered**: "Generate qualified B2B leads for our event production services in the DACH market"
> **Challenge type**: auto (inferred from objective)

---

## Pre-Conditions

- The user has logged in and navigated to `/{namespace}/playbook/strategy`.
- The strategy document is empty (first visit).
- The onboarding form is displayed (PlaybookOnboarding component).
- The user has filled in:
  - **Company domain**: `unitedarts.cz`
  - **GTM objective**: "Generate qualified B2B leads for our event production services in the DACH market"

---

## Act 1: Onboarding Trigger (T+0s to T+2s)

### [T+0.0s] USER ACTION: Clicks "Get Started"

```
[WHAT HAPPENS]:
  1. handleOnboardGenerate fires
  2. Objective saved to document via PUT /api/playbook {objective: "..."}
  3. Research triggered via POST /api/playbook/research {domains: ["unitedarts.cz"], primary_domain: "unitedarts.cz", challenge_type: "auto"}
  4. Research runs in a background thread (non-blocking)
  5. Chat message sent immediately via POST /api/playbook/chat (SSE streaming)
     Prompt: "Generate a complete GTM strategy playbook for my company (unitedarts.cz).
              GTM objective: Generate qualified B2B leads for our event production
              services in the DACH market. Primary challenge: Auto. Use the company
              research data provided in your context to write the strategy..."
  6. setSkipped(true) — onboarding form disappears, split-view appears

[CHAT SHOWS]:
  - User message is hidden (is_onboarding_trigger=true, extra.hidden=true)
  - ThinkingIndicator appears: pulsing cyan dot + "Thinking..."

[EDITOR SHOWS]:
  - Empty document with no content (blank state)
  - The split-view layout is visible: editor ~60% left, chat ~40% right

[BACKEND]:
  - Background thread: ResearchService.research_company() begins
    - Fetches unitedarts.cz homepage HTML
    - Parses company info from website
    - Calls Perplexity for market context, competitors, industry trends
    - Saves results to enrichment tables (L1, profile, signals, market)
  - Chat endpoint: Detects research is in_progress, polls every 2s for up to 45s
    waiting for enrichment data to land before calling Claude
```

### [T+0.5s] FRONTEND STATE: Split-view transition

```
[CHAT SHOWS]:
  - ThinkingIndicator: pulsing dot + "Thinking..."
  - (Research is running in background; chat endpoint is waiting for it)

[EDITOR SHOWS]:
  - Empty document, placeholder text visible: "Your strategy will appear here..."
  - Strategy sub-tabs visible but inactive: [Strategy Overview] [ICP Tiers] [Buyer Personas]
```

---

## Act 2: Research Completes, AI Begins (T+10s to T+25s)

### [T+10s to T+20s] BACKEND: Research pipeline completes

```
[WHAT HAPPENS]:
  - ResearchService finishes all steps:
    1. Website fetch + parse (2-3s)
    2. Perplexity web search for company context (3-5s)
    3. Synthesis into structured enrichment profile (2-3s)
    4. Save to CompanyEnrichmentProfile, CompanyEnrichmentSignals,
       CompanyEnrichmentMarket tables (1s)
    5. Company status set to terminal state
  - Progress events saved as chat messages (tool cards for research steps)
  - Total research time: ~10-20s

[CHAT SHOWS]:
  - ThinkingIndicator still showing (chat endpoint still waiting)
  - Research progress tool cards may appear via polling (every 3s):
    - "Fetching unitedarts.cz..." (tool card)
    - "Analyzing market position..." (tool card)

[EDITOR SHOWS]:
  - Still empty — waiting for AI to start writing
```

### [T+20s] BACKEND: Chat endpoint detects research complete, calls Claude

```
[WHAT HAPPENS]:
  - Chat endpoint poll loop detects company.status is no longer in_progress
  - _load_enrichment_data() loads all enrichment data
  - build_system_prompt() constructs prompt WITH enrichment data:
    - Company profile (name, industry, size, HQ)
    - Company overview from research
    - Products & technology
    - Market & competition (competitors, customer segments)
    - Pain points & opportunities
    - Market signals (digital initiatives, hiring, AI adoption)
  - Claude API call begins with full context + tools

[CHAT SHOWS]:
  - ThinkingIndicator: still showing "Thinking..."
```

---

## Act 3: AI First Response — Warm One-Liner (T+22s)

### [T+22s] SSE EVENT: chunk (intermediate text before tool calls)

```
[WHAT HAPPENS]:
  - Claude's first response includes text + tool_use blocks
  - Intermediate text chunk is streamed first

[CHAT SHOWS]:
  - ThinkingIndicator disappears
  - StreamingBubble appears with the warm one-liner:

    "Building your event production strategy for unitedarts.cz to support
     your expansion into the German market..."

  - This text streams in character-by-character (typewriter effect)
  - The streaming bubble is the LAST item in chat (always at bottom)

[EDITOR SHOWS]:
  - Still empty — no tool calls executed yet
```

---

## Act 4: Web Research Phase (T+23s to T+45s)

The AI uses web_search to supplement the enrichment data with fresh market intelligence.
With enrichment data already loaded in the system prompt, the AI should NOT search for
basic company info. Instead, web_search is used for:
- Industry trends specific to event production in DACH
- Competitor analysis (specific DACH-market competitors)
- Market sizing and opportunity data

### [T+23s] SSE EVENT: tool_start — web_search #1

```
[WHAT HAPPENS]:
  - Claude calls web_search({"query": "event production industry DACH market trends 2026"})

[CHAT SHOWS]:
  - ThinkingIndicator appears below the warm one-liner:
    pulsing dot + "Searching the web..."
  - The warm one-liner stays visible above

[EDITOR SHOWS]:
  - Still empty
```

### [T+26s] SSE EVENT: tool_result — web_search #1

```
[WHAT HAPPENS]:
  - Perplexity returns market data: event industry growth in DACH, key trends,
    market size, digital transformation in events
  - Duration: ~3s

[CHAT SHOWS]:
  - Tool card appears (collapsed): "Web search" with green checkmark
    Expandable to show query + answer preview
  - ThinkingIndicator moves below the tool card (still last item)

[EDITOR SHOWS]:
  - Still empty
```

### [T+26s] SSE EVENT: tool_start — web_search #2

```
[WHAT HAPPENS]:
  - Claude calls web_search({"query": "B2B event production agencies Germany competitors market leaders"})

[CHAT SHOWS]:
  - ThinkingIndicator updates: "Searching the web..."
  - Previous tool card visible above

[EDITOR SHOWS]:
  - Still empty
```

### [T+29s] SSE EVENT: tool_result — web_search #2

```
[WHAT HAPPENS]:
  - Perplexity returns competitor data: top agencies in DACH, their positioning,
    service differentiators

[CHAT SHOWS]:
  - Second tool card appears: "Web search" with green checkmark
  - ThinkingIndicator still at bottom: "Researching your market..."

[EDITOR SHOWS]:
  - Still empty
```

### [T+29s] SSE EVENT: tool_start — web_search #3 (optional)

```
[WHAT HAPPENS]:
  - Claude calls web_search({"query": "B2B lead generation strategies for event production companies"})
  - This search fills gaps in channel strategy and messaging angles

[CHAT SHOWS]:
  - ThinkingIndicator: "Searching the web..."

[EDITOR SHOWS]:
  - Still empty
```

### [T+32s] SSE EVENT: tool_result — web_search #3

```
[CHAT SHOWS]:
  - Third tool card appears
  - ThinkingIndicator updates: "Writing your strategy..."
  - All three search tool cards visible in sequence above

[EDITOR SHOWS]:
  - Still empty — about to change
```

---

## Act 5: Strategy Section Writing Phase (T+33s to T+90s)

This is where the user sees the most satisfying progress — sections appear one by one
in the editor, each with specific, researched content. The AI writes all 7 sections
in sequence using update_strategy_section tool calls.

### [T+33s] SSE EVENT: tool_start — get_strategy_document

```
[WHAT HAPPENS]:
  - Claude calls get_strategy_document to see current state (empty template)

[CHAT SHOWS]:
  - ThinkingIndicator: "Reading strategy..."
  - (This is a quick internal check — no visible tool card needed)

[EDITOR SHOWS]:
  - Still empty
```

### [T+33.5s] SSE EVENT: tool_result — get_strategy_document

```
[CHAT SHOWS]:
  - Tool card (minimal): "Read strategy document" — checkmark
  - ThinkingIndicator: "Writing your strategy..."
```

### [T+34s] SSE EVENT: tool_start — update_strategy_section (Executive Summary)

```
[WHAT HAPPENS]:
  - Claude calls update_strategy_section({
      section: "Executive Summary",
      content: "United Arts (unitedarts.cz) is a Prague-based event production company
                specializing in corporate events, conferences, and cultural productions.
                With a strong domestic presence in the Czech Republic, the company is
                now positioned to expand into the German-speaking (DACH) market...
                [150-250 words of specific, researched content]"
    })

[CHAT SHOWS]:
  - ThinkingIndicator: "Updating Executive Summary..."
  - Tool cards from research visible above

[EDITOR SHOWS]:
  - Still empty (tool executing)
```

### [T+34.5s] SSE EVENT: tool_result — update_strategy_section + section_update

```
[WHAT HAPPENS]:
  - Tool returns {success: true, section: "Executive Summary", version: 2}
  - section_update SSE event fires
  - Frontend receives onSectionUpdate callback
  - Document query invalidated — editor refreshes

[CHAT SHOWS]:
  - Tool card: "Updated Executive Summary" with green checkmark
  - ThinkingIndicator moves below: "Writing your strategy..."
  - Toast notification: "Section saved: Executive Summary"

[EDITOR SHOWS]:
  >>> FIRST VISIBLE CONTENT APPEARS <<<
  - "## Executive Summary" heading appears with full content below
  - The content is specific and references actual research:
    "United Arts (unitedarts.cz) is a Prague-based event production company..."
  - Smooth fade-in animation as content loads
  - Scroll position stays at top so user can read from the beginning
```

### [T+36s] SSE EVENT: tool_start — update_strategy_section (Value Proposition & Messaging)

```
[WHAT HAPPENS]:
  - Claude calls update_strategy_section({
      section: "Value Proposition & Messaging",
      content: "**Core Value Proposition**: United Arts combines Central European
                creativity with German-standard execution — delivering memorable
                corporate events at 20-30% lower cost than German agencies while
                maintaining the same production quality...

                **Key Messaging Pillars**:
                - **Cross-cultural expertise**: Bridging Czech creativity with DACH corporate expectations
                - **Cost advantage without compromise**: Premium production, competitive pricing
                - **End-to-end capability**: From concept to post-event analytics

                **Proof Points**:
                - [Research-grounded examples from enrichment data]
                - Track record with [specific client types from research]..."
    })

[CHAT SHOWS]:
  - ThinkingIndicator: "Updating Value Proposition & Messaging..."

[EDITOR SHOWS]:
  - Executive Summary fully visible
  - (New section being written)
```

### [T+37s] SSE EVENT: tool_result — update_strategy_section (Value Proposition)

```
[CHAT SHOWS]:
  - Tool card: "Updated Value Proposition & Messaging" — checkmark
  - Toast: "Section saved: Value Proposition & Messaging"

[EDITOR SHOWS]:
  >>> SECOND SECTION APPEARS <<<
  - "## Value Proposition & Messaging" heading + full content
  - User can now see TWO completed sections
  - Editor shows growing document — satisfying progress feeling
```

### [T+39s to T+40s] — update_strategy_section (Competitive Positioning)

```
[CHAT SHOWS]:
  - ThinkingIndicator: "Updating Competitive Positioning..."
  - Then: tool card with checkmark

[EDITOR SHOWS]:
  >>> THIRD SECTION APPEARS <<<
  - "## Competitive Positioning" with:
    - Competitive landscape table (from web_search data)
    - SWOT-style analysis specific to DACH expansion
    - Key differentiators vs. German agencies

  Content example:
  "### Competitive Landscape

  | Competitor | HQ | Strength | Vulnerability |
  |-----------|-----|----------|---------------|
  | Vok Dams | Germany | Market leader, enterprise focus | High cost, slow iteration |
  | Eventive | Austria | Creative excellence | Limited cross-border |
  | United Arts | Czech Republic | Cost-quality ratio, bilingual team | Unknown brand in DACH |

  **Positioning**: The 'bridge builder' — Central European creativity with DACH-grade reliability."
```

### [T+42s to T+43s] — update_strategy_section (Channel Strategy)

```
[EDITOR SHOWS]:
  >>> FOURTH SECTION APPEARS <<<
  - "## Channel Strategy" with:
    - Primary: LinkedIn (direct outreach to corporate event managers)
    - Secondary: Industry events/trade shows (IMEX, BOE)
    - Tertiary: Referral partnerships with German agencies
    - Channel rationale tied to ICP

  Each channel has: why, how, expected timeline, KPIs
```

### [T+45s to T+46s] — update_strategy_section (Messaging Framework)

```
[EDITOR SHOWS]:
  >>> FIFTH SECTION APPEARS <<<
  - "## Messaging Framework" with:
    - Cold outreach templates (LinkedIn, email)
    - Objection handling scripts
    - Subject line formulas
    - Follow-up cadence
    - Tone guidelines (professional, not salesy, European sensibility)
```

### [T+48s to T+49s] — update_strategy_section (Metrics & KPIs)

```
[EDITOR SHOWS]:
  >>> SIXTH SECTION APPEARS <<<
  - "## Metrics & KPIs" with:
    - Reply rate target: 15-25%
    - Meeting rate target: 5-10%
    - Pipeline goal: EUR 200K in 90 days
    - Leading indicators (LinkedIn acceptance rate, email open rate)
    - Lagging indicators (deals closed, revenue)
    - Weekly/monthly review cadence
```

### [T+51s to T+52s] — update_strategy_section (90-Day Action Plan)

```
[EDITOR SHOWS]:
  >>> SEVENTH (FINAL) SECTION APPEARS <<<
  - "## 90-Day Action Plan" with:

    "### Month 1: Foundation
    - [ ] Set up LinkedIn Sales Navigator for DACH
    - [ ] Create German-language company profile
    - [ ] Build initial prospect list (50 companies)
    - [ ] Develop 3 case study one-pagers for DACH audience

    ### Month 2: Outreach Launch
    - [ ] Begin LinkedIn outreach (20 new connections/week)
    - [ ] Launch email sequences to ICP-matched companies
    - [ ] Attend 1 industry event (BOE or similar)

    ### Month 3: Optimization
    - [ ] Analyze response rates, optimize messaging
    - [ ] Pursue warm leads to demo/proposal stage
    - [ ] Establish 2-3 referral partnerships"

[CHAT SHOWS]:
  - 7 tool cards visible (one per section), all with green checkmarks
  - ThinkingIndicator: "Setting up your ICP..."
  - Toast notifications have appeared for each section

  The user has watched the document grow from empty to 7 fully-written sections
  over ~20 seconds. This is the peak satisfaction moment.
```

**Timing summary for section writing**: ~18 seconds total (T+34s to T+52s)
Each section takes ~2-3s (1s for Claude to generate content + 0.5s tool execution + 0.5s frontend refresh)

---

## Act 6: ICP Tiers & Buyer Personas (T+53s to T+60s)

After writing all strategy sections, the AI populates the structured data tabs.
This happens automatically — the user does NOT need to click anything.

### [T+53s] SSE EVENT: tool_start — set_icp_tiers

```
[WHAT HAPPENS]:
  - Claude calls set_icp_tiers({
      tiers: [
        {
          name: "Enterprise DACH Corporates",
          description: "Large German/Austrian/Swiss corporations with 500+ employees
                        that regularly host corporate events, product launches, and
                        internal conferences. High event budget, need for reliable
                        cross-border production.",
          priority: 1,
          criteria: {
            industries: ["Technology", "Automotive", "Financial Services", "Pharma"],
            company_size_min: 500,
            company_size_max: 50000,
            revenue_min: 50000000,
            geographies: ["Germany", "Austria", "Switzerland"],
            tech_signals: ["SAP", "Salesforce", "HubSpot"],
            qualifying_signals: ["Recent corporate event", "Hiring event manager",
                                  "Office expansion in DACH"]
          }
        },
        {
          name: "Mid-Market DACH Companies",
          description: "Growing mid-market companies (100-500 employees) in DACH
                        that need professional event production but cannot afford
                        top-tier German agencies. Price-sensitive, quality-conscious.",
          priority: 2,
          criteria: {
            industries: ["SaaS", "Consulting", "Professional Services", "E-commerce"],
            company_size_min: 100,
            company_size_max: 500,
            revenue_min: 10000000,
            revenue_max: 50000000,
            geographies: ["Germany", "Austria", "Switzerland"],
            qualifying_signals: ["Growing team", "Recent funding", "International expansion"]
          }
        },
        {
          name: "Agencies & Event Partners",
          description: "German event agencies seeking a reliable production partner
                        for overflow work or Central European projects. Partnership
                        model rather than direct client relationship.",
          priority: 3,
          criteria: {
            industries: ["Event Management", "Marketing Agency", "PR Agency"],
            company_size_min: 10,
            company_size_max: 100,
            geographies: ["Germany", "Austria"],
            qualifying_signals: ["Subcontracting mention", "Partner program",
                                  "Cross-border projects"]
          }
        }
      ]
    })

[CHAT SHOWS]:
  - ThinkingIndicator: "Setting up ICP tiers..."

[EDITOR SHOWS]:
  - All 7 strategy sections visible in the "Strategy Overview" tab
  - ICP Tiers tab has a notification badge (optional) indicating new data
```

### [T+54s] SSE EVENT: tool_result — set_icp_tiers

```
[CHAT SHOWS]:
  - Tool card: "Set 3 ICP tiers" with green checkmark

[EDITOR / TABS]:
  - If user clicks "ICP Tiers" tab, they see 3 structured tier cards:
    1. Enterprise DACH Corporates (Priority 1)
    2. Mid-Market DACH Companies (Priority 2)
    3. Agencies & Event Partners (Priority 3)
  - Each card shows: name, description, priority, and criteria
  - Cards are editable (user can modify criteria later)
```

### [T+55s] SSE EVENT: tool_start — set_buyer_personas

```
[WHAT HAPPENS]:
  - Claude calls set_buyer_personas({
      personas: [
        {
          name: "Corporate Event Manager",
          role: "Head of Events / Event Manager",
          seniority: "Manager",
          pain_points: [
            "Budget pressure to deliver premium events at lower cost",
            "Difficulty finding reliable production partners outside Germany",
            "Tight timelines for corporate event planning",
            "Need for multilingual event support (DE/EN/CZ)"
          ],
          goals: [
            "Deliver memorable events that impress C-suite",
            "Reduce per-event costs by 15-25%",
            "Build a reliable network of production partners"
          ],
          preferred_channels: ["LinkedIn", "Email", "Industry events"],
          messaging_hooks: [
            "German-standard quality at Central European prices",
            "Case studies from similar corporate events",
            "End-to-end production so you can focus on strategy"
          ],
          objections: [
            "Never heard of you — who are your German clients?",
            "How do you handle logistics across borders?",
            "What if something goes wrong during the event?"
          ],
          linked_tiers: ["Enterprise DACH Corporates", "Mid-Market DACH Companies"]
        },
        {
          name: "Marketing Director",
          role: "CMO / VP Marketing / Head of Marketing",
          seniority: "Director",
          pain_points: [
            "Events must generate measurable ROI for the business",
            "Brand consistency across all touchpoints including events",
            "Coordinating between internal teams and external vendors"
          ],
          goals: [
            "Use events as a pipeline generation tool",
            "Build brand presence in new markets",
            "Demonstrate marketing ROI to the board"
          ],
          preferred_channels: ["LinkedIn", "Email", "Referrals"],
          messaging_hooks: [
            "Events as pipeline accelerators with measurable impact",
            "Full creative control with professional execution",
            "Post-event analytics and ROI reporting"
          ],
          objections: [
            "We already have an agency — why switch?",
            "Can you handle our brand guidelines?",
            "What is your experience with B2B events specifically?"
          ],
          linked_tiers: ["Enterprise DACH Corporates"]
        },
        {
          name: "Agency Partner Lead",
          role: "Managing Director / Head of Production",
          seniority: "Director",
          pain_points: [
            "Overflow capacity during peak season",
            "Need for cost-effective production for international projects",
            "Quality assurance with remote teams"
          ],
          goals: [
            "Expand service capacity without hiring",
            "Offer competitive pricing on Central European projects",
            "Build long-term production partnerships"
          ],
          preferred_channels: ["LinkedIn", "Industry events", "Referrals"],
          messaging_hooks: [
            "White-label production partnership",
            "Flexible capacity model — scale up or down",
            "Proven track record with German clients"
          ],
          objections: [
            "How do we maintain quality control?",
            "What is your turnaround time?",
            "Can you work under our brand?"
          ],
          linked_tiers: ["Agencies & Event Partners"]
        }
      ]
    })

[CHAT SHOWS]:
  - ThinkingIndicator: "Setting up buyer personas..."
```

### [T+56s] SSE EVENT: tool_result — set_buyer_personas

```
[CHAT SHOWS]:
  - Tool card: "Set 3 buyer personas" with green checkmark

[EDITOR / TABS]:
  - If user clicks "Buyer Personas" tab, they see 3 persona cards:
    1. Corporate Event Manager
    2. Marketing Director
    3. Agency Partner Lead
  - Each card shows: role, seniority, pain points, goals, messaging hooks, objections
  - Linked tiers show which ICP tier each persona maps to
```

---

## Act 7: Assumption Tracking (T+57s to T+60s)

The AI tracks the key assumptions it made during strategy generation, so the user
can validate or invalidate them in follow-up conversation.

### [T+57s] SSE EVENT: tool_start — track_assumption #1

```
[WHAT HAPPENS]:
  - Claude calls track_assumption({
      assumption_id: "dach_cost_advantage",
      text: "United Arts can offer 20-30% lower pricing than German agencies while
             maintaining equivalent production quality",
      status: "open",
      source: "web research"
    })
```

### [T+57.5s] SSE EVENT: tool_result — track_assumption #1

```
[CHAT SHOWS]:
  - Tool card (collapsed): "Tracked assumption" — checkmark
```

### [T+58s] SSE EVENT: tool_start — track_assumption #2

```
[WHAT HAPPENS]:
  - Claude calls track_assumption({
      assumption_id: "icp_enterprise_dach",
      text: "Enterprise DACH corporates (500+ employees) are the primary ICP with
             the highest LTV and willingness to work with cross-border providers",
      status: "open",
      source: "market analysis"
    })
```

### [T+58.5s] SSE EVENT: tool_result — track_assumption #2

```
[CHAT SHOWS]:
  - Tool card: "Tracked assumption" — checkmark
```

### [T+59s] SSE EVENT: tool_start — track_assumption #3

```
[WHAT HAPPENS]:
  - Claude calls track_assumption({
      assumption_id: "channel_linkedin_primary",
      text: "LinkedIn is the most effective channel for reaching DACH corporate
             event managers and marketing directors",
      status: "open",
      source: "industry analysis"
    })
```

### [T+59.5s] SSE EVENT: tool_result — track_assumption #3

```
[CHAT SHOWS]:
  - Tool card: "Tracked assumption" — checkmark
```

---

## Act 8: Strategic Brief in Chat (T+60s to T+70s)

After all tool calls complete, Claude delivers the Strategic Brief as its final
text response. This is the chat message the user reads — separate from the strategy
document sections that were written via tools.

### [T+60s] SSE EVENT: chunk (final response text)

```
[WHAT HAPPENS]:
  - Claude streams its final text response
  - This is the Strategic Brief — a high-level summary with strategic bets,
    proposed sequence, and open questions

[CHAT SHOWS]:
  - ThinkingIndicator disappears
  - All tool cards visible above (web search x3, section updates x7, tiers, personas, assumptions x3)
  - StreamingBubble appears with the Strategic Brief, streaming in:

  ---

  # United Arts -- Strategic Brief (Draft v0.1)

  > **What this is:** A first-pass GTM framework based on public research and
  > your stated objective. Several assumptions need validation before this
  > becomes actionable. Key decision points are flagged for your input.

  ---

  ## What We're Working With

  United Arts is a Prague-based event production company with a strong domestic
  portfolio including corporate events, conferences, and cultural productions.
  The company operates across technical production, creative direction, and
  project management. Your expansion into DACH represents a classic "adjacent
  market entry" play — leveraging an existing capability set in a new geography.

  ## Strategic Bets

  ### Bet 1: The Cost-Quality Arbitrage
  German event production commands premium pricing (EUR 50-150K per corporate
  event). United Arts can deliver equivalent quality at 20-30% lower cost by
  leveraging Prague-based operations while maintaining German-facing client
  management.

  *Assumption: DACH buyers are willing to work with a Czech-based provider
  if quality proof points are strong enough.*

  ### Bet 2: The Agency Partnership Backdoor
  Rather than competing head-to-head with established German agencies (Vok Dams,
  Eventive), start by positioning as a production partner for overflow/international
  work. This builds reference clients and market knowledge simultaneously.

  *Assumption: German agencies have capacity constraints during peak season
  and are open to cross-border partnerships.*

  ## Proposed Sequence

  1. **Weeks 1-4**: Foundation (German-language collateral, case studies, LinkedIn presence)
  2. **Weeks 5-8**: Direct outreach to mid-market targets + agency partnership outreach
  3. **Weeks 9-12**: Optimization based on response data, double down on winning channels

  ## Foundation Phase -- What Needs to Exist

  | Asset | Why It's Blocking | Estimated Effort |
  |-------|-------------------|------------------|
  | German case studies (3) | No credibility without them | 2 weeks |
  | LinkedIn company page (DE) | Can't run outreach without it | 3 days |
  | Pricing comparison sheet | Must prove cost advantage | 1 week |
  | Reference clients in DACH | Social proof is table stakes | Ongoing |

  ## Open Questions

  I made three assumptions that need your input:

  1. **Cost positioning**: Can you actually deliver at 20-30% below German agencies?
     What is your current pricing vs. the German market?

  -> Yes, our costs are significantly lower
  -> Partly — depends on the project type
  -> Not sure — I need to research competitor pricing
  -> [Tell me more]

  ---

[EDITOR SHOWS]:
  - All 7 sections fully written and visible
  - Document is scrollable — the user can read through the full strategy
  - "Saved" indicator appears briefly in the top bar
```

### [T+68s] SSE EVENT: done

```
[WHAT HAPPENS]:
  - Done event received with metadata:
    - tool_calls: 16 total (3 web_search, 1 get_strategy_document,
      7 update_strategy_section, 1 set_icp_tiers, 1 set_buyer_personas,
      3 track_assumption)
    - total_input_tokens: ~15,000
    - total_output_tokens: ~8,000
    - total_cost_usd: ~$0.08
  - Assistant message saved to DB (StrategyChatMessage)
  - documentChanged flag set — editor refreshes from server

[CHAT SHOWS]:
  - Strategic Brief is fully rendered (markdown formatted)
  - The question at the end has clickable option buttons:
    -> Yes, our costs are significantly lower
    -> Partly — depends on the project type
    -> Not sure — I need to research competitor pricing
    -> [Tell me more]
  - Chat input is enabled and focused, ready for user response
  - Suggestion chips appear below the input:
    ["Refine my ICP criteria", "Add more buyer personas",
     "Strengthen the value proposition", "Suggest outreach channels"]

[EDITOR SHOWS]:
  - Full strategy document with all 7 sections
  - Content is specific, researched, not generic
  - "Undo AI edit" button appears in the top-right corner
  - Auto-save indicator shows "Saved"

[TABS]:
  - "Strategy Overview" tab active (showing the full document)
  - "ICP Tiers" tab shows 3 tiers (clickable to view)
  - "Buyer Personas" tab shows 3 personas (clickable to view)
```

---

## Act 9: User Responds — Convergent Discovery (T+70s+)

The user now engages in a back-and-forth conversation to refine the strategy.
Each exchange should validate or invalidate one assumption, progressively
converging toward a production-ready strategy.

### [T+70s] USER ACTION: Clicks "Yes, our costs are significantly lower"

```
[WHAT HAPPENS]:
  - Message sent: "Yes, our costs are significantly lower"
  - Chat endpoint called

[CHAT SHOWS]:
  - User message bubble appears
  - ThinkingIndicator appears below: "Thinking..."

[BACKEND]:
  - Claude receives the response with full context (strategy doc + enrichment)
  - Claude should:
    1. Call track_assumption({assumption_id: "dach_cost_advantage", status: "validated",
       source: "user confirmed"})
    2. Respond with a brief acknowledgment and the NEXT question (one at a time)
```

### [T+73s] AI RESPONSE: Validates assumption, asks next question

```
[CHAT SHOWS]:
  - Tool card: "Updated assumption: dach_cost_advantage -> validated"
  - AI message (SHORT — under 150 words):

    "Good — that cost advantage is your strongest weapon in DACH. I've updated
    the strategy to lead with this in all messaging.

    **Next question**: Do you have any existing German-speaking clients or
    reference projects? This determines whether we lead with case studies
    or a partnership approach.

    -> Yes, we have DACH clients already
    -> We have international clients but none in DACH
    -> No — this would be our first entry into German-speaking markets
    -> [Tell me more]"

[EDITOR SHOWS]:
  - No changes yet (AI is asking, not writing)
  - Changes will come after the user answers and the AI refines sections
```

### [T+80s] USER ACTION: Clicks "We have international clients but none in DACH"

```
[CHAT SHOWS]:
  - User message appears
  - ThinkingIndicator: "Thinking..."

[BACKEND]:
  - Claude should:
    1. track_assumption({assumption_id: "existing_dach_clients", text: "...",
       status: "invalidated", source: "user confirmed"})
    2. update_strategy_section for "Competitive Positioning" to emphasize
       international track record rather than DACH-specific references
    3. Possibly update "90-Day Action Plan" to prioritize building DACH references
    4. Ask the NEXT question
```

### [T+85s] AI RESPONSE: Updates strategy, asks next question

```
[CHAT SHOWS]:
  - Tool card: "Updated assumption: existing_dach_clients -> invalidated"
  - Tool card: "Updated Competitive Positioning"
  - Tool card: "Updated 90-Day Action Plan"
  - AI message:

    "That changes the approach. I've adjusted the strategy:

    - **Competitive Positioning**: Now leads with your international portfolio
      rather than local DACH references
    - **90-Day Action Plan**: Added 'Secure 2 pilot projects at reduced rate'
      in Month 1 to build reference cases fast

    **Next question**: Which of these outreach channels do you already use?

    -> LinkedIn — actively posting and connecting
    -> Email outreach — have templates/tools
    -> Industry events — attend regularly
    -> None of these — starting from scratch
    -> [We use something else]"

[EDITOR SHOWS]:
  - Competitive Positioning section updated (visible if user scrolls to it)
  - 90-Day Action Plan section updated
  - "Undo AI edit" button available
  - Toast: "Section saved: Competitive Positioning"
  - Toast: "Section saved: 90-Day Action Plan"
```

---

## Act 10: Readiness Check (after 3-5 rounds of discovery)

After several rounds of Q&A, the AI checks whether the strategy has converged.

### [T+~5min] AI calls check_readiness

```
[WHAT HAPPENS]:
  - After validating/invalidating several assumptions, the AI calls check_readiness()
  - Result: {ready: true, score: 0.85, checks_passed: 4, total_checks: 4, gaps: []}

[CHAT SHOWS]:
  - Tool card: "Readiness check: 85% — READY"
  - AI message:

    "Your strategy has solid foundations:
    - ICP with specific tiers and disqualifiers
    - 3 buyer personas with validated pain points
    - Research-grounded messaging angles
    - Channel strategy with rationale

    Ready to move to the **Contacts** phase? I'll filter your contact database
    using these ICP criteria and help you select the best prospects for outreach.

    -> Yes, let's find contacts
    -> I want to refine the strategy more first
    -> Show me the readiness details"
```

---

## Complete Timeline Summary

| Phase | Time Range | Duration | What User Sees |
|-------|-----------|----------|---------------|
| Onboarding trigger | T+0s to T+2s | 2s | Form disappears, split-view appears, thinking indicator |
| Research (background) | T+0s to T+20s | 20s | Thinking indicator, research tool cards |
| AI warm one-liner | T+22s | 1s | First chat message streams in |
| Web search (market intel) | T+23s to T+32s | 9s | 3 web search tool cards |
| Strategy sections written | T+33s to T+52s | 19s | 7 sections appear one by one in editor |
| ICP tiers set | T+53s to T+54s | 1s | Tiers tab populated |
| Buyer personas set | T+55s to T+56s | 1s | Personas tab populated |
| Assumptions tracked | T+57s to T+60s | 3s | 3 assumption tool cards |
| Strategic Brief streams | T+60s to T+68s | 8s | Full brief with question at end |
| **Total initial generation** | **T+0s to T+68s** | **~70s** | **Complete strategy + brief** |
| Convergent discovery | T+70s to T+5min+ | 3-5min | Refine through Q&A, 3-5 rounds |
| Readiness check | T+~5min | 5s | Ready to move to Contacts |

---

## Tool Call Sequence Summary (Initial Generation)

| # | Tool | Purpose | Timing |
|---|------|---------|--------|
| 1 | web_search | DACH event market trends | T+23s |
| 2 | web_search | German event agencies/competitors | T+26s |
| 3 | web_search | B2B lead gen strategies for events | T+29s |
| 4 | get_strategy_document | Check current state | T+33s |
| 5 | update_strategy_section | Executive Summary | T+34s |
| 6 | update_strategy_section | Value Proposition & Messaging | T+36s |
| 7 | update_strategy_section | Competitive Positioning | T+39s |
| 8 | update_strategy_section | Channel Strategy | T+42s |
| 9 | update_strategy_section | Messaging Framework | T+45s |
| 10 | update_strategy_section | Metrics & KPIs | T+48s |
| 11 | update_strategy_section | 90-Day Action Plan | T+51s |
| 12 | set_icp_tiers | 3 tiers with criteria | T+53s |
| 13 | set_buyer_personas | 3 personas with details | T+55s |
| 14 | track_assumption | Cost advantage assumption | T+57s |
| 15 | track_assumption | ICP enterprise DACH assumption | T+58s |
| 16 | track_assumption | LinkedIn primary channel assumption | T+59s |

Total: 16 tool calls in one turn (within the MAX_TOOL_ITERATIONS=25 limit).

---

## Key UX Principles Enforced

1. **Progress at all times**: The user sees sections appearing one by one in the editor.
   There is never a moment where nothing is happening after T+22s.

2. **Thinking indicator is always last**: The pulsing dot + status text always appears
   below all other content in the chat. It never gets buried above messages.

3. **Chat messages are SHORT**: The warm one-liner is one sentence. Follow-up messages
   are under 150 words. Only the Strategic Brief is longer (up to 400 words).

4. **Questions are ONE at a time**: The Strategic Brief ends with ONE question with
   clickable options. Each follow-up round has exactly ONE question.

5. **Research data from enrichment**: The AI uses the enrichment data from the system
   prompt for company-specific info. web_search is only for market trends, competitors,
   and industry data that enrichment does not cover.

6. **Never refuses to generate**: Even if research data is thin, the AI generates a
   complete strategy with TODO markers and assumptions, then asks to refine.

7. **Assumptions are tracked**: Every strategic bet is explicitly tracked as an
   assumption (open/validated/invalidated) so the conversation converges.

8. **Structured data populates tabs**: ICP tiers and buyer personas go to their
   dedicated tabs via set_icp_tiers and set_buyer_personas — never written into the
   document via update_strategy_section.

---

## Anti-Patterns to Avoid

1. **DO NOT** have the AI describe what it will do before doing it.
   WRONG: "I'll start by researching your market, then write each section..."
   RIGHT: Just do it. Call the tools. The user sees the tool cards.

2. **DO NOT** expose failed searches or internal reasoning.
   WRONG: "The web search for unitedarts.cz didn't return direct results. Let me try..."
   RIGHT: Silently retry with a different query. Show results, not process.

3. **DO NOT** ask multiple questions at once.
   WRONG: "I have 5 questions: 1) What is your pricing? 2) Who are your clients?..."
   RIGHT: "What is your pricing compared to German agencies? -> [options]"

4. **DO NOT** write ICP or persona content into the document.
   WRONG: update_strategy_section({section: "Executive Summary", content: "...ICP Tier 1..."})
   RIGHT: set_icp_tiers({tiers: [...]}) — tiers go in their own tab.

5. **DO NOT** wait for research before showing any progress.
   The warm one-liner should appear within 22s. If research takes longer, the AI
   should start writing with what it has from the objective/description.

6. **DO NOT** use placeholder text like "[X]" or "[Company Name]".
   Always use specific data from research or enrichment. If data is missing,
   use "based on similar companies in this sector" with a concrete example.

7. **DO NOT** start with filler phrases.
   WRONG: "Great question! I'd be happy to help you build..."
   RIGHT: "Building your event production strategy for unitedarts.cz..."
