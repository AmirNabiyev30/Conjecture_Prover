"""
Integration test for prove_lemma — uses a minimal StateGraph with real MCP + LLM.

Marked with @pytest.mark.mcp and @pytest.mark.slow so it can be skipped in CI.
Run with:  pytest tests/integration_tests/test_prove_lemma.py -v -m "mcp"
"""

import sys
from pathlib import Path

# The agent package uses bare imports (e.g. `from config import ...`),
# which require `src/agent` to be on sys.path.
_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

import pytest
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from state import State, Context
from nodes.prove_lemma import prove_lemma

pytestmark = pytest.mark.anyio

# Load API keys from .env (DEEPSEEK_API_KEY)
load_dotenv()


SIN_LOWER_BOUND_TASK = {
    "name": "sin_lower_bound",
    "kind": "lemma",
    "statement": "For all x ∈ [0,π], (1/π)·x·(π-x) ≤ sin x",
    "proof_sketch": (
        "Let f(x) = (1/π)·x·(π-x). Define g(x) = sin x - f(x). "
        "Note g(0) = g(π) = 0. Compute g'(x) = cos x - (π-2x)/π. "
        "Show g' has exactly one zero in (0,π) at x = π/2, where g is positive. "
        "Conclude g(x) ≥ 0 on [0,π]."
    ),
    "file": "LeanWorkspace.lean",
    "start_line": 27,
    "end_line": 35,
    "dependencies": [],
}

SIN_LOWER_BOUND_DECL = (
    "lemma sin_lower_bound (x : ℝ) (hx : x ∈ Icc (0 : ℝ) π) : "
    "(1 / π) * x * (π - x) ≤ sin x := by\n  sorry_using []"
)


@pytest.mark.mcp
@pytest.mark.slow
async def test_prove_lemma_mini_graph_sin_lower_bound():
    """Build a minimal graph (prove_lemma → END) and attempt to prove
    sin_lower_bound using real MCP and LLM.

    This test validates:
    - The LangGraph wiring for prove_lemma works correctly
    - The node receives state from the graph and returns pending_proposals
    - The ProofProposal shape is correct
    """
    builder = StateGraph(State, context_schema=Context)
    builder.add_node("prove_lemma", prove_lemma)
    builder.add_edge(START, "prove_lemma")
    builder.add_edge("prove_lemma", END)

    graph = builder.compile()

    print(f"\n{'─' * 70}")
    print(f"🧪 INTEGRATION TEST: prove_lemma mini-graph")
    print(f"   Lemma: {SIN_LOWER_BOUND_TASK['name']}")
    print(f"   Kind:  {SIN_LOWER_BOUND_TASK['kind']}")
    print(f"   Dependencies: {SIN_LOWER_BOUND_TASK['dependencies'] or 'none'}")
    print(f"   Proof sketch: {SIN_LOWER_BOUND_TASK['proof_sketch'][:120]}...")
    print(f"   Model: deepseek-chat  |  Max turns: 20")
    print(f"{'─' * 70}\n")

    result = await graph.ainvoke(
        {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
        },
        context={"max_turns_per_lemma": 20, "model": "deepseek-chat"},
    )

    # Assert the graph produced output
    assert result is not None
    assert "pending_proposals" in result

    proposals = result["pending_proposals"]
    assert len(proposals) >= 1, "Expected at least one ProofProposal"

    p = proposals[0]

    print(f"\n{'─' * 70}")
    print(f"📋 RESULT for '{p['lemma_id']}':")
    print(f"   Proved:  {p['proved']}")
    if p["proved"]:
        print(f"   ✅ Proof accepted!")
        print(f"\n   ── Proof ──")
        for line in (p["new_str"] or "").split("\n"):
            print(f"   │ {line}")
        print(f"   ────────────")
    else:
        print(f"   ❌ Proof failed")
        print(f"   Feedback: {p['feedback']}")
    print(f"{'─' * 70}\n")

    # Verify the ProofProposal shape
    assert "lemma_id" in p
    assert p["lemma_id"] == "sin_lower_bound"
    assert "status" in p
    assert p["status"] in ("PROVED", "TOO_HARD", "FAILED")
    assert "old_str" in p
    assert p["old_str"] == SIN_LOWER_BOUND_DECL
    assert "new_str" in p  # may be None if failed
    assert "proved" in p
    assert isinstance(p["proved"], bool)
    assert "feedback" in p
    assert isinstance(p["feedback"], str)

    print("   ✅ ProofProposal shape validated")
