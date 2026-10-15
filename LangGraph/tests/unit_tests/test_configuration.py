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
    assert Path(config.WORKSPACE_PATH) == config.PROJECT_ROOT / config.WORKSPACE_NAME
    assert config.MATHLIB4_ROOT == config.PROJECT_ROOT / "mathlib4"


def test_workspace_name_defaults_and_is_overridable_by_env() -> None:
    """The workspace filename is configurable, but a blank value must fall back.

    A checkout names its Lean root module after its own Lake library, so the
    name cannot be a constant. An unset *or blank* ``WORKSPACE_NAME`` must still
    yield the documented default rather than ``PROJECT_ROOT / ""``.
    """
    assert config.DEFAULT_WORKSPACE_NAME == "ConjectureProver.lean"
    assert config.workspace_name({}) == config.DEFAULT_WORKSPACE_NAME
    assert (
        config.workspace_name({"WORKSPACE_NAME": "LeanWorkspace.lean"})
        == "LeanWorkspace.lean"
    )
    assert config.workspace_name({"WORKSPACE_NAME": "   "}) == config.DEFAULT_WORKSPACE_NAME


def test_workspace_module_is_the_filename_stem() -> None:
    """The blueprint module name must be derived from the workspace, not repeated.

    ``lake build :blueprintJson`` writes ``<module>.json``, and ``<module>`` is
    the module the workspace compiles into. Keeping this derived is what stops
    a rename from leaving blueprint lookups pointed at a file Lake never emits.
    """
    assert config.WORKSPACE_MODULE == Path(config.WORKSPACE_NAME).stem
    assert config.WORKSPACE_MODULE == "ConjectureProver"
