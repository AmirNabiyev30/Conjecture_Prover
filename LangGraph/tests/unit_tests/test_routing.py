"""Unit tests for the routing helpers in ``nodes/routing.py``.

``theorem_proving`` is the **batch slicer** — the gate between blueprint parsing
and the prover fan-out. It returns at most ``max_parallel_provers`` Sends, and
the batch loop is driven by the attempted-ledger it derives from
``pending_proposals``. These tests pin four things the barrier depends on:

1. only declarations that still hold a ``sorry_using`` placeholder are Sent
   (the blueprint JSON has no ``sorryFree`` field, so the real source text is
   the only authority);
2. a pass never exceeds the configured batch width;
3. lemmas already dispatched this round are not dispatched again;
4. a drained queue routes to the aggregator as a *string*, because an empty
   ``Send`` list schedules nothing and would silently skip the round increment.

``route_after_aggregator`` decides whether the refine loop continues; its round
budget is a per-run setting read from the Runtime context.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langgraph.graph import END

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import Blueprint  # noqa: E402
from config import MAX_PARALLEL_PROVERS, MAX_REFINEMENT_ROUNDS  # noqa: E402
from nodes.routing import (  # noqa: E402
    attempted_lemma_ids,
    dispatch_gate,
    next_batch_or_aggregate,
    route_after_aggregator,
    route_after_batch,
    route_after_rebuild,
    theorem_proving,
)
from state import State  # noqa: E402

# A file with one valid `sorry_using` placeholder and several things that must
# NOT be dispatched: a def with a real body, a bare `sorry`, and a real proof.
WORKSPACE_TEXT = """\
import Mathlib

lemma has_placeholder (x : ℝ) : x = x := by
  sorry_using []

def helper : Nat :=
  42

lemma bare_sorry (x : ℝ) : x = x := by
  sorry

lemma real_proof (x : ℝ) : x = x := by
  rfl
"""

# Four dispatchable placeholders plus one real proof, so batch slicing and the
# attempted-ledger have more candidates than a single batch holds.
BATCH_WORKSPACE_TEXT = """\
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


def _node(name: str, start: int, end: int) -> dict:
    return {
        "name": name,
        "kind": "lemma" if name != "helper" else "definition",
        "statement": "",
        "proof_sketch": None,
        "file": "Test.lean",
        "start_line": start,
        "end_line": end,
        "dependencies": [],
        "sorry_free": False,
    }


def _make_state(workspace_path: str, node_list: list[dict], statuses: dict[str, dict]) -> State:
    return State(
        workspacePATH=workspace_path,
        project_root=str(Path(workspace_path).parent),
        blueprint=Blueprint(nodes=node_list),
        lemma_statuses=statuses,
    )


def _unproved(name: str) -> dict:
    return {"name": name, "statement": "", "sorry_free": False,
            "status": "unproved", "dependencies": [], "feedback": ""}


def _proposal(lemma_id: str) -> dict:
    """A minimal prove_lemma result; only `lemma_id` matters to the ledger."""
    return {
        "lemma_id": lemma_id, "status": "TOO_HARD", "old_str": "",
        "new_str": None, "proved": False, "feedback": "",
    }


@pytest.fixture()
def workspace_file(tmp_path: Path):
    p = tmp_path / "Test.lean"
    p.write_text(WORKSPACE_TEXT, encoding="utf-8")
    return str(p)


@pytest.fixture()
def batch_workspace(tmp_path: Path):
    p = tmp_path / "Batch.lean"
    p.write_text(BATCH_WORKSPACE_TEXT, encoding="utf-8")
    return str(p)


def _batch_nodes() -> list[dict]:
    return [
        _node("l1", 3, 4),
        _node("l2", 6, 7),
        _node("l3", 9, 10),
        _node("l4", 12, 13),
        _node("l5", 15, 16),
    ]


def _batch_state(batch_workspace: str, attempted: list[str] | None = None) -> State:
    nodes = _batch_nodes()
    state = _make_state(
        batch_workspace, nodes, {n["name"]: _unproved(n["name"]) for n in nodes}
    )
    state.pending_proposals = [_proposal(name) for name in (attempted or [])]
    return state


# ── candidate filtering ──────────────────────────────────────────────────────

