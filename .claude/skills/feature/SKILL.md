---
name: feature
description: "Spec-driven feature lifecycle: backlog check, spec (3 docs with questions), worktree, implement, quality gates, deploy rev to staging, PR. Use when the user wants to build something new end-to-end. Invoke with `/feature <description>`."
---

# Feature Lifecycle (Spec-Driven Development)

Every feature starts with a specification, not code. You spend 80% of effort on spec and validation, 20% on writing code. You never merge — the PR is the handoff point.

This skill is a **coordinator** — it delegates to other skills where they exist. The lifecycle follows CLAUDE.md exactly.

**Three mandatory pauses**: (1) clarifying questions, (2) spec approval, (3) human inspection of staging.

---

## Phase 0: Backlog Check

Invoke `/backlog` (no arguments) to check the current backlog state. Then:

1. Check if this feature already exists as a backlog item
2. Check for related items that could be bundled
3. Check for dependency conflicts (don't start X if Y isn't done yet)
4. If a matching item exists, tell the user and ask whether to proceed or pivot

If no matching item exists, one will be created during the spec phase.

## Phase 1: Spec First (80% of Your Time)

This is the core of spec-driven development. The spec has **three documents**, each reviewed before moving to the next.

### 1a. Explore

Read relevant code — use Glob, Grep, and Read to understand the current state. Read:
- `docs/ARCHITECTURE.md`
- `BACKLOG.md`
- `docs/PRODUCT_STRATEGY.md` (if exists)
- `docs/TECHNICAL_STRATEGY.md` (if exists)
- `docs/DESIGN_STRATEGY.md` (if exists)
- Existing specs in `docs/specs/`
- ADRs in `docs/adr/`
- Actual source code for affected components

### 1b. Clarifying Questions — PAUSE 1

After exploration, ask 3-5 clarifying questions using AskUserQuestion. Questions must cover:
- **Intent**: What problem are you solving? What does success look like?
- **Scope**: Minimum viable vs full version — which do you want?
- **Constraints**: Timeline, compatibility, things to avoid
- **Acceptance criteria**: How will we verify this works? (Given/When/Then)
- **Trade-offs**: Surface any technical choices that need a business decision

**Do not write any spec until answers are received.**

### 1c. Write Three Spec Documents

Create `docs/specs/{feature-name}/` directory with three files:

**1. `requirements.md`** — What and why
- Purpose (business problem, who it serves)
- Functional requirements (FR-1, FR-2, ...)
- Non-functional requirements (NFR-1, NFR-2, ...)
- Acceptance criteria (Given/When/Then format)
- Out of scope (explicit exclusions)

**2. `design.md`** — How it works
- Affected components (specific file paths)
- Data model changes (tables, columns, migrations)
- API contracts (endpoints, request/response shapes)
- UX flow (user journey, interactions, layout, states)
- Architecture decisions (reference existing ADRs, flag new ones)
- Edge cases and how they're handled
- Security considerations (auth, validation, multi-tenancy)

**3. `tasks.md`** — What to build, in what order
- Atomic implementation tasks (each one is a commit-sized unit)
- Traceability matrix: AC → task → test (every acceptance criterion maps to a task and a test)
- Task dependencies (which must come first)
- Testing strategy (unit tests, E2E tests, test data needed)

### 1d. Spec Review — PAUSE 2

Present all three documents to the user. **Do not write code until all three are approved.** If the user requests changes, update the documents and re-present.

Also create/update the backlog item in `BACKLOG.md` with status "Refined" and a link to the spec.

## Phase 2: Worktree + Branch

Invoke the `superpowers:using-git-worktrees` skill to create an isolated worktree for this feature. It handles:

- Branch naming (`feature/{short-kebab-name}`)
- Worktree creation from `origin/staging`
- `.env.dev` copying
- Safety verification

## Phase 3: Implement

Follow `tasks.md` in order. Use the `superpowers:test-driven-development` skill as the implementation discipline.

1. **Start the dev server** — `DEV_SLOT=N make dev` (pick the next free slot via `make dev-status`)
2. **TDD loop** — for each task in `tasks.md`: write tests first (from the traceability matrix), then implement to make them pass
3. **Commit incrementally** — commit after each task, push to remote immediately
4. **Update the spec** — specs are living documents. If you discover something during implementation that changes requirements, update the spec files and note it to the user.
5. **Update backlog** — mark the item as "In Progress"

If you encounter bugs or unexpected behavior, invoke `superpowers:systematic-debugging` before guessing at fixes.

