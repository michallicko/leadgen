# Product Strategy

**Last updated**: 2026-03-02

## Vision

Leadgen Pipeline becomes the **end-to-end GTM engineering platform** for small companies, freelancers, and startups. In 12 months, a user signs up, imports their contacts from any source, keeps them enriched and up-to-date automatically, selects audiences for hyper-personalized outreach, delivers campaigns across channels, and sees closed-loop analytics that coach them to improve — all from one multi-tenant SaaS product.

## Target Market

**Who**: Small companies (5-50 people), freelancers, and early-stage startups doing their own outbound sales. Typically 1-3 person sales/founder-led teams without dedicated sales ops.

**Pain**: Contact data rots fast — people change roles, companies pivot, emails bounce. These teams can't afford ZoomInfo/Apollo subscriptions and don't have the ops capacity to keep CRM data clean. They cobble together 5-10 tools (LinkedIn + CSV + enrichment API + outreach tool + spreadsheet tracking) and lose signal at every handoff.

**Why now**: LLM-powered enrichment and personalization have made it possible to deliver enterprise-grade GTM automation at indie-hacker prices. The "AI SDR" market is exploding but most tools are point solutions. There's a gap for an integrated, affordable E2E platform.

## Strategic Themes

### Theme 1: Contact Intelligence
**Status**: Active | **Quarter**: Q1-Q2 2026
**Metric**: Contacts ingested per month, enrichment accuracy rate, data freshness (% contacts updated in last 30 days)
**Backlog items**: BL-004, BL-006, BL-007, BL-008, BL-009, BL-010, BL-012, BL-013, BL-014, BL-015, BL-016, BL-017, BL-018, BL-019, BL-020, BL-021, BL-022, BL-023, BL-024, BL-025

The foundation layer. Users bring contacts from anywhere — CSV/XLSX today, LinkedIn Sales Navigator exports, personal LinkedIn connections, and influencer engagement signals (who's engaging with a person of interest's posts) in the future. All contacts go through:
- **Cleanup**: Validation, deduplication, normalization
- **Enrichment**: Missing fields researched via Perplexity (company info, role, email)
- **Freshness**: Ongoing monitoring for role changes, company changes, stale data

This is a standalone value prop — many small teams would pay just for "keep my contacts clean and current."

### Theme 2: Outreach Engine
**Status**: Active — Phase 1 shipped, Phase 2 in progress | **Quarter**: Q1-Q2 2026
**Metric**: Campaigns launched per user/month, personalization quality score, reply rates
**Backlog items**: BL-031, BL-032, BL-033, BL-034, BL-035, BL-036, BL-037, BL-038, BL-039, BL-040, BL-041, BL-042, BL-043, BL-044

Select contacts via filtering criteria, run them through a hyper-personalization pipeline, and deliver across channels:
- **Audience selection**: Filter by enrichment data, tags, engagement signals, custom fields
- **Personalization pipeline**: AI-generated approach per contact, with review gates
- **Plugins**: Hyper-personalized branded PDF generator (potential standalone product), custom templates
- **Delivery**: Lemlist integration, Resend (email), custom LinkedIn browser extension
- **Review workflow**: Human-in-the-loop approval before send

**Shipped**: Message review workflow (BL-045), campaign system (BL-031-036), playbook messaging phase (BL-118), campaign auto-config (BL-116/117), campaign templates (BL-037), campaign clone (BL-038), custom prompt instructions (BL-044). Lemlist integration and Resend email (BL-090-093) planned for Q2.

### Theme 3: Closed-Loop Analytics
**Status**: In Progress — signals layer active, coaching layer in design | **Quarter**: Q2-Q3 2026
**Metric**: Activity capture rate, conversion funnel visibility, user engagement with coaching
**Backlog items**: BL-005, BL-020, BL-120, BL-122