def test_dispatch_only_sends_sorry_using_lemmas(workspace_file: str):
    """Out of four unproved declarations, only the one with `sorry_using` is Sent."""
    nodes = [
        _node("has_placeholder", 3, 4),
        _node("helper", 6, 7),
        _node("bare_sorry", 9, 10),
        _node("real_proof", 12, 13),
    ]
    statuses = {n["name"]: _unproved(n["name"]) for n in nodes}
    state = _make_state(workspace_file, nodes, statuses)

    sends = theorem_proving(state)

    dispatched = [s.arg["lemma_task"]["name"] for s in sends]
    assert dispatched == ["has_placeholder"]


def test_dispatch_skips_out_of_range_splice(workspace_file: str, tmp_path: Path):
    """A node whose line range misses the file content is skipped (no sorry_using)."""
    nodes = [
        _node("has_placeholder", 3, 4),
        _node("ghost", 100, 101),  # beyond EOF → empty splice
    ]
    statuses = {n["name"]: _unproved(n["name"]) for n in nodes}
    state = _make_state(workspace_file, nodes, statuses)

    sends = theorem_proving(state)

    dispatched = [s.arg["lemma_task"]["name"] for s in sends]
    assert dispatched == ["has_placeholder"]


def test_dispatch_empty_when_no_unproved(workspace_file: str):
    """When nothing is unproved, no Sends are produced."""
    nodes = [_node("has_placeholder", 3, 4)]
    statuses = {
        "has_placeholder": {"name": "has_placeholder", "statement": "",
                            "sorry_free": True, "status": "proved",
                            "dependencies": [], "feedback": ""}
    }
    state = _make_state(workspace_file, nodes, statuses)

    assert theorem_proving(state) == []


# ── batch width (the barrier) ────────────────────────────────────────────────

def test_batch_never_exceeds_the_configured_width(batch_workspace: str):
    """Four dispatchable lemmas, width 2 → exactly the first two are Sent."""
    state = _batch_state(batch_workspace)

    sends = theorem_proving(state, _runtime(max_parallel_provers=2))

    assert [s.arg["lemma_task"]["name"] for s in sends] == ["l1", "l2"]


def test_batch_falls_back_to_the_config_width_without_a_runtime(batch_workspace: str):
    """A hand-built call (no Runtime) uses config.MAX_PARALLEL_PROVERS, not no cap."""
    state = _batch_state(batch_workspace)

    sends = theorem_proving(state)

    assert len(sends) == MAX_PARALLEL_PROVERS
    assert [s.arg["lemma_task"]["name"] for s in sends] == ["l1", "l2", "l3"]


def test_batch_is_smaller_than_the_width_when_candidates_run_out(batch_workspace: str):
    """With only one dispatchable lemma left, the batch is one task (no padding)."""
    state = _batch_state(batch_workspace, attempted=["l1", "l2", "l3"])

    sends = theorem_proving(state, _runtime(max_parallel_provers=3))

    assert [s.arg["lemma_task"]["name"] for s in sends] == ["l4"]


# ── attempted ledger ─────────────────────────────────────────────────────────

def test_attempted_lemma_ids_ignores_blank_ids():
    state = State()
    state.pending_proposals = [_proposal("a"), _proposal(""), _proposal("b")]

    assert attempted_lemma_ids(state) == {"a", "b"}


def test_dispatch_moves_to_the_next_batch_after_attempts(batch_workspace: str):
    """The ledger is what advances the loop: batch 1 done → batch 2 is different."""
    state = _batch_state(batch_workspace, attempted=["l1", "l2"])

    sends = theorem_proving(state, _runtime(max_parallel_provers=2))

    assert [s.arg["lemma_task"]["name"] for s in sends] == ["l3", "l4"]


def test_dispatch_returns_empty_when_every_candidate_is_attempted(batch_workspace: str):
    """l5 is unproved but has a real proof, so the round's queue is genuinely drained."""
    state = _batch_state(batch_workspace, attempted=["l1", "l2", "l3", "l4"])

    assert theorem_proving(state, _runtime(max_parallel_provers=2)) == []


