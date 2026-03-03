# Leadgen Pipeline — AI Token Cost & Unit Economics Analysis

**Date:** 2026-02-22
**Author:** Business Model Analysis (automated from codebase)
**Data Sources:** Production code, test cost reports (2026-02-20), API pricing docs

---

## 1. Service-by-Service Cost Breakdown

### 1.1 L1 Enrichment (Company Profile)

**File:** `api/services/l1_enricher.py`
**Model:** Perplexity `sonar` (standard) / `sonar-pro` (boost)
**Calls per company:** 1 Perplexity call

| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~559 tokens (system prompt ~400 + user prompt ~159) |
| Output tokens | ~260 tokens (avg from 17 test calls: range 205-384) |
| Model | `sonar` ($1/$1 per 1M tokens) |
| Cost per company | **$0.00082** (avg from test data) |

**System prompt:** 456 chars (~114 tokens) - B2B research assistant instructions.
**User prompt:** ~1,800 chars (~450 tokens) - company name, domain, contacts, claims, website content (truncated to 4,000 chars).
**Website scraping:** HTTP GET with 10s timeout, BeautifulSoup extraction, truncated to 4,000 chars. No API cost, negligible compute.

**Boost mode (sonar-pro):** Would increase cost to ~$0.005/company ($3/$15 per 1M tokens).

### 1.2 L2 Enrichment (Deep Research)

**File:** `api/services/l2_enricher.py`
**Calls per company:** 2 Perplexity + 1 Anthropic = **3 LLM calls**

#### Phase 1a: News Research (Perplexity)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~496 tokens |
| Output tokens | ~165 tokens (range 89-434) |
| Model | `sonar-pro` ($3/$15 per 1M tokens) |
| Cost per call | **$0.0040** (avg from 9 test calls) |

#### Phase 1b: Strategic Signals (Perplexity)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~384 tokens |
| Output tokens | ~140 tokens (range 63-247) |
| Model | `sonar-pro` ($3/$15 per 1M tokens) |
| Cost per call | **$0.0032** (avg from 9 test calls) |

#### Phase 2: Synthesis (Anthropic)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~792 tokens |
| Output tokens | ~1,854 tokens (range 399-2,184) |
| Model | `claude-sonnet-4-5-20250929` ($3/$15 per 1M tokens) |
| Cost per call | **$0.0072** (avg from 5 test calls) |

**Total L2 cost per company:** **$0.0144** (avg)

### 1.3 Person Enrichment (Contact-Level)

**File:** `api/services/person_enricher.py`
**Calls per contact:** 2 Perplexity + 1 Anthropic = **3 LLM calls**

#### Profile Research (Perplexity)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~598 tokens |
| Output tokens | ~290 tokens (range 128-368) |
| Model | `sonar` ($1/$1 per 1M tokens) |
| Cost per call | **$0.00089** (avg from 9 test calls) |

#### Decision Signals (Perplexity)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~530 tokens |
| Output tokens | ~148 tokens (range 89-274) |
| Model | `sonar` ($1/$1 per 1M tokens) |
| Cost per call | **$0.00069** (avg from 8 test calls) |

#### Personalization Synthesis (Anthropic)
| Metric | Measured Value |
|--------|---------------|
| Input tokens | ~507 tokens |
| Output tokens | ~538 tokens (range 399-637) |
| Model | `claude-sonnet-4-5-20250929` ($3/$15 per 1M tokens) |
| Cost per call | **$0.00258** (avg from 5 test calls) |

**Total Person cost per contact:** **$0.0042** (avg)

### 1.4 Playbook Chat (GTM Strategy Assistant)

**File:** `api/services/playbook_service.py`, `api/routes/playbook_routes.py`
**Model:** `claude-haiku-4-5-20251001` ($1/$5 per 1M tokens) via `AnthropicClient` default
**Calls per message:** 1 Anthropic call (streaming or sync)

