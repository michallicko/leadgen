#!/bin/bash
# Run enrichment tests with cost tracking
# Usage: ./run_enrichment_tests.sh [pytest args]
#
# Examples:
#   ./run_enrichment_tests.sh                    # Run all
#   ./run_enrichment_tests.sh -k "l1_research"   # Just L1 research
#   ./run_enrichment_tests.sh -k "triage"        # Just triage (no API cost)
#   ./run_enrichment_tests.sh -m "not costly"    # Skip expensive tests
#   ./run_enrichment_tests.sh -m "not slow"      # Skip slow tests

set -e
cd "$(dirname "$0")/../.."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Load .env.dev if it exists (contains API keys)
if [ -f .env.dev ]; then
    set -a
    source .env.dev
    set +a
fi

echo "=== Enrichment Node Tests ==="
echo "Starting at $(date)"
echo ""

# Check for API keys
if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "WARNING: PERPLEXITY_API_KEY not set — Perplexity tests will be skipped"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY not set — Anthropic tests will be skipped"
fi
echo ""

pytest tests/enrichment/ -v --tb=short -m enrichment "$@"
