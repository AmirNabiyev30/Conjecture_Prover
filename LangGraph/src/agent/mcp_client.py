"""
MCP client factory for the Conjecture Prover graph.

Provides a simple factory that creates MultiServerMCPClient instances
pre-configured for the Lean REPL server. Each call creates a new client
so nodes get isolated sessions.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient

from config import LEAN_MCP_CONFIG


def create_lean_mcp_client() -> MultiServerMCPClient:
    """Create a new MultiServerMCPClient configured for the Lean REPL server.
    
    Returns:
        A fresh client instance (call .get_tools() to start the session).
    """
    return MultiServerMCPClient({"lean": dict(LEAN_MCP_CONFIG)})