| Metric | Estimated Value |
|--------|----------------|
| System prompt | ~3,000-6,000 chars (~750-1,500 tokens) depending on enrichment data |
| Chat history | Up to 20 messages (MAX_HISTORY_MESSAGES), ~200 tokens each = ~4,000 tokens |
| User message | ~100 tokens |
| Total input | ~2,000-5,500 tokens per turn |
| Output tokens | ~500-2,000 tokens (max_tokens=4,096) |
| Model | `claude-haiku-4-5-20251001` ($1/$5 per 1M tokens) |
| Cost per message | **$0.0040-$0.0145** |
| Avg estimated | **$0.008** per chat turn |

**Note:** System prompt includes: tenant context, 8-section strategy structure, current document content (could be large), and enrichment data (company profile, L1/L2 fields). The cost grows as the document grows and chat history accumulates.

### 1.5 Playbook Extract (Strategy Data Extraction)

**File:** `api/routes/playbook_routes.py` (extract_strategy endpoint)
**Model:** `claude-haiku-4-5-20251001` (AnthropicClient default)
**Calls per extraction:** 1

| Metric | Estimated Value |
|--------|----------------|
| System prompt | ~600 tokens (extraction schema + instructions) |
| User content | Full strategy document (~2,000-8,000 tokens) |
| Output tokens | ~500-1,500 tokens (structured JSON) |
| Model | `claude-haiku-4-5-20251001` ($1/$5 per 1M tokens) |
| Cost per extraction | **$0.005-$0.015** |
| Avg estimated | **$0.008** per extraction |

**Frequency:** Triggered manually by user after editing playbook. Expected: 1-3 times per company.

### 1.6 Playbook Self-Research (Company Self-Enrichment)

**File:** `api/routes/playbook_routes.py` (_run_self_research)
**Calls per research trigger:** L1 + L2 = all calls from 1.1 + 1.2

| Metric | Value |
|--------|-------|
| Cost per trigger | **$0.015** (L1 $0.0008 + L2 $0.0144) |
| Frequency | 1-2 times per tenant (initial setup + optional re-research) |

### 1.7 Message Generation

**File:** `api/services/message_generator.py`
**Model:** `claude-haiku-3-5-20241022` ($0.80/$4.00 per 1M tokens)
**Calls per message:** 1

| Metric | Measured/Estimated Value |
|--------|--------------------------|
| System prompt | ~200 tokens (SYSTEM_PROMPT constant — B2B copywriter instructions) |
| User prompt | ~600-1,200 tokens (contact data, company data, enrichment, strategy, sequence context) |
| Total input | ~800-1,400 tokens |
| Output tokens | ~200-400 tokens (JSON with subject + body) |
| Model | `claude-haiku-3-5-20241022` ($0.80/$4.00 per 1M tokens) |
| Cost per message | **$0.0016** (estimated from compute_cost with EST_INPUT=800, EST_OUTPUT=200) |

**Note:** Message generation uses Haiku 3.5 (older, cheaper model). The code hardcodes `GENERATION_MODEL = "claude-haiku-3-5-20241022"`.

**Messages per contact:** Typically 3-5 steps in a campaign sequence (LinkedIn connect, LinkedIn message, email, follow-up).

---

## 2. Pricing Reference (Verified February 2026)

### Perplexity Models
| Model | Input $/1M tokens | Output $/1M tokens | Used For |
|-------|-------------------|---------------------|----------|
| `sonar` | $1.00 | $1.00 | L1 enrichment, Person profile/signals |
| `sonar-pro` | $3.00 | $15.00 | L2 news, L2 signals |
| `sonar-reasoning-pro` | $2.00 | $8.00 | L2 boost mode |

### Anthropic Models
| Model | Input $/1M tokens | Output $/1M tokens | Used For |
|-------|-------------------|---------------------|----------|
| `claude-haiku-3-5-20241022` | $0.80 | $4.00 | Message generation |
| `claude-haiku-4-5-20251001` | $1.00 | $5.00 | Playbook chat, extraction (default) |
| `claude-sonnet-4-5-20250929` | $3.00 | $15.00 | L2 synthesis, Person synthesis |

---

## 3. Full Pipeline Cost Per Entity

