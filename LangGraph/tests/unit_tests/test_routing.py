"""Unit tests for the theorem_proving dispatcher's `sorry_using` guard.

The dispatcher (``nodes/routing.py::theorem_proving``) is the gate between
blueprint parsing and the parallel prove_lemma nodes. The generated blueprint
JSON does not encode whether a declaration still holds a ``sorry_using``
placeholder (there is no ``sorryFree`` field), so the dispatcher inspects the
declaration text spliced from the file and only Sends lemmas whose body
actually contains ``sorry_using``. Definitions with real bodies, bare ``sorry``
declarations, real proofs, and out-of-range splices must be skipped.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import Blueprint  # noqa: E402
from nodes.routing import theorem_proving  # noqa: E402
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
