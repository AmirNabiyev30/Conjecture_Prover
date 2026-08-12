"""Real-workspace integration test for blueprint refinement.

This test intentionally edits ``LeanWorkspace.lean``.  Run it directly rather
than as part of the mock refinement integration test suite.

Run with::

    pytest -s tests/integration_tests/test_blueprint_refiner_real_workspace.py -m mcp
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from blueprint import Blueprint  # noqa: E402
from config import MODEL_NAME, PROJECT_ROOT, WORKSPACE_PATH  # noqa: E402
from lean_tools_cache import get_lean_tools  # noqa: E402
from mathlib_doc_tools import doc_tools  # noqa: E402
from nodes.blueprint_refiner import blueprint_refiner  # noqa: E402
from state import Context, State  # noqa: E402
from tools import file_tools, human_tools  # noqa: E402


pytestmark = [pytest.mark.anyio, pytest.mark.mcp, pytest.mark.slow]
load_dotenv()


def _route(state: State, turns: dict[str, int]) -> str:
    """Continue the focused loop only while the refiner has tool calls."""
    turns["count"] += 1
    message = state.blueprint_refiner_messages[-1]
    return "tools_br" if getattr(message, "tool_calls", None) else END


@pytest.mark.mcp
@pytest.mark.slow
async def test_blueprint_refiner_real_workspace():
    """Run the refiner against the actual configured workspace."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    workspace = Path(WORKSPACE_PATH)
    assert workspace.is_file(), f"Workspace file does not exist: {workspace}"
    before = workspace.read_text(encoding="utf-8")

    # Inputs are synthetic; the workspace and tool environment are real.
    refinement_blueprint = Blueprint(
        theorem_name="putnam_2025_a2",
        statement="Putnam 2025 A2 sine quadratic bounds.",
        nodes=[
            {
                "name": "sin_ge_one_over_pi_mul", "kind": "lemma",
                "statement": "The lower sine bound on [0, π].",
                "proof_sketch": "Use symmetry and a lower bound for sine.",
                "file": "LeanWorkspace.lean", "start_line": 1, "end_line": 1,
                "dependencies": [], "sorry_free": True,
            },
            {
                "name": "sin_le_four_over_pi_sq_mul", "kind": "lemma",
                "statement": "The upper sine bound on [0, π].",
                "proof_sketch": "Analyze the quadratic envelope and sine.",
                "file": "LeanWorkspace.lean", "start_line": 1, "end_line": 1,
                "dependencies": ["sin_ge_one_over_pi_mul"], "sorry_free": False,
            },
        ],
    )
    statuses = {
        "sin_ge_one_over_pi_mul": {
            "name": "sin_ge_one_over_pi_mul", "status": "proved",
            "statement": "The lower sine bound on [0, π].",
            "sorry_free": True, "dependencies": [], "feedback": "",
        },
        "sin_le_four_over_pi_sq_mul": {
            "name": "sin_le_four_over_pi_sq_mul", "status": "unproved",
            "statement": "The upper sine bound on [0, π].",
            "sorry_free": False, "dependencies": ["sin_ge_one_over_pi_mul"],
            "feedback": (
                "PROOF_TOO_HARD: introduce substantive helper lemmas for the "
                "interval argument and rewire this lemma through them."
            ),
        },
    }

    lean_tools = await get_lean_tools()
    refinement_tools = file_tools + human_tools + lean_tools + doc_tools
    tool_node = ToolNode(refinement_tools, messages_key="blueprint_refiner_messages")
    turns = {"count": 0}

    builder = StateGraph(State, context_schema=Context)
    builder.add_node("blueprint_refiner", blueprint_refiner)
    builder.add_node("tools_br", tool_node)
    builder.add_edge(START, "blueprint_refiner")
    builder.add_conditional_edges(
        "blueprint_refiner", lambda state: _route(state, turns)
    )
    builder.add_edge("tools_br", "blueprint_refiner")
    graph = builder.compile()

    result = await graph.ainvoke(
        {
            "theorem": (
                "Refine the existing blueprint in the workspace. Make a concrete "
                "structural refinement for the diagnosed hard lemma, then validate it."
            ),
            "workspacePATH": str(workspace),
            "project_root": str(PROJECT_ROOT),
            "blueprint": refinement_blueprint,
            "lemma_statuses": statuses,
        },
        context={
            "model": MODEL_NAME,
            "max_iterations": 16,
            "max_turns_per_lemma": 20,
        },
        config={"recursion_limit": 100},
    )

    after = workspace.read_text(encoding="utf-8")
    messages = result["blueprint_refiner_messages"]
    tool_calls = [
        call["name"]
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]

    print("\n===== REAL WORKSPACE BLUEPRINT REFINEMENT =====")
    print(f"turns={turns['count']}")
    print(f"tool_calls={tool_calls}")
    print(f"workspace_changed={before != after}")
    print(f"final_content={str(getattr(messages[-1], 'content', ''))[:1000]}")
    print("================================================\n")

    assert turns["count"] <= 20, "Refinement exceeded 20 model turns"
    assert "read_workspace" in tool_calls, "Refiner did not read the real workspace"
    assert before != after, "Refiner did not change the real workspace"
    assert after, "Refiner emptied the real workspace"
