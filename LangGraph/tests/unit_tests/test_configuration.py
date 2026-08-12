import pytest
from langgraph.pregel import Pregel

from agent.graph import build_graph


@pytest.mark.asyncio
async def test_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify graph construction without starting the real Lean MCP server."""
    async def fake_get_lean_tools() -> list:
        return []

    monkeypatch.setattr("agent.graph.get_lean_tools", fake_get_lean_tools)
    g = await build_graph()
    assert isinstance(g, Pregel)
