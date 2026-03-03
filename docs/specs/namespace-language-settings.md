# LANG: Namespace Language Settings

**Status**: Spec'd
**Sprint**: 3B
**Priority**: Should Have
**Effort**: L
**Theme**: Platform
**Depends on**: none (BL-057 depends on this)

## Problem

Language handling is fragmented across the stack:

| Layer | Current state | Gap |
|-------|--------------|-----|
| Tenant/namespace | No language setting | No way to set a default language for the workspace |
| Enrichment (L1/L2/Person) | English-only prompts | Can't research companies in their local language |
| Playbook chat | English-only | AI always responds in English regardless of user's language |
| Contact model | 4-language enum (en/de/nl/cs) | Missing fr/es/it/pl/pt/sv/no/fi/da |
| Owner model | `default_language` column exists in DB but not in ORM | Phantom column — never read by API |
| Campaign generation | `language` key in JSONB, no UI (BL-057 scope) | Campaign language selector is BL-057's responsibility |
| Message regen dialog | 13 languages hardcoded in frontend | Inconsistent with 4-language backend enum |
| `LANGUAGE_DISPLAY` maps | 4 entries (backend + frontend) | Mismatches regen dialog's 13 languages |
| Date formatting | Mixed locales (en-GB, en-US, browser default) | No consistent locale |

A Czech founder targeting DACH companies currently gets: English enrichment research, English playbook responses, and must manually set language per-campaign (once BL-057 ships). There's no single place to say "my workspace operates in Czech."

## Solution

Add a **namespace-level language setting** that cascades as the default across all language-dependent operations, with per-operation overrides remaining possible.

```
Namespace language (tenant.settings.language)
  ├── Enrichment output language (default: namespace language)
  ├── Playbook chat language (default: namespace language)
  ├── Contact default language (default: namespace language)
  ├── Campaign generation language (override per campaign — BL-057)
  └── Date/number formatting locale (default: namespace language)
```

### Scope boundaries

**In scope (this item):**
1. Namespace language setting (DB + API + Settings UI)
2. Expand `language_enum` to 13 languages
3. Unify `LANGUAGE_DISPLAY` maps (backend + frontend)
4. Wire `owners.default_language` into ORM + API
5. Enrichment language parameter (L1/L2/Person prompts)
6. Playbook chat language parameter
7. Date/number locale consistency

**Out of scope (handled by BL-057):**
- Campaign-level language selector UI on MessageGenTab
- Expanded tone/formality vocabulary
- Bulk regeneration
- Per-message language override in regen dialog (already works)

**Out of scope (future):**
- UI i18n / translated interface strings (would need react-i18next, translation files — separate initiative)
- RTL language support
- Per-contact language auto-detection from LinkedIn profile

## User Stories

### US-1: Set namespace language
**As a** namespace admin
**I want to** set a default language for my workspace
**So that** all AI operations default to my preferred language without per-operation config.

### US-2: Enrichment in local language
**As a** user enriching DACH companies
**I want** enrichment research to query and summarize in German
**So that** I get culturally relevant insights and local-language news coverage.

### US-3: Playbook chat in my language
**As a** Czech founder
**I want** the AI playbook assistant to respond in Czech
**So that** I can think and strategize in my native language.

### US-4: Consistent language list
**As a** user
**I want** the same language options everywhere (contacts, campaigns, regen)
**So that** I'm not confused by different lists in different places.

## Acceptance Criteria

### AC-1: Namespace language setting
```
Given I am a namespace admin on the Settings page
When I select a language from the language dropdown
Then the namespace default language is saved to tenant.settings.language
And all new operations default to this language
```

### AC-2: Language enum expansion
```
Given the database has language_enum with 4 values
When migration runs
Then language_enum contains: en, de, nl, cs, fr, es, it, pl, pt, sv, no, fi, da
And LANGUAGE_DISPLAY in api/display.py lists all 13
And LANGUAGE_DISPLAY in frontend/src/lib/display.ts lists all 13
And contacts.language accepts all 13 values
```

### AC-3: Enrichment language
```
Given namespace language is set to "de"
When L1/L2/Person enrichment runs for a contact in this namespace
Then Perplexity queries include language instruction (e.g., "Research in German, return results in German")
And LLM synthesis prompts instruct output in German
And the enrichment results are stored in the specified language
```

### AC-4: Playbook chat language
```
Given namespace language is set to "cs"
When I send a message in the playbook chat
Then the AI responds in Czech
And the system prompt includes "Respond in Czech" instruction
```

### AC-5: Owner default language wire-up
```
Given owners.default_language exists in DB
When the Owner model is loaded
Then default_language is available on the ORM model
And GET /api/users returns default_language for each owner
And the owner's default_language is used as fallback when namespace language is not set
```

### AC-6: Date/number locale
```
Given namespace language is set to "de"
When dates are rendered in the frontend
Then toLocaleDateString uses "de-DE" locale consistently
And number formatting uses German conventions (1.000,00)
```

## Technical Approach

### 1. Database migration

```sql
-- Expand language enum
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'fr';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'es';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'it';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'pl';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'pt';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'sv';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'no';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'fi';
ALTER TYPE language_enum ADD VALUE IF NOT EXISTS 'da';
```

No data migration needed — existing contacts keep their current language.

### 2. Tenant settings schema

Store in existing `tenant.settings` JSONB:

```json
{
  "language": "cs",
  "enrichment_language": "en"
}
```

- `language`: workspace default (affects chat, new contacts, date formatting)
- `enrichment_language`: optional override for enrichment (defaults to `language`). Some users may want Czech UI but English enrichment research.

### 3. API changes

**New endpoint**: `PATCH /api/tenants/<id>/settings`
```json
{ "language": "cs", "enrichment_language": "en" }
```