Close the feedback loop from outreach to outcome:
- **Activity logging**: Browser extension + email integration capture all touchpoints
- **Dashboards**: Funnel analytics, response rates, pipeline velocity
- **Coaching**: AI-powered recommendations ("your reply rate drops on Fridays", "contacts in fintech respond 2x better to case study PDFs")
- **Attribution**: Which enrichment signals and personalization approaches drive replies

**Shipped**: Enrichment gaps chat tool (BL-120), Proactive Strategy Agent (BL-122), Activity logging via browser extension (BL-020). These form the signals layer — the system now captures events and proactively identifies gaps. Campaign performance coaching and AI-powered recommendations are the next design target.

### Theme 4: Platform Foundation
**Status**: Active | **Quarter**: Q1 2026
**Metric**: Airtable dependency eliminated, tenant onboarding time, system uptime
**Backlog items**: BL-002, BL-003

The infrastructure that makes everything else possible:
- **Data ownership**: Complete Airtable → PostgreSQL migration (workflows write to PG directly)
- **Multi-tenancy**: Namespace routing, tenant isolation, role-based access
- **Billing**: Credit-based model for LLM operations + monthly subscription tiers
- **API platform**: Clean REST APIs that the dashboard and future integrations consume

### Theme 5: Agent-Driven GTM
**Status**: Active | **Quarter**: Q1-Q2 2026
**Metric**: Chat tool usage per session, strategy generation rate, research actions per playbook
**Backlog items**: WRITE, ANALYZE, SEARCH, THINK, BL-120, BL-122

A chat interface with AI-powered tools transforms how founders interact with their GTM data. Instead of navigating dashboards and running manual queries, users converse with an AI agent that has direct access to their contacts, companies, enrichment data, and market research. The agent writes strategy, scores contacts, synthesizes research, and shows its reasoning transparently.

- **Strategy generation (WRITE)**: AI drafts GTM strategy sections — ICP definitions, value propositions, messaging frameworks — directly from onboarding context and enrichment data
- **Contact analysis (ANALYZE)**: AI scores and segments contacts/companies by ICP fit, engagement signals, and enrichment quality
- **Web research (SEARCH)**: AI runs live web searches to fill knowledge gaps, verify claims, and discover market context
- **Transparent reasoning (THINK)**: AI shows its chain-of-thought so founders can audit and steer decisions
- **Enrichment gaps (BL-120)**: AI proactively identifies missing data that would improve targeting
- **Proactive strategy (BL-122)**: AI surfaces strategic recommendations without being asked

**Planned**: Next-action ranking (what should I do right now?), competitor tracking (alert when a prospect evaluates alternatives).

### Theme 6: Playbook-Driven Execution
**Status**: Active | **Quarter**: Q1-Q2 2026
**Metric**: Playbook completion rate, phase auto-advance accuracy, onboarding-to-first-campaign time
**Backlog items**: BL-113, BL-114, BL-115, BL-118, BL-121, BL-111

The playbook becomes the control plane for GTM execution. Instead of navigating disconnected pages, users follow a guided multi-phase workflow: Strategy → Contacts → Messages → Campaign. Each phase tracks its own status, auto-advances when ready, and provides contextual tools.

- **Contacts phase (BL-115)**: ICP pre-filters surface the right contacts for a campaign, with search and scoring
- **Messages phase (BL-118)**: AI generates personalized messages per contact, with review and edit workflow
- **Phase auto-advance (BL-114)**: Playbook detects when a phase is complete and nudges the user forward
- **Onboarding → playbook (BL-113)**: New users answer 3 questions and get an AI-generated GTM strategy as their first playbook
- **Smart onboarding (BL-121)**: Research-backed onboarding that pre-fills strategy from web data about the user's company
- **Onboarding signpost (BL-111)**: Smart empty states that guide users to the next meaningful action

## Monetization

**Model**: Subscription + credits (hybrid, like Lovable/Claude)

| Tier | Monthly Fee | Included Credits | Overage |
|------|-------------|-----------------|---------|
| Starter | $29-49 | 500 credits | Pay-as-you-go or upgrade prompt |
| Growth | $99-149 | 2,000 credits | Pay-as-you-go |
| Agency | $249-399 | 10,000 credits | Volume discount |

