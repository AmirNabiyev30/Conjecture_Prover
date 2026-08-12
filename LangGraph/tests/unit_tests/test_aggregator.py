"""Unit tests for aggregator control flow and rollback behavior."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.messages import AIMessage

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from blueprint import Blueprint  # noqa: E402
from nodes.aggregator import aggregator  # noqa: E402
from state import State  # noqa: E402


pytestmark = pytest.mark.anyio


def _runtime(max_turns: int = 3):
    runtime = MagicMock()
    runtime.context = {"model": "test-model", "max_turns_per_lemma": max_turns}
    return runtime


def _proposal(*, proved: bool = True, feedback: str = ""):
    return {
        "lemma_id": "target_lemma",
        "status": "PROVED" if proved else "TOO_HARD",
        "old_str": "lemma target_lemma : P := by\n  sorry_using []",
        "new_str": "lemma target_lemma : P := by\n  exact proof_term" if proved else None,
        "proved": proved,
        "feedback": feedback,
    }


def _state(workspace: Path, proposals=None) -> State:
    return State(
        workspacePATH=str(workspace),
        project_root=str(workspace.parent),
        global_round=2,
        pending_proposals=proposals if proposals is not None else [_proposal()],
        lemma_statuses={
            "target_lemma": {
                "name": "target_lemma", "statement": "P", "sorry_free": False,
                "status": "unproved", "dependencies": [], "feedback": "",
            }
        },
    )


def _llm(response: AIMessage):
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=response)
    return llm


def _mcp():
    client = MagicMock()
    client.get_tools = AsyncMock(return_value=[])
    return client


async def test_no_valid_proposals_skips_model_and_build(tmp_path):
    workspace = tmp_path / "Workspace.lean"
    workspace.write_text("original")
    state = _state(workspace, proposals=[_proposal(proved=False)])

    with patch("nodes.aggregator.create_lean_mcp_client") as mcp, \
         patch("nodes.aggregator.init_chat_model") as llm, \
         patch("nodes.aggregator.subprocess.run") as build:
        result = await aggregator(state, _runtime())

    assert result["global_round"] == 3
    assert result["pending_proposals"] == []
    assert result["lemma_statuses"] == state.lemma_statuses
    mcp.assert_called_once()
    llm.assert_not_called()
    build.assert_not_called()


async def test_mcp_startup_failure_preserves_statuses(tmp_path):
    workspace = tmp_path / "Workspace.lean"
    workspace.write_text("original")
    state = _state(workspace)

    with patch("nodes.aggregator.create_lean_mcp_client", side_effect=RuntimeError("offline")), \
         patch("nodes.aggregator.Path.read_text", return_value="prompt"):
        result = await aggregator(state, _runtime())

    assert result["global_round"] == 3
    assert result["pending_proposals"] == []
    assert result["lemma_statuses"] == state.lemma_statuses
    assert workspace.read_text() == "original"


async def test_build_failure_rolls_back_and_forwards_feedback(tmp_path):
    workspace = tmp_path / "Workspace.lean"
    original = "original workspace"
    workspace.write_text(original)
    feedback = "TOO_HARD: proof failed after all attempts"
    state = _state(workspace, proposals=[_proposal(feedback=feedback)])
    llm = _llm(AIMessage(content="Done applying the proposal."))
    failed_build = SimpleNamespace(returncode=1, stderr="Lean error", stdout="")

    with patch("nodes.aggregator.create_lean_mcp_client", return_value=_mcp()), \
         patch("nodes.aggregator.init_chat_model", return_value=llm), \
         patch("nodes.aggregator.Path.read_text", side_effect=[original, "prompt"]), \
         patch("nodes.aggregator.subprocess.run", return_value=failed_build):
        # Simulate the fixer changing the file before the failed rebuild.
        workspace.write_text("broken workspace")
        result = await aggregator(state, _runtime())

    assert workspace.read_text() == original
    assert result["global_round"] == 3
    assert result["pending_proposals"] == []
    assert result["lemma_statuses"]["target_lemma"]["feedback"] == feedback


async def test_successful_build_returns_fresh_blueprint_and_statuses(tmp_path):
    workspace = tmp_path / "Workspace.lean"
    workspace.write_text("workspace")
    state = _state(workspace)
    llm = _llm(AIMessage(content="Applied and validated."))
    blueprint_json = [{
        "type": "node",
        "data": {
            "name": "target_lemma",
            "statement": {"latexEnv": "lemma", "text": "P"},
            "proof": {"usesLabels": [], "text": "proof"},
            "sorryFree": True,
            "location": {"range": {"pos": {"line": 1}, "endPos": {"line": 2}}},
        },
    }]
    successful_build = SimpleNamespace(returncode=0, stderr="", stdout="built")

    with patch("nodes.aggregator.create_lean_mcp_client", return_value=_mcp()), \
         patch("nodes.aggregator.init_chat_model", return_value=llm), \
         patch("nodes.aggregator.Path.read_text", side_effect=["workspace", "prompt"]), \
         patch("nodes.aggregator.subprocess.run", return_value=successful_build), \
         patch("nodes.aggregator.load_blueprint_json", return_value=blueprint_json):
        result = await aggregator(state, _runtime())

    assert result["global_round"] == 3
    assert result["pending_proposals"] == []
    assert result["blueprint"].node_by_id("target_lemma") is not None
    assert result["lemma_statuses"]["target_lemma"]["status"] == "proved"
