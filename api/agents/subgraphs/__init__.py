"""Multi-agent subgraphs for specialist task routing.

Each subgraph is a compiled LangGraph StateGraph with focused tools
and system prompts for a specific domain (strategy, research, etc.).
"""

from .research import build_research_subgraph
from .strategy import build_strategy_subgraph

__all__ = ["build_strategy_subgraph", "build_research_subgraph"]
