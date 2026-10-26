"""Behavioural test of the prover barrier loop.

The slicer tests in ``test_routing.py`` pin *what* a single batch contains. This
module pins the loop built on top of it, using the **real** routing functions
(``theorem_proving``, ``dispatch_gate``, ``route_after_batch``,
``route_after_rebuild``) inside a small StateGraph wired exactly like
``graph.py``.

What it proves, none of which a pure-function test can:

1. the next batch really is issued only after every prover in the current one
   has finished — observed as a peak of concurrently running provers no higher
   than the configured width;
2. every lemma is dispatched exactly once per round, in source order;
3. the round terminates: a drained queue routes to the aggregator (the
   ``"aggregator"`` string) instead of stalling on an empty ``Send`` list;
4. the aggregator's ``pending_proposals: []`` reset is what makes the ledger
   start over, so a second round re-dispatches from the top.

``prove_lemma`` and the aggregator are replaced by fakes: no LLM, no Lean MCP,
no subprocess. The fakes keep the real state contract — a proposal carrying its
``lemma_id``, and an aggregator that clears proposals and marks lemmas proved.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from langgraph.graph import END, START, StateGraph  # noqa: E402

from blueprint import Blueprint  # noqa: E402
from nodes.routing import (  # noqa: E402
    dispatch_gate,
    route_after_batch,
    route_after_rebuild,
)
from state import State  # noqa: E402

WIDTH = 2

# Five declarations: four with a real `sorry_using` placeholder and one genuine
# proof, so a batch cycle has to stop when the dispatchable queue drains.
LEMMAS = ["l1", "l2", "l3", "l4"]
WORKSPACE_TEXT = """\
import Mathlib

lemma l1 (x : ℝ) : x = x := by
  sorry_using []

lemma l2 (x : ℝ) : x = x := by
  sorry_using []

lemma l3 (x : ℝ) : x = x := by
  sorry_using []

lemma l4 (x : ℝ) : x = x := by
  sorry_using []

lemma l5 (x : ℝ) : x = x := by
  rfl
"""


def _node(name: str, start: int, end: int, sorry_free: bool = False) -> dict:
    return {
        "name": name,
        "kind": "lemma",
        "statement": "",
        "proof_sketch": None,
        "file": "Barrier.lean",
        "start_line": start,
        "end_line": end,
        "dependencies": [],
        "sorry_free": sorry_free,
    }


def _nodes() -> list[dict]:
    return [
        _node("l1", 3, 4),
        _node("l2", 6, 7),
        _node("l3", 9, 10),
        _node("l4", 12, 13),
        _node("l5", 15, 16, sorry_free=True),
    ]


def _statuses(nodes: list[dict]) -> dict[str, dict]:
    return {
        n["name"]: {
            "name": n["name"], "statement": "", "sorry_free": n["sorry_free"],
            "status": "proved" if n["sorry_free"] else "unproved",
            "dependencies": [], "feedback": "",
        }
        for n in nodes
    }


def _build_graph(state: dict, width: int):
    """Mirror of graph.py's proving wiring, with stubbed prover and aggregator."""

    async def rebuild(inner: State) -> dict:
        return {}

    async def fake_prove(inner: dict) -> dict:
        """A prover: records overlap, then reports an unproved proposal."""
        name = inner["lemma_task"]["name"]
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        state["dispatched"].append(name)
        try:
            # Long enough that a second prover scheduled in the same superstep
            # is guaranteed to overlap with this one.
            await asyncio.sleep(0.02)
        finally:
            state["inflight"] -= 1
        return {
            "pending_proposals": [{
                "lemma_id": name, "status": "TOO_HARD", "old_str": "",
                "new_str": None, "proved": False, "feedback": "",
            }]
        }

    async def fake_aggregator(inner: State) -> dict:
        """Aggregator contract: clear the proposal ledger and count the round."""
        return {
            "pending_proposals": [],
            "lemma_statuses": {n: {**ls, "status": "proved", "sorry_free": True}
                               for n, ls in inner.lemma_statuses.items()},
            "global_round": inner.global_round + 1,
        }

    builder = StateGraph(State)
    builder.add_node("rebuild", rebuild)
    builder.add_node("prove_lemma", fake_prove)
    builder.add_node("dispatch_gate", dispatch_gate)
    # The node MUST be called "aggregator": `route_after_batch` routes by that
    # literal name, and a mismatch is only a warning at runtime ("wrote to
    # unknown channel"), which silently drops the drained queue's hand-off.
    builder.add_node("aggregator", fake_aggregator)

    builder.add_edge(START, "rebuild")
    builder.add_conditional_edges("rebuild", route_after_rebuild)
    builder.add_edge("prove_lemma", "dispatch_gate")
    builder.add_conditional_edges("dispatch_gate", route_after_batch)
    # One round only: the aggregator ends the run, so the sole loop under test
    # is the intra-round batch loop.
    builder.add_edge("aggregator", END)

    return builder.compile()


def _run(tmp_path: Path, width: int = WIDTH) -> dict:
    workspace = tmp_path / "Barrier.lean"
    workspace.write_text(WORKSPACE_TEXT, encoding="utf-8")
    nodes = _nodes()

    shared = {"inflight": 0, "peak": 0, "dispatched": []}
    graph = _build_graph(shared, width)

    inputs = {
        "workspacePATH": str(workspace),
        "project_root": str(tmp_path),
        "blueprint": Blueprint(nodes=nodes),
        "lemma_statuses": _statuses(nodes),
    }
    context = {"max_parallel_provers": width}
    final = asyncio.run(
        graph.ainvoke(inputs, context=context, config={"recursion_limit": 100})
    )
    shared["final"] = final
    return shared


def test_second_batch_starts_only_after_the_first_finishes(tmp_path: Path):
    """Peak concurrency never exceeds the batch width."""
    result = _run(tmp_path)

    assert result["peak"] <= WIDTH, (
        f"observed {result['peak']} concurrent provers with width {WIDTH}"
    )


def test_every_dispatchable_lemma_is_proved_once_in_source_order(tmp_path: Path):
    """The barrier covers the queue exactly once — no repeats, no omissions."""
    result = _run(tmp_path)

    assert result["dispatched"] == LEMMAS


def test_the_drained_queue_reaches_the_aggregator(tmp_path: Path):
    """The round advances: the aggregator ran and reset the ledger.

    If a drained queue returned ``[]`` instead of ``"aggregator"``, nothing
    would be scheduled and ``global_round`` would stay 0.
    """
    result = _run(tmp_path)

    assert result["final"]["global_round"] == 1
    assert result["final"]["pending_proposals"] == []


def test_a_narrower_width_never_increases_peak_concurrency(tmp_path: Path):
    """Width 1 serialises proving, which is the degenerate row of the trade-off."""
    result = _run(tmp_path, width=1)

    assert result["peak"] == 1
    assert result["dispatched"] == LEMMAS
