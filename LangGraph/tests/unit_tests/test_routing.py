"""Unit tests for the routing helpers in ``nodes/routing.py``.

``theorem_proving`` — the dispatcher — is the gate between blueprint parsing and
the parallel prove_lemma nodes. The generated blueprint JSON does not encode
whether a declaration still holds a ``sorry_using`` placeholder (there is no
``sorryFree`` field), so the dispatcher inspects the declaration text spliced
from the file and only Sends lemmas whose body actually contains ``sorry_using``.
Definitions with real bodies, bare ``sorry`` declarations, real proofs, and
out-of-range splices must be skipped.

``route_after_aggregator`` decides whether the refine loop continues; its round
budget is a per-run setting read from the Runtime context.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langgraph.graph import END

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import Blueprint  # noqa: E402
from config import MAX_REFINEMENT_ROUNDS  # noqa: E402
from nodes.routing import route_after_aggregator, theorem_proving  # noqa: E402
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


@pytest.fixture()
def workspace_file(tmp_path: Path):
    p = tmp_path / "Test.lean"
    p.write_text(WORKSPACE_TEXT, encoding="utf-8")
    return str(p)


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