### Per Company (L1 + L2)
| Stage | Calls | Cost |
|-------|-------|------|
| L1 (sonar) | 1 | $0.0008 |
| L2 News (sonar-pro) | 1 | $0.0040 |
| L2 Signals (sonar-pro) | 1 | $0.0032 |
| L2 Synthesis (sonnet 4.5) | 1 | $0.0072 |
| **Total per company** | **4** | **$0.0152** |

### Per Contact (Person Enrichment)
| Stage | Calls | Cost |
|-------|-------|------|
| Profile (sonar) | 1 | $0.0009 |
| Signals (sonar) | 1 | $0.0007 |
| Synthesis (sonnet 4.5) | 1 | $0.0026 |
| **Total per contact** | **3** | **$0.0042** |

### Per Message (Generation)
| Stage | Calls | Cost |
|-------|-------|------|
| Generation (haiku 3.5) | 1 | $0.0016 |
| **Regeneration** (optional) | 1 | $0.0016 |

### Per Chat Message (Playbook)
| Stage | Calls | Cost |
|-------|-------|------|
| Chat turn (haiku 4.5) | 1 | $0.008 |

### Per Playbook Setup (Self-Research)
| Stage | Calls | Cost |
|-------|-------|------|
| Self-research (L1+L2) | 4 | $0.015 |
| Extraction | 1 | $0.008 |
| **Total per setup** | **5** | **$0.023** |

---

## 4. Monthly Cost Per User Scenarios

### Assumptions
- Each company has ~2-3 contacts on average
- Campaign messages: 4 steps per contact (LinkedIn connect, LinkedIn message, email, follow-up)
- Playbook: 1 self-research + 1 extraction per tenant
- All costs are API costs only (no hosting/infra)

### Light User (Solo SDR / Early Adopter)
| Activity | Volume | Unit Cost | Total |
|----------|--------|-----------|-------|
| L1 Enrichment | 50 companies | $0.0008 | $0.04 |
| L2 Enrichment | 50 companies | $0.0144 | $0.72 |
| Person Enrichment | 100 contacts | $0.0042 | $0.42 |
| Chat Messages | 20 messages | $0.008 | $0.16 |
| Generated Messages | 50 messages | $0.0016 | $0.08 |
| Playbook Setup | 1 | $0.023 | $0.02 |
| **Total API Cost** | | | **$1.44** |

### Medium User (Active Sales Team Member)
| Activity | Volume | Unit Cost | Total |
|----------|--------|-----------|-------|
| L1 Enrichment | 200 companies | $0.0008 | $0.16 |
| L2 Enrichment | 200 companies | $0.0144 | $2.88 |
| Person Enrichment | 500 contacts | $0.0042 | $2.10 |
| Chat Messages | 100 messages | $0.008 | $0.80 |
| Generated Messages | 200 messages | $0.0016 | $0.32 |
| Playbook Setup | 1 | $0.023 | $0.02 |
| **Total API Cost** | | | **$6.28** |

### Heavy User (Power User / Sales Manager)
| Activity | Volume | Unit Cost | Total |
|----------|--------|-----------|-------|
| L1 Enrichment | 500 companies | $0.0008 | $0.40 |
| L2 Enrichment | 500 companies | $0.0144 | $7.20 |
| Person Enrichment | 1,500 contacts | $0.0042 | $6.30 |
| Chat Messages | 300 messages | $0.008 | $2.40 |
| Generated Messages | 500 messages | $0.0016 | $0.80 |
| Playbook Setup | 1 | $0.023 | $0.02 |
| **Total API Cost** | | | **$17.12** |

---

## 5. Infrastructure Costs (Fixed Monthly)

### Current Infrastructure
| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| Production VPS (Lightsail) | ~$10/mo | 2GB RAM, hosts n8n + Caddy + containers |
| Staging VPS (Lightsail) | ~$10/mo | 2GB RAM, staging environment |
| RDS PostgreSQL | ~$15/mo | db.t3.micro, shared by production + staging |
| Domain/DNS | ~$1/mo | Cloudflare/Route53 |
| **Total Infra** | **~$36/mo** | |

### Per-User Marginal Infrastructure
- **Database storage:** ~0.5MB per company (profile + enrichment data) = negligible
- **Compute:** Flask API is stateless, scales within existing container
- **n8n:** Legacy workflows still active but being migrated to native Python

