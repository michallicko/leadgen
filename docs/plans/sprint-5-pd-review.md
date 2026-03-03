# Sprint 5 — PD Design Challenge

**Reviewer**: PD Analyst
**Date**: 2026-03-02
**Sprint**: Sprint 5 — Seamless Flow (22 items)
**Status**: Engineers are actively building. This review provides course corrections.

---

## Verdict: APPROVED WITH CHANGES

Sprint 5 tackles the right problems — the baseline test exposed that features are isolated islands with zero connective tissue. The item list covers every major gap. However, several items lack specific design direction, and the proactive UX pattern (the KEY differentiator for this sprint) needs a cohesive visual language before engineers improvise independently.

---

## Design Consistency Score: 7/10

The existing codebase has a **strong, coherent dark-mode design language** established in `index.css`:
- Surface hierarchy: `bg (#0D0F14) > surface (#14171E) > surface-alt (#1A1E28)`
- Purple accent brand (#6E2C8B) + cyan action accent (#00B8CF)
- Typography: Lexend Deca for titles, Work Sans for body
- Border style: subtle `rgba(110,44,139,0.15)` with solid `#231D30` for emphasis
- Consistent 8px default radius, 12px for larger containers
- Pill-shaped buttons for interactive chips (`rounded-full`)
- Card pattern: `bg-surface rounded-lg border border-border-solid`

The deductions come from:
- **Inconsistent empty states** — `ChatMessages.EmptyState` (inline) vs `EmptyState` component (centralized) vs `EntrySignpost` (full-page). Three different empty patterns.
- **No standardized dialog/modal pattern** — the undo dialog in PlaybookPage uses inline JSX with `fixed inset-0 z-50`. Save Template dialog duplicates the same pattern. Sprint 5 adds at least 3 more dialogs (ICP extraction summary, cost approval, save confirmation). Need a reusable `Dialog` component.
- **Suggestion chips inconsistency** — PlaybookChat uses `rounded-full border-accent/30 text-accent` for suggestions. The onboarding challenge types use `rounded-md border-border-solid`. These are the same interaction pattern (choose from options) but look different.

---

## UX Flow Review

Here is the ideal user journey through all Sprint 5 changes, describing what the user should see, click, and feel at each step:

### First Visit (empty namespace)

1. **Login** -> user lands on namespace root
2. **EntrySignpost** (BL-136 fix) fills the page. Three cards: Build a Strategy, Import Contacts, Browse Templates. Clean, centered layout. The existing design in `EntrySignpost.tsx` is good — keep it.
3. User clicks **"Build a Strategy"** -> navigates to Playbook

### Strategy Creation

4. **PlaybookOnboarding** (BL-121 simplified) shows just 2 inputs: company domain + description. Feels lightweight, not a form.
5. User submits -> **AI immediately starts working** (BL-150). No "I'll do this" text. The chat panel shows:
   - ThinkingIndicator dots (existing pattern -- good)
   - ToolCallCards appear: "Researching unitedarts.cz..." (web_search, BL-137)
   - More ToolCallCards: "Writing Executive Summary..." (update_strategy_section)
   - All 9 sections complete in ONE turn (BL-140)
6. Strategy appears in the editor. **Auto-save indicator** shows "Saved" (existing pattern).
7. **Proactive suggestion** (BL-135) appears in chat: "Strategy complete. I've extracted your ICP criteria. Ready to review them?" with a chip button.

### ICP Extraction + Phase Transition

8. User clicks the suggestion chip (or the "Extract ICP" button).
9. **Extraction confirmation dialog** (BL-141) slides in with a summary:
   - Target Industries: Event management, Marketing agencies
   - Geography: Czech Republic, Slovakia
   - Company Size: 10-50 employees
   - Job Titles: Event manager, Marketing director
   - Qualification Signals: Active event portfolio
10. User confirms -> **Auto-advance countdown** (BL-114) shows: "Moving to Contacts in 5s..." with a progress bar. User can click to advance immediately or cancel.

### Contact Selection (Phase 2)

11. **ContactsPhasePanel** (BL-143) shows ICP-filtered contacts in a data table. Filter chips show the extracted criteria. This component already exists and is well-designed.
12. The chat sidebar proactively says: "I found 8 contacts matching your ICP. 2 need enrichment. Import more?" (BL-135)

### Import (if needed)

13. User goes to Import page. **Column mapping works** (BL-134 fix). The mapping UI shows AI confidence scores per column.
14. After import, chat proactively suggests: "10 contacts imported. Run enrichment?" (BL-135)

### Enrichment

15. **Run button works** (BL-148 fix). Cost estimate shows **in credits** (BL-146).
16. **Workflow orchestrator** (BL-144) shows real-time progress: "L1 enrichment: 7/10 companies..."
17. On completion, chat says: "Enrichment done. 7 companies passed triage. Create a campaign?" (BL-135)

### Campaign + Messages

18. Strategy-aware message generation (BL-145) uses ICP data for personalization.
19. The save progress indicator (BL-151) confirms every action.

**Overall feel**: The user is never lost. Every completed step leads to the next. The AI is an assistant that does the work and asks for approval, not a chatbot waiting for instructions.

---

## Item-by-Item Review

### BL-136: EntrySignpost Fix

- **Design quality**: Good. The existing `EntrySignpost.tsx` is well-designed — centered layout, three clear path cards with hover states (`hover:border-accent/40 hover:bg-accent/5`), icon + title + description + "Get started" reveal on hover.
- **Consistency**: Matches the design system. Uses `bg-surface`, `border-border-solid`, `rounded-xl`, brand accent color.
- **Accessibility**: Cards are `<button>` elements (correct). Disabled state on mutation. Missing: `aria-label` on each card for screen readers.
- **Correction for engineers**: Add `aria-label={card.title}` to each path card button. The existing component is solid -- the bug is a rendering condition, not a design issue.

### BL-134: Import Column Mapping Fix

- **Design quality**: Cannot evaluate the mapping UI since it crashes. The wizard structure (3-step: Upload, Map, Preview) is good.
- **Consistency**: The import wizard should match the PlaybookOnboarding visual style -- centered card with step indicators.
- **Suggested design for the mapping step**: Each column should be a row with:
  - Source column name (left, `text-text font-medium`)
  - Arrow icon (center, `text-text-dim`)
  - Target field dropdown (right, `bg-surface-alt border-border-solid rounded-md`)
  - Confidence badge: `>= 0.95` = green pill (`bg-success/10 text-success`), `0.7-0.94` = amber pill (`bg-warning/10 text-warning`), `< 0.7` = red pill (`bg-error/10 text-error`)
  - AI warning text below the row in `text-xs text-warning` if applicable
- **Correction for engineers**: After the crash fix, ensure the mapping step has a loading skeleton while the API responds. Use the existing skeleton pattern from `ChatMessages.tsx` (`.animate-pulse` blocks).

### BL-141: ICP Extraction Summary Dialog

- **Design quality**: Needs work. The spec says "confirmation panel/dialog" but gives no design direction.
- **Suggested design**: Use a slide-in panel (not a centered modal) that appears on the right side of the editor, overlapping the chat panel temporarily. This keeps the strategy visible for reference.
  ```
  Layout:
  [Strategy Editor 60%] [Extraction Summary Panel 40%]

  Panel structure:
  - Header: "ICP Criteria Extracted" + checkmark icon (text-success)
  - Subtitle: "Review the criteria below. These will filter your contacts."
  - Sections (each a mini-card):
    - Industries: pill tags (bg-accent/10 text-accent rounded-full)
    - Geography: pill tags
    - Company Size: range display ("10-50 employees")
    - Job Titles: pill tags
    - Qualification Signals: bulleted list (text-xs text-text-muted)
  - Footer: "Confirm & Continue" button (bg-accent text-white) + "Edit in Strategy" link (text-accent)
  ```
- **Accessibility**: Panel should trap focus when open. Escape key to dismiss. All tags should be readable as a list for screen readers.
- **Correction for engineers**: Do NOT use a centered modal (`fixed inset-0 z-50`). Use a side panel that replaces the chat temporarily, so the user can see their strategy while reviewing extracted criteria.

### BL-143: Phase 2 Contacts Panel

- **Design quality**: Good. The existing `ContactsPhasePanel.tsx` is already well-built with:
  - ICP banner when no data (amber warning style)
  - Search input with icon
  - Filter chips with removable tags
  - DataTable with checkbox selection
  - Pagination controls
  - Footer with confirm button + selection count
- **Consistency**: Matches the existing patterns. Uses proper border, surface, and text color tokens.
- **Accessibility**: The `IcpBadge` uses color alone to convey meaning (green/amber). Add a text prefix or aria-label: "Strong Fit" vs just color change.
- **Suggested improvement**: Add a sticky header row to the table that shows column headers even when scrolling. The current DataTable may already do this -- verify.
- **Correction for engineers**: The "Confirm Selection" button uses `bg-accent text-bg`. Confirm that `text-bg` (#0D0F14) provides sufficient contrast against `bg-accent` (#6E2C8B). It does (dark on dark-purple) -- switch to `text-white` for better readability. Also: add a "Select All" checkbox in the table header.

### BL-135: Proactive Suggestions in Chat

- **Design quality**: Needs specific design direction. This is THE most important UX item in the sprint.
- **Current state**: `PlaybookChat.tsx` already has suggestion chips: `rounded-full border-accent/30 text-accent hover:bg-accent/10`. These are small, pill-shaped buttons above the input.
- **Problem with current approach**: Small pills above the input feel like afterthought prompts, not proactive AI guidance. For the "strategist-in-residence" vision, proactive suggestions should feel like the AI is stepping forward with a recommendation, not presenting a multiple-choice quiz.
- **Suggested design for proactive suggestions**:

  **Type 1: Contextual Next-Step Card** (appears after a major action completes)
  ```
  ┌──────────────────────────────────────┐
  │ [cyan dot] AI Suggestion             │
  │                                      │
  │ Strategy complete. I've identified   │
  │ 3 target industries and 4 key job    │
  │ titles for your ICP.                 │
  │                                      │
  │ [Review ICP ──>]  [Skip]            │
  ├──────────────────────────────────────┤
  │ Step 1 of 4: Strategy ✓ → Contacts  │
  └──────────────────────────────────────┘
  ```

  - Container: `bg-accent-cyan/5 border border-accent-cyan/20 rounded-lg` (subtle cyan tint to distinguish from regular messages)
  - Header: small cyan dot + "AI Suggestion" in `text-xs text-accent-cyan font-medium`
  - Body: `text-sm text-text` -- conversational, specific (not generic)
  - Primary CTA: `bg-accent-cyan text-white rounded-md px-4 py-1.5 text-xs font-medium`
  - Secondary: `text-text-muted text-xs` link
  - Progress footer: `border-t border-accent-cyan/10 px-3 py-1.5 text-[11px] text-text-dim` -- shows workflow position

  **Type 2: Inline Quick Suggestion** (for minor follow-ups)
  Keep the existing pill chips but add an icon prefix:
  ```
  [lightbulb] Refine my ICP criteria
  [lightbulb] Add more buyer personas
  ```
  - Same `rounded-full border-accent/30 text-accent` style
  - Prepend a small lightbulb SVG (12x12) in `text-accent/60`

  **Type 3: Persistent Progress Strip** (always visible, not a suggestion)
  At the bottom of the chat (above input), show a mini workflow progress bar:
  ```
  Strategy ✓ → Contacts → Enrich → Campaign → Launch
  ```
  - `text-[10px]` with step dots
  - Current step highlighted in cyan, completed in success green, future in dim
  - Clickable to navigate phases
  - This replaces/complements the PhaseIndicator at the top of the Playbook page

- **Accessibility**: All suggestion cards need `role="alert"` or `aria-live="polite"` so screen readers announce new suggestions. CTAs need clear labels.
- **Correction for engineers**:
  1. Create a new `SuggestionCard` component (not inline JSX in PlaybookChat).
  2. Distinguish between Type 1 (major next-step) and Type 2 (minor refinement) visually.
  3. The suggestion card should animate in with a subtle `slideIn` animation (already defined in `index.css`).
  4. Only ONE Type 1 suggestion at a time. Multiple Type 2 chips are fine.

### BL-111: Smart Empty States

- **Design quality**: Needs work -- currently inconsistent.
- **Current patterns** (3 different approaches):
  1. `EntrySignpost` -- full-page, centered, 3-card grid. Used for namespace root when no data at all.
  2. `EmptyState` (ui component) -- icon + title + description + optional CTA button. `py-16 px-6 text-center`. Used in MessagesTab.
  3. `ContactsEmptyState` / `CampaignsEmptyState` -- context-aware wrappers around `EmptyState` that check onboarding status.
  4. `ChatMessages.EmptyState` -- separate inline component (not using the shared one!).

- **Design direction for consistency across 4 pages**:

  **Contacts page (no contacts)**:
  - Already done in `SmartEmptyState.tsx`. Design is good but needs an icon. Currently the icon is a custom SVG inline. Use the same icon style as `EntrySignpost` (outlined, `w-12 h-12`).
  - Context-aware message is correct: "Your strategy is ready -- now find your audience" when strategy exists.

  **Campaigns page (no campaigns)**:
  - Already done in `SmartEmptyState.tsx`. Missing icon. Add one.
  - The CampaignsEmptyState should show a progress hint: "Step 4 of 5: Create your first campaign" to reinforce the workflow position.

  **Enrich page (no enrichment data)**:
  - Missing entirely. The DAG visualization renders even with no data. When no contacts exist at all, show an EmptyState: "Import contacts first, then enrich them with company and contact intelligence."
  - Icon: chemistry/flask outline.

  **Messages page (no messages in campaign)**:
  - Already uses `EmptyState` in MessagesTab. Good.

  **Unified empty state styling**:
  ```
  All empty states MUST use the shared EmptyState component from ui/EmptyState.tsx.
  Do NOT create inline empty state JSX.

  Structure:
  - Icon: outlined SVG, w-12 h-12, text-text-dim opacity-50
  - Title: text-sm font-medium text-text
  - Description: text-sm text-text-muted max-w-xs
  - CTA button (optional): bg-accent text-white rounded-md
  - Workflow hint (new): text-[11px] text-text-dim mt-3
    e.g., "Step 2 of 5: Import your contacts"

  Tone: Professional, not playful. Short sentences.
  No illustrations (we don't have an illustration system).
  No emojis.
  ```

- **Correction for engineers**:
  1. Fix `ChatMessages.tsx` to use the shared `EmptyState` component, not its own inline version.
  2. Add a `hint` prop to `EmptyState` for the workflow position hint.
  3. Every empty state should include a workflow progress hint ("Step N of 5") so the user knows where they are.
  4. Add `aria-label="empty state"` to the container div.

### BL-121: Simplified Onboarding

- **Design quality**: Good concept -- reducing from 3 steps to 2 inputs.
- **Current state**: `PlaybookOnboarding.tsx` already has a clean form with: company description (textarea), challenge type (2x2 grid), domains (tag input). The "challenge type" selector is the heaviest visual element.
- **Suggested simplified design**:
  ```
  ┌─────────────────────────────────────┐
  │  Tell us about your company         │
  │                                     │
  │  [Company domain input]             │
  │  unitedarts.cz (auto-filled from    │
  │  tenant config)                     │
  │                                     │
  │  [Description textarea]             │
  │  What do you sell? Who do you       │
  │  target? What's your challenge?     │
  │                                     │
  │  [Generate My Strategy]             │
  │                                     │
  │  I'll write it myself ->            │
  └─────────────────────────────────────┘
  ```
  - Remove the challenge type selector entirely. The AI can infer the challenge from the description.
  - Remove the multi-domain input. Keep just one primary domain, auto-filled from tenant config.
  - The description textarea should be larger (4-5 rows) with a more conversational placeholder: "We're a circus performance company that sells corporate entertainment to event agencies in the Czech Republic..."
  - Keep the "Skip" link at the bottom.
  - The card should be narrower (max-w-md instead of max-w-lg) to feel more conversational and less form-like.
- **Accessibility**: Form labels are correctly associated via `htmlFor`. Focus should auto-focus the description textarea since domain is pre-filled.
- **Correction for engineers**: Do not just remove fields from the existing form. Redesign the visual weight: the description textarea should be the hero input, domain should be a small pre-filled field above it. Kill the challenge type selector completely.

### BL-148: Enrichment Run Button

- **Design quality**: Cannot evaluate current design since the button is stuck in loading.
- **Suggested loading/ready states**:
  - **Loading**: Skeleton shimmer on the button area. `animate-pulse` on a 120px wide block.
  - **Ready**: `bg-accent-cyan text-white rounded-md px-4 py-2 text-sm font-medium`. Include a play icon (`>|`) before "Run Enrichment".
  - **Running**: Button disabled, shows spinner + "Enriching... 3/10 companies". Same button width to prevent layout shift.
  - **Complete**: Brief green flash (`bg-success text-white`) then return to Ready state.
- **Correction for engineers**: The Run button should show a cost estimate INLINE before clicking: "Run Enrichment (~200 credits)" -- not in a separate confirmation dialog. Reduce friction.

### BL-149: Namespace Persistence

- **Design quality**: The namespace dropdown behavior is a system-level UX decision, not a visual design issue.
- **Correction for engineers**: After switching namespaces, the URL should update immediately and the page should refresh data. The dropdown should show the current namespace with a checkmark, not just text selection. Add a small icon (globe or building) before each namespace name in the dropdown.

### BL-151: Save Progress Indicator

- **Design quality**: The existing auto-save indicator in `PlaybookPage.tsx` is good:
  - "Saving..." (`text-text-muted animate-pulse`)
  - "Saved" (`text-success font-medium` with fadeIn)
  - "Save failed" (`text-error`)
- **Suggested toast design**: For non-playbook saves (campaign settings, import confirmations, etc.), use the existing toast system with these refinements:
  - Success toast: left cyan border (`border-l-4 border-accent-cyan`), no icon bloat, just text
  - Error toast: left red border, clear error message
  - Duration: 3s for success, 5s for error, manual dismiss for blocking errors
- **Correction for engineers**: Standardize ALL save feedback through the same toast component. Do not use inline "Saved" text outside of the Playbook auto-save context. The toast should slide in from the bottom-right (existing `slideIn` animation).

### BL-114: Auto-Advance Countdown

- **Design quality**: Needs careful design. A countdown can feel pressuring if done wrong.
- **Suggested visual treatment**:
  ```
  ┌──────────────────────────────────────────────┐
  │ ✓ ICP criteria extracted successfully         │
  │                                               │
  │ Moving to Contacts phase in 5s...             │
  │ ████████████░░░░░░░░  [Go now] [Stay here]   │
  └──────────────────────────────────────────────┘
  ```
  - Container: `bg-success/5 border border-success/20 rounded-lg p-3` (green tint for success context)
  - Progress bar: `h-1 bg-success rounded-full` with CSS transition `width` over 5s
  - "Go now" button: `text-success font-medium text-xs` (accelerate)
  - "Stay here" button: `text-text-dim text-xs` (cancel the auto-advance)
  - Place this INSIDE the chat panel as a special card, not as a modal or toast
  - Duration: 5 seconds is correct. Not less (feels rushed). Not more (feels laggy).
- **Alternative consideration**: Instead of a countdown, use a persistent banner at the top of the phase panel that says "Ready for next step: Contacts" with a button. The countdown pattern is fine for the playbook flow because the user just completed an explicit action (extraction), so auto-advancing is expected.
- **Accessibility**: The countdown should be `aria-live="polite"` so screen readers announce it. The "Stay here" button should get focus when the countdown appears.
- **Correction for engineers**: Do NOT use `setTimeout` chains for the countdown visual. Use a CSS `transition` on the progress bar width (0% to 100% over 5s) with a single `setTimeout` for the actual navigation. This ensures smooth animation regardless of JS event loop jitter.

### BL-144: Workflow Orchestrator Progress

- **Design quality**: Needs design direction. This is the "progress indicator" for multi-step enrichment runs.
- **Suggested design**: A collapsible status card in the chat panel:
  ```
  ┌──────────────────────────────────────┐
  │ [spinner] Enrichment Running          │
  ├──────────────────────────────────────┤
  │ ✓ Company Profile     10/10          │
  │ ● Triage              7/10           │
  │ ○ Deep Research        0/10          │
  │ ○ Contact Intel        0/10          │
  │ ○ Quality Check        0/10          │
  ├──────────────────────────────────────┤
  │ Estimated time: ~3 min  Cost: 450 cr │
  └──────────────────────────────────────┘
  ```
  - Use the same card style as ToolCallCards (`bg-surface-alt border border-border-solid rounded-lg`)
  - ✓ = `text-success`, dot = `text-accent-cyan animate-pulse`, circle = `text-text-dim`
  - Progress counts in `tabular-nums text-text-muted text-xs`
  - Footer: `text-[11px] text-text-dim border-t border-border-solid`
  - Collapsible: click header to expand/collapse (save vertical space in chat)
- **Correction for engineers**: This card should appear in the chat panel as a persistent element (not a regular message), positioned between the message list and the input. It should not scroll away with messages.

---

## Proactive UX Design Direction

The product vision says the AI is a "strategist-in-residence" -- not a chatbot. Proactive UX is what distinguishes this from every other SaaS tool with a chat sidebar. Here is how it should feel:

### The Three Tiers of Proactive Behavior

**Tier 1: System Suggestions** (BL-135)
- Triggered by: completed actions (strategy saved, contacts imported, enrichment done)
- Visual: `SuggestionCard` component (Type 1 design described above)
- Tone: Conversational, specific, action-oriented
- Example: "Strategy looks solid. I found 3 industries and 4 job titles in your ICP. Want me to filter your contacts?"
- One at a time. Dismissable. Persists until acted on or dismissed.

**Tier 2: Contextual Hints** (BL-135)
- Triggered by: page navigation, time on page, data state
- Visual: Small chips (Type 2 design) or inline text in the chat
- Tone: Brief, optional, non-blocking
- Example: Suggestion chips like "Refine my ICP" or "Add buyer personas" after strategy generation
- Multiple allowed. Disappear after first user message.

**Tier 3: Workflow Progress** (BL-144)
- Always visible when a background process is running
- Visual: Persistent status card (design above) or the mini progress strip
- Tone: Factual, no personality
- Example: "L1 enrichment: 7/10 complete. ~2 min remaining."

### What Proactive UX Should NEVER Do

- **Never auto-execute** without user approval (cost, data changes, external sends)
- **Never block the UI** -- suggestions should be dismissable, not modal
- **Never nag** -- if the user dismisses a suggestion, do not repeat it
- **Never be vague** -- "Try our enrichment feature!" is bad. "Run L1 enrichment on your 10 companies (~200 credits)?" is good.
- **Never use exclamation marks** in suggestions
- **Never use marketing language** -- no "Supercharge your pipeline!" or "Unlock insights!"

### Visual Language for "The System is Thinking Ahead"

The cyan accent color (`#00B8CF`) should be the signature color for proactive AI actions:
- AI suggestion cards: cyan-tinted background (`bg-accent-cyan/5`)
- "AI Suggestion" header label: cyan dot + cyan text
- Progress indicators: cyan spinner, cyan progress bar
- Proactive chat messages from the AI that include a CTA: cyan CTA button

This creates a visual pattern: cyan = the AI is offering something. Purple = user/brand. Green = success. The user learns to associate cyan UI elements with "the system is helping me."

---

## Empty State Design Direction

### Unified Guidelines

All empty states must follow these rules:

1. **Use the shared `EmptyState` component** from `components/ui/EmptyState.tsx`. No inline empty state JSX.
2. **Always include**: icon (outlined, 48x48), title (1 line), description (1-2 lines), optional CTA button.
3. **Add workflow position hint**: "Step N of 5: [action]" below the description in `text-[11px] text-text-dim`.
4. **Context-aware messaging**: Use `useOnboardingStatus()` to show different messages based on what the user has already done.
5. **Professional tone**: No playful language, no emojis, no illustrations (we have none). Calm, helpful, direct.
6. **Single CTA**: Each empty state should have exactly 0 or 1 action button. Not multiple choices (that is the EntrySignpost's job).

### Per-Page Empty States

| Page | Condition | Title | Description | CTA | Hint |
|------|-----------|-------|-------------|-----|------|
| **Contacts** (no strategy) | 0 contacts, no strategy | "No contacts yet" | "Import your prospect list to start building campaigns." | "Import Contacts" | Step 2 of 5: Import contacts |
| **Contacts** (has strategy) | 0 contacts, has strategy | "Your strategy is ready -- now find your audience" | "Import contacts that match your ICP criteria." | "Import Contacts" | Step 2 of 5: Import contacts |
| **Campaigns** (no contacts) | 0 campaigns, 0 contacts | "No campaigns yet" | "Import contacts first, then create a campaign." | none (no point) | Step 4 of 5: Create a campaign |
| **Campaigns** (has contacts) | 0 campaigns, >0 contacts | "Ready to reach out" | "You have N contacts. Create a campaign to start outreach." | none (header has New Campaign button) | Step 4 of 5: Create a campaign |
| **Enrich** (no contacts) | 0 contacts | "Nothing to enrich yet" | "Import contacts first. The enrichment pipeline will add company and contact intelligence." | "Import Contacts" | Step 3 of 5: Enrich your data |
| **Enrich** (has contacts, none enriched) | >0 contacts, 0 enrichment | "Ready to enrich" | "N companies waiting. Run the pipeline to gather intelligence." | "Configure Run" | Step 3 of 5: Enrich your data |
| **Playbook** (chat empty) | 0 messages | "Your AI strategist is ready" | "Describe your business and I'll draft a complete GTM strategy." | none (input is the CTA) | -- |

---

## Critical Design Issues (notify engineers)

### CRITICAL-1: Create a Reusable Dialog Component

Sprint 5 adds at least 3 new dialogs (ICP extraction summary, cost approval gate, save template). The current pattern of inline `fixed inset-0 z-50` JSX in PlaybookPage.tsx is unsustainable.

**Action**: Before building any new dialogs, create `components/ui/Dialog.tsx`:
```tsx
interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  actions?: React.ReactNode
  width?: 'sm' | 'md' | 'lg'  // max-w-sm, max-w-md, max-w-lg
}
```
Style: `fixed inset-0 z-50 flex items-center justify-center bg-black/40` overlay with `bg-surface border border-border-solid rounded-lg shadow-lg` card. Trap focus. Close on Escape. Close on overlay click.

### CRITICAL-2: SuggestionCard Component Must Exist Before BL-135

BL-135 is the most visible UX change. Do not let engineers inline suggestion card JSX in PlaybookChat. Create `components/chat/SuggestionCard.tsx` as a proper component with:
- Type 1 (next-step card) and Type 2 (quick chip) variants
- Proper animation (slideIn)
- Dismissal callback
- Accessibility attributes (`role="alert"`, `aria-live="polite"`)

### CRITICAL-3: Fix ContactsPhasePanel Confirm Button Contrast

The "Confirm Selection" button currently uses `bg-accent text-bg`. The text color `text-bg` resolves to `#0D0F14` (nearly black) on `bg-accent` (`#6E2C8B`) which is dark purple. This fails WCAG AA contrast. Change to `text-white`.

### CRITICAL-4: Standardize Loading States

I see three different loading patterns:
1. `animate-spin` border spinner (PlaybookPage loading, ChatInput send button disabled)
2. `animate-pulse` skeleton blocks (ChatSkeleton)
3. "Loading..." text (enrichment Run button, strategy extracting)

Standardize:
- **Full page loading**: Spinner + "Loading..." text (existing PlaybookPage pattern). Good.
- **Inline content loading**: Skeleton blocks with `animate-pulse`. Good.
- **Button loading**: Replace text with spinner inside the button. Button width must not change (use `min-w` to prevent layout shift). Do NOT use "Loading..." text in buttons.
- **Background process**: Spinner outside the button + descriptive text: "Enriching... 3/10 companies" (not inside a button).

---

## Design System Tokens to Use

### Colors (for new Sprint 5 components)

| Token | Hex | Usage in Sprint 5 |
|-------|-----|-------------------|
| `--color-accent` | `#6E2C8B` | Primary buttons, selected states, brand elements |
| `--color-accent-cyan` | `#00B8CF` | AI suggestions, proactive cards, progress indicators, CTAs from AI |
| `--color-success` | `#34D399` | Completed steps, extraction success, enrichment done |
| `--color-warning` | `#FBBF24` | Cost estimates, medium confidence, review needed |
| `--color-error` | `#F87171` | Failed states, crash feedback, extraction errors |
| `--color-surface` | `#14171E` | Card backgrounds, dialog backgrounds |
| `--color-surface-alt` | `#1A1E28` | Input backgrounds, tool call cards, secondary surfaces |
| `--color-border-solid` | `#231D30` | Card borders, dividers, table borders |
| `--color-text` | `#E8EAF0` | Primary text |
| `--color-text-muted` | `#A0A8B8` | Secondary text, descriptions |
| `--color-text-dim` | `#8890A0` | Hints, timestamps, workflow position |

### Typography

| Token | Value | Usage in Sprint 5 |
|-------|-------|-------------------|
| `--font-title` | Lexend Deca | Dialog titles, card headers, page titles |
| `--font-body` | Work Sans | All body text, descriptions, messages |
| Weight 600 | Semibold | Section headings, card titles, CTA buttons |
| Weight 500 | Medium | Labels, filter chips, badges |
| Weight 400 | Regular | Body text, descriptions |

### Spacing

| Pattern | Value | Usage |
|---------|-------|-------|
| `gap-2` | 8px | Between filter chips, between suggestion pills |
| `gap-3` | 12px | Between form fields, between card sections |
| `gap-4` | 16px | Between major layout sections, between messages |
| `p-3` | 12px | Card internal padding (compact) |
| `p-4` | 16px | Card internal padding (standard) |
| `p-6` | 24px | Dialog internal padding, EntrySignpost card padding |
| `rounded-md` | 6px | Buttons, inputs, filter chips |
| `rounded-lg` | 8px | Cards, dialogs, message bubbles |
| `rounded-xl` | 12px | Large cards (EntrySignpost), onboarding wizard |

### Key Gradients (from design system)

| Name | CSS | Usage |
|------|-----|-------|
| Header | `linear-gradient(90deg, #6E2C8B, #00B8CF)` | Body top accent bar (already applied in index.css) |
| Cover | `linear-gradient(135deg, #4A1D5E, #6E2C8B 40%, #008B9A)` | Not used in app -- for reports/exports only |

### Animation Tokens

| Animation | Duration | Usage |
|-----------|----------|-------|
| `slideIn` | 0.3s | Toast notifications, suggestion cards appearing |
| `animate-spin` | 1s linear infinite | Loading spinners in buttons |
| `animate-pulse` | 2s cubic-bezier infinite | Skeleton loading, "Thinking..." text |
| `thinkPulse` | 1.4s infinite | Thinking indicator dots |
| `transition-colors` | 150ms | Hover states on all interactive elements |

---

## Summary of Corrections for Engineers

1. **BL-135**: Create `SuggestionCard.tsx` component BEFORE implementing proactive suggestions. Use cyan accent for AI suggestions. Type 1 (card) vs Type 2 (chip) variants.
2. **BL-141**: Use a side panel (not modal) for ICP extraction summary. Keep strategy visible.
3. **BL-143**: Change "Confirm Selection" button text to `text-white` (contrast fix).
4. **BL-111**: Use shared `EmptyState` component everywhere. Add workflow position hint. Fix ChatMessages inline empty state.
5. **BL-121**: Remove challenge type selector. Single domain + description textarea. Narrower card (max-w-md).
6. **BL-114**: CSS transition for countdown bar, not JS interval. Place inside chat panel, not as a modal.
7. **BL-148**: Show cost estimate inline on the Run button: "Run Enrichment (~200 cr)". No separate dialog.
8. **All dialogs**: Create reusable `Dialog.tsx` before building any new modals.
9. **All loading states**: Spinner inside buttons, skeleton for content, never "Loading..." text in buttons.
10. **All new components**: Use design tokens from `index.css`, not hardcoded hex values. Cyan (`--color-accent-cyan`) for AI-initiated actions.
