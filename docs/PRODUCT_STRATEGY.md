# Product Strategy

**Last updated**: 2026-02-16

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
**Status**: Planned | **Quarter**: Q2-Q3 2026
**Metric**: Campaigns launched per user/month, personalization quality score, reply rates
**Backlog items**: BL-031, BL-032, BL-033, BL-034, BL-035, BL-036, BL-037, BL-038, BL-039, BL-040, BL-041, BL-042, BL-043, BL-044

Select contacts via filtering criteria, run them through a hyper-personalization pipeline, and deliver across channels:
- **Audience selection**: Filter by enrichment data, tags, engagement signals, custom fields
- **Personalization pipeline**: AI-generated approach per contact, with review gates
- **Plugins**: Hyper-personalized branded PDF generator (potential standalone product), custom templates
- **Delivery**: Lemlist integration, Resend (email), custom LinkedIn browser extension
- **Review workflow**: Human-in-the-loop approval before send

### Theme 3: Closed-Loop Analytics
**Status**: Planned | **Quarter**: Q3-Q4 2026
**Metric**: Activity capture rate, conversion funnel visibility, user engagement with coaching
**Backlog items**: BL-005

Close the feedback loop from outreach to outcome:
- **Activity logging**: Browser extension + email integration capture all touchpoints
- **Dashboards**: Funnel analytics, response rates, pipeline velocity
- **Coaching**: AI-powered recommendations ("your reply rate drops on Fridays", "contacts in fintech respond 2x better to case study PDFs")
- **Attribution**: Which enrichment signals and personalization approaches drive replies

### Theme 4: Platform Foundation
**Status**: Active | **Quarter**: Q1 2026
**Metric**: Airtable dependency eliminated, tenant onboarding time, system uptime
**Backlog items**: BL-002, BL-003

The infrastructure that makes everything else possible:
- **Data ownership**: Complete Airtable → PostgreSQL migration (workflows write to PG directly)
- **Multi-tenancy**: Namespace routing, tenant isolation, role-based access
- **Billing**: Credit-based model for LLM operations + monthly subscription tiers
- **API platform**: Clean REST APIs that the dashboard and future integrations consume

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
| Ingestion sources | CSV only | CSV, XLSX, LinkedIn (3 types) | Q3 2026 |
| Airtable dependency | Partial (workflows) | Eliminated | Q2 2026 |
| Outreach campaigns | Manual (Lemlist) | Platform-native | Q3 2026 |
| MRR | $0 | $2,000-5,000 | Q4 2026 |

## Current Quarter Focus (Q1 2026)

1. **Complete Platform Foundation** — Finish Airtable migration (BL-002 → BL-003), own the data layer entirely
2. **Expand Contact Intelligence** — LinkedIn ingestion, enrichment automation, data freshness monitoring
3. **Ship Import Phase 2** — Enrichment depth selection, cost estimation, better dedup

## Competitive Position

**Alternatives**: Apollo.io ($49-119/mo, enterprise-focused), Lemlist ($59-99/mo, outreach-only), Clay ($149-349/mo, enrichment-focused), manually stitching together 5+ tools.

**Moat**: Integrated E2E workflow (ingest → enrich → personalize → deliver → analyze) at indie-hacker pricing. LLM-native architecture means enrichment quality improves with models, not manual data entry. Multi-tenant from day one enables agency model.

**Differentiation**: Not just another "AI SDR" — this is GTM engineering infrastructure. Users control the pipeline, see every enrichment decision, and can customize personalization. Transparency + control, not black-box automation.

## Product Principles

1. **Automation over manual**: Invest in making things hands-off. Every manual step is a candidate for automation. If a user does something twice, build a workflow for it.
2. **Quality over volume**: Better to enrich 100 leads with deep research than blast 1,000 with shallow data. Personalization quality drives reply rates, not send volume.
3. **Data freshness is a feature**: Stale contacts are worse than no contacts. The platform should actively monitor and refresh data, not just store it.
4. **Plugin architecture**: Core platform stays lean. Advanced capabilities (PDF generator, LinkedIn extension, email integration) are plugins that can be developed, priced, and shipped independently.
5. **Transparent pricing**: Users should always know what operations cost before they run them. No surprise bills — show credit estimates before execution.
6. **User experience first**: Every interaction should feel fast and intuitive. Lazy load everything, show progress for long operations, provide clear error messages. The product should feel polished even in MVP.
