# TMPL: GTM Strategy Templates (Hybrid)

**Status**: Spec'd
**Sprint**: 3B
**Priority**: Should Have
**Effort**: M
**Theme**: Playbook Core
**Depends on**: ONBOARD

## Problem

Every new namespace starts with a blank strategy document. The onboarding flow (ONBOARD) asks discovery questions and generates a draft, but the AI starts from zero every time — no industry knowledge, no proven frameworks, no reference structures.

Users who've built a working GTM strategy for one market segment can't reuse that structure for a new segment. Consultants managing multiple namespaces recreate similar strategies manually.

## Solution

A **hybrid template system** that combines structured starter templates with AI-powered customization:

1. **System templates** — pre-built GTM frameworks for common scenarios (e.g., "B2B SaaS DACH expansion", "Professional Services local market")
2. **User templates** — save a working strategy as a reusable template
3. **AI-assisted application** — when loading a template, the AI adapts it to the user's context using onboarding answers and enrichment data

```
Template (skeleton)  +  Onboarding answers  +  Company enrichment
         ↓                    ↓                       ↓
         └──────── AI merges into personalized draft ──┘
```

## Scope

### In scope
- Strategy template data model and API
- System template seeding (3-5 starter templates)
- "Save strategy as template" action
- Template selection during onboarding (after discovery questions, before draft generation)
- AI-assisted template application (merge template + context → personalized draft)

### Out of scope
- Template marketplace / sharing between tenants
- Template versioning
- Template categories/tags (add later when library grows)
- Campaign templates (separate concern — BL-037)

## User Stories

### US-1: Start from a template
**As a** new user going through onboarding
**I want to** select a GTM strategy template before the AI drafts my strategy
**So that** I get a more structured, proven starting point instead of a blank-page draft.

### US-2: Save my strategy as a template
**As a** user with a working GTM strategy
**I want to** save it as a reusable template
**So that** I can apply the same framework to new market segments or namespaces.

### US-3: Browse available templates
**As a** user
**I want to** browse system and my saved templates with descriptions
**So that** I can choose the most relevant starting point.

## Data Model

### `strategy_templates` table

