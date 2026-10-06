"""Unit tests for the experiment harness's matrix selection.

These live under LangGraph/tests so the one canonical command runs everything:

    cd LangGraph && .venv/bin/python -m pytest tests/unit_tests

Behavior contract:
- ``run_id`` keeps the historical ``<condition>__<problem>`` form for the default
  budget, so the recorded stage-1 run ids and their filenames stay valid. Only a
  non-default budget appends a suffix.
- ``parse_run_id`` is exact: it rejects anything malformed or unknown rather than
  falling back to substring matching, which used to silently select the wrong
  axis members.
- ``build_cells`` expands the axes for a normal run, but ``only`` is taken
  literally — it must not be re-expanded into a cross product.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from experiments import runner  # noqa: E402
from experiments.runner import (  # noqa: E402
    BUDGETS,
    CONDITIONS,
    DEFAULT_BUDGET,
    PROBLEMS,
    Budget,
    build_cells,
    parse_run_id,
    run_id,
)


# ── run_id ───────────────────────────────────────────────────────────────────

def test_default_budget_keeps_the_historical_run_id():
    """Recorded stage-1 ids, filenames and --resume checks all depend on this."""
    assert run_id("with_analyzer", "fateX_94") == "with_analyzer__fateX_94"
    assert run_id("with_analyzer", "fateX_94", DEFAULT_BUDGET) == "with_analyzer__fateX_94"


def test_non_default_budget_is_suffixed():
    assert run_id("with_analyzer", "fateX_94", "wide") == "with_analyzer__fateX_94__wide"


# ── parse_run_id ─────────────────────────────────────────────────────────────

def test_parse_run_id_round_trips_both_forms():
    assert parse_run_id("with_analyzer__fateX_94") == (
        "with_analyzer", "fateX_94", DEFAULT_BUDGET
    )
    custom = Budget(name="wide", max_turns_per_lemma=20, max_refinement_rounds=16)
    BUDGETS["wide"] = custom
    try:
        assert parse_run_id("with_analyzer__fateX_94__wide") == (
            "with_analyzer", "fateX_94", "wide"
        )
    finally:
        del BUDGETS["wide"]


@pytest.mark.parametrize("rid", [
    "no-separator",
    "a__b__c__d",
    "",
])
def test_parse_run_id_rejects_malformed_ids(rid):
    with pytest.raises(ValueError, match="Invalid run_id"):
        parse_run_id(rid)


@pytest.mark.parametrize("rid,label", [
    ("bogus_condition__fateX_94", "condition"),
    ("with_analyzer__bogus_problem", "problem"),
])
def test_parse_run_id_rejects_unknown_axis_members(rid, label):
    with pytest.raises(ValueError, match=label):
        parse_run_id(rid)


def test_parse_run_id_rejects_an_unknown_budget():
    with pytest.raises(ValueError, match="budget"):
        parse_run_id("with_analyzer__fateX_94__bogus")


# ── build_cells ──────────────────────────────────────────────────────────────

def test_build_cells_expands_the_axes():
    cells = build_cells()
    assert set(cells) == {
        (condition, problem, DEFAULT_BUDGET)
        for condition in CONDITIONS
        for problem in PROBLEMS
    }
    assert len(cells) == len(CONDITIONS) * len(PROBLEMS)


def test_only_is_taken_literally_not_expanded():
    """Two ids naming two conditions must yield two cells, not a cross product."""
    cells = build_cells(only=["with_analyzer__fateX_94", "wo_analyzer__fateX_94"])
    assert cells == [
        ("with_analyzer", "fateX_94", DEFAULT_BUDGET),
        ("wo_analyzer", "fateX_94", DEFAULT_BUDGET),
    ]


def test_only_preserves_the_order_given():
    cells = build_cells(only=["wo_analyzer__fateX_94", "with_analyzer__fateX_94"])
    assert [c[0] for c in cells] == ["wo_analyzer", "with_analyzer"]


@pytest.mark.parametrize("kwargs,label", [
    ({"problems": ["nope"]}, "problem"),
    ({"conditions": ["nope"]}, "condition"),
    ({"budgets": ["nope"]}, "budget"),
])
def test_build_cells_rejects_unknown_axis_members(kwargs, label):
    with pytest.raises(ValueError, match=label):
        build_cells(**kwargs)


# ── Budget ───────────────────────────────────────────────────────────────────

def test_default_budget_sets_no_env_so_it_cannot_drift_from_config():
    """`None` means "use config.py's value" — the numbers are not restated here."""
    assert BUDGETS[DEFAULT_BUDGET].to_env() == {}


def test_budget_renders_only_the_fields_it_sets():
    budget = Budget(name="wide", max_turns_per_lemma=20)
    assert budget.to_env() == {"MAX_TURNS_PER_LEMMA": "20"}

    both = Budget(name="wide", max_turns_per_lemma=20, max_refinement_rounds=16)
    assert both.to_env() == {
        "MAX_TURNS_PER_LEMMA": "20",
        "MAX_REFINEMENT_ROUNDS": "16",
    }


# ── recorded schema ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("column", [
    "budget", "model", "model_timeout", "max_turns_per_lemma", "max_refinement_rounds",
])
def test_results_schema_records_the_settings(column):
    """Without these the results table cannot be traced back to its configuration."""
    assert column in runner.RESULT_FIELDS
