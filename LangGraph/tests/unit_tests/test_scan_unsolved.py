"""Unit tests for scan_unsolved() — how many nodes were left unsolved after the
workflow ran to its budget.

Behavior contract (TDD spec):
- scan_unsolved() counts EVERY node with status == "unproved", regardless of
  kind (an unproved definition is counted the same as an unproved lemma).
- Returns an UnsolvedSummary(total, proved, unproved, unsolved).
- When lemma_statuses is None, statuses are derived fresh from the blueprint via
  derive_lemma_statuses().
- total = len(blueprint.nodes) when a blueprint is given, else len(lemma_statuses).
- Empty blueprint / empty statuses -> zeros and an empty unsolved list.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import (
    Blueprint,
    UnsolvedSummary,
    derive_lemma_statuses,
    derive_lemma_statuses_from_source,
    derive_lemma_statuses_from_workspace,
    scan_unsolved,
    scan_unsolved_from_file,
)


def _node(name, kind="lemma", sorry_free=False, deps=()):
    """A minimal LemmaTask dict (fields consumed by derive_lemma_statuses)."""
    return {
        "name": name,
        "kind": kind,
        "statement": "P",
        "proof_sketch": None,
        "file": "ConjectureProver.lean",
        "start_line": 1,
        "end_line": 3,
        "dependencies": list(deps),
        "sorry_free": sorry_free,
    }


def _bp(nodes):
    return Blueprint(nodes=list(nodes))


# ── basic counting ────────────────────────────────────────────────────────────


def test_counts_mixed_proved_and_unproved():
    bp = _bp([
        _node("proved_lemma", sorry_free=True),
        _node("unproved_theorem", kind="theorem"),
        _node("unproved_def", kind="definition"),
    ])
    statuses = derive_lemma_statuses(bp)
    s = scan_unsolved(bp, statuses)

    assert isinstance(s, UnsolvedSummary)
    assert s.total == 3
    assert s.proved == 1
    assert s.unproved == 2
    assert set(s.unsolved) == {"unproved_theorem", "unproved_def"}


def test_kind_agnostic_definitions_are_counted():
    """An unproved definition counts the same as an unproved lemma."""
    bp = _bp([_node("only_def", kind="definition")])
    s = scan_unsolved(bp, derive_lemma_statuses(bp))

    assert s.total == 1
    assert s.unproved == 1
    assert s.unsolved == ["only_def"]


def test_all_proved_returns_zero_unproved():
    bp = _bp([
        _node("a", sorry_free=True),
        _node("b", sorry_free=True),
    ])
    s = scan_unsolved(bp, derive_lemma_statuses(bp))

    assert s.total == 2
    assert s.proved == 2
    assert s.unproved == 0
    assert s.unsolved == []


def test_all_unproved_equals_total():
    bp = _bp([_node("a"), _node("b"), _node("c")])
    s = scan_unsolved(bp, derive_lemma_statuses(bp))

    assert s.unproved == 3
    assert s.total == 3
    assert len(s.unsolved) == 3


# ── edge cases ────────────────────────────────────────────────────────────────


def test_empty_blueprint():
    bp = _bp([])
    s = scan_unsolved(bp, derive_lemma_statuses(bp))

    assert s.total == 0
    assert s.proved == 0
    assert s.unproved == 0
    assert s.unsolved == []


def test_empty_statuses_without_blueprint():
    s = scan_unsolved(lemma_statuses={})

    assert s.total == 0
    assert s.unproved == 0
    assert s.unsolved == []


# ── status derivation paths ───────────────────────────────────────────────────


def test_derives_statuses_from_blueprint_when_none_passed():
    bp = _bp([
        _node("proved_lemma", sorry_free=True),
        _node("unproved_lemma"),
    ])
    s = scan_unsolved(bp)  # no lemma_statuses

    assert s.total == 2
    assert s.proved == 1
    assert s.unproved == 1
    assert s.unsolved == ["unproved_lemma"]


def test_blueprint_none_with_statuses_total_from_statuses():
    statuses = {
        "a": {"name": "a", "statement": "P", "sorry_free": True, "status": "proved",
              "dependencies": [], "feedback": ""},
        "b": {"name": "b", "statement": "P", "sorry_free": False, "status": "unproved",
              "dependencies": [], "feedback": "TOO_HARD"},
    }
    s = scan_unsolved(lemma_statuses=statuses)

    assert s.total == 2
    assert s.proved == 1
    assert s.unproved == 1
    assert s.unsolved == ["b"]


def test_both_none_returns_empty_summary():
    s = scan_unsolved()

    assert s.total == 0
    assert s.unproved == 0
    assert s.unsolved == []


# ── summary shape ─────────────────────────────────────────────────────────────


def test_unsolved_preserves_statuses_order():
    bp = _bp([_node("a"), _node("b"), _node("c")])
    statuses = derive_lemma_statuses(bp)
    statuses["a"]["status"] = "proved"
    s = scan_unsolved(bp, statuses)

    assert s.unsolved == ["b", "c"]


# ── source-text scan path ─────────────────────────────────────────────────────
#
# The LeanArchitect blueprint JSON emits no `sorryFree` field, so statuses must
# be derived from the actual .lean declaration bodies. Nodes below use
# sorry_free=False (mimicking the missing-JSON field) so that the JSON-derived
# status is "unproved" and the source-text derivation must override it.

_SAMPLE_SOURCE = """\
@[blueprint (statement := /-- D -/)]
def d : Nat := 42

