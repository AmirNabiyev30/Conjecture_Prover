"""Unit tests for RunSettings — the single source of truth for per-run config.

Behavior contract:
- ``from_env()`` defaults to the ``config.py`` values and overrides only the
  fields the environment actually sets.
- An empty ``refiner_prompt`` is normalised to the mode's prompt variant; an
  explicit override always wins.
- An invalid analyzer mode, a negative budget, or a non-integer int fails loudly
  rather than silently falling back to a default.
- ``to_context()`` keys match ``state.Context`` exactly — that equality is the
  injection contract between this module and LangGraph's Runtime.
"""

import json
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

import config
from run_settings import RunSettings
from state import Context


def _defaults() -> RunSettings:
    """Settings with every field at its config default (empty environment)."""
    return RunSettings.from_env({})


# ── defaults & overrides ─────────────────────────────────────────────────────

def test_defaults_come_from_config():
    settings = _defaults()
    assert settings.model == config.MODEL_NAME
    assert settings.model_timeout == config.MODEL_TIMEOUT
    assert settings.max_turns_per_lemma == config.MAX_TURNS_PER_LEMMA
    assert settings.max_refinement_rounds == config.MAX_REFINEMENT_ROUNDS
    assert settings.generator_prompt == config.BLUEPRINT_GENERATOR_PROMPT
    assert settings.refiner_analyzer_mode == "required"
    assert settings.refiner_prompt == config.BLUEPRINT_REFINER_PROMPT_BY_MODE["required"]
    assert settings.enable_module_analysis is True
    assert settings.enable_workspace_writes is True


def test_env_overrides_every_field():
    settings = RunSettings.from_env({
        "MODEL_NAME": "test-model",
        "MODEL_TIMEOUT": "7",
        "MAX_TURNS_PER_LEMMA": "4",
        "MAX_REFINEMENT_ROUNDS": "5",
        "BLUEPRINT_GENERATOR_PROMPT": "/tmp/gen.md",
        "BLUEPRINT_REFINER_PROMPT": "/tmp/ref.md",
        "BLUEPRINT_REFINER_ANALYZER_MODE": "none",
        "ENABLE_MODULE_ANALYSIS": "false",
        "ENABLE_WORKSPACE_WRITES": "0",
    })
    assert (settings.model, settings.model_timeout) == ("test-model", 7)
    assert (settings.max_turns_per_lemma,
            settings.max_refinement_rounds) == (4, 5)
    assert settings.generator_prompt == "/tmp/gen.md"
    assert settings.refiner_prompt == "/tmp/ref.md"
    assert settings.refiner_analyzer_mode == "none"
    assert settings.enable_module_analysis is False
    assert settings.enable_workspace_writes is False


# ── environment parsing ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
    ("0", False), ("false", False), ("no", False), ("off", False), ("", False),
])
def test_bool_env_parsing(raw, expected):
    settings = RunSettings.from_env({"ENABLE_MODULE_ANALYSIS": raw})
    assert settings.enable_module_analysis is expected


def test_unset_bool_uses_its_default():
    assert _defaults().enable_module_analysis is True


@pytest.mark.parametrize("name", [
    "MODEL_TIMEOUT", "MAX_TURNS_PER_LEMMA", "MAX_REFINEMENT_ROUNDS",
])
def test_malformed_int_fails_loudly(name):
    with pytest.raises(ValueError, match=name):
        RunSettings.from_env({name: "not-a-number"})


def test_blank_int_env_falls_back_to_default():
    settings = RunSettings.from_env({"MAX_TURNS_PER_LEMMA": "   "})
    assert settings.max_turns_per_lemma == config.MAX_TURNS_PER_LEMMA


# ── validation ───────────────────────────────────────────────────────────────

def test_invalid_analyzer_mode_raises():
    with pytest.raises(ValueError, match="refiner_analyzer_mode"):
        RunSettings.from_env({"BLUEPRINT_REFINER_ANALYZER_MODE": "bogus"})


@pytest.mark.parametrize("name", [
    "max_turns_per_lemma", "max_refinement_rounds",
])
def test_negative_budget_raises(name):
    with pytest.raises(ValueError, match=name):
        replace(_defaults(), **{name: -1})


def test_zero_refinement_rounds_is_allowed():
    """0 rounds is meaningful ("stop immediately") and used by the e2e test."""
    assert replace(_defaults(), max_refinement_rounds=0).max_refinement_rounds == 0


def test_model_timeout_must_be_positive():
    with pytest.raises(ValueError, match="model_timeout"):
        replace(_defaults(), model_timeout=0)


# ── refiner prompt resolution ────────────────────────────────────────────────

@pytest.mark.parametrize("mode", config.BLUEPRINT_REFINER_ANALYZER_MODES)
def test_empty_refiner_prompt_resolves_from_mode(mode):
    settings = RunSettings.from_env({"BLUEPRINT_REFINER_ANALYZER_MODE": mode})
    assert settings.refiner_prompt == config.BLUEPRINT_REFINER_PROMPT_BY_MODE[mode]


def test_explicit_refiner_prompt_wins_over_mode():
    settings = RunSettings.from_env({
        "BLUEPRINT_REFINER_ANALYZER_MODE": "none",
        "BLUEPRINT_REFINER_PROMPT": "/tmp/custom.md",
    })
    assert settings.refiner_prompt == "/tmp/custom.md"


# ── context / serialisation contract ─────────────────────────────────────────

def test_settings_are_frozen():
    with pytest.raises(FrozenInstanceError):
        _defaults().model = "other"


def test_to_context_keys_match_context_schema():
    """Every RunSettings field must be a declared Context key, and vice versa.

    This is the injection contract: Context is what nodes read, RunSettings is
    what the harness writes, and neither may drift from the other.
    """
    assert set(_defaults().to_context()) == set(Context.__annotations__)


def test_to_context_is_json_serializable():
    payload = _defaults().to_context()
    assert json.loads(json.dumps(payload)) == payload
