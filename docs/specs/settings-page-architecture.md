# Settings Page Architecture

**Purpose**: Shared settings page used by BL-037 (campaign templates), LANG (language), and TMPL (strategy templates).

## Problem

Three Sprint 3B items need a settings page that doesn't exist. The current PreferencesPage is a single card showing browser extension status. Without a shared design, each item will improvise a different approach.

## Solution

Expand PreferencesPage into a sectioned settings page at `/:namespace/preferences`.

### Route
`/:namespace/preferences` (existing route, currently minimal)

### Layout
Vertical tab navigation on the left (240px), content area on the right. On mobile (<768px), tabs collapse to a dropdown selector at the top.

### Sections (Sprint 3B)

| Tab | Source | Content |
|-----|--------|---------|
| **General** | Existing | Browser extension status (current content) |
| **Language** | LANG | Namespace language dropdown, enrichment language override, date format preview |
| **Campaign Templates** | BL-037 | List of saved campaign templates, rename/delete actions, system templates (read-only) |
| **Strategy Templates** | TMPL | List of saved strategy templates, delete action, system templates with preview |

### Future sections (not Sprint 3B)
- Integrations (CRM connections, API keys)
- Notifications (email preferences)
- Data (export, import settings)

### Design tokens
- Tab active: `var(--accent)` text + left border
- Tab hover: `var(--bg-hover)` background
- Section cards: `var(--bg-surface)` with `var(--border-subtle)` border
- Consistent with AdminPage card layout

### Component structure
```
PreferencesPage.tsx
├── PreferencesTabs.tsx (vertical tab nav)
├── sections/
│   ├── GeneralSection.tsx (existing content moved here)
│   ├── LanguageSection.tsx (LANG)
│   ├── CampaignTemplatesSection.tsx (BL-037)
│   └── StrategyTemplatesSection.tsx (TMPL)
```

### Accessibility
- Tabs use role="tablist" / role="tab" / role="tabpanel"
- Arrow keys navigate between tabs
- Active tab has aria-selected="true"
- Tab panels have aria-labelledby pointing to their tab
