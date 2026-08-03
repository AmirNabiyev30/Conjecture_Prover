import pytest
from langgraph.pregel import Pregel

from agent.graph import build_graph


@pytest.mark.asyncio
async def test_placeholder() -> None:
    """Verify the graph can be built and is a valid Pregel instance."""
    g = await build_graph()
    assert isinstance(g, Pregel)
