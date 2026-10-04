import pytest
from langgraph.pregel import Pregel
from pathlib import Path

from agent import config
from agent.graph import build_graph


@pytest.mark.asyncio
async def test_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify graph construction without starting the real Lean MCP server."""
    async def fake_get_lean_tools() -> list:
        return []

    monkeypatch.setattr("agent.graph.get_lean_tools", fake_get_lean_tools)
    g = await build_graph()
    assert isinstance(g, Pregel)


def test_project_root_resolves_to_repo_root() -> None:
    """PROJECT_ROOT must be derived from this file's location, not hardcoded.

    Guards the ``parents[3]`` derivation in config.py: if the depth ever changes,
    these repo-root markers stop resolving and the test fails loudly instead of
    the whole suite quietly pointing at a non-existent directory.
    """
    assert config.PROJECT_ROOT.is_absolute()
    assert (config.PROJECT_ROOT / "LangGraph" / "pyproject.toml").is_file()
    assert (config.PROJECT_ROOT / "prompts").is_dir()


def test_paths_are_anchored_to_project_root() -> None:
    """Workspace and Mathlib paths must follow PROJECT_ROOT, not duplicate it."""
    assert Path(config.WORKSPACE_PATH) == config.PROJECT_ROOT / "ConjectureProver.lean"
    assert config.MATHLIB4_ROOT == config.PROJECT_ROOT / "mathlib4"
