# Frontend & API Modernization — Target Stack + Migration Strategy

**Date**: 2026-02-16 | **Status**: Draft

## Why Now

The vanilla JS dashboard has hit its scaling limit:
- **11 pages, 13K lines** — 87% of JS is inline, duplicated across pages
- **7 copies of `apiFetch`**, 12+ duplicated CSS class definitions
- **No component reuse** — every new page starts by copy-pasting 200+ lines of boilerplate
- **No type safety** — API contract changes silently break pages
- **XSS surface** — 7 `innerHTML` usages with dynamic data, no consistent escaping
- Adding the next wave of features (outreach campaigns, analytics dashboards, billing) will multiply the problem

## Target Stack

### Frontend

| Layer | Choice | Why |
|-------|--------|-----|
| **Framework** | React 19 | Component model, ecosystem, hiring pool. Hooks + Server Components ready. |
| **Language** | TypeScript (strict mode) | Catch API contract breaks at build time. Self-documenting props/state. |
| **Styling** | Tailwind CSS v4 | Utility-first, no naming debates, tiny production CSS, design-system alignment via `theme.extend`. |
| **Build** | Vite 6 | Fast HMR (<100ms), ESBuild for dev, Rollup for prod. Zero-config React+TS support. |
| **Routing** | React Router v7 | Client-side routing, namespace-aware layout, code-splitting per route. |
| **Data fetching** | TanStack Query v5 | Cache, deduplication, background refetch, optimistic updates. Replaces all `apiFetch` copies. |
| **Forms** | React Hook Form + Zod | Validation, type inference from schema. Zod schemas shared with API types. |
| **State** | React context + TanStack Query | Server state in Query cache, minimal client state. Add Zustand only if needed. |
| **Testing** | Vitest + Playwright | Vitest for unit/component, Playwright for E2E (already configured). |
| **Linting** | ESLint + Prettier | Consistent formatting, catch errors early. Biome as future option. |

### Backend (Flask Standardization)

| Layer | Current | Target | Why |
|-------|---------|--------|-----|
| **Validation** | Manual in routes | **Pydantic v2** request/response schemas | Type-safe, auto-generates OpenAPI, shared with frontend types |
| **Serialization** | Manual dict building | **Pydantic models** with `.model_dump()` | Replaces `to_dict()` and raw dict construction |
| **API docs** | None | **Flask-Smorest** (OpenAPI 3.1) | Auto-generated from Pydantic schemas, Swagger UI at `/api/docs` |
| **Error handling** | Manual JSON returns | **Standardized error schema** | `{"error": str, "code": str, "details": dict}` everywhere |
| **DB queries** | Raw SQL + minimal ORM | **Keep raw SQL for complex queries**, add ORM relationships for simple CRUD | Pragmatic — don't rewrite working analytics queries |
| **Testing** | SQLite in-memory | **Keep SQLite for unit**, add PG testcontainers for integration | Closes TD-003 gap |

### Shared Contracts (Frontend ↔ Backend)

```
api/schemas/           ← Pydantic models (source of truth)
    ↓ (openapi-ts)
frontend/src/api/      ← Auto-generated TypeScript types
```

**Flow**: Pydantic schema → OpenAPI JSON → `openapi-typescript` → TS types. No manual type duplication. When backend adds a field, frontend gets it at build time.

## Project Structure

```
leadgen-pipeline/
  api/                          # Flask backend (unchanged location)
    schemas/                    # NEW: Pydantic request/response schemas
    routes/                     # Existing blueprints (add schema decorators)
    models.py                   # Existing SQLAlchemy models
    ...
  frontend/                     # NEW: React application
    src/
      api/                      # Generated types + TanStack Query hooks
        types.ts                # Auto-generated from OpenAPI
        client.ts               # Axios/fetch wrapper with auth interceptor
        queries/                # TanStack Query hooks per resource
          useCompanies.ts
          useContacts.ts
          ...
      components/
        layout/                 # App shell, nav, sidebar
          AppNav.tsx            # Port of nav.js
          AppShell.tsx          # Shared layout wrapper
        ui/                     # Reusable primitives
          Button.tsx
          Badge.tsx
          DataTable.tsx         # Virtual scroll table (port of current pattern)
          Modal.tsx
          Toast.tsx
          FilterBar.tsx
        domain/                 # Business-specific components
          CompanyDetail.tsx
          ContactCard.tsx
          PipelineStatus.tsx
          ...
      pages/                    # Route-level components (one per current HTML page)
        contacts/
        companies/
        messages/
        enrich/
        import/
        admin/
        playbook/
        echo/
        llm-costs/
      hooks/                    # Shared React hooks
        useAuth.ts              # Port of auth.js
        useNamespace.ts         # Namespace resolution
        useDebounce.ts
      lib/                      # Utilities
        auth.ts                 # Token management
        formatters.ts           # Display enums, dates, currency
      styles/
        tailwind.css            # Tailwind directives + custom theme
    public/
      visionvolve-icon-color.svg
      visionvolve-logo-white.svg
    index.html                  # Vite entry point
    vite.config.ts
    tailwind.config.ts
    tsconfig.json
    package.json
  dashboard/                    # OLD: vanilla JS (kept during migration, deleted after)
  deploy/
    deploy-frontend.sh          # NEW: build + scp dist/ to VPS
  ...
```