**Modified**: `GET /api/tenants/<id>` — returns settings including language.

**Modified**: Owner model — add `default_language` to SQLAlchemy model.

**New helper**: `get_effective_language(tenant, owner=None, campaign=None)` — resolves the cascade:
```
campaign.generation_config.language  (if set)
  → owner.default_language           (if set)
    → tenant.settings.language        (if set)
      → "en"                          (fallback)
```

### 4. Enrichment prompt changes

Add language instruction to all enrichment system prompts:

```python
# In L1/L2/Person enrichers
language = get_effective_language(tenant)
enrichment_lang = tenant.settings.get("enrichment_language", language)

# Append to system prompt:
f"\n\nIMPORTANT: Conduct research and write all output in {LANGUAGE_NAMES[enrichment_lang]}."
```

Perplexity `search_domain_filter` and `search_recency_filter` remain unchanged — Perplexity naturally surfaces local-language sources when the query is in that language.

### 5. Playbook chat changes

In `playbook_service.py` `build_system_prompt()`:

```python
language = get_effective_language(tenant)
if language != "en":
    prompt += f"\n\nIMPORTANT: Always respond in {LANGUAGE_NAMES[language]}. "
    prompt += "The user's workspace language is set to this language."
```

### 6. Frontend changes

**Settings page** (`SettingsPage.tsx` or namespace admin panel):
- Language dropdown with 13 options
- Optional "Enrichment language" dropdown (defaults to "Same as workspace")
- Save via `PATCH /api/tenants/<id>/settings`

**Unified language constants** (`frontend/src/lib/languages.ts`):
```typescript
export const LANGUAGES = [
  { code: 'en', name: 'English', locale: 'en-US' },
  { code: 'cs', name: 'Czech', locale: 'cs-CZ' },
  { code: 'de', name: 'German', locale: 'de-DE' },
  // ... all 13
] as const;
```

Replace all hardcoded language lists (RegenerationDialog, display.ts, ContactDetail) with this single source.

**Date formatting**: Create `formatDate(date, tenant)` utility that uses the tenant locale.

### 7. Canonical language list

| Code | Name | Formality support | Locale |
|------|------|-------------------|--------|
| en | English | — | en-US |
| cs | Czech | yes (tykání/vykání) | cs-CZ |
| de | German | yes (du/Sie) | de-DE |
| fr | French | yes (tu/vous) | fr-FR |
| es | Spanish | yes (tú/usted) | es-ES |
| it | Italian | yes (tu/Lei) | it-IT |
| pl | Polish | yes (ty/Pan) | pl-PL |
| nl | Dutch | yes (je/u) | nl-NL |
| pt | Portuguese | yes (tu/você) | pt-PT |
| sv | Swedish | — | sv-SE |
| no | Norwegian | — | nb-NO |
| fi | Finnish | — | fi-FI |
| da | Danish | — | da-DK |

### Change Confirmation UX

When the user changes the namespace language:
- Show brief inline summary below the dropdown: "Future enrichments, chat responses, and new contact defaults will use [German]. Existing data is not affected."
- No confirmation dialog needed (non-destructive, reversible).

### Contact Language Override Indicator

On ContactDetail, when a contact's language differs from the namespace default:
- Show a small badge next to the language field: "Override" or the namespace default in muted text: "Namespace: Czech"
- This helps users understand why a contact's language doesn't match the workspace setting.

### Settings Page Location

Language settings live in the shared Preferences page at `/:namespace/preferences` under the "Language" tab. See `docs/specs/settings-page-architecture.md` for the page architecture.

## Task Breakdown

| # | Task | Effort | Files |
|---|------|--------|-------|
| 1 | Migration: expand `language_enum` to 13 values | S | `migrations/` |
| 2 | Wire `owners.default_language` into ORM model | S | `api/models.py` |
| 3 | Unify `LANGUAGE_DISPLAY` to 13 languages (backend) | S | `api/display.py` |
| 4 | Create `frontend/src/lib/languages.ts` canonical list | S | `frontend/src/lib/languages.ts` |
| 5 | Replace hardcoded language lists in frontend | S | `RegenerationDialog.tsx`, `display.ts`, `ContactDetail.tsx` |
| 6 | `get_effective_language()` cascade helper | S | `api/services/language.py` |
| 7 | `PATCH /api/tenants/<id>/settings` endpoint | S | `api/routes/tenants.py` |
| 8 | Enrichment prompt language injection (L1/L2/Person) | M | `api/services/l1_enricher.py`, `l2_enricher.py`, `person_enricher.py` |
| 9 | Playbook chat language injection | S | `api/services/playbook_service.py` |
| 10 | Settings page language selector UI | M | `frontend/src/pages/settings/` |
| 11 | Date/number locale utility + adoption | S | `frontend/src/lib/format.ts`, various pages |

## Relationship to BL-057

LANG provides the **foundation layer** that BL-057 builds on:

- LANG expands the language enum and creates the canonical list → BL-057 uses it in the campaign language dropdown
- LANG creates `get_effective_language()` → BL-057 uses it for campaign generation defaults
- LANG adds `enrichment_language` to tenant settings → BL-057 can reference it for generation context
- LANG is a **prerequisite** for BL-057 (BL-057 should depend on LANG)

## Risks

1. **Enrichment quality in non-English**: Perplexity's coverage varies by language. Czech/Finnish company news may be sparse. Mitigation: allow `enrichment_language` override separate from workspace language.
2. **Playbook prompt size**: Adding language instruction slightly increases token usage. Minimal impact.
3. **Mixed-language data**: If enrichment was done in English but messages are generated in Czech, the LLM bridges the gap. This already works (BL-057 context) — Claude handles cross-language synthesis well.
