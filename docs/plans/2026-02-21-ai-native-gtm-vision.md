# AI-Native GTM: Product Vision

> Date: 2026-02-21 | Status: Draft | Author: Michal + Claude

---

## 1. Vision Statement

GTM execution is about to undergo the same transformation that happened to code: AI does the work, humans provide judgment. This product exists because we believe the winning GTM tool won't be the one with the most features -- it will be the one that learns the most from each interaction. We are building a system where every enrichment, every outreach, every reply, and every market signal compounds into a proprietary intelligence layer that makes your GTM motion measurably better every week. The user's role shifts from doing to directing -- from "marketing specialist executing a plan" to "marketing strategist overseeing strategy and results."

## 2. The Problem

Software is cheap to build. Any team can prompt-engineer a contact enrichment tool or an AI message writer in a few days. The market already has dozens of tools that enrich contacts (Apollo, Clearbit, Clay), generate outreach (Lemlist AI, Instantly, LaGrowthMachine), and manage campaigns (HubSpot, Outreach, Salesloft). They all converge on the same feature set because the features themselves are commoditized.

The failure mode is obvious: compete on features, lose on features. Ship enrichment -- three competitors ship it the same month. Ship AI message generation -- it's table stakes within a quarter. The underlying LLM APIs are identical. The data sources are identical. There is no feature moat.

What existing tools fail at is *connecting the dots*. Apollo enriches contacts but doesn't know which messaging angle gets replies in your specific market. Lemlist sends messages but doesn't know that a prospect's company just got funded and your "growth infrastructure" framing converts 3x better for recently-funded companies. HubSpot tracks everything but surfaces none of it as actionable intelligence.

The gap is not in data or features. The gap is in intelligence that compounds with usage.

## 3. The Moat Strategy

Three moats, layered from strongest to most visible:

### Moat 1: Compounding Context (strongest)

Every interaction makes the system smarter about YOUR specific GTM motion. After three months of usage:

- The system knows that "operational efficiency" messaging gets 40% reply rates from healthcare contacts, but "competitive threat" framing works better for fintech.
- It knows that VP-level contacts at 50-200 person companies respond 2.3x more to LinkedIn messages than email.
- It knows that contacts who recently changed jobs have a 5-day window where cold outreach converts at 3x the normal rate.

A competitor starting from scratch has none of this. They have the same LLMs, the same enrichment APIs, the same sending infrastructure -- but zero accumulated knowledge about what works for THIS user in THIS market with THIS product.

Concrete example: User runs three campaigns targeting SaaS companies. Campaign 1 (pain-point framing) gets 12% reply rate. Campaign 2 (social proof framing) gets 8%. Campaign 3 (ROI framing) gets 22%. The system learns: for SaaS targets, lead with ROI. Next campaign auto-generates messages using ROI angles and ranks contacts by predicted fit. A new tool would treat Campaign 4 the same as Campaign 1.

### Moat 2: Cross-Signal Intelligence

Enrichment data, outreach performance, response signals, and market events are typically siloed in different tools. Connecting them creates intelligence that no single-purpose tool can replicate.

Concrete example: Contact X got promoted to VP Engineering last week (LinkedIn signal) + Company Y's competitor just raised $50M (news signal) + your "competitive threat" framing has 40% reply rate in this segment (performance signal) + Contact X's company is 200 people with no dedicated DevOps (enrichment signal) = the system generates a specific, timely message and ranks it as the #1 action today. No human would connect these four signals manually across 2,000 contacts.

### Moat 3: Strategy-as-Control-Plane

The playbook is not a document -- it IS the control plane for GTM execution. When the user changes the ICP definition from "50-500 person SaaS companies" to "50-500 person SaaS companies in healthcare," every downstream system auto-adjusts:

- Contact scoring re-ranks all 2,000 contacts; healthcare-adjacent ones rise to the top.
- Message templates regenerate with healthcare-specific value propositions.
- Campaign targeting filters update automatically.
- The enrichment pipeline prioritizes research on healthcare verticals.

