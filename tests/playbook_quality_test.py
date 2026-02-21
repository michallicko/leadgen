#!/usr/bin/env python3
"""Quality test for playbook template and system prompt generation.

Run standalone:
    cd /Users/michal/git/leadgen-pipeline/.worktrees/playbook-onboarding
    python tests/playbook_quality_test.py

Evaluates build_seeded_template() and build_system_prompt() against 5 real
company enrichment profiles, scoring each on relevance, specificity,
actionability, completeness, and accuracy.
"""

import sys
import os
import textwrap

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.playbook_service import build_seeded_template, build_system_prompt
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 5 real company enrichment profiles (matching _load_enrichment_data structure)
# ---------------------------------------------------------------------------

PROFILES = {
    "Stripe": {
        "company": {
            "name": "Stripe",
            "domain": "stripe.com",
            "industry": "Financial Technology",
            "industry_category": "Payments & Infrastructure",
            "summary": "Stripe builds economic infrastructure for the internet, offering payment processing, billing, and financial tools for businesses of all sizes.",
            "company_size": "8000+",
            "revenue_range": "$1B+",
            "hq_country": "US",
            "hq_city": "San Francisco",
            "tier": "Tier 1 - Platinum",
            "status": "enriched_l2",
        },
        "triage_notes": "Dominant payments platform with strong API-first approach. High technical sophistication. Key decision-makers are engineering leaders and CFOs.",
        "pre_score": 92.0,
        "confidence": 0.95,
        "company_overview": "Stripe processes hundreds of billions of dollars annually for millions of businesses. Their suite includes Stripe Payments, Stripe Billing, Stripe Connect (marketplace payments), Stripe Atlas (incorporation), Stripe Radar (fraud), and Stripe Treasury (banking-as-a-service). They serve everyone from startups to Fortune 500 companies.",
        "ai_opportunities": "AI-driven fraud detection improvements, intelligent payment routing optimization, automated financial reconciliation, smart dunning for subscription recovery, predictive analytics for merchant risk assessment.",
        "pain_hypothesis": "Despite sophisticated internal tooling, Stripe's merchant customers struggle with: (1) complex multi-currency reconciliation, (2) subscription churn management, (3) fraud rule optimization without blocking legitimate transactions, (4) PCI compliance overhead for custom integrations.",
        "quick_wins": "1. Offer a pilot for AI-enhanced fraud rule tuning for their top-tier merchants. 2. Propose a churn prediction model integration with Stripe Billing. 3. Partner on automated compliance documentation generation.",
        "company_intel": "Founded in 2010 by Patrick and John Collison. Last valued at $50B+ (2023). Revenue estimated at $14-16B. Major enterprise push with Stripe Financial Connections and embedded finance. Strong developer community. Competes with Adyen, PayPal/Braintree, and Square.",
        "key_products": "Stripe Payments, Stripe Billing, Stripe Connect, Stripe Radar, Stripe Atlas, Stripe Treasury, Stripe Issuing, Stripe Financial Connections",
        "customer_segments": "Startups and SMBs (self-serve), Mid-market SaaS companies, Enterprise e-commerce, Marketplace platforms, Financial services firms",
        "competitors": "Adyen, PayPal/Braintree, Square (Block), Worldpay, Checkout.com",
        "tech_stack": "Ruby, Scala, Java, React, AWS, custom infrastructure, Sorbet (Ruby type-checker they built)",
        "leadership_team": "Patrick Collison (CEO), John Collison (President), David Singleton (CTO), Dhivya Suryadevara (CFO)",
        "certifications": "PCI DSS Level 1, SOC 1/2, ISO 27001",
        "digital_initiatives": "Embedded finance platform expansion, AI-powered fraud prevention, global payment method coverage (200+ countries), real-time financial reporting, developer experience improvements",
        "hiring_signals": "Actively hiring for AI/ML engineers, enterprise sales, financial partnerships, global expansion roles in APAC and LATAM",
        "ai_adoption_level": "Advanced - internal AI for fraud detection (Radar), payment routing optimization, and risk assessment",
        "growth_indicators": "35% YoY revenue growth, expanding into banking-as-a-service, Treasury product launch, significant enterprise upmarket push",
        "recent_news": "Stripe launched AI-powered revenue optimization tools (2025). Completed tender offer at $65B valuation. Expanded Stripe Financial Connections to 15 new markets.",
        "funding_history": "Series I at $65B valuation (2023). Total funding: $8.7B from Sequoia, Andreessen Horowitz, Tiger Global, and others.",
    },
    "Notion": {
        "company": {
            "name": "Notion",
            "domain": "notion.so",
            "industry": "Productivity Software",
            "industry_category": "Collaboration & Knowledge Management",
            "summary": "Notion is an all-in-one workspace combining notes, docs, wikis, project management, and databases into a single collaborative platform.",
            "company_size": "800-1000",
            "revenue_range": "$250M-500M",
            "hq_country": "US",
            "hq_city": "San Francisco",
            "tier": "Tier 1 - Platinum",
            "status": "enriched_l2",
        },
        "triage_notes": "Product-led growth champion with strong freemium adoption. Team plan upsell is the primary revenue driver. Key buyers are team leads and department heads.",
        "pre_score": 88.0,
        "confidence": 0.92,
        "company_overview": "Notion combines documents, databases, wikis, and project management into one tool. It has 30M+ users globally, with strong adoption in tech companies, startups, and increasingly in enterprise. Their PLG motion drives individual adoption that expands to team and enterprise plans.",
        "ai_opportunities": "AI writing assistance (Notion AI already launched), intelligent knowledge graph for organizational wikis, automated template suggestions based on team workflows, smart search across workspace content, meeting notes auto-generation and action item extraction.",
        "pain_hypothesis": "Notion faces challenges with: (1) enterprise-grade security and compliance requirements (SOC 2 achieved but HIPAA/FedRAMP gaps), (2) performance at scale with large databases, (3) competing with specialized tools (Jira for dev, Confluence for docs, Monday for PM), (4) user onboarding complexity for non-technical teams.",
        "quick_wins": "1. Provide an enterprise security assessment and compliance gap analysis. 2. Offer performance optimization consulting for large-scale deployments. 3. Build a migration toolkit from legacy wiki/PM tools.",
        "company_intel": "Founded by Ivan Zhao and Simon Last (2013). Valued at $10B (2021 funding round). Revenue estimated $250M+ ARR. Strong brand among developers and designers. Recently launched Notion AI, Notion Calendar (acquired Cron), and Notion Sites. Competing for the 'workplace OS' positioning.",
        "key_products": "Notion Workspace, Notion AI, Notion Calendar, Notion Sites, Notion Projects, Notion Databases, API & Integrations platform",
        "customer_segments": "Individual knowledge workers (freemium), Startup teams (Team plan), Mid-market departments (Business plan), Enterprise organizations (Enterprise plan)",
        "competitors": "Confluence (Atlassian), Coda, Monday.com, Asana, ClickUp, Microsoft Loop, Google Workspace",
        "tech_stack": "TypeScript, React, Electron, Kotlin (backend), PostgreSQL, Redis, AWS, custom block-based editor",
        "leadership_team": "Ivan Zhao (CEO/Co-founder), Akshay Kothari (COO), Simon Last (Co-founder)",
        "certifications": "SOC 2 Type II, GDPR compliant, ISO 27001 in progress",
        "digital_initiatives": "Notion AI integration across all features, API ecosystem expansion, enterprise admin controls, Notion Sites for public-facing pages, template marketplace growth",
        "hiring_signals": "Heavy hiring for AI/ML team, enterprise sales, international expansion (Japan, Korea focus), security & compliance engineers",
        "ai_adoption_level": "Moderate-Advanced - Notion AI launched as paid add-on, integrating AI across writing, summarization, and Q&A features",
        "growth_indicators": "30M+ users, expanding from PLG to enterprise sales motion, AI monetization through Notion AI add-on, international expansion in Asia",
        "recent_news": "Notion launched Projects feature to compete with PM tools (2025). Acquired Skiff for end-to-end encryption. Notion AI reaching $100M+ ARR as add-on.",
        "funding_history": "Series C at $10B valuation (2021). Total funding: $343M from Sequoia, Index Ventures, Coatue.",
    },
    "Patagonia": {
        "company": {
            "name": "Patagonia",
            "domain": "patagonia.com",
            "industry": "Outdoor Apparel & Gear",
            "industry_category": "Retail & Consumer Goods",
            "summary": "Patagonia designs outdoor clothing and gear with a mission to save the planet, pioneering sustainable business practices and environmental activism in retail.",
            "company_size": "3000-4000",
            "revenue_range": "$1B+",
            "hq_country": "US",
            "hq_city": "Ventura",
            "tier": "Tier 2 - Gold",
            "status": "enriched_l2",
        },
        "triage_notes": "Mission-driven brand with premium positioning. Unique ownership structure (purpose trust). Purchase decisions driven by brand values alignment and product quality. Sustainability officer and procurement leads are key contacts.",
        "pre_score": 75.0,
        "confidence": 0.88,
        "company_overview": "Patagonia generates $1.5B+ in annual revenue selling outdoor apparel, gear, and provisions. Uniquely, the company was transferred to a purpose trust (Holdfast Collective) in 2022 by founder Yvon Chouinard, with all profits going to fight climate change. They operate 70+ retail stores, robust e-commerce, and a wholesale channel.",
        "ai_opportunities": "Supply chain transparency and traceability optimization, AI-powered demand forecasting to reduce overproduction waste, personalized product recommendations aligned with sustainability values, automated environmental impact reporting, predictive maintenance for Worn Wear (repair) program.",
        "pain_hypothesis": "Patagonia's challenges include: (1) scaling sustainable supply chains while maintaining quality and margins, (2) balancing growth with their anti-consumption ethos ('Don't Buy This Jacket'), (3) authenticating sustainability claims against greenwashing accusations, (4) managing a complex global supply chain with 100+ supplier factories.",
        "quick_wins": "1. Propose a supply chain AI audit for environmental impact optimization. 2. Offer predictive analytics for Worn Wear inventory management. 3. Build a customer lifetime value model incorporating repair/reuse behavior.",
        "company_intel": "Founded 1973 by Yvon Chouinard. Transferred to Holdfast Collective purpose trust (2022). Revenue $1.5B+. Pioneer of 1% for the Planet. Known for 'Don't Buy This Jacket' anti-consumption campaigns. Worn Wear program for clothing repair and resale. B Corp certified since 2012.",
        "key_products": "Technical outerwear, base layers, fleece, wetsuits, outdoor gear, Provisions (food), Worn Wear (resale/repair)",
        "customer_segments": "Outdoor enthusiasts (climbing, skiing, surfing), Environmentally conscious consumers, Corporate sustainability programs, Wholesale outdoor retailers",
        "competitors": "The North Face (VF Corp), Arc'teryx (Amer Sports), REI (co-op), Columbia Sportswear, prAna",
        "tech_stack": "Salesforce Commerce Cloud, SAP (ERP), Oracle (supply chain), custom sustainability tracking tools",
        "leadership_team": "Ryan Gellert (CEO), Yvon Chouinard (Founder), Hilary Dessouky (General Counsel), Helena Price Hambrecht (Board)",
        "certifications": "B Corp, Fair Trade Certified, Bluesign, 1% for the Planet member",
        "digital_initiatives": "Direct-to-consumer e-commerce growth, Worn Wear online platform expansion, supply chain traceability (Footprint Chronicles), digital storytelling for activism campaigns",
        "hiring_signals": "Hiring for e-commerce technology, supply chain sustainability, data analytics, and international market expansion",
        "ai_adoption_level": "Early - primarily using analytics for demand planning and supply chain optimization, exploring AI for sustainability metrics",
        "growth_indicators": "Revenue growth despite anti-consumption messaging, international expansion, Worn Wear growing as circular economy model, B2B corporate gifting program expansion",
        "recent_news": "Patagonia expanded Worn Wear program internationally (2025). Launched regenerative organic cotton collection. Purpose trust model inspiring other companies.",
        "funding_history": "Privately held, no external funding. Transferred to Holdfast Collective purpose trust in 2022.",
    },
    "Datadog": {
        "company": {
            "name": "Datadog",
            "domain": "datadoghq.com",
            "industry": "Cloud Monitoring & Analytics",
            "industry_category": "DevOps & Observability",
            "summary": "Datadog is a monitoring and security platform for cloud applications, providing infrastructure monitoring, APM, log management, and security analytics.",
            "company_size": "5000-6000",
            "revenue_range": "$2B+",
            "hq_country": "US",
            "hq_city": "New York",
            "tier": "Tier 1 - Platinum",
            "status": "enriched_l2",
        },
        "triage_notes": "Public company (NASDAQ: DDOG) with strong land-and-expand model. Technical buyers (SREs, DevOps, platform engineers) drive adoption. Expansion is upsell across product modules. VP Eng and CTO are strategic decision-makers.",
        "pre_score": 90.0,
        "confidence": 0.94,
        "company_overview": "Datadog (NASDAQ: DDOG) provides a unified observability and security platform. Revenue $2.1B+ (FY2024). 27,000+ customers, with 3,200+ spending $100K+ ARR. Products span infrastructure monitoring, APM, log management, synthetic monitoring, real user monitoring, security (SIEM, CSPM), CI visibility, and database monitoring.",
        "ai_opportunities": "AIOps for automated root cause analysis, intelligent alerting to reduce noise, AI-powered log pattern detection, automated runbook generation from incident history, LLM-based query assistance for non-technical users, predictive scaling recommendations.",
        "pain_hypothesis": "Datadog customers face: (1) alert fatigue from too many monitoring signals, (2) cost management challenges as data volume scales, (3) bridging the gap between observability data and actionable remediation, (4) skill gaps in SRE/DevOps teams for advanced features, (5) vendor lock-in concerns with proprietary query language.",
        "quick_wins": "1. Offer an alert optimization audit to reduce noise by 50%+. 2. Propose a cost optimization review for log indexing strategies. 3. Build a custom integration for their biggest customer pain points.",
        "company_intel": "Founded 2010 by Olivier Pomel (CEO) and Alexis Le-Quoc (CTO). IPO 2019. Market cap ~$40B. Known for strong execution and land-and-expand GTM. Average customer uses 4+ product modules. Net revenue retention rate 120%+. Competing in the consolidation of DevOps toolchain.",
        "key_products": "Infrastructure Monitoring, APM & Distributed Tracing, Log Management, Synthetic Monitoring, Real User Monitoring (RUM), Security (Cloud SIEM, CSPM), CI Visibility, Database Monitoring, Workflow Automation",
        "customer_segments": "Cloud-native startups, Mid-market engineering teams, Enterprise DevOps/SRE organizations, Security operations teams, Platform engineering teams",
        "competitors": "Splunk (Cisco), New Relic, Dynatrace, Elastic, Grafana Labs, PagerDuty",
        "tech_stack": "Go, Python, React, Kafka, Cassandra, custom time-series database, Kubernetes, multi-cloud (AWS/GCP/Azure)",
        "leadership_team": "Olivier Pomel (CEO/Co-founder), Alexis Le-Quoc (CTO/Co-founder), David Obstler (CFO), Ami Aharonovich (SVP Engineering)",
        "certifications": "SOC 2 Type II, ISO 27001, FedRAMP Moderate (in progress), HIPAA, PCI DSS",
        "digital_initiatives": "Bits AI (LLM-powered assistant for incidents), OpenTelemetry native support, unified security and observability platform, Flex Logs for cost-effective log storage, Workflow Automation for incident response",
        "hiring_signals": "Aggressive hiring for AI/ML engineers, sales (enterprise and commercial), product managers for security products, and APAC/EMEA expansion",
        "ai_adoption_level": "Advanced - Bits AI assistant launched, ML-driven anomaly detection, automated root cause analysis, Watchdog AI for proactive alerts",
        "growth_indicators": "25%+ YoY revenue growth, customer count growing 15%+ YoY, $100K+ customer cohort expanding, security products fastest-growing segment",
        "recent_news": "Datadog launched Bits AI assistant for natural language incident investigation (2025). Acquired Cloudcraft for infrastructure diagramming. Expanded FedRAMP offerings.",
        "funding_history": "IPO September 2019 at $10.4B valuation. Total pre-IPO funding: $148M from Index Ventures, OpenView, RTP Ventures.",
    },
    "Oscar Health": {
        "company": {
            "name": "Oscar Health",
            "domain": "hioscar.com",
            "industry": "Health Insurance",
            "industry_category": "Healthcare & InsurTech",
            "summary": "Oscar Health is a technology-driven health insurance company using data, technology, and design to make health insurance simpler, smarter, and more affordable.",
            "company_size": "3000-4000",
            "revenue_range": "$5B+",
            "hq_country": "US",
            "hq_city": "New York",
            "tier": "Tier 2 - Gold",
            "status": "enriched_l2",
        },
        "triage_notes": "Public InsurTech company (NYSE: OSCR) with strong tech DNA. Key buyers are technology leaders and operations executives. Regulated industry with long sales cycles. Focus on individual and small group markets.",
        "pre_score": 78.0,
        "confidence": 0.85,
        "company_overview": "Oscar Health (NYSE: OSCR) is a tech-first health insurance company serving 1.5M+ members. Revenue $6.5B+ (FY2024, mostly premiums). They differentiate through a proprietary technology platform (+Oscar), telemedicine, and member engagement tools. Operating in individual, small group, and Medicare Advantage markets across 20+ states.",
        "ai_opportunities": "AI-powered care navigation and triage, predictive risk adjustment optimization, automated claims processing and fraud detection, personalized member health recommendations, NLP for medical records analysis, chatbot-driven member support.",
        "pain_hypothesis": "Oscar faces: (1) medical loss ratio optimization — balancing member care costs with premium revenue, (2) provider network management complexity, (3) regulatory compliance across 20+ state markets, (4) member engagement and retention in competitive ACA marketplace, (5) scaling +Oscar platform licensing to other payers.",
        "quick_wins": "1. Propose an AI-driven claims anomaly detection pilot. 2. Offer member engagement optimization through predictive outreach models. 3. Build a regulatory compliance automation tool for multi-state operations.",
        "company_intel": "Founded 2012 by Joshua Kushner, Mario Schlosser, and Kevin Nazemi. IPO March 2021 (NYSE: OSCR). First operating profit in 2024. +Oscar technology platform licensed to other health insurers. Key differentiator: full-stack technology platform vs legacy insurers. Cigna partnership for small group market.",
        "key_products": "+Oscar technology platform, Individual health plans (ACA marketplace), Small group plans, Medicare Advantage plans, Oscar Care (telemedicine), Virtual Primary Care",
        "customer_segments": "Individual ACA marketplace members, Small business employers, Medicare-eligible seniors, Health insurance companies (platform licensing via +Oscar)",
        "competitors": "UnitedHealth Group, Anthem (Elevance Health), Centene, Clover Health, Bright Health (defunct), Alignment Healthcare",
        "tech_stack": "Python, Kotlin, React, PostgreSQL, Kubernetes, AWS, Snowflake, custom claims processing engine",
        "leadership_team": "Mark Bertolini (CEO, former Aetna CEO), Mario Schlosser (Co-founder, CTO), Scott Blackley (CFO)",
        "certifications": "HITRUST CSF, SOC 2 Type II, HIPAA compliant, state insurance department licenses in 20+ states",
        "digital_initiatives": "+Oscar platform licensing to external payers, virtual-first care models, AI-powered care navigation, member mobile app redesign, data-driven provider network optimization",
        "hiring_signals": "Hiring for data science, actuarial, product engineering, regulatory affairs, and Medicare Advantage expansion roles",
        "ai_adoption_level": "Moderate-Advanced - using AI for claims processing, risk adjustment, member engagement predictions, and care pathway recommendations",
        "growth_indicators": "1.5M+ members, first operating profit (2024), +Oscar platform licensing gaining traction, Medicare Advantage market expansion, revenue 25%+ YoY growth",
        "recent_news": "Oscar Health reported first-ever annual operating profit (2024). Expanded +Oscar licensing to two new payer partners. Launched AI care navigation for members.",
        "funding_history": "IPO March 2021. Total funding: $1.6B from Thrive Capital, Founders Fund, Khosla Ventures, Google Capital (GV), Fidelity.",
    },
}

