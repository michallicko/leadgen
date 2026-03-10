"""Bridge between existing tool_registry handlers and LangGraph tools.

The graph in graph.py uses the tool_registry directly via get_tools_for_api()
for tool definitions and get_tool() for execution, rather than wrapping
handlers in LangChain StructuredTool objects. This module is reserved for
future LangGraph native tool binding if we migrate away from the manual
tool execution in tools_node().
"""
