-- Migration 038: Strategy Templates
-- Creates the strategy_templates table and seeds 3 system templates.

CREATE TABLE IF NOT EXISTS strategy_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    content_template TEXT NOT NULL,
    extracted_data_template JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_templates_tenant
    ON strategy_templates (tenant_id);
CREATE INDEX IF NOT EXISTS idx_strategy_templates_system
    ON strategy_templates (is_system) WHERE is_system = TRUE;

-- Seed: B2B SaaS — New Market Entry
INSERT INTO strategy_templates (name, description, category, content_template, extracted_data_template, is_system)
VALUES (
    'B2B SaaS — New Market Entry',
    'Comprehensive GTM framework for SaaS companies entering a new geographic or vertical market. Covers positioning, ICP definition, outbound sequences, and success metrics.',
    'SaaS',
    '# GTM Strategy: {{company_name}} — New Market Entry

## Executive Summary

{{company_name}} is expanding into {{target_market}}. This strategy outlines a phased approach to establish presence, generate pipeline, and achieve first revenue in the new market.

## Ideal Customer Profile

**Industry:** {{target_industry}}
**Company Size:** {{company_size_range}}
**Key Personas:**
- {{persona_1_title}} — Primary decision maker
- {{persona_2_title}} — Technical evaluator
- {{persona_3_title}} — Budget holder

**Qualifying Signals:**
- Currently using {{competitor_or_category}}
- Recently raised funding or expanded team
- Active on LinkedIn discussing {{pain_point_topic}}

## Positioning & Messaging

**Value Proposition:** {{one_line_value_prop}}

**Key Messages by Persona:**
1. For {{persona_1_title}}: Focus on business outcomes and ROI
2. For {{persona_2_title}}: Focus on technical capabilities and integration
3. For {{persona_3_title}}: Focus on cost savings and efficiency gains

## Outbound Strategy

### Channel Mix
- **LinkedIn:** Connection requests + 3-touch sequence
- **Email:** 5-step cold outbound sequence
- **Events:** {{target_market}} industry conferences

### Sequence Design
1. **Day 1:** Personalized connection request referencing {{trigger_event}}
2. **Day 3:** Value-first message sharing relevant insight
3. **Day 7:** Case study or social proof from similar company
4. **Day 14:** Direct ask for 15-minute discovery call
5. **Day 21:** Break-up message with useful resource

## Success Metrics

| Metric | Target (Month 1) | Target (Month 3) | Target (Month 6) |
|--------|------------------|------------------|------------------|
| Outreach volume | {{m1_outreach}} | {{m3_outreach}} | {{m6_outreach}} |
| Response rate | 5-8% | 8-12% | 12-15% |
| Meetings booked | {{m1_meetings}} | {{m3_meetings}} | {{m6_meetings}} |
| Pipeline value | {{m1_pipeline}} | {{m3_pipeline}} | {{m6_pipeline}} |

## Risk Mitigation

- **Low response rates:** A/B test messaging, adjust ICP criteria
- **Long sales cycles:** Introduce product-led motion or free assessment
- **Competitive pressure:** Develop battlecards and competitive positioning',
    '{"target_market": "", "target_industry": "", "company_size_range": "50-500 employees", "personas": [], "channels": ["linkedin", "email"]}',
    TRUE
)
ON CONFLICT DO NOTHING;