If `tasks.md` has 2+ independent tasks, consider `superpowers:dispatching-parallel-agents` to work on them concurrently.

### Implementation Rules

- Stay in the worktree directory at all times
- Never `git checkout` or `git switch` — you're in a worktree
- Follow existing code patterns — read before writing
- Every acceptance criterion must have a corresponding test

## Phase 4: Quality Gates

Every feature must pass ALL of these before deployment:

1. **Tests** — Run `make test-all` (unit + E2E). Show the output. All must pass.
2. **Self-review** — Review all changed files. Check for security issues, edge cases, consistency with existing patterns.
3. **Security audit** — Check for OWASP top 10 (XSS, injection, auth bypass). Validate at system boundaries. Never trust client input.
4. **Documentation** — Update `docs/ARCHITECTURE.md` if components changed. Update `CHANGELOG.md`. Write ADR in `docs/adr/` for any non-trivial technical decision.
5. **Backlog** — Update `BACKLOG.md`. Mark completed items, add new items discovered during work.
6. **All committed and pushed** — Nothing local-only. `git status` must be clean.

Invoke `superpowers:verification-before-completion` to ensure evidence-based validation — never claim "tests pass" without running them and showing output.

## Phase 5: Deploy Revision to Staging

This is the standard flow — do not ask, just do it. Every feature gets a staging revision for acceptance testing.

1. **Deploy the revision**:
   ```bash
   bash deploy/deploy-revision.sh
   ```
   This deploys the feature branch as an API revision at `/api-rev-{commit}/` on staging.

2. **If the feature includes frontend changes**, also deploy the dashboard build to staging. The `?rev=` param only routes API calls — new pages, components, or JS changes require the dashboard to be deployed too.

3. **Report the staging URL** to the user:
   - API: `https://leadgen-staging.visionvolve.com/api-rev-{commit}/health`
   - Dashboard: `https://leadgen-staging.visionvolve.com/visionvolve/?rev={commit}`

### Human Inspection — PAUSE 3

The user will manually verify on staging. Wait for their confirmation before proceeding to PR.

## Phase 6: PR

After the user confirms the staging revision works:

```bash
gh pr create --base staging --title "Short description" --body "$(cat <<'EOF'
## Summary
- bullet points from the spec

## Spec
`docs/specs/{feature-name}/`

## Staging revision
Deployed and verified at `?rev={commit}`

## Test plan
- [ ] Unit tests pass (`make test`)
- [ ] E2E tests pass (`make test-e2e`)
- [ ] Staging acceptance testing passed
- [ ] Quality gates passed (security, docs, backlog)

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Report the PR URL to the user.

After the PR is merged (by someone else — never by you), clean up:
```bash
bash deploy/teardown-revision.sh {commit}
```

---

## Key Behaviors

- **Spec-driven** — 80% spec and validation, 20% code. The spec is the primary artifact.
- **Three pauses, no more** — (1) clarifying questions, (2) spec approval, (3) staging inspection. Don't add extra approval gates.
- **Three spec documents** — requirements.md, design.md, tasks.md. Each serves a distinct purpose.
- **Living specs** — update during implementation when reality diverges from plan.
- **Traceability** — every AC maps to a task, every task maps to a test. Nothing falls through cracks.
- **Quality gates are mandatory** — tests, self-review, security, docs, backlog. All six before deployment.
- **Always deploy to rev** — standard flow, not optional. Every feature gets a staging revision.
- **Frontend changes need dashboard deploy too** — `?rev=` only routes API calls.
- **Never merge** — not to staging, not to main, not locally. PR is the handoff.
- **Never deploy to production** — only `deploy-revision.sh` for staging revisions.
- **Commit and push constantly** — work must never exist only locally.
- **Stay in your worktree** — never touch the main worktree's files.

## Skill Delegation Map

| Phase | Skill | Purpose |
|-------|-------|---------|
| 0 | `/backlog` | Check existing items, dependencies |
| 1 | (built-in) | Explore, question, write 3 spec docs |
| 2 | `superpowers:using-git-worktrees` | Isolated branch + worktree |
| 3 | `superpowers:test-driven-development` | TDD implementation loop |
| 3 | `superpowers:systematic-debugging` | When bugs arise (on demand) |
| 3 | `superpowers:dispatching-parallel-agents` | Independent tasks (on demand) |
| 4 | `superpowers:verification-before-completion` | Evidence-based quality gates |
| 5 | `deploy/deploy-revision.sh` | Deploy to staging for acceptance |
| 6 | `gh pr create` | PR targeting staging |