## Migration Strategy: Strangler Fig

New React app runs alongside old dashboard. Pages migrate one at a time. No big bang rewrite.

### Phase 0: Foundation (1-2 days)

Set up the React project scaffold — no feature work, just infrastructure.

1. `npm create vite@latest frontend -- --template react-ts`
2. Install: `tailwindcss`, `@tailwindcss/vite`, `react-router`, `@tanstack/react-query`, `zod`
3. Configure Tailwind theme to match existing CSS variables (purple/cyan palette, Lexend Deca + Work Sans fonts)
4. Build `AppShell.tsx` — port `nav.js` + `nav.css` to React component
5. Build `useAuth.ts` — port `auth.js` to React hook (JWT, login overlay, role gating)
6. Build `client.ts` — single API client with auth interceptor (replaces 7× `apiFetch`)
7. Set up React Router with namespace-aware routing (`/:namespace/contacts`, etc.)
8. Deploy script: `vite build` → `scp dist/` → Caddy serves from `/srv/frontend/`
9. Caddy config: serve React `index.html` for all non-API, non-file routes (SPA fallback)

**Deliverable**: Empty app shell with working nav, auth, and routing. No pages yet.

### Phase 1: First Page — Contacts (2-3 days)

Port the most-used page to prove the stack works end-to-end.

1. Create `useContacts.ts` TanStack Query hook (list, filters, pagination)
2. Build `DataTable.tsx` — reusable virtual scroll table (port existing pattern from ADR-001)
3. Build `FilterBar.tsx` — reusable filter component
4. Build `ContactDetail.tsx` — modal detail view
5. Wire up `/contacts` route
6. **Dual-run**: Caddy serves React app at `/{namespace}/contacts`, old `contacts.html` removed from deployment

**Acceptance**: Contacts page in React matches current functionality. No regressions.

### Phase 2: Data Pages — Companies, Messages (3-4 days)

Port pages that share the most code with Contacts.

1. **Companies** — reuses `DataTable`, `FilterBar`, adds `CompanyDetail` (the most complex detail view — L2, registry, legal profile sections)
2. **Messages** — reuses `DataTable`, adds message editing, approval workflow
3. Extract shared patterns discovered during porting into `components/ui/`

### Phase 3: Action Pages — Import, Enrich (2-3 days)

Port the workflow-oriented pages.

1. **Import** — multi-step wizard (reuse React Hook Form + Zod for validation)
2. **Enrich** — pipeline trigger + progress polling (reuse TanStack Query mutations)

### Phase 4: Admin & Utility Pages (1-2 days)

1. **Admin** — user management, tenant management (super_admin)
2. **LLM Costs** — charts/tables (consider adding recharts or similar)
3. **Playbook, Echo** — lightweight static-ish pages

### Phase 5: Cleanup (1 day)

1. Delete `dashboard/` directory entirely
2. Delete `pipeline-archive.html`
3. Update `deploy/deploy-dashboard.sh` → `deploy/deploy-frontend.sh`
4. Update ARCHITECTURE.md, CLAUDE.md
5. Update Caddy config — remove old HTML file serving

### Phase 6: Backend Standardization (parallel, ongoing)

Can happen alongside frontend phases. Doesn't block frontend work.

