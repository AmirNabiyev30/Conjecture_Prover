"""Unit tests for the canonical blueprint data model (``blueprint.py``)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import Blueprint, derive_lemma_statuses


def _sample_blueprint_json():
    """A minimal ``lake build :blueprintJson`` document (array-of-nodes format)."""
    return [
        {
            "type": "node",
            "data": {
                "name": "def_inner_product",
                "statement": {"text": "Define the inner product on R^n", "latexEnv": "definition"},
                "proof": {"usesLabels": [], "uses": []},
                "file": "LeanWorkspace.lean",
                "location": {"range": {"pos": {"line": 1}, "endPos": {"line": 3}}},
                "sorryFree": True,
            },
        },
        {
            "type": "node",
            "data": {
                "name": "lemma_norm_sq_nonneg",
                "statement": {"text": "||x - lambda y||^2 >= 0", "latexEnv": "lemma"},
                "proof": {"usesLabels": ["def_inner_product"], "uses": ["def_inner_product"]},
                "file": "LeanWorkspace.lean",
                "location": {"range": {"pos": {"line": 5}, "endPos": {"line": 9}}},
                "sorryFree": False,
            },
        },
        {
            "type": "node",
            "data": {
                "name": "main",
                "statement": {"text": "|⟨x, y⟩| ≤ ‖x‖ ‖y‖", "latexEnv": "theorem"},
                "proof": {"usesLabels": ["lemma_norm_sq_nonneg"], "uses": []},
                "file": "LeanWorkspace.lean",
                "location": {"range": {"pos": {"line": 11}, "endPos": {"line": 20}}},
                "sorryFree": False,
            },
        },
    ]


# ── from_blueprint_json ───────────────────────────────────────────────────────


def test_from_blueprint_json_parses_nodes():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json(), theorem_name="cauchy_schwarz")
    assert bp.theorem_name == "cauchy_schwarz"
    assert [n["name"] for n in bp.nodes] == ["def_inner_product", "lemma_norm_sq_nonneg", "main"]

    node = bp.node_by_id("lemma_norm_sq_nonneg")
    assert node["kind"] == "lemma"
    assert node["statement"] == "||x - lambda y||^2 >= 0"
    assert node["dependencies"] == ["def_inner_product"]
    assert node["sorry_free"] is False
    assert node["file"] == "LeanWorkspace.lean"
    assert (node["start_line"], node["end_line"]) == (5, 9)


def test_from_blueprint_json_prefers_uses_labels_over_uses():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json())
    assert bp.node_by_id("main")["dependencies"] == ["lemma_norm_sq_nonneg"]


def test_from_blueprint_json_theorem_name_falls_back_to_root():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json())
    assert bp.root_node() == "main"
    assert bp.theorem_name == "main"


def test_from_blueprint_json_ignores_non_node_entries():
    data = _sample_blueprint_json() + [{"type": "metadata", "data": {}}]
    bp = Blueprint.from_blueprint_json(data)
    assert len(bp.nodes) == 3


def test_from_blueprint_json_empty():
    bp = Blueprint.from_blueprint_json([])
    assert bp.nodes == []
    assert bp.root_node() is None
    assert bp.theorem_name == ""


# ── dict round-trip ───────────────────────────────────────────────────────────


def test_dict_round_trip():
    original = Blueprint.from_blueprint_json(_sample_blueprint_json(), theorem_name="cauchy_schwarz")
    original.statement = "For vectors x, y ∈ ℝⁿ, |⟨x, y⟩| ≤ ‖x‖ ‖y‖."
    original.imports = ["Mathlib.Analysis.InnerProductSpace.Basic"]
    original.domain = ["linear algebra"]
    original.source = "blueprint"

    restored = Blueprint.from_dict(original.to_dict())

    assert restored.theorem_name == "cauchy_schwarz"
    assert restored.statement == original.statement
    assert restored.imports == original.imports
    assert restored.domain == original.domain
    assert restored.source == original.source
    assert [n["name"] for n in restored.nodes] == [n["name"] for n in original.nodes]
    assert restored.node_by_id("lemma_norm_sq_nonneg")["dependencies"] == ["def_inner_product"]


def test_to_dict_shape():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json(), theorem_name="cauchy_schwarz")
    d = bp.to_dict()
    assert d["theorem"] == "cauchy_schwarz"
    assert set(d["blueprint"]) == {"nodes", "edges"}
    assert d["blueprint"]["nodes"][0]["name"] == "def_inner_product"
    assert {"source": "main", "target": "lemma_norm_sq_nonneg"} in d["blueprint"]["edges"]
    assert d["metadata"]["source"] == "blueprint"


# ── workflow projections ──────────────────────────────────────────────────────


def test_blueprint_nodes_are_lemma_tasks():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json())
    tasks = bp.nodes
    assert len(tasks) == 3
    task = tasks[1]
    assert task["name"] == "lemma_norm_sq_nonneg"
    assert task["kind"] == "lemma"
    assert task["statement"] == "||x - lambda y||^2 >= 0"
    assert task["dependencies"] == ["def_inner_product"]
    assert (task["start_line"], task["end_line"]) == (5, 9)
    assert task["proof_sketch"] is None
    assert task["sorry_free"] is False


def test_derive_lemma_statuses():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json())
    statuses = derive_lemma_statuses(bp)
    assert statuses["def_inner_product"]["status"] == "proved"   # sorry_free=True
    assert statuses["lemma_norm_sq_nonneg"]["status"] == "unproved"
    assert statuses["main"]["status"] == "unproved"
    assert statuses["main"]["dependencies"] == ["lemma_norm_sq_nonneg"]
    assert statuses["main"]["feedback"] == ""


# ── topological order ─────────────────────────────────────────────────────────


def test_topological_order():
    bp = Blueprint.from_blueprint_json(_sample_blueprint_json())
    assert bp.topological_order() == ["def_inner_product", "lemma_norm_sq_nonneg", "main"]


def test_topological_order_detects_cycle():
    bp = Blueprint(nodes=[
        {"name": "a", "kind": "lemma", "statement": "", "dependencies": ["b"]},
        {"name": "b", "kind": "lemma", "statement": "", "dependencies": ["a"]},
    ])
    with pytest.raises(ValueError):
        bp.topological_order()