Today this is a 2-week manual process: update the strategy doc, re-segment lists, rewrite templates, reconfigure campaigns. With strategy-as-control-plane, it is a single edit with cascading updates.

## 4. User Personas & Entry Points

Four entry points, all converging on the same intelligence graph:

### Entry Point 1: Data Cleanup / Import
**Who**: Marketing ops person with a messy CSV export from a CRM or event, or a founder with a LinkedIn connections dump.
**What they need**: Clean, deduplicated, enriched contact list they can actually use.
**Aha moment**: "You uploaded 847 contacts. After dedup, you have 612 unique ones. 340 match your ICP. Here's the insight: 60% of your ICP-matching contacts are at companies expanding into new markets -- that's your opening."
**Convergence**: Imported contacts feed the intelligence graph. Their enrichment data becomes the substrate for outreach and strategy.
**Status**: BUILT -- CSV import with AI column mapping, dedup, Google Contacts import, Gmail scan, browser extension for LinkedIn.

### Entry Point 2: Personalized Outreach
**Who**: Founder or SDR who needs to reach prospects with messages that don't sound like mass email.
**What they need**: Hyper-personalized messages at scale, with a review workflow that lets them maintain quality control.
**Aha moment**: First batch of 10 messages, each referencing specific company intel (recent funding, hiring patterns, tech stack), drafted in < 5 minutes. User reviews and sends 8 of 10 without editing.
**Convergence**: Outreach performance (opens, replies, meetings) feeds back into the intelligence loop. Message edits during review train the system on the user's voice and preferences.
**Status**: PARTIALLY BUILT -- campaign management, message generation via Claude, review workflow with version tracking and edit reason tags. Missing: performance tracking, feedback loop, intelligent ranking.

### Entry Point 3: Strategy Creation
**Who**: Founder or marketing lead starting from scratch, or revisiting their GTM after a pivot.
**What they need**: A structured GTM playbook (ICP, personas, messaging, channels) grounded in real data, not guesswork.
**Aha moment**: User enters their domain and a 2-sentence description of what they sell. System researches their company, analyzes their market, and produces a first-draft ICP playbook with specific segment recommendations backed by enrichment data. "Based on your product and market position, we recommend targeting VP Engineering at Series B fintech companies (50-200 people) -- they have the budget, the pain point, and the urgency."
**Convergence**: The strategy document becomes the control plane. ICP definition drives scoring, messaging, and targeting.
**Status**: JUST BUILT -- playbook onboarding with self-company research (L1+L2 enrichment), AI chat for strategy refinement, Tiptap editor, strategy extraction.

### Entry Point 4: Market Intelligence
**Who**: Someone who wants to understand their competitive landscape, identify trends, or monitor prospects.
**What they need**: Continuous market signals surfaced as actionable insights, not raw data.
**Aha moment**: "Three of your top-10 prospects posted job listings for your buyer persona's role this week. Companies hiring for this role convert at 2.5x your average."
**Convergence**: Market signals feed enrichment, trigger outreach timing, and update strategy recommendations.
**Status**: PARTIALLY BUILT -- company enrichment surfaces signals (hiring, funding, digital initiatives), but no continuous monitoring or proactive alerting.

## 5. End-to-End Flows

### Traditional vs. AI-Native GTM

**Traditional (human-driven, 4-8 week cycle):**
1. Research market manually (1-2 weeks)
2. Write GTM plan in Google Docs (1 week)
3. Build prospect lists in spreadsheets (1 week)
4. Write message templates (3-5 days)
5. Personalize each message (ongoing, 15 min/contact)
6. Send via email tool (batch)
7. Wait for responses (1-2 weeks)
8. Manually analyze what worked (if ever)
9. Revise plan (maybe quarterly)

**AI-native (AI-driven, continuous cycle):**
1. User provides intent: "I sell DevOps tooling to mid-market SaaS companies" (2 minutes)
2. System researches user's company + market (5 minutes, autonomous)
3. System generates strategy playbook (30 seconds)
4. User reviews and adjusts ICP/messaging (10 minutes of judgment, not writing)
5. System identifies top contacts, researches each, drafts personalized messages (autonomous, ranked by predicted fit)
6. User reviews messages: Send / Edit / Skip / Regenerate (judgment, not creation)
7. System sends, monitors opens/replies/meetings (continuous, autonomous)
8. System learns: "Healthcare contacts respond 2x to your efficiency angle" (automatic)
9. System adjusts: next batch auto-weights healthcare and efficiency framing (continuous)

