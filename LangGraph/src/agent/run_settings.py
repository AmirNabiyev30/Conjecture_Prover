"""
Per-run settings for the Conjecture Prover graph.

One immutable :class:`RunSettings` value holds every parameter that varies from
one run to the next. It is:

- built once from the environment by :meth:`RunSettings.from_env` — defaults come
  from :mod:`config`, and the environment only overrides them;
- injected into every node through the LangGraph Runtime ``Context``
  (:meth:`RunSettings.to_context`);
- recorded verbatim in the run summary, so a result row can always be traced
  back to the settings that produced it.

Scope: ``RunSettings`` describes *how* a run is configured. The problem being
solved — the theorem text and the target workspace path — is run *data* and
stays on :class:`state.State`.

Every field is normalised at construction, so consumers never re-derive
anything: ``refiner_prompt`` is always the concrete prompt path, whether it came
from an explicit override or from the analyzer mode.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from config import (
    BLUEPRINT_GENERATOR_PROMPT,
    BLUEPRINT_REFINER_ANALYZER_MODES,
    BLUEPRINT_REFINER_PROMPT_BY_MODE,
    MAX_ITERATIONS,
    MAX_REFINEMENT_ROUNDS,
    MAX_TURNS_PER_LEMMA,
    MODEL_NAME,
    MODEL_TIMEOUT,
)

#: Default analyzer mode for the refiner when the environment does not set one.
DEFAULT_REFINER_ANALYZER_MODE: str = "required"

#: Values accepted for boolean environment variables.
_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    """Read a boolean env var; anything other than a truthy token is False."""
    raw = env.get(name)
    return default if raw is None else raw.strip().lower() in _TRUTHY


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    """Read an integer env var, failing loudly on a malformed value."""
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class RunSettings:
    """Immutable configuration for a single graph run.

    Attributes:
        model: Chat model name passed to the LLM factory.
        model_timeout: Per-invocation LLM timeout in seconds.
        max_iterations: Global iteration ceiling.
        max_turns_per_lemma: Per-prover turn budget.
        max_refinement_rounds: Safety ceiling for refinement loops.
        generator_prompt: Path to the blueprint-generator prompt.
        refiner_prompt: Path to the blueprint-refiner prompt. An empty value at
            construction means "use the variant selected by
            ``refiner_analyzer_mode``"; the stored value is always concrete.
        refiner_analyzer_mode: One of ``config.BLUEPRINT_REFINER_ANALYZER_MODES``.
            Selects both the refiner prompt variant and whether the
            ``analyze_mathlib_module`` tool is bound.
        enable_module_analysis: Bind ``analyze_mathlib_module`` for the generator.
        enable_workspace_writes: Bind the writing file tools instead of the
            read-only subset.
    """

    model: str
    model_timeout: int
    max_iterations: int
    max_turns_per_lemma: int
    max_refinement_rounds: int
    generator_prompt: str
    refiner_prompt: str
    refiner_analyzer_mode: str
    enable_module_analysis: bool
    enable_workspace_writes: bool = True

    def __post_init__(self) -> None:
        mode = self.refiner_analyzer_mode
        if mode not in BLUEPRINT_REFINER_ANALYZER_MODES:
            raise ValueError(
                f"Invalid refiner_analyzer_mode={mode!r}; "
                f"expected one of {BLUEPRINT_REFINER_ANALYZER_MODES}."
            )
        # Normalise the prompt path in place. The instance is still being
        # constructed, so bypassing the frozen guard is safe here and keeps
        # every later read free of override-precedence logic.
        if not self.refiner_prompt:
            object.__setattr__(
                self, "refiner_prompt", BLUEPRINT_REFINER_PROMPT_BY_MODE[mode]
            )
        for name in (
            "max_iterations",
            "max_turns_per_lemma",
            "max_refinement_rounds",
        ):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if self.model_timeout < 1:
            raise ValueError(f"model_timeout must be >= 1, got {self.model_timeout}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RunSettings":
        """Build settings from ``env``, defaulting to ``os.environ``.

        Passing an explicit mapping keeps this testable without mutating the
        process environment.
        """
        env = os.environ if env is None else env
        return cls(
            model=env.get("MODEL_NAME") or MODEL_NAME,
            model_timeout=_env_int(env, "MODEL_TIMEOUT", MODEL_TIMEOUT),
            max_iterations=_env_int(env, "MAX_ITERATIONS", MAX_ITERATIONS),
            max_turns_per_lemma=_env_int(
                env, "MAX_TURNS_PER_LEMMA", MAX_TURNS_PER_LEMMA
            ),
            max_refinement_rounds=_env_int(
                env, "MAX_REFINEMENT_ROUNDS", MAX_REFINEMENT_ROUNDS
            ),
            generator_prompt=env.get("BLUEPRINT_GENERATOR_PROMPT")
            or BLUEPRINT_GENERATOR_PROMPT,
            refiner_prompt=env.get("BLUEPRINT_REFINER_PROMPT") or "",
            refiner_analyzer_mode=env.get("BLUEPRINT_REFINER_ANALYZER_MODE")
            or DEFAULT_REFINER_ANALYZER_MODE,
            enable_module_analysis=_env_bool(env, "ENABLE_MODULE_ANALYSIS", True),
            enable_workspace_writes=_env_bool(env, "ENABLE_WORKSPACE_WRITES", True),
        )

    def to_context(self) -> dict[str, Any]:
        """Return the dict injected as the graph's Runtime ``Context``.

        The same mapping is written into the run summary, so a recorded result
        always carries the exact settings that produced it.
        """
        return asdict(self)
