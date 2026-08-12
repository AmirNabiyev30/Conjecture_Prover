"""Focused model-backed integration test for blueprint refinement.

This is intentionally a section test, not a full-workflow test.  It supplies a
synthetic blueprint and prover diagnosis, then runs the real refiner model
through a small LangGraph tool loop.  Workspace and Lean tools are controlled so
the test evaluates model behavior without mutating the repository or invoking
the aggregator/prover stages.

Run with::

    pytest -s tests/integration_tests/test_blueprint_refiner.py -m mcp
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from config import (  # noqa: E402
    BLUEPRINT_REFINER_PROMPT,
    MODEL_NAME,
)
from blueprint import Blueprint  # noqa: E402
import nodes.blueprint_refiner as blueprint_refiner_module  # noqa: E402
from nodes.blueprint_refiner import blueprint_refiner  # noqa: E402
from state import Context, State  # noqa: E402


pytestmark = [pytest.mark.anyio, pytest.mark.mcp, pytest.mark.slow]
load_dotenv()


INITIAL_WORKSPACE = """import Mathlib
import Architect

@[blueprint]
lemma easy_helper (x : ℝ) : x = x := by
  sorry_using []

@[blueprint]
lemma hard_lemma (x : ℝ) : x + 0 = x := by
  sorry_using [easy_helper]

@[blueprint]
theorem target_theorem (x : ℝ) : x + 0 = x := by
  sorry_using [hard_lemma]
