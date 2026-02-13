# ADR-001: Virtual Scroll for Companies & Contacts Tables

**Date**: 2026-02-13 | **Status**: Accepted

## Context

The companies table has ~1,800 rows and contacts ~2,600 rows. The initial implementation used server-side pagination (Previous/Next buttons, 25 per page). This was replaced with infinite scroll (IntersectionObserver + append), but performance degraded past ~1,000 rows because all DOM nodes accumulated in the tbody — ~26,000+ `<td>` elements for contacts, each with event listeners.

## Decision

Implement **virtual scroll** (DOM windowing) on both `companies.html` and `contacts.html`:

- **Data layer**: `state.items[]` accumulates all fetched JS objects in memory (lightweight — ~2KB per object, ~5MB total for 2,600 contacts). API pagination (`page` + `page_size=50`) still fetches incrementally.
- **DOM layer**: Only ~60-80 `<tr>` elements exist at any time (viewport rows + 20-row buffer above/below). Spacer `<tr>` elements with calculated height maintain correct scroll position.
- **Render cycle**: `renderWindow()` runs on every scroll event (throttled via `requestAnimationFrame`). It calculates which rows should be visible based on `scrollTop / ROW_HEIGHT`, clears `<tbody>`, and rebuilds only the visible window.
- **Row height**: Fixed at 41px (10px padding + ~21px line + border). All rows use `white-space: nowrap` so height is uniform.
- **Fetch trigger**: `IntersectionObserver` on a sentinel `<div>` below the table triggers `loadMore()` when the user scrolls near the bottom of loaded data. `rootMargin: 200px` pre-fetches before the user reaches the end.

## Consequences

**Positive**:
- Constant DOM node count regardless of dataset size — scrolling 2,600 rows feels identical to 50
- No new dependencies — vanilla JS, `IntersectionObserver`, and `requestAnimationFrame` are supported in all target browsers
- API contract unchanged — same `page`/`page_size` params

**Negative**:
- Fixed `ROW_HEIGHT` assumption (41px) — if row styling changes, this constant needs updating or dynamic measurement
- `tbody.textContent = ''` on every scroll frame (within rAF) — more aggressive than append-only, but benchmarks fine for ~80 rows
- Text search (Ctrl+F) only finds rows currently in the DOM window, not all loaded data