**The user's time**: ~30 minutes of judgment calls vs. 4-8 weeks of execution work. The quality is higher because every decision is data-informed.

### Detailed Outreach Flow (Phase 2 Focus)

1. **"Who are you reaching out to?"** -- System presents draft ICP from playbook, or asks 2-3 questions to create one.
2. **"Upload contacts or let us find them"** -- Import CSV, connect CRM, or let prospecting find matches.
3. **"What problem do you solve?"** -- 2-3 sentences from the user. System generates 3-4 messaging angles automatically.
4. **First batch ready in < 5 minutes**: Top 10 contacts ranked by predicted fit. Each shows: company context summary, recent signals (funding, hiring, news), recommended messaging angle, drafted message.
5. **User reviews**: Send (approve as-is) / Edit (inline edit with reason tag) / Skip (not now) / Regenerate (different angle, tone, or language). Each action trains the system.
6. **Performance dashboard**: Real-time opens, replies, meetings booked. AI commentary surfaces patterns: "Healthcare contacts respond 2x to your efficiency angle. Your Tuesday morning sends have 35% higher open rates."

### Detailed Strategy Flow (Just Built)

1. User enters company domain and a short objective ("We want to sell AI consulting to mid-market companies in the Nordics").
2. System runs L1 enrichment on the user's own company: industry, size, positioning, competitors.
3. System runs L2 deep research: market analysis, strategic signals, opportunity mapping.
4. System seeds a structured playbook template with research-backed recommendations.
5. User refines via AI chat: "Make the ICP more specific to healthcare" -- system adjusts all sections.
6. User extracts structured data (ICP criteria, persona definitions) that becomes the control plane.

## 6. The Intelligence Loop

### What Data We Collect

- **Enrichment signals**: Company profile, market position, hiring patterns, funding, tech stack, leadership changes, legal status (11 enrichment stages already built).
- **Outreach performance**: Message sent, opened, replied, meeting booked -- per contact, per messaging angle, per channel, per time-of-day.
- **User edits**: Every message edit during review includes a structured reason tag (tone, length, personalization, accuracy, etc.) and the before/after text. This is explicit training signal.
- **Strategy decisions**: ICP changes, persona updates, channel preferences, messaging framework adjustments.

### How the System Learns

**Short-term (within a campaign)**: Contact rankings update based on early signals. If the first 20 sends show healthcare contacts replying 3x more, the remaining 180 contacts re-rank healthcare higher.

**Medium-term (across campaigns)**: Messaging angle performance aggregates. The system builds a per-tenant model: "For SaaS targets, ROI framing converts at 22%. For healthcare, operational efficiency converts at 40%." New campaigns auto-select the winning angle per segment.

**Long-term (strategic)**: Pattern recognition across enrichment + performance data. "Companies with recent leadership changes respond 2x to your 'new direction' messaging within 30 days of the change. After 30 days, response drops to baseline." This becomes a proactive trigger: leadership change detected, system auto-queues outreach with the right framing at the right time.

### What the User Experiences

Not a dashboard full of charts. Instead:

- A notification: "3 high-priority contacts identified today. View recommended actions."
- An insight in the playbook: "Your ICP section says '50-500 employees,' but 80% of your replies come from 100-300. Consider narrowing."
- A message suggestion: "Based on 47 previous sends to fintech companies, this angle has the highest predicted reply rate for this contact."
- A weekly digest: "This week: 12 replies (up 40% from last week). Top-performing segment: healthcare VP Engineering. Underperforming: financial services -- consider different framing."

## 7. The Onboarding Experience

### Principle: Outcome-Centric, Not Feature-Centric

Instead of "Pick your use case" (feature menu), the system runs an adaptive interview:

