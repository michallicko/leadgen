# Agentic Chatbot Test Scenarios

## Overview
Test scenarios for validating the agentic chatbot across two testing layers:
- **Layer 1**: Deterministic E2E (Playwright) — UI correctness, pass/fail
- **Layer 2**: Conversation Quality (Claude Code /test-chat skill) — agent behavior, scored 1-5

## Scenario 1: Playbook Onboarding — United Arts (PRIMARY)

### Input
- Domain: `unitedarts.cz`
- Goal: "Increase market penetration in Czech regions and pilot engagements with DACH event agencies"
- Starting state: Empty playbook, no existing strategy

### Expected Agent Behavior (ordered)
1. Acknowledges goal briefly in chat (1-2 sentences max)
2. Starts researching unitedarts.cz — fetches actual website
3. Shows live finding: company type, location, core services
4. Writes Company Profile to editor immediately with confirmed facts
5. Researches Czech event market + competitors
6. Researches DACH agency landscape
7. Cross-checks external findings against website content
8. Asks 2-3 targeted discovery questions based on research gaps
9. Writes Market Analysis with real competitor data
10. Builds ICP — specific industries, company sizes, decision makers
11. Writes buyer personas grounded in research
12. Writes messaging/positioning with differentiated angles
13. Writes channel recommendations
14. Scores each section after writing (completeness + quality)
15. Offers quick actions: [Score full strategy], [Go to Contacts →]

### Quality Criteria
| Criterion | Min Score | What to Check |
|-----------|-----------|---------------|
| Research grounding | 4.5 | Company profile matches unitedarts.cz website |
| Cross-checking | 4.0 | External data compared against website |
| Discovery quality | 4.0 | Questions are targeted, not generic |
| Strategy quality | 4.0 | ICP is specific, messaging is differentiated |
| UX quality | 4.0 | Chat is brief, editor has content, quick actions offered |

### Edge Cases
- Website may be in Czech — agent should still extract key facts
- Conflicting team size data — should trust website
- User interrupts mid-research: "Actually focus on DACH first"
- User types answer before agent asks the question

### Grounding Facts (verify against actual website)
Before running this scenario, fetch unitedarts.cz and document:
- Company name and tagline
- Core services listed
- Team information (if available)
- Client logos or testimonials
- Contact information / location
These become the ground truth for scoring research accuracy.

---

## Scenario 2: Strategy Refinement — Returning User

### Input
- Existing strategy for unitedarts.cz (from Scenario 1 output)
- User message: "The ICP is too broad — we only want to target tech companies running developer conferences"

### Expected Agent Behavior
1. Loads strategy_refinement plan (NOT onboarding)
2. Reads current ICP section
3. Researches tech companies running dev conferences in Czech/DACH
4. Rewrites ICP section with narrow focus
5. Identifies downstream impact — messaging needs updating
6. Suggests messaging changes proactively
7. Creates version snapshot before overwriting
8. Re-scores affected sections

### Quality Criteria
| Criterion | Min Score | What to Check |
|-----------|-----------|---------------|
| Plan selection | Pass/Fail | Loaded refinement, not onboarding |
| Research targeted | 4.0 | Researched dev conferences specifically |
| ICP specificity | 4.5 | Narrowed to tech companies + dev conferences |
| Downstream awareness | 4.0 | Proactively suggested messaging update |
| Versioning | Pass/Fail | Version created before overwrite |

---

## Scenario 3: Mid-Plan Interruption — User Correction

### Input
- Start Scenario 1 (playbook onboarding for unitedarts.cz)
- After agent starts researching (wait for first finding), send: "Stop — we don't do festivals anymore. We pivoted to corporate-only 2 years ago."

### Expected Agent Behavior
1. Current research step completes (no abort mid-fetch)
2. Agent pauses at next node boundary
3. Acknowledges correction: "Got it — corporate events only, no festivals"
4. Updates internal context with correction
5. Resumes research with corrected scope
6. All subsequent output reflects "corporate only"
7. NO festival references in final strategy

### Quality Criteria
| Criterion | Min Score | What to Check |
|-----------|-----------|---------------|
| Acknowledgment speed | 4.0 | Acknowledged within 1-2 messages of correction |
| Context persistence | 5.0 | Zero festival references in entire output |
| Work preservation | 4.0 | Didn't restart from scratch |
| Adaptation quality | 4.0 | Research redirected to corporate-only scope |

