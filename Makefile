.PHONY: dev dev-status sync pr-scan agents db-pull db-reset test test-e2e test-all lint

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

## Run Python unit tests
test:
	pytest tests/unit/ -v

## Run Playwright browser tests (requires make dev running)
test-e2e:
	cd frontend && VITE_PORT=$(VITE_PORT) FLASK_PORT=$(FLASK_PORT) npx playwright test

## Run all tests
test-all: test test-e2e

## Run linters
lint:
	ruff check api/ && ruff format --check api/
	cd frontend && npm run lint