**Question 1**: "Tell me about your business in one sentence." (Free text, e.g., "We sell AI consulting to mid-market Nordic companies")

**Question 2**: "What's your most pressing GTM challenge right now?" (Select one)
- "I have contacts but need better outreach" --> Outreach flow
- "I need to find the right prospects" --> Import + enrichment flow
- "I'm starting from scratch and need a plan" --> Strategy flow
- "I want to understand my market better" --> Intelligence flow

**Question 3** (contextual, based on Q2):
- If outreach: "Do you have a contact list ready? (CSV, CRM, or LinkedIn)"
- If import: "Where are your contacts today? (Spreadsheet, CRM, LinkedIn, Gmail)"
- If strategy: "What's your company website?"
- If intelligence: "Which companies or segments are you most interested in?"

### The First 5 Minutes

Whatever path the user takes, within 5 minutes they see intelligence they did not have before. Not just "we processed your data," but a specific insight:

- **Outreach path**: "Your 340 ICP-matching contacts cluster into 3 segments. Segment A (healthcare VP Eng) has the strongest enrichment signal -- we recommend starting here. Here are 10 draft messages."
- **Import path**: "612 unique contacts after dedup. 23 have changed jobs since your last update. 60% are at companies expanding into new markets."
- **Strategy path**: "Based on your domain and market, here's a draft ICP with 3 recommended segments, ranked by estimated TAM and competitive density."
- **Intelligence path**: "Here's what's happening in your target market this week: 4 funding rounds, 7 leadership changes, 12 job postings matching your buyer persona."

### How Paths Converge

Every path feeds the same intelligence graph. The outreach user's contact data improves market intelligence. The strategy user's ICP definition improves contact scoring for outreach. The import user's cleaned data enriches the strategy recommendations. There are no dead ends -- every interaction adds to the compounding context.

## 8. What We Serve vs. What We Don't

### In Scope

- **Contact intelligence**: Enrichment, verification, scoring, deduplication, staleness detection.
- **Company intelligence**: Multi-stage research (L1 triage, L2 deep dive, registry checks, signal monitoring).
- **GTM strategy**: AI-assisted playbook creation grounded in real enrichment data.
- **Personalized outreach**: AI-generated messages with human review, multi-channel (LinkedIn, email).
- **Performance intelligence**: Closed-loop learning from outreach results.
- **Multi-source import**: CSV, Google Contacts, Gmail scan, LinkedIn (browser extension), CRM sync.

### Explicitly Out of Scope

- **Email sending infrastructure**: We integrate with Resend and Lemlist, not build our own SMTP/deliverability stack. Email infrastructure is a deep specialty with its own scaling challenges (IP warming, blacklist management, DMARC). We export approved messages to tools that do this well.
- **CRM replacement**: We are an intelligence layer, not a deal management tool. HubSpot/Pipedrive/Notion will be integration targets, not competitors. Users manage deals in their CRM; we feed them better leads and intel.
- **Marketing automation**: No drip campaigns, no landing pages, no form builders. We focus on the 1:1 outreach motion, not the 1:many marketing motion.
- **Data provider**: We don't sell contact databases. We enrich contacts the user already has or identifies. The value is in the intelligence layer, not the raw data.
- **Enterprise sales orchestration**: Multi-stakeholder deal rooms, buying committee mapping, enterprise approval workflows. We serve founders and small teams doing direct outreach, not enterprise sales orgs with 50-person SDR teams.

### Why These Boundaries

Every out-of-scope item is a product that requires dedicated infrastructure, compliance (email deliverability, data privacy), and domain expertise. Trying to be everything dilutes the core advantage -- compounding intelligence -- and puts us in direct competition with well-funded specialists. Better to integrate than to build.

## 9. Feature Roadmap (Phased)

### Phase 1: Foundation (Current -- BUILT)

What exists today:

