"""
MCP client factory for the Conjecture Prover graph.

Provides a simple factory that creates MultiServerMCPClient instances
pre-configured for the Lean REPL server. Each call creates a new client
so nodes get isolated sessions.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient

from config import LEAN_MCP_CONFIG


def create_lean_mcp_client(disabled_tools: list[str] | None = None) -> MultiServerMCPClient:
    """Create a new MultiServerMCPClient configured for the Lean REPL server.

    If `disabled_tools` is provided, the MCP server is started with
    `LEAN_MCP_DISABLED_TOOLS` set so those tool names are removed from the
    tool listing before the agent sees them.

    Returns:
        A fresh client instance (call .get_tools() to start the session).
    """
    config = dict(LEAN_MCP_CONFIG)
    env = dict(config.get("env", {}))
    if disabled_tools:
        env["LEAN_MCP_DISABLED_TOOLS"] = ",".join(disabled_tools)
    config["env"] = env
    return MultiServerMCPClient({"lean": config})
