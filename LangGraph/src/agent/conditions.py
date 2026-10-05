"""
Analyzer-utilization conditions — the arms of the code-module-analyzer study.

One :class:`AnalyzerCondition` describes a single arm: which blueprint-generator
prompt it uses, whether the ``analyze_mathlib_module`` tool is available to the
generator, and which refiner analyzer mode it selects. :data:`CONDITIONS` is the
single source of truth for those values.

``AnalyzerCondition.to_env`` renders a condition into the environment variables
that ``graph.main()`` — and therefore ``RunSettings.from_env`` — reads. That is
how the experiment harness applies an arm to a run subprocess, and it keeps the
dependency one-directional: the harness knows about conditions, the graph only
knows about settings.

Prompt paths come from :mod:`config`, so this table cannot drift from the files
the agent actually loads.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    BLUEPRINT_GENERATOR_OPTIONAL_ANALYZER_PROMPT,
    BLUEPRINT_GENERATOR_PROMPT,
    BLUEPRINT_GENERATOR_WO_ANALYZER_PROMPT,
    BLUEPRINT_REFINER_ANALYZER_MODES,
    BLUEPRINT_REFINER_PROMPT_BY_MODE,
)


@dataclass(frozen=True)
class AnalyzerCondition:
    """One arm of the analyzer-utilization study.

    Attributes:
        name: Condition slug, also used as the ``<condition>__<problem>`` run-id
            prefix.
        generator_prompt: Prompt the blueprint generator loads for this arm.
        enable_module_analysis: Whether ``analyze_mathlib_module`` is available to
            the generator.
        refiner_analyzer_mode: Refiner analyzer mode; selects both the refiner
            prompt variant and whether the analyzer tool is bound there.
        description: Human-readable summary, for reports and logs.
    """

    name: str
    generator_prompt: str
    enable_module_analysis: bool
    refiner_analyzer_mode: str
    description: str = ""

    def __post_init__(self) -> None:
        if self.refiner_analyzer_mode not in BLUEPRINT_REFINER_ANALYZER_MODES:
            raise ValueError(
                f"Condition {self.name!r} has invalid refiner_analyzer_mode="
                f"{self.refiner_analyzer_mode!r}; expected one of "
                f"{BLUEPRINT_REFINER_ANALYZER_MODES}."
            )

    @property
    def refiner_prompt(self) -> str:
        """The refiner prompt path this condition resolves to, via its mode."""
        return BLUEPRINT_REFINER_PROMPT_BY_MODE[self.refiner_analyzer_mode]

    def to_env(self) -> dict[str, str]:
        """The environment variables that reproduce this condition in a run.

        Feed the result to ``RunSettings.from_env`` (directly, or through a
        graph subprocess) to obtain exactly this arm.
        """
        return {
            "BLUEPRINT_GENERATOR_PROMPT": self.generator_prompt,
            "ENABLE_MODULE_ANALYSIS": "true" if self.enable_module_analysis else "false",
            "BLUEPRINT_REFINER_ANALYZER_MODE": self.refiner_analyzer_mode,
        }

    def to_dict(self) -> dict[str, object]:
        """The condition labels recorded in the run summary.

        Mirrors the graph's own recorded condition block, so a summary written by
        the harness and one written by the graph describe an arm identically.
        """
        return {
            "blueprint_generator_prompt": self.generator_prompt,
            "enable_module_analysis": self.enable_module_analysis,
            "blueprint_refiner_analyzer_mode": self.refiner_analyzer_mode,
        }


#: The three aligned arms: the analyzer is available at both route-planning
#: stages, at neither, or only optionally (the model decides).
CONDITIONS: dict[str, AnalyzerCondition] = {
    "with_analyzer": AnalyzerCondition(
        name="with_analyzer",
        generator_prompt=BLUEPRINT_GENERATOR_PROMPT,
        enable_module_analysis=True,
        refiner_analyzer_mode="required",
        description="Analyzer available and steered toward at both stages.",
    ),
    "wo_analyzer": AnalyzerCondition(
        name="wo_analyzer",
        generator_prompt=BLUEPRINT_GENERATOR_WO_ANALYZER_PROMPT,
        enable_module_analysis=False,
        refiner_analyzer_mode="none",
        description="Analyzer unavailable at both stages (control arm).",
    ),
    "optional_analyzer": AnalyzerCondition(
        name="optional_analyzer",
        generator_prompt=BLUEPRINT_GENERATOR_OPTIONAL_ANALYZER_PROMPT,
        enable_module_analysis=True,
        refiner_analyzer_mode="optional",
        description="Analyzer available at both stages, but optional.",
    ),
}
