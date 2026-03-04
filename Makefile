.PHONY: dev dev-status sync pr-scan agents db-pull db-reset test test-changed test-e2e test-all test-enrichment lint lint-changed backlog

# Slot computation from DEV_SLOT env var (default 0)
SLOT       ?= $(or $(DEV_SLOT),0)
FLASK_PORT := $(shell echo $$((5001 + $(SLOT))))
VITE_PORT  := $(shell echo $$((5173 + $(SLOT))))

## Start local dev environment (PG + Flask + Vite)
dev:
	DEV_SLOT=$(SLOT) bash scripts/dev.sh

## Show active dev slots and PG status
dev-status:
	@echo "==> Dev slot status"
	@echo ""
	@for s in 0 1 2 3 4 5 6 7 8 9; do \
		fp=$$((5001 + s)); vp=$$((5173 + s)); \
		flask_pid=$$(lsof -ti :$$fp 2>/dev/null || true); \
		vite_pid=$$(lsof -ti :$$vp 2>/dev/null || true); \
		if [ -n "$$flask_pid" ] || [ -n "$$vite_pid" ]; then \
			echo "  Slot $$s: Flask=:$$fp $${flask_pid:+(pid $$flask_pid)}$${flask_pid:-STOPPED}  Vite=:$$vp $${vite_pid:+(pid $$vite_pid)}$${vite_pid:-STOPPED}"; \
		fi; \
	done
	@echo ""
	@if docker exec leadgen-dev-pg pg_isready -U leadgen -q 2>/dev/null; then \
		echo "  PG: running (port 5433)"; \
	else \
		echo "  PG: not running"; \
	fi

## Fetch + rebase onto origin/staging (the only correct base)
sync:
	git fetch origin staging
	@BEHIND=$$(git rev-list --count HEAD..origin/staging 2>/dev/null || echo 0); \
	if [ "$$BEHIND" = "0" ]; then \
		echo "Already up to date with origin/staging."; \
	else \
		echo "Rebasing onto origin/staging ($$BEHIND commits behind)..."; \
		git rebase origin/staging; \
	fi

## Scan open PRs for file conflicts before creating a new PR
pr-scan:
	bash scripts/pr-conflict-scan.sh

## List active agents from registry (+ cleanup stale)
agents:
	bash scripts/registry.sh cleanup
	bash scripts/registry.sh list

## Pull staging DB to local PostgreSQL
db-pull:
	bash scripts/pull-staging-db.sh

## Drop and recreate local PostgreSQL database (empty)
db-reset:
	docker exec leadgen-dev-pg psql -U leadgen -d postgres -c "DROP DATABASE IF EXISTS leadgen;"
	docker exec leadgen-dev-pg psql -U leadgen -d postgres -c "CREATE DATABASE leadgen;"
	@echo "Local DB reset (empty). Run 'make db-pull' to restore data."

## Run Python unit tests (testmon: only re-runs affected tests)
test:
	pytest tests/unit/ -v

## Run all unit tests ignoring testmon cache (full run)
test-full:
	pytest tests/unit/ -v -p no:testmon

## Run enrichment tests with live API calls (testmon-aware)
test-enrich:
	set -a && . .env.dev && set +a && pytest tests/enrichment/ -v

## Run enrichment tests — full run, ignore cache
test-enrich-full:
	set -a && . .env.dev && set +a && pytest tests/enrichment/ -v -p no:testmon

## Run enrichment triage tests only (free, no API calls)
test-triage:
	pytest tests/enrichment/test_l1_triage.py -v

## Run Playwright browser tests (requires make dev running)
test-e2e:
	cd frontend && VITE_PORT=$(VITE_PORT) FLASK_PORT=$(FLASK_PORT) npx playwright test

## Run enrichment scoring tests (scorecard)
test-enrichment:
	python -m pytest tests/unit/test_enrichment_scoring.py -v --tb=short

## Run all tests
test-all: test test-enrich test-e2e

## Open backlog dashboard in browser (serves docs/backlog/ via HTTP)
backlog:
	@echo "Opening backlog dashboard at http://localhost:8090"
	@(sleep 0.5 && open http://localhost:8090 2>/dev/null || xdg-open http://localhost:8090 2>/dev/null || true) &
	@cd docs/backlog && python3 -m http.server 8090

## Run targeted tests on changed files only (vs origin/staging)
test-changed:
	@CHANGED=$$(git diff --name-only origin/staging...HEAD -- '*.py' 2>/dev/null); \
	TEST_FILES=""; \
	for f in $$CHANGED; do \
		base=$$(basename "$$f" .py); \
		found=$$(find tests/ -name "test_$${base}.py" -o -name "test_$${base}_*.py" 2>/dev/null); \
		TEST_FILES="$$TEST_FILES $$found"; \
		if echo "$$f" | grep -q "^tests/"; then \
			TEST_FILES="$$TEST_FILES $$f"; \
		fi; \
	done; \
	TEST_FILES=$$(echo "$$TEST_FILES" | tr ' ' '\n' | sort -u | tr '\n' ' '); \
	if [ -n "$$(echo "$$TEST_FILES" | tr -d ' ')" ]; then \
		echo "Running targeted tests: $$TEST_FILES"; \
		pytest $$TEST_FILES -v --timeout=60; \
	else \
		echo "No test files to run for changed sources"; \
	fi

## Lint only changed Python files (vs origin/staging)
lint-changed:
	@CHANGED=$$(git diff --name-only origin/staging...HEAD -- '*.py' 2>/dev/null | tr '\n' ' '); \
	if [ -n "$$CHANGED" ]; then \
		echo "Linting changed files: $$CHANGED"; \
		ruff check $$CHANGED && ruff format --check $$CHANGED; \
	else \
		echo "No Python files changed, skipping lint"; \
	fi

## Run linters (full)
lint:
	ruff check api/ && ruff format --check api/
	cd frontend && npm run lint