**Credit consumption**: Every LLM operation (enrichment, personalization, research) costs credits. Non-LLM operations (import, filter, export) are free. When credits are exhausted, user is prompted to pay for more or upgrade tier.

**Standalone products**: Branded PDF generator could be offered as a separate product/plugin with its own pricing.

## Success Metrics

| Metric | Current | Target (12 months) | Timeline |
|--------|---------|---------------------|----------|
| Active tenants | 1 (VisionVolve) | 20-50 paying | Q4 2026 |
| Contacts managed | 2,608 | 100,000+ across tenants | Q4 2026 |
| Ingestion sources | CSV, XLSX, Google Contacts (3 sources) | CSV, XLSX, LinkedIn, Google Contacts (4+ types) | Q3 2026 |
| Airtable dependency | Eliminated for reads (PG primary); n8n workflows still dual-write | Eliminated | Q2 2026 |
| Outreach campaigns | Platform-native (campaigns + templates + review built; Lemlist export pending) | Platform-native with multi-channel delivery | Q3 2026 |
| MRR | $0 | $2,000-5,000 | Q4 2026 |

## Current Quarter Focus (Q2 2026)

1. **Scale Outreach Engine** — Lemlist integration (BL-090+) for multi-step sequence execution, Resend email for direct sending (BL-091-093), connected accounts hub (BL-098)
2. **Closed-Loop Intelligence** — Campaign performance coaching that learns from reply rates and engagement signals. AI-powered recommendations that get sharper with every campaign cycle.
3. **Browser Extension Expansion** — LinkedIn message sending (BL-094-095), Gmail reply detection (BL-096-097). Turn the browser extension from a passive listener into an active outreach channel.

## Competitive Position

**Alternatives**: Apollo.io ($49-119/mo, enterprise-focused), Lemlist ($59-99/mo, outreach-only), Clay ($149-349/mo, enrichment-focused), manually stitching together 5+ tools.

**Moat**: Integrated E2E workflow (ingest → enrich → personalize → deliver → analyze) at indie-hacker pricing. LLM-native architecture means enrichment quality improves with models, not manual data entry. Multi-tenant from day one enables agency model.

**Intelligence compounding is the real moat.** After 3 months of use, the system knows what messaging angles, contact tiers, and timing windows drive replies in YOUR market. That accumulated intelligence — across enrichment signals, campaign results, and AI-refined strategy — is impossible to replicate by switching tools. The agent-driven approach (Theme 5) accelerates this: every chat interaction, every strategy revision, every research query adds signal that sharpens recommendations.

**Differentiation**: Not just another "AI SDR" — this is GTM engineering infrastructure with an embedded AI strategist. Users control the pipeline, see every enrichment decision, and can customize personalization. The agent doesn't just execute — it reasons, recommends, and learns. Transparency + control + compounding intelligence, not black-box automation.

## Product Principles

1. **Automation over manual**: Invest in making things hands-off. Every manual step is a candidate for automation. If a user does something twice, build a workflow for it. The agent-driven approach (Theme 5) takes this further — instead of automating clicks, the AI automates decisions. Strategy generation, contact scoring, and gap analysis that used to require manual thought are now proactive agent capabilities.
2. **Quality over volume**: Better to enrich 100 leads with deep research than blast 1,000 with shallow data. Personalization quality drives reply rates, not send volume.
3. **Data freshness is a feature**: Stale contacts are worse than no contacts. The platform should actively monitor and refresh data, not just store it.
4. **Plugin architecture**: Core platform stays lean. Advanced capabilities (PDF generator, LinkedIn extension, email integration) are plugins that can be developed, priced, and shipped independently.
5. **Transparent pricing**: Users should always know what operations cost before they run them. No surprise bills — show credit estimates before execution.
6. **User experience first**: Every interaction should feel fast and intuitive. Lazy load everything, show progress for long operations, provide clear error messages. The product should feel polished even in MVP.
