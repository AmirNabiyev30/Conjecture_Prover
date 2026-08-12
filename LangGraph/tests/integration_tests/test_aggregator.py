"""Model-backed integration test for the focused aggregator node.

The real aggregator model is exercised against a temporary workspace file. The
Lean diagnostics, build result, and blueprint JSON are controlled so this test
does not invoke the full graph or modify the repository workspace.

Run with::

    pytest -s tests/integration_tests/test_aggregator.py -m mcp
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv
from langchain_core.tools import tool

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from blueprint import Blueprint  # noqa: E402
from config import MODEL_NAME  # noqa: E402
from nodes.aggregator import aggregator  # noqa: E402
from state import Context, State  # noqa: E402
import nodes.aggregator as aggregator_module  # noqa: E402


pytestmark = [pytest.mark.anyio, pytest.mark.mcp, pytest.mark.slow]
load_dotenv()


ORIGINAL = "lemma target_lemma : P := by\n  sorry_using []\n"
REPLACEMENT = "lemma target_lemma : P := by\n  exact proof_term\n"


class AggregatorHarness:
    """Temporary-file tools and deterministic Lean/build responses."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.tool_calls: list[str] = []

    def file_tools(self) -> list:
        harness = self

        @tool
        def search_replace_workspace(
            relative_path: str, old_string: str, new_string: str
        ) -> str:
            """Replace one exact proposal in the temporary workspace."""
            harness.tool_calls.append("search_replace_workspace")
            content = harness.workspace.read_text()
            if content.count(old_string) != 1:
                return "ERROR: old_string must occur exactly once"
            harness.workspace.write_text(content.replace(old_string, new_string))
            return "Replaced 1 occurrence."

        @tool
        def read_workspace(workspace_path: str) -> str:
            """Read the temporary workspace for diagnosing an error."""
            harness.tool_calls.append("read_workspace")
            return harness.workspace.read_text()

        return [search_replace_workspace, read_workspace]


class FakeMcpClient:
    def __init__(self, harness: AggregatorHarness):
        self.harness = harness

    async def get_tools(self) -> list:
        harness = self.harness

        @tool
        def lean_diagnostic_messages(file_path: str) -> str:
            """Return successful diagnostics for the temporary workspace."""
            harness.tool_calls.append("lean_diagnostic_messages")
            return "No real Lean errors."

        return [lean_diagnostic_messages]


def _proposal():
    return {
        "lemma_id": "target_lemma",
        "status": "PROVED",
        "old_str": ORIGINAL.rstrip("\n"),
        "new_str": REPLACEMENT.rstrip("\n"),
        "proved": True,
        "feedback": "PROVED: validated by the prover",
    }


def _blueprint_json():
    return [{
        "type": "node",
        "data": {
            "name": "target_lemma",
            "statement": {"latexEnv": "lemma", "text": "P"},
            "proof": {"usesLabels": [], "text": "exact proof_term"},
            "sorryFree": True,
            "location": {"range": {"pos": {"line": 1}, "endPos": {"line": 2}}},
        },
    }]


async def test_aggregator_model_applies_and_validates_proposal(tmp_path, monkeypatch):
    """The real model applies the proposal through the aggregator tool loop."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    workspace = tmp_path / "Workspace.lean"
    workspace.write_text(ORIGINAL)
    harness = AggregatorHarness(workspace)
    mcp = FakeMcpClient(harness)

    monkeypatch.setattr(aggregator_module, "file_tools", harness.file_tools())
    monkeypatch.setattr(aggregator_module, "create_lean_mcp_client", lambda: mcp)
    monkeypatch.setattr(
        aggregator_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout="built"),
    )
    monkeypatch.setattr(aggregator_module, "load_blueprint_json", lambda root: _blueprint_json())

    state = State(
        workspacePATH=str(workspace),
        project_root=str(tmp_path),
        global_round=0,
        pending_proposals=[_proposal()],
        lemma_statuses={
            "target_lemma": {
                "name": "target_lemma", "statement": "P", "sorry_free": False,
                "status": "unproved", "dependencies": [], "feedback": "",
            }
        },
    )
    runtime = type("Runtime", (), {
        "context": {"model": MODEL_NAME, "max_turns_per_lemma": 8}
    })()

    result = await aggregator(state, runtime)

    assert "search_replace_workspace" in harness.tool_calls
    assert "lean_diagnostic_messages" in harness.tool_calls
    assert workspace.read_text() == REPLACEMENT
    assert result["global_round"] == 1
    assert result["pending_proposals"] == []
    assert result["lemma_statuses"]["target_lemma"]["status"] == "proved"
