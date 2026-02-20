"""LLM API cost tracking across enrichment test runs.

Collects per-call cost data from Perplexity and Anthropic APIs,
generates summary reports per provider, per node, and per test.
"""

import json
import os
from datetime import datetime, timezone


# Pricing per 1M tokens (mirrors production client pricing)
PRICING = {
    "perplexity": {
        "sonar":               {"input_per_m": 1.0,  "output_per_m": 1.0},
        "sonar-pro":           {"input_per_m": 3.0,  "output_per_m": 15.0},
        "sonar-reasoning-pro": {"input_per_m": 2.0,  "output_per_m": 8.0},
        "sonar-reasoning":     {"input_per_m": 1.0,  "output_per_m": 5.0},
    },
    "anthropic": {
        "claude-haiku-4-5-20251001":  {"input_per_m": 0.80, "output_per_m": 4.0},
        "claude-sonnet-4-5-20250929": {"input_per_m": 3.0,  "output_per_m": 15.0},
        "claude-sonnet-4-5-20241022": {"input_per_m": 3.0,  "output_per_m": 15.0},
    },
}


def estimate_cost(provider, model, input_tokens, output_tokens):
    """Estimate cost in USD from token counts."""
    provider_pricing = PRICING.get(provider, {})
    model_pricing = provider_pricing.get(model)
    if not model_pricing:
        # Fallback: try partial match
        for key, pricing in provider_pricing.items():
            if key in model:
                model_pricing = pricing
                break
    if not model_pricing:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * model_pricing["input_per_m"]
    output_cost = (output_tokens / 1_000_000) * model_pricing["output_per_m"]
    return round(input_cost + output_cost, 6)


class CostTracker:
    """Tracks LLM API costs across test runs."""

    def __init__(self):
        self.calls = []

    def log_call(self, provider, model, input_tokens, output_tokens,
                 cost_usd, test_name, node_name):
        """Record a single API call with cost data."""
        self.calls.append({
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "test_name": test_name,
            "node_name": node_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_summary(self):
        """Generate cost summary grouped by provider, node, and test."""
        total_cost = sum(c["cost_usd"] for c in self.calls)
        total_input = sum(c["input_tokens"] for c in self.calls)
        total_output = sum(c["output_tokens"] for c in self.calls)

        by_provider = {}
        for c in self.calls:
            p = c["provider"]
            if p not in by_provider:
                by_provider[p] = {"cost_usd": 0, "calls": 0,
                                  "input_tokens": 0, "output_tokens": 0}
            by_provider[p]["cost_usd"] += c["cost_usd"]
            by_provider[p]["calls"] += 1
            by_provider[p]["input_tokens"] += c["input_tokens"]
            by_provider[p]["output_tokens"] += c["output_tokens"]

        by_node = {}
        for c in self.calls:
            n = c["node_name"]
            if n not in by_node:
                by_node[n] = {"cost_usd": 0, "calls": 0}
            by_node[n]["cost_usd"] += c["cost_usd"]
            by_node[n]["calls"] += 1

        by_test = {}
        for c in self.calls:
            t = c["test_name"]
            if t not in by_test:
                by_test[t] = {"cost_usd": 0, "calls": 0}
            by_test[t]["cost_usd"] += c["cost_usd"]
            by_test[t]["calls"] += 1

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_calls": len(self.calls),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "by_provider": by_provider,
            "by_node": by_node,
            "by_test": by_test,
        }

    def save_report(self, path=None):
        """Save JSON report to file."""
        if path is None:
            reports_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = os.path.join(reports_dir, "cost_{}.json".format(timestamp))

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_summary(),
            "calls": self.calls,
        }
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        return path

    def print_summary(self):
        """Pretty-print cost summary to stdout."""
        summary = self.get_summary()
        print("\n" + "=" * 60)
        print("  ENRICHMENT TEST COST REPORT")
        print("=" * 60)
        print("  Total cost:     ${:.4f}".format(summary["total_cost_usd"]))
        print("  Total API calls: {}".format(summary["total_calls"]))
        print("  Total tokens:    {} in / {} out".format(
            summary["total_input_tokens"], summary["total_output_tokens"]))

        if summary["by_provider"]:
            print("\n  By Provider:")
            for p, data in sorted(summary["by_provider"].items()):
                print("    {:<15} ${:.4f}  ({} calls)".format(
                    p, data["cost_usd"], data["calls"]))

        if summary["by_node"]:
            print("\n  By Node:")
            for n, data in sorted(summary["by_node"].items(),
                                  key=lambda x: x[1]["cost_usd"], reverse=True):
                print("    {:<25} ${:.4f}  ({} calls)".format(
                    n, data["cost_usd"], data["calls"]))

        if summary["by_test"]:
            print("\n  By Test:")
            for t, data in sorted(summary["by_test"].items(),
                                  key=lambda x: x[1]["cost_usd"], reverse=True):
                print("    {:<35} ${:.4f}".format(t, data["cost_usd"]))

        print("=" * 60 + "\n")