### Infrastructure Scaling Estimate
| Users | Infra Needed | Monthly Infra Cost |
|-------|-------------|-------------------|
| 1-10 | Current setup | $36 |
| 10-50 | Upgrade VPS to 4GB RAM | $56 |
| 50-200 | Dedicated API server + larger RDS | $100-150 |
| 200+ | Kubernetes / auto-scaling | $300+ |

---

## 6. Cost Dominance Analysis

### Where the Money Goes (Per Company, Full Pipeline)

```
L2 Synthesis (Sonnet 4.5)     $0.0072  ████████████████████  47.4%
L2 News (sonar-pro)           $0.0040  ███████████           26.3%
L2 Signals (sonar-pro)        $0.0032  ████████              21.1%
L1 Research (sonar)            $0.0008  ██                     5.3%
                                       ───────────────────────
Total                          $0.0152                       100.0%
```

### Where the Money Goes (Per Contact, Full Pipeline)

```
Person Synthesis (Sonnet 4.5)  $0.0026  ██████████████████    61.9%
Person Profile (sonar)         $0.0009  ████                  21.4%
Person Signals (sonar)         $0.0007  ███                   16.7%
                                       ───────────────────────
Total                          $0.0042                       100.0%
```

### Key Finding: Anthropic Sonnet 4.5 Dominates Costs

The synthesis steps (Claude Sonnet 4.5) account for:
- **47% of company enrichment cost** (L2 synthesis)
- **62% of person enrichment cost** (person synthesis)
- Sonnet 4.5 is 15x more expensive on output than `sonar` ($15 vs $1 per 1M output tokens)

### Top 3 Cost Levers
1. **L2 Synthesis model choice:** Switching from Sonnet 4.5 to Haiku 4.5 for synthesis would reduce L2 cost from $0.0144 to ~$0.0090 (37% reduction) at some quality tradeoff
2. **sonar-pro for L2 research:** Switching L2 research to `sonar` would reduce L2 research cost from $0.0072 to ~$0.0016 (78% reduction) but with lower research quality
3. **Person synthesis model:** Same Sonnet-to-Haiku switch would reduce person cost from $0.0042 to ~$0.0025 (40% reduction)

---

## 7. Business Model Scenarios

### Pricing Tiers (Subscription)

| Tier | Price/mo | API Budget | Margin | Target User |
|------|----------|------------|--------|-------------|
| Starter | $49/mo | ~$6 API cost | 88% | Light user (50 companies/mo) |
| Professional | $149/mo | ~$17 API cost | 89% | Medium-heavy user (200-500 companies/mo) |
| Enterprise | $399/mo | ~$50 API cost | 87% | Team of 3-5 users |

### Why These Margins Work
- AI API costs are remarkably low ($1-17/user/month)
- Fixed infrastructure cost ($36-150/mo) is amortized across users
- The value delivered (research that would take hours manually) justifies pricing
- Competitors (Apollo, ZoomInfo, Lusha) charge $79-399/seat/month for similar data

### Revenue Model Math

**Break-even with 4M CZK (~$160K) runway:**

| Scenario | Users | MRR | Burn Rate | Runway |
|----------|-------|-----|-----------|--------|
| Pre-revenue (current) | 1 (internal) | $0 | ~$1,500/mo (infra + dev) | 107 months |
| Early traction | 10 users @ $49 | $490 | ~$1,600/mo | 64 months |
| Growth | 50 users @ mix | $5,000 | ~$2,500/mo | Cash-flow positive |
| Break-even | 30 users @ $149 avg | $4,470 | ~$4,000/mo (with marketing) | Sustainable |

**Key insight:** With current API costs, the product is profitable at just 30 users on a $149/mo plan. The AI costs are not the constraint -- customer acquisition is.

### Cost Sensitivity Analysis

| If API prices drop 50% | Impact |
|------------------------|--------|
| Light user cost | $0.72 (was $1.44) |
| Medium user cost | $3.14 (was $6.28) |
| Heavy user cost | $8.56 (was $17.12) |
| Margin improvement | ~5-6 percentage points |

