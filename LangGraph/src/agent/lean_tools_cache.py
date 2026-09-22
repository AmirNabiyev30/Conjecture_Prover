"""
Lean MCP tools for the Conjecture Prover graph.

Sessions are intentionally short-lived. ``MultiServerMCPClient.get_tools()``
opens (and tears down) a fresh REPL session per tool call, so no Lean REPL is
ever held for the lifetime of the process. A single long-lived REPL was
observed to exhaust memory over multi-round runs, so we deliberately do not
cache a client or tools at module scope.
"""

from mcp_client import create_lean_mcp_client


async def get_lean_tools(disabled_tools: list[str] | None = None):
    """Return Lean MCP tools that open a fresh REPL session per tool call.

    Nothing here is cached for the lifetime of the process: every call builds a
    fresh client, and each tool invocation opens (and reaps) its own session.
    """
    client = create_lean_mcp_client(disabled_tools=disabled_tools)
    return await client.get_tools()