# ---------------------------------------------------------------------------
# Scoring criteria
# ---------------------------------------------------------------------------

CRITERIA = [
    ("relevance", "Does the content relate specifically to THIS company's industry and context?"),
    ("specificity", "Does it use concrete data, names, numbers from the enrichment profile?"),
    ("actionability", "Could someone act on this content without additional research?"),
    ("completeness", "Are all sections populated with meaningful content (not generic placeholders)?"),
    ("accuracy", "Are the facts consistent with the enrichment data provided?"),
]


def score_template(company_name, template_text, enrichment_data):
    """Score a generated template against quality criteria.

    Returns a dict of criterion -> (score, notes).
    """
    scores = {}
    co = enrichment_data.get("company", {})

    # 1. Relevance: check for company-specific terms
    relevance_hits = 0
    relevance_checks = [
        co.get("name", ""),
        co.get("industry", ""),
        co.get("industry_category", ""),
    ]
    # Add some L2 keywords
    for field in ["ai_opportunities", "pain_hypothesis", "company_overview"]:
        val = enrichment_data.get(field, "")
        if val:
            # Take first significant keyword from each
            words = [w for w in val.split() if len(w) > 6][:3]
            relevance_checks.extend(words)

    for check in relevance_checks:
        if check and check.lower() in template_text.lower():
            relevance_hits += 1
    relevance_score = min(5.0, (relevance_hits / max(len(relevance_checks), 1)) * 5)
    scores["relevance"] = (relevance_score, "{}/{} terms found".format(
        relevance_hits, len(relevance_checks)))

    # 2. Specificity: check for concrete data points
    specificity_hits = 0
    specificity_checks = []
    # Products
    products = enrichment_data.get("key_products", "")
    if products:
        for p in products.split(",")[:3]:
            specificity_checks.append(p.strip())
    # Competitors
    comps = enrichment_data.get("competitors", "")
    if comps:
        for c in comps.split(",")[:3]:
            specificity_checks.append(c.strip())
    # Leadership
    leaders = enrichment_data.get("leadership_team", "")
    if leaders:
        # Check for at least one leader name
        first_leader = leaders.split(",")[0].split("(")[0].strip()
        specificity_checks.append(first_leader)
    # Revenue/size
    rev = co.get("revenue_range", "")
    if rev:
        specificity_checks.append(rev)
    size = co.get("company_size", "")
    if size:
        specificity_checks.append(size)

    for check in specificity_checks:
        if check and check.lower() in template_text.lower():
            specificity_hits += 1
    specificity_score = min(5.0, (specificity_hits / max(len(specificity_checks), 1)) * 5)
    scores["specificity"] = (specificity_score, "{}/{} data points found".format(
        specificity_hits, len(specificity_checks)))

    # 3. Actionability: check for action-oriented language
    action_keywords = [
        "target", "focus on", "prioritize", "reach out", "leverage",
        "pilot", "propose", "offer", "build", "launch", "test",
        "identify", "engage", "partner", "optimize",
    ]
    action_hits = sum(1 for kw in action_keywords if kw in template_text.lower())
    actionability_score = min(5.0, (action_hits / 5) * 5)
    scores["actionability"] = (actionability_score, "{}/{} action keywords".format(
        action_hits, len(action_keywords)))

    # 4. Completeness: check all sections have real content (not just placeholders)
    sections = [
        "Executive Summary",
        "Ideal Customer Profile",
        "Buyer Personas",
        "Value Proposition",
        "Competitive Positioning",
        "Channel Strategy",
        "Messaging Framework",
        "Metrics",
        "90-Day Action Plan",
    ]
    generic_phrases = [
        "define your", "identify", "outline your", "set measurable",
        "break your strategy", "articulate your",
    ]
    populated_sections = 0
    for section in sections:
        if section in template_text:
            # Find the section content
            idx = template_text.index(section)
            # Get text until next ## or end
            rest = template_text[idx + len(section):]
            next_section = rest.find("\n## ")
            if next_section > 0:
                section_content = rest[:next_section].strip()
            else:
                section_content = rest.strip()

            # Check if it has real content (not just a generic placeholder)
            is_generic = any(gp in section_content.lower() for gp in generic_phrases)
            has_substance = len(section_content) > 80

            if has_substance and not is_generic:
                populated_sections += 1

    completeness_score = (populated_sections / len(sections)) * 5
    scores["completeness"] = (completeness_score, "{}/{} sections with real content".format(
        populated_sections, len(sections)))

    # 5. Accuracy: cross-reference facts
    accuracy_checks = 0
    accuracy_hits = 0
    # Check key facts are correctly represented
    if co.get("name"):
        accuracy_checks += 1
        if co["name"] in template_text:
            accuracy_hits += 1
    if co.get("industry"):
        accuracy_checks += 1
        if co["industry"] in template_text:
            accuracy_hits += 1
    if co.get("hq_city"):
        accuracy_checks += 1
        if co["hq_city"] in template_text:
            accuracy_hits += 1
    # Check L2 data snippets appear correctly
    for field in ["ai_opportunities", "pain_hypothesis", "quick_wins"]:
        val = enrichment_data.get(field, "")
        if val:
            accuracy_checks += 1
            # Check first clause appears
            first_clause = val.split(".")[0].split(",")[0][:50]
            if first_clause.lower() in template_text.lower():
                accuracy_hits += 1

    accuracy_score = (accuracy_hits / max(accuracy_checks, 1)) * 5
    scores["accuracy"] = (accuracy_score, "{}/{} facts verified".format(
        accuracy_hits, accuracy_checks))

    return scores


