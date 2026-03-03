# Sprint 6 Manual Tests

## Overview

Manual test scenarios for Sprint 6 enrichment features. Run against staging root after all Sprint 6 PRs are merged.

**Staging URL**: `https://leadgen-staging.visionvolve.com`
**Test user**: `test@staging.local` / `staging123`
**Namespace**: `visionvolve`

---

## Test 1: Company L2 Enrichment Display (BL-156)

**Precondition**: Navigate to an enriched company (e.g., search for a company with "Enriched L2" stage).

- [ ] **1.1** Company detail loads without errors
- [ ] **1.2** Overview tab shows Classification, CRM, Key Metrics sections
- [ ] **1.3** Intelligence tab shows module cards: Company Profile, Strategic Signals, Market Intelligence, AI Opportunity
- [ ] **1.4** Executive Brief section visible with pitch framing badge and pain hypothesis
- [ ] **1.5** Module cards expand/collapse on click
- [ ] **1.6** Company Profile shows: company_intel, key_products, customer_segments, competitors, tech_stack
- [ ] **1.7** Strategic Signals shows: AI adoption, digital maturity, growth indicators
- [ ] **1.8** Market Intelligence shows: revenue trend, recent news, funding history
- [ ] **1.9** AI Opportunity shows: pain hypothesis, AI opportunities, quick wins

## Test 2: Contact Person Enrichment Display (BL-184)

**Precondition**: Navigate to an enriched contact (one with enrichment cost > 0).

- [ ] **2.1** Contact detail loads without errors
- [ ] **2.2** Enrichment tab visible (only for contacts with person enrichment)
- [ ] **2.3** Person Summary section shows summary + relationship insights
- [ ] **2.4** Career & Background section shows career trajectory, previous companies, education
- [ ] **2.5** Buying Signals section shows AI Champion badge, authority score, budget signals
- [ ] **2.6** Relationship Strategy section shows personalization angle, connection points

## Test 3: Data Quality Indicators (BL-158)

- [ ] **3.1** Company header shows "DQ XX" quality badge
- [ ] **3.2** L1 Confidence percentage visible in overview
- [ ] **3.3** Quality score visible in overview
- [ ] **3.4** QC flags displayed as colored badges when present
- [ ] **3.5** History tab shows enrichment costs and quality scores

## Test 4: Copy-to-Clipboard (BL-157)

- [ ] **4.1** Hover over any field value (email, phone, domain, etc.) -- copy icon appears
- [ ] **4.2** Click copy icon -- checkmark feedback appears for 1.5 seconds
- [ ] **4.3** Paste into another app -- correct value is in clipboard
- [ ] **4.4** Empty fields (showing "-") do NOT show copy icon
- [ ] **4.5** Multi-line fields (notes, summaries) copy full text including line breaks
- [ ] **4.6** Link fields (email, LinkedIn) copy the text value
- [ ] **4.7** Copy works on both company and contact detail pages

## Test 5: Enrichment Pipeline (existing)

- [ ] **5.1** Enrich page loads with pipeline stages visible
- [ ] **5.2** Stage selection checkboxes are interactive
- [ ] **5.3** Tag filter shows namespace-scoped tags
- [ ] **5.4** Run button becomes interactive after loading

## Test 6: Workflow & Chat (BL-135, BL-169, BL-170)

- [ ] **6.1** Playbook page loads chat panel
- [ ] **6.2** Phase stepper shows Strategy/Contacts/Messages/Campaign
- [ ] **6.3** Clicking a phase changes the active view
- [ ] **6.4** Chat textarea accepts input and send works
- [ ] **6.5** Workflow suggestions appear contextually

## Test 7: Cross-Cutting

- [ ] **7.1** No 500 errors navigating through: enrich, companies, company detail, contacts, contact detail, playbook
- [ ] **7.2** No console errors on enrichment pages
- [ ] **7.3** Namespace isolation: switching namespaces shows correct data