-- Seed: Professional Services — Local Market
INSERT INTO strategy_templates (name, description, category, content_template, extracted_data_template, is_system)
VALUES (
    'Professional Services — Local Market',
    'GTM framework for professional services firms (consulting, agencies, legal, accounting) targeting local or regional markets through relationship-driven outbound.',
    'Services',
    '# GTM Strategy: {{company_name}} — Local Market Growth

## Executive Summary

{{company_name}} provides {{service_type}} to {{target_segment}} in the {{geographic_area}} region. This strategy focuses on relationship-driven business development and referral networks.

## Target Market Definition

**Geography:** {{geographic_area}}
**Segments:**
- {{segment_1}} — Primary focus
- {{segment_2}} — Secondary focus
- {{segment_3}} — Expansion target

**Ideal Client Profile:**
- Annual revenue: {{revenue_range}}
- Employee count: {{employee_range}}
- Current pain: {{primary_pain_point}}

## Relationship Development Strategy

### Referral Network
- **Existing clients:** Systematic referral asks after successful deliverables
- **Partners:** {{partner_type}} firms with complementary services
- **Advisors:** Local {{advisor_type}} who serve the same client base

### Thought Leadership
- Monthly insights on {{expertise_topic}}
- Speaking at {{local_event_type}} events
- Guest posts on local business publications

## Outreach Sequences

### Warm Introduction Path
1. Research prospect + find mutual connection
2. Ask for warm intro via LinkedIn or email
3. Follow up with personalized value message
4. Propose coffee meeting or office visit

### Cold Outreach Path
1. **Day 1:** Personalized email referencing local context
2. **Day 4:** LinkedIn connection with note
3. **Day 8:** Share relevant case study from similar local business
4. **Day 15:** Phone call with specific value proposition
5. **Day 22:** Final touch with complimentary assessment offer

## Metrics & Goals

| Activity | Weekly Target | Monthly Target |
|----------|--------------|----------------|
| New connections | {{weekly_connections}} | {{monthly_connections}} |
| Coffee meetings | {{weekly_meetings}} | {{monthly_meetings}} |
| Proposals sent | — | {{monthly_proposals}} |
| New clients | — | {{monthly_new_clients}} |

## Quarterly Review Checklist

- [ ] Pipeline health: enough prospects in each stage?
- [ ] Referral sources: who sent business this quarter?
- [ ] Market feedback: what are prospects saying about our positioning?
- [ ] Competitive landscape: any new entrants or changes?',
    '{"geographic_area": "", "service_type": "", "target_segment": "", "channels": ["linkedin", "email", "phone", "events"]}',
    TRUE
)
ON CONFLICT DO NOTHING;

-- Seed: Tech Startup — First Outbound
INSERT INTO strategy_templates (name, description, category, content_template, extracted_data_template, is_system)
VALUES (
    'Tech Startup — First Outbound',
    'Lean GTM playbook for early-stage startups running their first outbound motion. Focuses on founder-led sales, rapid iteration, and learning what resonates.',
    'Startup',
    '# GTM Strategy: {{company_name}} — First Outbound Campaign

## Executive Summary

{{company_name}} is launching its first structured outbound effort. As a {{stage}} startup, the primary goal is learning — finding product-market fit through direct conversations with potential customers.

## Discovery Questions (Answer Before Starting)

1. Who are your best existing customers and why did they buy?
2. What problem does your product solve that alternatives cannot?
3. Where do your target buyers spend time online?
4. What is your average deal size and sales cycle?

## ICP Hypothesis

**Company Profile:**
- Industry: {{target_industry}}
- Size: {{company_size}}
- Tech stack: Uses {{relevant_tools}}
- Growth signals: {{growth_signals}}

**Buyer Persona:**
- Title: {{buyer_title}}
- Reports to: {{reports_to}}
- Day-to-day challenges: {{daily_challenges}}
- Success metrics: {{success_metrics}}

## Messaging Framework

### Subject Line Templates
1. "Quick question about {{pain_point}}"
2. "{{mutual_connection}} suggested I reach out"
3. "Saw your post about {{topic}} — thought this might help"

### Email Body Framework
- **Hook:** Reference something specific about the prospect
- **Problem:** Name the pain point you solve
- **Proof:** One sentence on results for a similar company
- **Ask:** Specific, low-commitment CTA (15-min call, not a demo)

## 30-Day Sprint Plan

### Week 1: Foundation
- [ ] Finalize ICP hypothesis (above)
- [ ] Build prospect list: 100 contacts matching ICP
- [ ] Write 3 email variants for A/B testing
- [ ] Set up tracking (open rates, reply rates)

### Week 2: First Sends
- [ ] Send Batch 1: 30 prospects, Variant A vs B
- [ ] Monitor opens and replies daily
- [ ] Respond to every reply within 2 hours

### Week 3: Iterate
- [ ] Analyze Week 2 results: which variant won?
- [ ] Refine messaging based on replies and objections
- [ ] Send Batch 2: 40 prospects with winning variant
- [ ] Book first discovery calls

### Week 4: Scale What Works
- [ ] Double down on winning message + channel
- [ ] Send Batch 3: 30 prospects
- [ ] Document learnings: what ICP responded best?
- [ ] Plan Month 2 with refined approach

## Key Metrics to Track

| Metric | Target | Red Flag |
|--------|--------|----------|
| Emails sent per week | 30-50 | < 20 |
| Open rate | > 40% | < 25% |
| Reply rate | > 5% | < 2% |
| Positive reply rate | > 2% | < 0.5% |
| Meetings booked | 2-4/week | 0 for 2 weeks |

## Learning Log

After each batch, document:
- What messaging resonated?
- What objections came up?
- Any surprises about ICP fit?
- Adjustments for next batch',
    '{"stage": "seed", "target_industry": "", "company_size": "10-200 employees", "channels": ["email", "linkedin"]}',
    TRUE
)
ON CONFLICT DO NOTHING;