| If usage doubles (per user) | Impact |
|----------------------------|--------|
| Light user cost | $2.88 |
| Medium user cost | $12.56 |
| Heavy user cost | $34.24 |
| Still within pricing margin | Yes, even at 2x usage |

---

## 8. Cost Optimization Opportunities

### Immediate (No Quality Impact)
1. **Prompt caching (Anthropic):** Sonnet 4.5 supports prompt caching. The L2 synthesis system prompt (~190 tokens) is identical across all calls. With caching, repeated calls within 5 minutes get 90% input discount. Savings: ~$0.001/company in batch mode.
2. **Token budget optimization:** L2 Synthesis has `ANTHROPIC_MAX_TOKENS = 4000` but actual output averages 1,854 tokens. Reducing to 2,500 would prevent edge-case waste.

### Medium-Term (Minor Quality Tradeoff)
3. **Haiku 4.5 for person synthesis:** Person synthesis ($0.0026/contact) could use Haiku 4.5 ($0.0006/contact) -- 77% savings. The task (personalization angles) is less complex than company L2 synthesis.
4. **Conditional L2:** Skip L2 for companies that fail L1 triage (currently L2 only runs on `triage_passed`). This is already implemented -- good.

### Long-Term (Architectural)
5. **Result caching:** Cache enrichment results for companies researched by multiple users/tenants. A company like "Stripe" would be enriched once, not per-tenant.
6. **Incremental re-enrichment:** Only re-run L2 news research (time-sensitive), skip L2 strategic signals and synthesis if prior data is < 30 days old.
7. **Batch API:** Anthropic Batch API offers 50% discount for non-time-sensitive work. Enrichment batches could use this.

---

## 9. Comparison with Alternatives

### Build vs Buy: Per-Company Research Cost

| Source | Cost per Company | Data Depth |
|--------|-----------------|------------|
| **Leadgen Pipeline** | **$0.015** | L1 profile + L2 deep research + AI synthesis |
| Apollo.io | $0.50-2.00/credit | Basic company data, no AI analysis |
| ZoomInfo | $1.00-5.00/credit | Company + intent data |
| Clearbit | $0.10-0.50/lookup | Company enrichment only |
| Manual research | $5-15/company (1-2 hrs @ $10/hr) | Variable quality |

**Leadgen's cost advantage:** 10-100x cheaper than manual research, 30-300x cheaper than data vendors, with AI-synthesized actionable intelligence that vendors don't provide.

---

## 10. Summary & Recommendations

### Key Numbers
- **Full pipeline cost per company:** $0.015 (4 API calls)
- **Full pipeline cost per contact:** $0.004 (3 API calls)
- **Message generation cost:** $0.0016 per message
- **Playbook chat:** $0.008 per turn
- **Monthly API cost per user:** $1.44 (light) to $17.12 (heavy)
- **Infrastructure:** $36/mo fixed (current)

### Pricing Recommendation
- **Launch price:** $99/mo (Professional) -- covers ~$10 API cost + infra share, 85%+ margin
- **Entry tier:** $49/mo (Starter) -- limited to 50 companies/mo
- **Team tier:** $249/mo (3 seats) -- shared enrichment pool

### Break-Even Analysis
- **Fixed costs:** ~$2,000/mo (infra + minimal ops)
- **Variable costs:** $6-17/user/mo (API only)
- **Break-even:** ~25 users at $99/mo average
- **With 4M CZK runway (~$160K):** Can sustain 80+ months pre-revenue, or invest in growth

### Biggest Risk
The cost risk is NOT AI tokens (they're cheap). The risk is:
1. **Customer acquisition cost** -- finding and converting 25+ paying users
2. **Perplexity rate limits** -- high-volume usage may hit throttling before cost becomes an issue
3. **Model deprecation** -- Haiku 3.5 and Sonnet 4.5 pricing could change

### Next Steps
1. Implement LLM usage dashboard (data already logged to `llm_usage_log` table)
2. Add per-tenant cost tracking and usage limits
3. Test Haiku 4.5 for person synthesis quality
4. Evaluate Anthropic Batch API for overnight enrichment runs
5. Build tenant billing integration (Stripe metered billing)
