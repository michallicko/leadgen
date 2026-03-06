# Chat Sidebar Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the dual chat system (ChatPanel overlay + PlaybookChat inline) with a single ChatSidebar component that pushes content, works identically on every page, and collapses to an icon tab.

**Architecture:** Single ChatSidebar rendered in AppShell as a flex sibling to the main content area. Content reflows when sidebar opens/closes. No fixed/overlay positioning on desktop.

**Tech Stack:** React, TypeScript, Tailwind CSS, existing ChatProvider context

---

### Task 1: Create ChatSidebar component

**Files:**
- Create: `frontend/src/components/chat/ChatSidebar.tsx`

**What to build:**
- New component that replaces both ChatPanel and PlaybookChat
- Uses `useChatContext()` for all state (like ChatPanel does)
- Contains: header ("AI Strategist" + new thread btn + collapse btn), ChatMessages, ChatInput, all banners/suggestions
- Two visual states:
  - **Expanded**: `w-[400px] xl:w-[400px] md:w-[320px]` with full chat UI
  - **Collapsed**: `w-[40px]` thin strip with chat icon, unread badge, click to expand
- Collapse button in header toggles `isOpen` via `toggleChat()`
- When collapsed, show a vertical strip with centered chat icon and unread indicator
- CSS transition on width: `transition-all duration-300 ease-in-out`
- Full height: `h-full flex flex-col`
- Border-left: `border-l border-border`
- Context-aware placeholders per page (from current ChatPanel lines 85-93)
- Desktop only component — mobile uses overlay (handled separately)

**Reuse these existing components inside ChatSidebar:**
- `ChatMessages` — message list
- `ChatInput` — textarea + send
- `PhaseTransitionBanner`
- `WelcomeBackBanner`
- `WorkflowProgressStrip`
- `WorkflowSuggestionChips`

**Collapsed tab design:**
```tsx
// When !isOpen, render just the tab strip:
<div className="w-[40px] h-full border-l border-border bg-surface flex flex-col items-center pt-4 cursor-pointer"
     onClick={toggleChat}>
  {/* Chat icon */}
  {/* Unread dot if hasUnread */}
</div>
```

### Task 2: Modify AppShell layout

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`

**Changes:**
1. Replace `<ChatPanel />` with `<ChatSidebar />`
2. Change the content area from simple flex-col to flex-row for content + sidebar:

**Current layout (lines 95-114):**
```tsx
<div className="flex flex-col h-screen overflow-hidden">
  <AppNav />
  <BudgetWarningBanner />
  <div className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-5 py-3">
    <Outlet />
  </div>
  <ChatPanel />
  <MobileFAB />
</div>
```

**New layout:**
```tsx
<div className="flex flex-col h-screen overflow-hidden">
  <AppNav />
  <BudgetWarningBanner />
  <div className="flex flex-1 min-h-0">
    {/* Main content — grows to fill available space */}
    <div className="flex-1 min-w-0 overflow-y-auto px-3 sm:px-5 py-3">
      {renderSignpost ? <EntrySignpost /> : (
        <>
          {showChecklist && <ProgressChecklist ... />}
          <Outlet />
        </>
      )}
    </div>
    {/* Chat sidebar — desktop only, pushes content */}
    <div className="hidden md:block">
      <ChatSidebar />
    </div>
  </div>
  <MobileFAB />
</div>
```

3. Update MobileFAB: remove `isOnPlaybookPage` check (show on all pages on mobile)
4. Update imports: remove ChatPanel, add ChatSidebar

### Task 3: Simplify PlaybookPage

**Files:**
- Modify: `frontend/src/pages/playbook/PlaybookPage.tsx`

**Changes:**
1. Remove `PlaybookChat` import and usage
2. Remove the split layout (`flex-[3]` / `flex-[2]` columns)
3. PlaybookPage now renders only its content (PhasePanel, onboarding, tabs) — chat is handled by AppShell's ChatSidebar
4. The phase content should take full width of the content area
5. Keep all existing playbook functionality (phases, editor, save, undo, templates, tiers, personas)

**Current split layout (around lines 688-745) becomes:**
```tsx
<div className="flex flex-col h-full min-h-0 overflow-hidden">
  {/* Top bar: title + save status + undo button — KEEP */}
  <div className="flex items-center gap-3 mb-2 flex-shrink-0">...</div>

  {/* Strategy sub-tabs — KEEP */}
  {viewPhase === 'strategy' && !needsOnboarding && (
    <div className="flex items-center gap-1 mb-2 flex-shrink-0 border-b border-border">...</div>
  )}

  {/* Content — FULL WIDTH now (no split) */}
  <div className="flex-1 min-h-0 overflow-hidden">
    {needsOnboarding && showTemplateSelector ? <TemplateSelector ... /> :
     needsOnboarding ? <PlaybookOnboarding ... /> :
     activeStrategyTab === 'tiers' ? <IcpTiersTab /> :
     activeStrategyTab === 'personas' ? <BuyerPersonasTab /> :
     <PhasePanel ... />}
  </div>
</div>
```

6. Remove chat-related destructuring from useChatContext that's no longer needed for passing to PlaybookChat (messages, isStreaming, streamingText, chatInputRef, toolCalls, isThinking, thinkingStatus, etc.)
7. BUT KEEP: `documentChanged`, `clearDocumentChanged`, `sendMessage` — these are used for AI edit detection and proactive analysis

### Task 4: Update ChatProvider

**Files:**
- Modify: `frontend/src/providers/ChatProvider.tsx`

**Changes:**
1. Keep `isOnPlaybookPage` in context (still useful for context-aware behavior)
2. Update Cmd+K handler: always toggle sidebar (remove playbook-specific focus logic)
3. Keep all streaming, messaging, tool call logic unchanged

**Cmd+K handler change (lines 386-403):**
```tsx
// OLD:
if (isOnPlaybookPage) {
  chatInputRef.current?.focus()
} else {
  toggleChat()
}

// NEW:
toggleChat()
// After opening, focus the input
if (!isOpen) {
  setTimeout(() => chatInputRef.current?.focus(), 350) // after animation
}
```

### Task 5: Update AppNav ChatToggleButton

**Files:**
- Modify: `frontend/src/components/layout/AppNav.tsx`

**Changes:**
1. Remove `if (isOnPlaybookPage) return null` from ChatToggleButton (lines ~335)
2. ChatToggleButton should show on ALL pages including playbook
3. Keep unread badge and nudge count logic

### Task 6: Cleanup

**Files:**
- Delete: `frontend/src/components/chat/ChatPanel.tsx`
- Delete: `frontend/src/components/playbook/PlaybookChat.tsx`

**After deletion, verify:**
- No remaining imports of ChatPanel or PlaybookChat anywhere
- All tests still pass: `cd frontend && npx tsc --noEmit`

### Task 7: Commit

```bash
git add -A
git commit -m "refactor: unified ChatSidebar replacing ChatPanel + PlaybookChat

- Single right sidebar component in AppShell (pushes content, not overlay)
- Collapsible to icon tab on right edge
- Consistent behavior on every page including Playbook
- PlaybookPage simplified to full-width content
- Mobile keeps full-screen overlay behavior

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