- **Enrichment pipeline**: 11-stage DAG with L1 triage, L2 deep research, strategic signals, market intel, legal registry checks (ARES, BRREG, PRH, recherche-entreprises, ISIR), person enrichment, and QC.
- **Contact management**: Import (CSV, Google Contacts, Gmail scan, browser extension), deduplication, ICP filtering (8 dimensions), bulk operations.
- **Campaign & outreach**: Campaign CRUD, contact assignment, template presets (LinkedIn + Email, Email 3-Step, LinkedIn Only), Claude-powered message generation, review workflow with version tracking and edit reason tags.
- **Playbook**: AI-assisted strategy creation with self-company research, chat-based refinement, Tiptap editor, structured data extraction.
- **Platform**: Multi-tenant auth (JWT), namespace routing, PostgreSQL on RDS, Caddy reverse proxy, staging + production deployment.

### Phase 2: Personalized Outreach with Intelligence (Next)

- **Intelligent contact ranking**: Score contacts by predicted outreach success based on enrichment signals + ICP fit + timing signals.
- **Messaging angle selection**: Auto-select the messaging angle with highest predicted reply rate per segment, based on historical performance.
- **One-click review experience**: Streamlined flow -- see contact context, enrichment highlights, and drafted message on one screen. Send/Edit/Skip with zero page navigation.
- **Performance tracking**: Track opens, replies, and meetings per message, per contact, per campaign. Link back to enrichment data and messaging angle.
- **Strategy-to-outreach pipeline**: Extract ICP from playbook, auto-filter contacts, generate campaign with recommended settings.

### Phase 3: Intelligence Loop (3-6 months)

- **Cross-signal recommendations**: "Contact X + recent promotion + competitor funding + high-performing angle = send THIS message NOW."
- **Proactive alerts**: "3 of your top prospects posted job listings for your buyer persona. Companies hiring for this role convert at 2.5x."
- **Continuous market monitoring**: Track enrichment signal changes (job changes, funding rounds, hiring spikes) for contacts in active campaigns.
- **Playbook auto-suggestions**: "Your ICP says 50-500 employees, but 80% of replies come from 100-300. Consider narrowing."
- **Weekly intelligence digest**: Automated summary of outreach performance, top patterns, recommended adjustments.

### Phase 4: Strategy-as-Control-Plane (6-12 months)

- **Cascading ICP updates**: Edit ICP in playbook, all downstream (scoring, messaging, targeting) auto-adjusts.
- **Autonomous optimization**: System A/B tests messaging angles, channels, and timing without manual intervention. User sets guardrails (budget, volume, brand voice), system optimizes within them.
- **Multi-campaign orchestration**: Coordinate outreach across segments with budget allocation based on predicted ROI per segment.
- **Predictive pipeline**: "Based on current outreach velocity and conversion rates, you'll generate 12-15 qualified meetings this month. To hit 20, increase healthcare segment volume by 40%."

## 10. Success Metrics

### Product Metrics

| Metric | Phase 2 Target | Phase 3 Target | Why It Matters |
|--------|---------------|---------------|----------------|
| Time to first outreach | < 15 min | < 5 min | Core value prop: speed to action |
| Messages sent without editing | > 60% | > 75% | Quality of AI generation |
| Reply rate vs. industry avg | 1.5x | 2x | Outreach effectiveness |
| Contacts enriched per session | 50+ | 200+ | Platform throughput |
| Weekly active usage | 3+ sessions | Daily | Stickiness |

### Moat Health Metrics

| Metric | What It Measures | Healthy Signal |
|--------|-----------------|----------------|
| Intelligence graph density | Data points per contact over time | Growing every week without user effort |
| Prediction accuracy | Predicted vs. actual reply rates | Improving with each campaign |
| Strategy-to-execution latency | Time from ICP change to adjusted outreach | Decreasing toward real-time |
| Cross-signal triggers fired | Proactive recommendations generated per week | Increasing as more signals connect |
| Churn at 90 days vs. 30 days | Moat effectiveness (harder to leave over time) | 90-day churn significantly lower than 30-day |
| Edit rate decline | User edits per message over time | Decreasing as system learns user voice |

The ultimate moat metric: **switching cost perception**. After 3 months of usage, when asked "Would you switch to a competitor offering the same features for free?" the answer should be "No, because they don't know what I know." That accumulated knowledge -- which angles work, which segments convert, what timing matters -- is the product.
