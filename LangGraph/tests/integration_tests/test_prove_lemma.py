"""
Integration test for prove_lemma — uses a minimal StateGraph with real MCP + LLM.

Marked with @pytest.mark.mcp and @pytest.mark.slow so it can be skipped in CI.
Run with:  pytest tests/integration_tests/test_prove_lemma.py -v -m "mcp"
"""

import asyncio
import os
import sys
from pathlib import Path

# The agent package uses bare imports (e.g. `from config import ...`),
# which require `src/agent` to be on sys.path.
_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

import pytest
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.runtime import Runtime

from state import State, Context
from nodes.prove_lemma import prove_lemma
from config import MODEL_NAME

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

# ── Easy / too-hard / wrong-statement fixtures ──────────────────────────────

EASY_LEMMA_TASK = {
    "name": "two_plus_two",
    "kind": "lemma",
    "statement": "2 + 2 = 4",
    "proof_sketch": "norm_num",
    "file": "LeanWorkspace.lean",
    "start_line": 1,
    "end_line": 3,
    "dependencies": [],
}

EASY_LEMMA_DECL = "lemma two_plus_two : 2 + 2 = 4 := by\n  sorry_using []"

TOO_HARD_LEMMA_TASK = {
    "name": "flt_n3",
    "kind": "lemma",
    "statement": "There do not exist nonzero natural numbers a, b, c with a^3 + b^3 = c^3.",
    "proof_sketch": None,
    "file": "LeanWorkspace.lean",
    "start_line": 1,
    "end_line": 3,
    "dependencies": [],
}

TOO_HARD_LEMMA_DECL = (
    "lemma flt_n3 : ¬ ∃ a b c : ℕ, a ≠ 0 ∧ b ≠ 0 ∧ c ≠ 0 ∧ "
    "a^3 + b^3 = c^3 := by\n  sorry_using []"
)

WRONG_STATEMENT_TASK = {
    "name": "two_eq_three",
    "kind": "lemma",
    "statement": "2 = 3",
    "proof_sketch": None,
    "file": "LeanWorkspace.lean",
    "start_line": 1,
    "end_line": 3,
    "dependencies": [],
}

WRONG_STATEMENT_DECL = "lemma two_eq_three : 2 = 3 := by\n  sorry_using []"


async def _run_prove_lemma(task: dict, decl_text: str, max_turns: int = 20) -> dict:
    """Invoke prove_lemma directly (no graph) with a synthetic runtime context."""
    runtime = Runtime(context={"max_turns_per_lemma": max_turns, "model": MODEL_NAME})
    return await prove_lemma({"lemma_task": task, "lemma_decl_text": decl_text}, runtime)


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
    print(f"   Model: {MODEL_NAME}  |  Max turns: 20")
    print(f"{'─' * 70}\n")

    result = await graph.ainvoke(
        {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
        },
        context={"max_turns_per_lemma": 20, "model": MODEL_NAME},
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
    assert p["status"] in ("PROVED", "TOO_HARD", "STATEMENT_WRONG")
    assert "old_str" in p
    assert p["old_str"] == SIN_LOWER_BOUND_DECL
    assert "new_str" in p  # may be None if failed
    assert "proved" in p
    assert isinstance(p["proved"], bool)
    assert "feedback" in p
    assert isinstance(p["feedback"], str)

    print("   ✅ ProofProposal shape validated")


@pytest.mark.mcp
@pytest.mark.slow
async def test_prove_lemma_solves_easy_lemma():
    """prove_lemma should solve a trivial lemma and return a PROVED (Solved) proposal."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    result = await _run_prove_lemma(EASY_LEMMA_TASK, EASY_LEMMA_DECL, max_turns=10)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1, f"Expected 1 proposal, got {len(proposals)}"

    p = proposals[0]
    print(f"\n🧪 easy lemma '{p['lemma_id']}' → status={p['status']} proved={p['proved']}")

    assert p["status"] == "PROVED", f"Expected PROVED, got {p['status']}:\n{p['feedback']}"
    assert p["proved"] is True
    assert p["lemma_id"] == "two_plus_two"
    assert p["old_str"] == EASY_LEMMA_DECL
    assert p["new_str"] is not None
    assert "sorry" not in p["new_str"].lower(), f"new_str still contains 'sorry':\n{p['new_str']}"
    assert "axiom" not in p["new_str"].lower()
    assert isinstance(p["feedback"], str) and p["feedback"]


@pytest.mark.mcp
@pytest.mark.slow
async def test_prove_lemma_three_outcomes():
    """Three lemma tasks → one solved (PROVED), one too hard (TOO_HARD),
    one false statement (STATEMENT_WRONG). Each node must return its proper output."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    solved, too_hard, wrong = await asyncio.gather(
        _run_prove_lemma(EASY_LEMMA_TASK, EASY_LEMMA_DECL, max_turns=10),
        _run_prove_lemma(TOO_HARD_LEMMA_TASK, TOO_HARD_LEMMA_DECL, max_turns=4),
        _run_prove_lemma(WRONG_STATEMENT_TASK, WRONG_STATEMENT_DECL, max_turns=10),
    )

    solved_p = solved["pending_proposals"][0]
    too_hard_p = too_hard["pending_proposals"][0]
    wrong_p = wrong["pending_proposals"][0]

    print(f"\n🧪 outcomes: solved={solved_p['status']} | "
          f"too_hard={too_hard_p['status']} | wrong={wrong_p['status']}")

    # solved
    assert solved_p["status"] == "PROVED", (
        f"Expected PROVED, got {solved_p['status']}:\n{solved_p['feedback']}"
    )
    assert solved_p["proved"] is True
    assert solved_p["lemma_id"] == "two_plus_two"
    assert solved_p["new_str"] is not None
    assert "sorry" not in solved_p["new_str"].lower()

    # too hard
    assert too_hard_p["status"] == "TOO_HARD", (
        f"Expected TOO_HARD, got {too_hard_p['status']}"
    )
    assert too_hard_p["proved"] is False
    assert too_hard_p["lemma_id"] == "flt_n3"
    assert too_hard_p["new_str"] is None
    assert isinstance(too_hard_p["feedback"], str) and too_hard_p["feedback"]

    # statement wrong
    assert wrong_p["status"] == "STATEMENT_WRONG", (
        f"Expected STATEMENT_WRONG, got {wrong_p['status']}:\n{wrong_p['feedback']}"
    )
    assert wrong_p["proved"] is False
    assert wrong_p["lemma_id"] == "two_eq_three"
    assert wrong_p["new_str"] is None
    assert isinstance(wrong_p["feedback"], str) and wrong_p["feedback"]