def test_ledger_reset_by_the_aggregator_makes_lemmas_dispatchable_again(batch_workspace: str):
    """The aggregator resets pending_proposals to [], which resets the batch cursor.

    That reset is the only reason a new round starts from the whole candidate
    list again, so it is pinned here rather than left implicit.
    """
    state = _batch_state(batch_workspace, attempted=["l1", "l2", "l3", "l4"])
    assert theorem_proving(state, _runtime(max_parallel_provers=2)) == []

    state.pending_proposals = []  # what every aggregator return path writes

    sends = theorem_proving(state, _runtime(max_parallel_provers=2))
    assert [s.arg["lemma_task"]["name"] for s in sends] == ["l1", "l2"]


# ── the dispatch decision (gate) ─────────────────────────────────────────────

def test_next_batch_or_aggregate_returns_the_next_batch(batch_workspace: str):
    state = _batch_state(batch_workspace)

    result = next_batch_or_aggregate(state, _runtime(max_parallel_provers=2))

    assert isinstance(result, list)
    assert [s.arg["lemma_task"]["name"] for s in result] == ["l1", "l2"]


def test_drained_queue_routes_to_the_aggregator_as_a_string(batch_workspace: str):
    """Regression guard: an empty Send list schedules nothing.

    The pre-batching dispatcher logged "routing to aggregator" and returned [] —
    an empty fan-out, so the aggregator never ran and the round never advanced.
    A drained queue must therefore produce the routing STRING.
    """
    state = _batch_state(batch_workspace, attempted=["l1", "l2", "l3", "l4"])

    assert next_batch_or_aggregate(state, _runtime(max_parallel_provers=2)) == "aggregator"


def test_route_after_batch_forwards_the_shared_decision(batch_workspace: str):
    state = _batch_state(batch_workspace, attempted=["l1", "l2", "l3", "l4"])

    assert route_after_batch(state, _runtime(max_parallel_provers=2)) == "aggregator"


def test_route_after_rebuild_forwards_the_shared_decision(batch_workspace: str):
    """First batch of a round uses the same decision as every later batch."""
    state = _batch_state(batch_workspace)

    result = route_after_rebuild(state, _runtime(max_parallel_provers=2))

    assert isinstance(result, list)
    assert [s.arg["lemma_task"]["name"] for s in result] == ["l1", "l2"]


def test_dispatch_gate_is_a_no_op_join(batch_workspace: str):
    """The gate must not touch state, or it would clear the batching ledger."""
    state = _batch_state(batch_workspace, attempted=["l1"])

    assert asyncio.run(dispatch_gate(state)) == {}


# ── route_after_aggregator ───────────────────────────────────────────────────
# The round budget is a per-run setting delivered through the Runtime context,
# so these pin both the context read and the config fallback.

def _runtime(**context) -> MagicMock:
    """A minimal Runtime carrying only the per-run settings under test."""
    runtime = MagicMock()
    runtime.context = context
    return runtime


def _status(name: str, status: str) -> dict:
    return {"name": name, "statement": "", "sorry_free": status == "proved",
            "status": status, "dependencies": [], "feedback": ""}


def test_route_after_aggregator_continues_when_rounds_remain():
    state = State(global_round=1, lemma_statuses={"a": _status("a", "unproved")})
    assert route_after_aggregator(state, _runtime(max_refinement_rounds=5)) == "blueprint_refiner"


def test_route_after_aggregator_stops_at_the_context_budget():
    """A zero budget ends the run immediately, even with unproved lemmas.

    This is what lets the e2e test cap itself to a single aggregator round, and
    it is only expressible because the budget comes from the context.
    """
    state = State(global_round=0, lemma_statuses={"a": _status("a", "unproved")})
    assert route_after_aggregator(state, _runtime(max_refinement_rounds=0)) == END


def test_route_after_aggregator_stops_when_every_lemma_is_proved():
    state = State(global_round=1, lemma_statuses={"a": _status("a", "proved")})
    assert route_after_aggregator(state, _runtime(max_refinement_rounds=5)) == END


def test_route_after_aggregator_falls_back_to_the_config_default():
    """A hand-built context without the budget uses config.MAX_REFINEMENT_ROUNDS."""
    assert MAX_REFINEMENT_ROUNDS > 0, "this test assumes a non-zero default"
    state = State(global_round=0, lemma_statuses={"a": _status("a", "unproved")})
    assert route_after_aggregator(state, _runtime()) == "blueprint_refiner"
