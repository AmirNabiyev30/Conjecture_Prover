"""
Shared Lean MCP client used by blueprint-generation and refinement nodes.

A single global client instance avoids redundant process launches for
the blueprint tool loop.  Proving and aggregator nodes create their own
isolated clients via the factory in `mcp_client.py`.
"""

from mcp_client import create_lean_mcp_client

_client = create_lean_mcp_client()
_lean_tools = None


async def get_lean_tools():
    """Return the shared Lean MCP tools (cached after first call)."""
    global _lean_tools
    if _lean_tools is None:
        _lean_tools = await _client.get_tools()
    return _lean_tools