@[blueprint (statement := /-- L -/)]
lemma l : True := by
  sorry_using []

@[blueprint (statement := /-- T -/)]
theorem t : True := by
  trivial

@[blueprint (statement := /-- A -/)]
lemma a : False := by
  admit
"""


def _sample_nodes():
    """Nodes whose start/end lines match _SAMPLE_SOURCE."""
    return [
        {"name": "d", "kind": "definition", "statement": "D", "proof_sketch": None,
         "file": "ConjectureProver.lean", "start_line": 1, "end_line": 2,
         "dependencies": [], "sorry_free": False},
        {"name": "l", "kind": "lemma", "statement": "L", "proof_sketch": None,
         "file": "ConjectureProver.lean", "start_line": 4, "end_line": 6,
         "dependencies": [], "sorry_free": False},
        {"name": "t", "kind": "theorem", "statement": "T", "proof_sketch": None,
         "file": "ConjectureProver.lean", "start_line": 8, "end_line": 10,
         "dependencies": [], "sorry_free": False},
        {"name": "a", "kind": "lemma", "statement": "A", "proof_sketch": None,
         "file": "ConjectureProver.lean", "start_line": 12, "end_line": 14,
         "dependencies": [], "sorry_free": False},
    ]


def test_scan_unsolved_from_file_overrides_missing_sorry_free():
    bp = _bp(_sample_nodes())
    s = scan_unsolved_from_file(bp, _SAMPLE_SOURCE)

    assert s.total == 4
    assert s.proved == 2        # d (real def body), t (real proof)
    assert s.unproved == 2      # l (sorry_using), a (admit)
    assert s.unsolved == ["l", "a"]


def test_derive_statuses_from_source_marks_sorry_and_admit_unproved():
    bp = _bp(_sample_nodes())
    statuses = derive_lemma_statuses_from_source(bp, _SAMPLE_SOURCE)

    assert statuses["d"]["status"] == "proved"
    assert statuses["d"]["sorry_free"] is True
    assert statuses["l"]["status"] == "unproved"
    assert statuses["l"]["sorry_free"] is False
    assert statuses["t"]["status"] == "proved"
    assert statuses["t"]["sorry_free"] is True
    assert statuses["a"]["status"] == "unproved"
    assert statuses["a"]["sorry_free"] is False


def test_derive_from_source_falls_back_when_no_line_range():
    node = _node("orphan", sorry_free=True)
    node["start_line"] = 0
    node["end_line"] = 0
    bp = _bp([node])
    statuses = derive_lemma_statuses_from_source(bp, _SAMPLE_SOURCE)

    # No splice possible -> keep the JSON-derived status ("proved" since sorry_free=True)
    assert statuses["orphan"]["status"] == "proved"


def test_derive_statuses_from_workspace_reads_file(tmp_path):
    """derive_lemma_statuses_from_workspace must read the .lean file and mark
    real proofs proved (this is what lets the round loop terminate)."""
    ws = tmp_path / "ConjectureProver.lean"
    ws.write_text(_SAMPLE_SOURCE, encoding="utf-8")
    bp = _bp(_sample_nodes())

    statuses = derive_lemma_statuses_from_workspace(bp, ws)

    assert statuses["d"]["status"] == "proved"
    assert statuses["t"]["status"] == "proved"
    assert statuses["l"]["status"] == "unproved"
    assert statuses["a"]["status"] == "unproved"


def test_derive_statuses_from_workspace_falls_back_on_unreadable_path(tmp_path):
    """An unreadable workspace path must fall back to JSON-derived statuses
    rather than raising (keeps the run alive)."""
    bp = _bp(_sample_nodes())
    missing = tmp_path / "does_not_exist.lean"

    statuses = derive_lemma_statuses_from_workspace(bp, missing)

    # JSON fallback: nodes have sorry_free=False (mimics missing JSON field)
    assert all(ls["status"] == "unproved" for ls in statuses.values())