"""


def _blueprint() -> Blueprint:
    return Blueprint(
        theorem_name="target_theorem",
        statement="For every real x, x + 0 = x.",
        nodes=[
            {
                "name": "easy_helper", "kind": "lemma", "statement": "x = x",
                "proof_sketch": None, "file": "LeanWorkspace.lean",
                "start_line": 4, "end_line": 5, "dependencies": [],
                "sorry_free": True,
            },
            {
                "name": "hard_lemma", "kind": "lemma", "statement": "x + 0 = x",
                "proof_sketch": "Use a local algebraic helper.",
                "file": "LeanWorkspace.lean", "start_line": 8, "end_line": 9,
                "dependencies": ["easy_helper"], "sorry_free": False,
            },
            {
                "name": "target_theorem", "kind": "theorem",
                "statement": "x + 0 = x", "proof_sketch": None,
                "file": "LeanWorkspace.lean", "start_line": 12, "end_line": 13,
                "dependencies": ["hard_lemma"], "sorry_free": False,
            },
        ],
    )


class RefinementHarness:
    """Controlled tools exposed to the real refiner model."""

    def __init__(self):
        self.workspace = INITIAL_WORKSPACE
        self.tool_calls: list[str] = []
        self.edits: list[dict[str, str]] = []

    def tools(self) -> list:
        harness = self

        @tool
        def read_workspace(workspace_path: str) -> str:
            """Read the current synthetic Lean workspace."""
            harness.tool_calls.append("read_workspace")
            return harness.workspace

        @tool
        def write_workspace(workspace_path: str, content: str) -> str:
            """Replace the synthetic workspace with revised blueprint text."""
            harness.tool_calls.append("write_workspace")
            harness.workspace = content
            harness.edits.append({"old": "<whole file>", "new": content})
            return f"Wrote {len(content)} characters."

        @tool
        def search_replace_workspace(
            relative_path: str, old_string: str, new_string: str
        ) -> str:
            """Apply one exact edit to the synthetic workspace."""
            harness.tool_calls.append("search_replace_workspace")
            if harness.workspace.count(old_string) != 1:
                return "ERROR: old_string must occur exactly once"
            harness.workspace = harness.workspace.replace(old_string, new_string)
            harness.edits.append({"old": old_string, "new": new_string})
            return "Replaced 1 occurrence."

        @tool
        def lean_diagnostic_messages(file_path: str) -> str:
            """Return controlled successful diagnostics for the fixture."""
            harness.tool_calls.append("lean_diagnostic_messages")
            return "No real Lean errors. Expected sorry_using declarations are accepted."

        @tool
        def search_mathlib_docs(query: str, max_results: int = 8) -> str:
            """Return a minimal deterministic Mathlib lookup result."""
            harness.tool_calls.append("search_mathlib_docs")
            return "No additional Mathlib declaration is needed for this fixture."

        return [
            read_workspace,
            write_workspace,
            search_replace_workspace,
            lean_diagnostic_messages,
            search_mathlib_docs,
        ]


def _route(state: State, turns: dict[str, int]) -> str:
    turns["count"] += 1
    message = state.blueprint_refiner_messages[-1]
    return "tools_br" if getattr(message, "tool_calls", None) else END


async def test_blueprint_refiner_model_behavior(monkeypatch: pytest.MonkeyPatch):
    """The real model performs a structural refinement from synthetic feedback."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    harness = RefinementHarness()
    tools = harness.tools()
    turns = {"count": 0}

    # Keep the model-facing environment deterministic: the model is real, but
    # all workspace/diagnostic/search responses come from this fixture.
    monkeypatch.setattr(blueprint_refiner_module, "file_tools", tools)
    monkeypatch.setattr(blueprint_refiner_module, "human_tools", [])
    monkeypatch.setattr(blueprint_refiner_module, "doc_tools", [])
    monkeypatch.setattr(
        blueprint_refiner_module,
        "get_lean_tools",
        lambda: _empty_tools(),
    )

    builder = StateGraph(State, context_schema=Context)
    builder.add_node("blueprint_refiner", blueprint_refiner)
    builder.add_node("tools_br", ToolNode(tools, messages_key="blueprint_refiner_messages"))
    builder.add_edge(START, "blueprint_refiner")
    builder.add_conditional_edges(
        "blueprint_refiner", lambda state: _route(state, turns)
    )
    builder.add_edge("tools_br", "blueprint_refiner")
    graph = builder.compile()

    result = await graph.ainvoke(
        {
            "theorem": "Refine the blueprint for the target theorem.",
            "workspacePATH": "synthetic/LeanWorkspace.lean",
            "project_root": "synthetic",
            "blueprint": _blueprint(),
            "lemma_statuses": {
                "easy_helper": {
                    "name": "easy_helper", "status": "proved", "dependencies": [],
                    "statement": "x = x", "sorry_free": True, "feedback": "",
                },
                "hard_lemma": {
                    "name": "hard_lemma", "status": "unproved",
                    "dependencies": ["easy_helper"], "statement": "x + 0 = x",
                    "sorry_free": False,
                    "feedback": (
                        "PROOF_TOO_HARD: introduce a substantive intermediate helper "
                        "and wire hard_lemma through it."
                    ),
                },
                "target_theorem": {
                    "name": "target_theorem", "status": "unproved",
                    "dependencies": ["hard_lemma"], "statement": "x + 0 = x",
                    "sorry_free": False, "feedback": "",
                },
            },
            "blueprint_refiner_prompt": str(BLUEPRINT_REFINER_PROMPT),
        },
        context={
            "model": MODEL_NAME,
            "max_iterations": 16,
            "max_turns_per_lemma": 8,
        },
        config={"recursion_limit": 40},
    )

    messages = result["blueprint_refiner_messages"]
    assert turns["count"] <= 8
    assert harness.tool_calls, "The model did not use the refinement tools"
    assert "read_workspace" in harness.tool_calls
    assert harness.edits, "The model did not edit the synthetic blueprint"
    assert "theorem target_theorem (x : ℝ) : x + 0 = x" in harness.workspace
    assert "sorry_using" in harness.workspace
    assert "sorry" not in harness.workspace.replace("sorry_using", "")
    assert messages[-1].content or messages[-1].tool_calls


async def _empty_tools() -> list:
    """Async empty-tool provider matching ``get_lean_tools``."""
    return []
