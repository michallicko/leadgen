"""LangGraph-based agent architecture for AI chat.

This package replaces the monolithic agent_executor.py with a graph-based
agent using LangGraph StateGraph. Feature-flagged via LANGGRAPH_ENABLED env var.

Modules:
    state     — Typed state schema (AgentState)
    graph     — StateGraph definition and compilation
    nodes     — Graph node functions (route, call_model, execute_tools)
    tools     — Tool adapter from ToolRegistry to LangGraph @tool format
    prompts   — Layered prompt assembly with caching support
    streaming — LangGraph event → AG-UI SSE adapter
"""

from .graph import create_agent_graph
from .integration import is_langgraph_enabled, stream_langgraph_response
from .state import AgentState

__all__ = [
    "create_agent_graph",
    "AgentState",
    "is_langgraph_enabled",
    "stream_langgraph_response",
]