def run_quality_test():
    """Run the quality test suite and print results."""
    print("=" * 70)
    print("PLAYBOOK TEMPLATE QUALITY TEST")
    print("=" * 70)
    print()

    all_scores = {}
    all_pass = True

    for company_name, enrichment_data in PROFILES.items():
        print("-" * 60)
        print("Company: {}".format(company_name))
        print("-" * 60)

        # Generate template
        objective = "Build a GTM strategy to sell AI-powered solutions to {} and similar companies".format(
            enrichment_data["company"]["industry"]
        )
        template = build_seeded_template(
            objective=objective,
            enrichment_data=enrichment_data,
        )

        # Print template excerpt (first 500 chars)
        print()
        print("Template excerpt:")
        print(textwrap.indent(template[:600], "  "))
        if len(template) > 600:
            print("  ... ({} total chars)".format(len(template)))
        print()

        # Score it
        scores = score_template(company_name, template, enrichment_data)
        all_scores[company_name] = scores

        total = 0
        for criterion, (score, notes) in scores.items():
            status = "PASS" if score >= 4.0 else "FAIL"
            if score < 4.0:
                all_pass = False
            print("  {}: {:.1f}/5.0 ({}) [{}]".format(
                criterion.ljust(15), score, notes, status))
            total += score

        avg = total / len(scores)
        print()
        print("  AVERAGE: {:.1f}/5.0 {}".format(
            avg, "PASS" if avg >= 4.0 else "FAIL"))
        print()

    # Also test system prompt
    print("-" * 60)
    print("SYSTEM PROMPT QUALITY CHECK")
    print("-" * 60)
    print()

    # Pick one company for system prompt test
    test_company = "Stripe"
    enrichment = PROFILES[test_company]

    tenant = MagicMock()
    tenant.name = test_company
    doc = MagicMock()
    doc.content = build_seeded_template(
        objective="Sell AI solutions",
        enrichment_data=enrichment,
    )
    doc.objective = "Sell AI solutions to fintech companies"

    prompt = build_system_prompt(tenant, doc, enrichment_data=enrichment)

    # Check system prompt has structured research data
    prompt_checks = {
        "Company name in prompt": test_company in prompt,
        "Industry context": enrichment["company"]["industry"] in prompt,
        "Enrichment data present": "Research Data" in prompt or "research" in prompt.lower(),
        "Structured sections": prompt.count("---") >= 2,
        "Action-oriented tone": "specific" in prompt.lower() or "actionable" in prompt.lower(),
        "GTM role established": "gtm" in prompt.lower() or "go-to-market" in prompt.lower(),
    }

    prompt_pass = True
    for check_name, passed in prompt_checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            prompt_pass = False
        print("  {}: {}".format(check_name.ljust(30), status))

    print()
    print("  System prompt length: {} chars".format(len(prompt)))
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    for company_name, scores in all_scores.items():
        avg = sum(s for s, _ in scores.values()) / len(scores)
        status = "PASS" if avg >= 4.0 else "FAIL"
        print("  {}: {:.1f}/5.0 [{}]".format(company_name.ljust(15), avg, status))

    print()
    overall_avg = sum(
        sum(s for s, _ in scores.values()) / len(scores)
        for scores in all_scores.values()
    ) / len(all_scores)
    print("  Overall average: {:.1f}/5.0".format(overall_avg))
    print("  System prompt: {}".format("PASS" if prompt_pass else "FAIL"))
    print()

    if all_pass and prompt_pass:
        print("  RESULT: ALL QUALITY GATES PASSED")
        return 0
    else:
        print("  RESULT: QUALITY GATES FAILED — iteration needed")
        return 1


if __name__ == "__main__":
    sys.exit(run_quality_test())