1. **Add Pydantic schemas** for each route group (start with `/api/companies` since it's ported first)
2. **Generate OpenAPI spec** via Flask-Smorest
3. **Generate TS types** via `openapi-typescript` → `frontend/src/api/types.ts`
4. **Standardize error responses** — adopt `{"error": str, "code": str, "details": {}}` format
5. **Add input validation** everywhere Pydantic is adopted (closes TD-004)
6. **Add `/api/docs`** Swagger UI endpoint

## Caddy Routing (During Migration)

```
# During migration: React app + old pages coexist
leadgen.visionvolve.com {
    # API → Flask
    handle /api/* {
        reverse_proxy leadgen-api:5000
    }

    # n8n webhooks
    handle /webhook/* {
        reverse_proxy n8n:5678
    }

    # React SPA (new pages)
    # Vite build output served from /srv/frontend/
    @reactRoutes {
        not path /api/* /webhook/* *.svg *.png *.ico
        not file {
            root /srv/dashboard    # old HTML files still exist
        }
    }
    handle @reactRoutes {
        root * /srv/frontend
        try_files {path} /index.html
    }

    # Old dashboard files (fallback during migration)
    handle {
        root * /srv/dashboard
        file_server
    }
}
```

After Phase 5 cleanup, simplify to just React SPA + API.

## Tailwind Theme (Design System Alignment)

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        bg: '#0D0F14',
        surface: { DEFAULT: '#14171E', alt: '#1A1E28' },
        border: { DEFAULT: 'rgba(110,44,139,0.15)', solid: '#231D30' },
        text: { DEFAULT: '#E8EAF0', muted: '#8B92A0', dim: '#5A6170' },
        accent: { DEFAULT: '#6E2C8B', hover: '#8B47A8', cyan: '#00B8CF' },
        success: '#34D399',
        error: '#F87171',
        warning: '#FBBF24',
      },
      fontFamily: {
        title: ['"Lexend Deca"', 'system-ui', 'sans-serif'],
        body: ['"Work Sans"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '8px',
        lg: '12px',
      },
    },
  },
}
```

## What We Keep, What We Change

| Aspect | Keep | Change |
|--------|------|--------|
| Flask API | Yes — proven, working | Add Pydantic + OpenAPI |
| PostgreSQL | Yes | No change |
| JWT auth | Yes — same tokens | Frontend storage moves to React context |
| Caddy | Yes | Update routing for SPA |
| Multi-tenant namespace | Yes — `/{namespace}/page` | React Router handles client-side |
| Virtual scroll | Yes — same pattern | Port to React component |
| CSS variables palette | Yes — same colors | Mapped to Tailwind theme |
| Deploy: scp to VPS | Yes | `vite build` before scp |
| n8n removal plan | Unchanged | Unchanged |

## What This Does NOT Include

- **No SSR/Next.js** — unnecessary complexity for an internal tool. Client-side React is fine.
- **No monorepo tooling** (turborepo, nx) — one frontend, one backend. Keep it simple.
- **No GraphQL** — REST is working. API surface is small enough that REST + OpenAPI covers it.
- **No micro-frontends** — single team, single app.
- **No Docker for frontend dev** — `npm run dev` locally, deploy built files.

## Risks

| Risk | Mitigation |
|------|-----------|
| Migration stalls halfway (half React, half vanilla) | Strangler fig is designed for this — old pages keep working indefinitely |
| New stack slows feature velocity short-term | Phase 0 + Phase 1 are small. After Contacts is ported, subsequent pages are faster |
| Tailwind learning curve | Utility classes are self-documenting. VS Code Tailwind extension helps |
| Build step adds deploy complexity | One `npm run build` command. Deploy script handles it |
| Generated types drift from API | CI check: regenerate types, fail if diff |

## Timeline Estimate

| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 0 | Foundation (scaffold, auth, nav, routing) | 1-2 days |
| Phase 1 | Contacts page (prove the stack) | 2-3 days |
| Phase 2 | Companies + Messages | 3-4 days |
| Phase 3 | Import + Enrich | 2-3 days |
| Phase 4 | Admin + utility pages | 1-2 days |
| Phase 5 | Cleanup old dashboard | 1 day |
| Phase 6 | Backend Pydantic/OpenAPI (parallel) | Ongoing |
| **Total** | **Full migration** | **~2-3 weeks** |

## Success Criteria

- [ ] All 11 current pages functional in React with no feature regression
- [ ] Zero duplicated API fetch logic (single `client.ts`)
- [ ] Zero duplicated CSS (Tailwind utilities + shared components)
- [ ] TypeScript types auto-generated from Flask OpenAPI spec
- [ ] Lighthouse performance score >= current vanilla pages
- [ ] `dashboard/` directory deleted, single `frontend/` source of truth
- [ ] Playwright E2E tests pass against React app (same tests, new UI)
