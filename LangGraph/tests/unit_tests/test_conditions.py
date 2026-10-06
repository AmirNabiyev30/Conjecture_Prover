"""Unit tests for the analyzer-utilization condition table.

Behavior contract:
- Each arm's ``to_env()`` reproduces exactly that arm when fed to
  ``RunSettings.from_env`` — this is the bridge the harness relies on, since it
  applies an arm by setting environment variables on a graph subprocess.
- The labels an arm records (``to_dict()``) match the labels the graph records
  for the same arm, so summaries written by either side agree.
- ``wo_analyzer`` is a true control: no route to the analyzer at either stage.
- Every prompt path the table names exists on disk.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from conditions import CONDITIONS, AnalyzerCondition  # noqa: E402
from config import BLUEPRINT_REFINER_PROMPT_BY_MODE  # noqa: E402
from run_settings import RunSettings  # noqa: E402
from run_summary import condition_block  # noqa: E402


def test_all_three_arms_are_defined():
    assert set(CONDITIONS) == {"with_analyzer", "wo_analyzer", "optional_analyzer"}


def test_condition_name_matches_its_key():
    for key, condition in CONDITIONS.items():
        assert condition.name == key


# ── the harness -> graph bridge ──────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(CONDITIONS))
def test_to_env_round_trips_through_run_settings(name):
    """Applying an arm's env vars must produce exactly that arm's settings."""
    condition = CONDITIONS[name]
    settings = RunSettings.from_env(condition.to_env())
    assert settings.generator_prompt == condition.generator_prompt
    assert settings.enable_module_analysis == condition.enable_module_analysis
    assert settings.refiner_analyzer_mode == condition.refiner_analyzer_mode
    assert settings.refiner_prompt == condition.refiner_prompt


@pytest.mark.parametrize("name", sorted(CONDITIONS))
def test_recorded_condition_block_matches_the_graphs(name):
    """Harness-written and graph-written summaries must label an arm identically."""
    condition = CONDITIONS[name]
    settings = RunSettings.from_env(condition.to_env())
    assert condition.to_dict() == condition_block(settings)


# ── the study's invariants ───────────────────────────────────────────────────

def test_wo_analyzer_disables_the_analyzer_everywhere():
    """The control arm must have no route to the analyzer at either stage."""
    control = CONDITIONS["wo_analyzer"]
    assert control.enable_module_analysis is False
    assert control.refiner_analyzer_mode == "none"


@pytest.mark.parametrize("name", ["with_analyzer", "optional_analyzer"])
def test_analyzer_arms_enable_the_analyzer_for_the_generator(name):
    assert CONDITIONS[name].enable_module_analysis is True


def test_refiner_prompt_follows_the_mode():
    for condition in CONDITIONS.values():
        assert condition.refiner_prompt == (
            BLUEPRINT_REFINER_PROMPT_BY_MODE[condition.refiner_analyzer_mode]
        )


# ── validation ───────────────────────────────────────────────────────────────

def test_invalid_refiner_mode_is_rejected():
    with pytest.raises(ValueError, match="refiner_analyzer_mode"):
        AnalyzerCondition(
            name="broken",
            generator_prompt="p.md",
            enable_module_analysis=True,
            refiner_analyzer_mode="bogus",
        )


@pytest.mark.parametrize("name", sorted(CONDITIONS))
def test_prompt_files_exist_on_disk(name):
    """Guard against a prompt file being renamed out from under the table."""
    condition = CONDITIONS[name]
    assert Path(condition.generator_prompt).is_file(), condition.generator_prompt
    assert Path(condition.refiner_prompt).is_file(), condition.refiner_prompt
