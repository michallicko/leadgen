# Sprint 9 Revalidation Report

**Date**: 2026-03-04
**Target**: `https://leadgen-staging.visionvolve.com`
**Login**: `test@staging.local` / `staging123`
**Route tested**: `/visionvolve/playbook/strategy`

## Summary

| # | Criterion | Backlog Item | Result |
|---|-----------|-------------|--------|
| 1 | Tiers API returns empty array | BL-198 AC-2 | **PASS** |
| 2 | Personas API returns empty array | BL-199 AC-1 | **PASS** |
| 3 | System prompt hidden in chat | BL-208 AC-3 | **PASS** |
| 4 | Condensed message has user avatar | BL-208 AC-4 | **PASS** |
| 5 | Tab label says "Strategy Overview" | BL-197 AC-2 | **PASS** |

**Result: 5/5 PASS -- all previously failing criteria now pass.**

---

## Detailed Evidence

### 1. BL-198 AC-2: Tiers API returns empty array

**Previous failure**: 404 Not Found

**Revalidation**:
```
GET /api/playbook/strategy/tiers
Authorization: Bearer <token>
X-Namespace: visionvolve

Response: 200 OK
Body: {"tiers": []}
```

**Verdict**: **PASS** -- Endpoint exists, returns 200 with `{"tiers": []}`.

---

### 2. BL-199 AC-1: Personas API returns empty array

**Previous failure**: 404 Not Found

**Revalidation**:
```
GET /api/playbook/strategy/personas
Authorization: Bearer <token>
X-Namespace: visionvolve

Response: 200 OK
Body: {"personas": [{"goals": [], "pain_points": [], "title_patterns": []}]}
```

The `visionvolve` namespace returns one empty persona object because a blank persona was manually created during previous testing. When tested against the `test` namespace (no test data):

```
GET /api/playbook/strategy/personas
X-Namespace: test

Response: 200 OK
Body: {"personas": []}
```

**Verdict**: **PASS** -- Endpoint exists, returns 200 with the correct `{"personas": [...]}` structure. The non-empty array in `visionvolve` is test data (a blank persona was created via the UI "Add Persona" button), not a code defect. A clean namespace returns `{"personas": []}` as specified.

---

### 3. BL-208 AC-3: System prompt hidden in chat

**Previous failure**: Full internal prompt ("Generate a complete GTM strategy...") was visible in chat

**Revalidation**:
- Two onboarding trigger messages exist in chat history
- Both render as condensed italic text: `Strategy generation started...`
- The full system prompt text is NOT present anywhere in the page body
- Verified: `document.body.innerText` does NOT contain "Generate a complete GTM strategy", "You are a GTM strategist", or any other system prompt fragments

**HTML of condensed message**:
```html
<div class="flex gap-3 flex-row-reverse">
  <div class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 bg-accent/20 text-accent-hover">
    <svg><!-- user person icon --></svg>
  </div>
  <div class="text-xs text-text-muted italic py-2">Strategy generation started...</div>
</div>
```

**Verdict**: **PASS** -- Full prompt is hidden; only the condensed italic message "Strategy generation started..." is displayed.

---

### 4. BL-208 AC-4: Condensed message has user avatar

**Previous failure**: Dependent on AC-3 (system prompt was not hidden)

**Revalidation**:
- The condensed message container uses `flex-row-reverse` (right-aligned, user side)
- Contains a user avatar: a 28x28 rounded circle (`w-7 h-7 rounded-full`) with `bg-accent/20` background
- Inside the avatar circle is an SVG person icon (circle head + path body)
- The avatar matches the styling of other user messages in the chat

**Verdict**: **PASS** -- Condensed message displays with a user avatar (person icon in accent-colored circle) on the right side.

---

### 5. BL-197 AC-2: Tab label says "Strategy Overview"

**Previous failure**: Tab said "Strategy Document"

**Revalidation**:
- Navigated to `/visionvolve/playbook/strategy`
- Three tabs rendered in the sub-navigation bar:
  1. **"Strategy Overview"** (active, highlighted in accent color)
  2. "ICP Tiers"
  3. "Buyer Personas"

**Screenshot evidence**: The tab bar shows "Strategy Overview | ICP Tiers | Buyer Personas" with "Strategy Overview" as the first and active tab.

**Verdict**: **PASS** -- First tab reads "Strategy Overview" (not "Strategy Document").

---

## Notes

- The playbook tabs (Strategy Overview, ICP Tiers, Buyer Personas) only render when navigating to `/visionvolve/playbook/strategy` (with the `strategy` phase in the URL). The base `/visionvolve/playbook` URL loads a different view (contacts table) based on the tenant's current workflow phase.
- The tiers and personas API endpoints are functional and return proper JSON structures with 200 status codes.
- The condensed message rendering correctly hides the full system prompt and shows a user-styled italic summary instead.
