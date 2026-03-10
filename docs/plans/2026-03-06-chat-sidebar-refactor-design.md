# Chat Sidebar Refactor Design

## Date: 2026-03-06
## Branch: feature/visual-cleanup

## Problem

The chat component currently has two separate implementations:
- **ChatPanel**: sliding right-side overlay on all pages except Playbook (overlays content, doesn't push)
- **PlaybookChat**: inline right column on Playbook page only

This creates inconsistency — the chat behaves differently depending on which page you're on. Navigation also needs to be consistent with the same controls on every page.

## Requirements

1. **Unified right sidebar** — same ChatSidebar component on every page, including Playbook
2. **Collapsible** — sidebar collapses to a thin icon tab (~40px) on the right edge
3. **Content reflow** — when sidebar opens/closes, main content area expands/shrinks (no overlay)
4. **Full height** — sidebar spans from navbar to bottom of viewport
5. **Default open** — sidebar starts expanded on first visit, persists state to localStorage
6. **Consistent navigation** — AppNav renders identically on every page with same controls
7. **Mobile** — full-screen overlay (current behavior), FAB button to open

## Design

### Architecture

Single `ChatSidebar` component rendered in `AppShell`, sibling to the main content area.

```
AppShell
├── AppNav (top, full width)
└── ContentRow (flex-row, flex-1)
    ├── MainContent (flex-1, scrollable) ← grows when sidebar collapsed
    └── ChatSidebar (fixed width or collapsed tab) ← right side
```

### Component Changes

| File | Action | Details |
|------|--------|---------|
| `components/chat/ChatSidebar.tsx` | **CREATE** | New unified sidebar component, replaces ChatPanel |
| `components/chat/ChatPanel.tsx` | **DELETE** | Replaced by ChatSidebar |
| `components/playbook/PlaybookChat.tsx` | **DELETE** | Playbook uses ChatSidebar like all pages |
| `components/layout/AppShell.tsx` | **MODIFY** | Add flex-row inner layout for content + sidebar |
| `pages/PlaybookPage.tsx` | **MODIFY** | Remove split-view layout, use regular page content area |
| `providers/ChatProvider.tsx` | **MINIMAL** | Remove `isOnPlaybookPage` branching logic if no longer needed |

### Unchanged Components (reused inside ChatSidebar)

- `ChatMessages.tsx` — message list rendering
- `ChatInput.tsx` — textarea + send button
- `ChatMermaidBlock.tsx` — diagram rendering
- `PhaseTransitionBanner.tsx`, `WelcomeBackBanner.tsx`
- `WorkflowProgressStrip.tsx`, `WorkflowSuggestions.tsx`
- `ChatFilterSyncBar.tsx`, `useChatFilterSync.ts`

### Layout Behavior

**Desktop (>1200px):**
- Sidebar open: 400px wide, main content = viewport - nav - 400px
- Sidebar collapsed: 40px tab on right edge, main content = viewport - nav - 40px
- Transition: width animates 300ms ease-in-out, content reflows smoothly

**Tablet (768-1200px):**
- Sidebar open: 320px wide
- Sidebar collapsed: 40px tab
- Same reflow behavior as desktop

**Mobile (<768px):**
- No sidebar in layout — main content takes full width
- FAB button (bottom-right) opens full-screen overlay
- Close button returns to page

### Collapsed Tab

When sidebar is collapsed, a thin strip (~40px) stays visible on the right edge:
- Chat icon centered vertically
- Unread message badge (if applicable)
- Click to expand sidebar
- Subtle border-left to separate from content

### State Management

- `ChatProvider.isOpen` controls expanded/collapsed
- `localStorage('chat_panel_open')` persists state (already exists)
- Default: open on first visit
- Cmd+K toggles open/closed (already exists, just wire to new component)

### Navigation Consistency

AppNav already renders in AppShell for all authenticated routes. The fix:
- Ensure Playbook page doesn't override or hide any nav elements
- Same pillar icons, user menu, and controls on every page
- No page-specific nav modifications

### Playbook Page Simplification

Current PlaybookPage has a custom split-view layout (content left, chat right). After refactor:
- PlaybookPage becomes a regular page (just content, no chat column)
- Chat sidebar is handled by AppShell (same as every other page)
- Phase content takes full width of the main content area

## Migration Notes

- ChatProvider context API stays the same — no breaking changes to consumers
- Context-aware placeholders (per-page hints) move into ChatSidebar
- `isOnPlaybookPage` logic in ChatProvider can be simplified/removed
- Cmd+K handler stays in ChatProvider, behavior unchanged (toggle sidebar)