```sql
CREATE TABLE strategy_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),  -- NULL = system template
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,                            -- e.g., "B2B SaaS", "Professional Services", "E-commerce"
    content_template TEXT NOT NULL,           -- Markdown with {{placeholder}} tokens
    extracted_data_template JSONB DEFAULT '{}', -- Pre-filled extracted_data skeleton
    metadata JSONB DEFAULT '{}',             -- e.g., { "industries": ["SaaS"], "regions": ["DACH"] }
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

- `content_template`: Markdown strategy document with `{{placeholder}}` tokens that the AI replaces during application. Example: `"## ICP\n\nTarget {{industry}} companies in {{geography}} with {{company_size_range}} employees..."`.
- `extracted_data_template`: Pre-filled skeleton of `extracted_data` fields (ICP industries, channel preferences, metric targets) that serve as defaults the AI can override.
- System templates have `tenant_id IS NULL` and `is_system = TRUE`.

### Relationship to existing models

- `StrategyDocument.content` is the final personalized output (no placeholders)
- Templates are inputs; documents are outputs
- Templates do NOT replace onboarding — they enhance it (template + onboarding answers → better draft)

## API Endpoints

### `GET /api/strategy-templates`
List available templates (system + tenant-owned). Returns: `id, name, description, category, is_system, metadata, created_at`.

### `POST /api/strategy-templates`
Create a user template. Body: `{ name, description, category? }`. Auto-fills `content_template` from current `StrategyDocument.content` and `extracted_data_template` from `extracted_data` (with values generalized to placeholders where possible).

### `POST /api/playbook/apply-template`
Apply a template during onboarding or strategy reset. Body: `{ template_id }`. Process:
1. Load template's `content_template` and `extracted_data_template`
2. Load onboarding context: `StrategyDocument.objective`, enrichment data, discovery answers
3. Budget check: calls `check_budget(tenant_id, estimated_credits)` before the Claude call. Returns 402 with credit info if budget exceeded (hard mode).
4. Call Claude to merge template + context → personalized strategy content
5. Save to `StrategyDocument.content` and run extraction for `extracted_data`
6. Return the updated document

### `DELETE /api/strategy-templates/<id>`
Delete a tenant-owned template. Cannot delete system templates.

## System Templates (Seeded)

### 1. B2B SaaS — New Market Entry
- **Category**: B2B SaaS
- **Description**: GTM framework for SaaS companies expanding into a new geographic market. Covers ICP definition by market maturity, localized messaging, multi-channel cadence (LinkedIn + email), and pipeline metrics.
- **Sections**: Full 8-section strategy with SaaS-specific defaults (reply rate targets, ACV-based segmentation, product-led vs sales-led channel mix).

### 2. Professional Services — Local Market
- **Category**: Professional Services
- **Description**: GTM for consulting, agencies, and service firms targeting local/regional businesses. Emphasizes relationship-building, referral channels, and thought leadership content.
- **Sections**: ICP focused on revenue/employee thresholds, persona-driven messaging, networking + warm intro channels.

### 3. Tech Startup — First Outbound
- **Category**: Startup
- **Description**: Lean GTM for early-stage startups doing outbound for the first time. Minimal ICP (just enough to start), iterative messaging, and rapid feedback loops.
- **Sections**: Simplified ICP (3 criteria max), 2-step email sequence, weekly iteration cadence, founder-led messaging tone.

### Template Card Design

Template selection step uses a 2-column grid of cards (1-column on mobile <768px):

Each card shows:
- **Name** (bold, 16px)
- **Category badge** (e.g., "B2B SaaS" — small colored badge)
- **Description** (2-line truncated, 14px muted text)
- **Preview expand** — click to expand and see section headers (ICP, Channels, Metrics, etc.)
- **Select button** — primary action

"Blank slate" option is a special card with dashed border: "Start fresh — let the AI build your strategy from your answers alone."

### Loading & Undo During Template Application

**Loading state**: After selecting a template and confirming, show a full-page overlay with:
- Spinner + "Personalizing your strategy from [Template Name]..."
- Optional: progressive section labels as they generate ("Building ICP...", "Drafting channels...")
- Estimated time: 5-15 seconds

**Undo**: Template application creates a `StrategyVersion` row (via existing version tracking). After the template is applied, show a prominent undo bar at the top of the strategy editor:
- "Strategy generated from [Template Name]. [Undo] to revert to your previous draft."
- Uses existing `useUndoAIEdit` hook from PlaybookPage.
- Undo bar auto-dismisses after 30 seconds or on first manual edit.

**Error recovery**: If the Claude call fails, show error toast and do NOT modify the existing strategy document. The user stays on the template selection step.

## Frontend Changes

### Onboarding flow integration

### Onboarding Integration Detail

Template selection is inserted as a **wizard step** using the existing `WizardSteps` component (`frontend/src/components/ui/WizardSteps.tsx`).

Flow: Discovery Questions → **Template Selection** → AI Generates Draft → Strategy Editor

The template step appears only after discovery questions are answered (objective + enrichment data available). If the user clicks "Back" from template selection, they return to discovery questions.

After onboarding discovery questions complete and before the AI generates the draft:

1. Show template selection step: "Start from a proven framework or go blank?"
2. Display system templates + user templates as cards (name, description, category)
3. "Blank slate" option for users who prefer AI-only generation
4. Selected template ID passed to the draft generation call

### Strategy page — Save as Template
- "Save as Template" action in strategy document menu (kebab/more menu)
- Modal: name (pre-filled from namespace name), description, category dropdown
- Calls `POST /api/strategy-templates`

### Settings page — Template management
- List user templates with name, category, created date
- Delete action (with confirmation)
- No edit (templates are snapshots — create a new one from an updated strategy)

## Acceptance Criteria

### AC-1: Template selection during onboarding
```
Given I am going through onboarding and have answered discovery questions
When the template selection step appears
Then I see system templates and my saved templates as cards
And I can select one or choose "Blank slate"
And the AI generates my strategy using the selected template as a starting framework
```

### AC-2: AI-assisted template application
```
Given I select the "B2B SaaS — New Market Entry" template
And my onboarding answers say "targeting German manufacturing companies, 50-500 employees"
When the strategy is generated
Then the ICP section reflects German manufacturing (not generic SaaS)
And the channel strategy accounts for German business culture
And the template's structure and proven frameworks are preserved
```

### AC-3: Save strategy as template
```
Given I have a completed strategy document
When I click "Save as Template" and enter name + description
Then a new strategy_template is created with my tenant_id
And content_template = my current strategy content
And extracted_data_template = my current extracted_data
```

### AC-4: Template management
```
Given I have saved templates
When I go to Settings → Strategy Templates
Then I see my templates listed
And I can delete my templates (with confirmation)
And system templates are visible but not deletable
```

### AC-5: System templates seeded
```
Given a fresh deployment
When I check the strategy_templates table
Then 3 system templates exist with is_system=TRUE and tenant_id=NULL
And each has a complete content_template and extracted_data_template
```

## Task Breakdown

| # | Task | Effort |
|---|------|--------|
| 1 | Migration: create `strategy_templates` table | S |
| 2 | Model: add `StrategyTemplate` to models.py | S |
| 3 | API: CRUD endpoints for strategy templates | S |
| 4 | API: `POST /api/playbook/apply-template` with AI merge | M |
| 5 | Seed: 3 system templates (content + extracted_data) | M |
| 6 | Frontend: template selection step in onboarding flow | M |
| 7 | Frontend: "Save as Template" action on strategy page | S |
| 8 | Frontend: template management in Settings | S |

## Risks

1. **AI template application quality** — Merging a template with user context requires good prompt engineering. The AI might ignore the template structure or over-rely on it. Mitigation: template `content_template` uses explicit section headers that the AI preserves; test with all 3 system templates.
2. **Template staleness** — As the strategy document schema evolves, old templates may reference outdated section structures. Mitigation: templates are Markdown-based, not schema-coupled. The AI adapts structure during application.
