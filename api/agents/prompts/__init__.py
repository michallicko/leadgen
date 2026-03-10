"""Layered prompt system for the strategy agent.

Prompts are split into layers for Anthropic prompt caching:
  Layer 0 (identity): Static role, rules, tone (~800 tok, cached)
  Layer 1 (capabilities): Tool usage rules (~500-1500 tok, cached)
  Layer 2 (context): Dynamic strategy state, enrichment (~1-5K tok)
"""

STRATEGY_SECTIONS = [
    "Executive Summary",
    "Value Proposition & Messaging",
    "Competitive Positioning",
    "Channel Strategy",
    "Messaging Framework",
    "Metrics & KPIs",
    "90-Day Action Plan",
]