### Failure Conditions (automatic FAIL)
- Any mention of "festival" in the final strategy
- Agent restarts entire research from scratch
- Agent ignores the correction and continues original plan

---

## Scenario 4: Simple Q&A Routing — Chat Tier

### Input
- User is on contacts page
- Message: "How many contacts do I have?"

### Expected Agent Behavior
1. Chat tier (Haiku) handles directly
2. Responds with accurate count within 1 second
3. No planner activation
4. No transparent thinking bubble (too simple)
5. No research_finding events in SSE stream

### Quality Criteria
| Criterion | Min Score | What to Check |
|-----------|-----------|---------------|
| Response time | Pass/Fail | < 1 second |
| Accuracy | Pass/Fail | Count matches database |
| Routing | Pass/Fail | No planner activation (check SSE events) |
| Conciseness | 4.0 | Direct answer, no unnecessary explanation |

### Variations
- "What companies are in tier 1?" → data lookup, Haiku handles
- "Show me the latest batch" → data lookup, Haiku handles
- "Can you explain how enrichment works?" → Haiku handles (general knowledge)
- "Build me a strategy" → should escalate to planner

---

## Scenario 5: Bulk User Input — Adaptive Handling

### Input
- Playbook onboarding starts for unitedarts.cz
- Before agent asks ANY questions, user pastes:
  "We're an event production company in Prague. 15 years in business. Main clients are tech companies for developer conferences. Competitors are EventLab and SuperEvent. We want to expand to Brno and Ostrava regions and start working with DACH agencies for cross-border events."

### Expected Agent Behavior
1. Extracts ALL information from pasted text
2. Does NOT re-ask any answered questions
3. Cross-checks claims against website:
   - "event production company in Prague" — verify against website
   - "15 years in business" — verify against website
   - "EventLab and SuperEvent" — verify these are real companies
4. Writes sections using both website research AND pasted input
5. Only asks questions about genuine remaining gaps
6. Acknowledges the input: "Thanks for the context. Let me verify and build on this."

### Quality Criteria
| Criterion | Min Score | What to Check |
|-----------|-----------|---------------|
| Information extraction | 4.5 | All 6 facts from paste are captured |
| No re-asking | 5.0 | Zero redundant questions |
| Cross-checking | 4.0 | Competitor names verified as real |
| Graceful handling | 4.0 | Acknowledged input naturally |
| Gap identification | 4.0 | Asked about genuine remaining gaps only |

### Failure Conditions
- Re-asking "What does your company do?" after user already stated it
- Treating pasted text as chat message instead of extracting structured info
- Not verifying competitor names (EventLab, SuperEvent) against reality

---

## Scenario 6: Version Management — Undo and Restore

### Input
- Existing strategy with 3+ sections written
- AI writes a new section that user doesn't like
- User presses Ctrl+Z
- Later, user opens version browser

### Expected Agent Behavior
This is primarily a UI test (Playwright layer):
1. AI section write creates a version snapshot
2. Ctrl+Z undoes the entire AI section write (not character by character)
3. Version browser shows the snapshot
4. User can preview the snapshot content
5. User can restore any version

### Quality Criteria (Playwright — pass/fail)
- [ ] AI write triggers version creation
- [ ] Ctrl+Z undoes entire AI edit as one operation
- [ ] Version browser lists versions with correct metadata
- [ ] Preview shows correct historical content
- [ ] Restore loads old content and creates new version

---

## Scoring Summary

### Per-Scenario Pass Criteria
| Scenario | Layer | Pass Threshold |
|----------|-------|----------------|
| 1. Onboarding | Quality | All criteria ≥ 4.0, avg ≥ 4.2 |
| 2. Refinement | Quality | All criteria ≥ 4.0 |
| 3. Interruption | Quality | Zero festivals + all criteria ≥ 4.0 |
| 4. Simple Q&A | E2E | All pass/fail checks pass |
| 5. Bulk Input | Quality | All criteria ≥ 4.0, zero re-asks |
| 6. Versioning | E2E | All checkboxes pass |

### Statistical Requirements (Quality Layer)
- Run each quality scenario 3 times minimum
- Report: mean, min, max per criterion
- Regression threshold: mean drop > 0.5 from baseline
- Baseline established after Sprint 6 completion

### Overall Sprint Pass
- ALL E2E scenarios pass (deterministic)
- ALL quality scenarios meet thresholds (statistical)
- Zero FAIL-condition triggers across all runs
