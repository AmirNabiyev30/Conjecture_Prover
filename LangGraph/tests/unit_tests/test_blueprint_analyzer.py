"""Tests for the retrieve_blueprint_node tool."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from agents.blueprint_analyzer import retrieve_blueprint_node


# ── Helper: create a mock .lake/build/blueprint/module/LeanWorkspace.json ─────

@pytest.fixture
def mock_blueprint_json(tmp_path):
    """Create a temporary blueprint JSON that the tool can find."""
    lake_dir = tmp_path / ".lake" / "build" / "blueprint" / "module"
    lake_dir.mkdir(parents=True)

    bp = [
        {
            "type": "node",
            "data": {
                "name": "lemma_connectivity",
                "statement": {"text": "Show the graph is connected", "latexEnv": "lemma"},
                "proof": {"usesLabels": [], "uses": []},
                "file": "LeanWorkspace.lean",
            },
        },
        {
            "type": "node",
            "data": {
                "name": "main_thm",
                "statement": {"text": "The main result", "latexEnv": "theorem"},
                "proof": {"usesLabels": ["lemma_connectivity"], "uses": []},
                "file": "LeanWorkspace.lean",
            },
        },
    ]
    (lake_dir / "LeanWorkspace.json").write_text(json.dumps(bp))

    # Patch PROJECT_ROOT to point to tmp_path for this test
    import agents.blueprint_analyzer as ba
    import config
    original_root = config.PROJECT_ROOT
    config.PROJECT_ROOT = tmp_path
    ba.PROJECT_ROOT = tmp_path
    yield tmp_path
    config.PROJECT_ROOT = original_root
    ba.PROJECT_ROOT = original_root


@pytest.mark.asyncio
async def test_retrieve_blueprint_node_finds_existing_node(mock_blueprint_json):
    """The tool should find a node in the blueprint and return results."""
    result = await retrieve_blueprint_node.ainvoke({"node_id": "lemma_connectivity"})

    assert "lemma_connectivity" in result
    assert "Show the graph is connected" in result or "graph is connected" in result.lower()
    assert "Mathlib matches" in result


@pytest.mark.asyncio
async def test_retrieve_blueprint_node_handles_missing_node(mock_blueprint_json):
    """The tool should gracefully handle a node that doesn't exist in the blueprint."""
    result = await retrieve_blueprint_node.ainvoke({"node_id": "nonexistent_lemma"})

    assert "nonexistent_lemma" in result
    assert "Mathlib matches" in result  # still searches Mathlib


@pytest.mark.asyncio
async def test_retrieve_blueprint_node_returns_structured_output(mock_blueprint_json):
    """Output should contain all expected sections."""
    result = await retrieve_blueprint_node.ainvoke({"node_id": "main_thm"})

    assert "## Retrieval results for:" in result
    assert "### Mathlib matches" in result
    assert "main_thm" in result


def test_retrieve_blueprint_node_is_registered_as_tool():
    """Verify the tool has the correct LangChain tool metadata."""
    assert retrieve_blueprint_node.name == "retrieve_blueprint_node"
    assert "node_id" in retrieve_blueprint_node.description
    assert "Mathlib" in retrieve_blueprint_node.description
