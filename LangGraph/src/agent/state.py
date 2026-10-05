"""
State definitions and reducer helpers for the Conjecture Prover graph.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain.messages import AnyMessage

from blueprint import Blueprint, LemmaTask, LemmaStatus, ProofProposal

from config import BLUEPRINT_GENERATOR_PROMPT, PROJECT_ROOT, WORKSPACE_PATH


class Context(TypedDict):
    """Runtime context injected into every node via LangGraph Runtime.

    Transport shape for a :class:`run_settings.RunSettings` value: built by
    ``RunSettings.to_context()``, which is the source of truth for these fields.
    Nodes read them with ``runtime.context.get(...)`` and never re-derive an
    override precedence.
    """
    model: str  # e.g. "deepseek-v4-flash"
    model_timeout: int
    max_iterations: int
    max_turns_per_lemma: int
    max_refinement_rounds: int
    generator_prompt: str
    refiner_prompt: str
    refiner_analyzer_mode: str
    enable_module_analysis: bool
    enable_workspace_writes: bool


def _reset_or_add(old: list, new: list) -> list:
    """Reducer for pending_proposals.
    
    Parallel provers add via concat (old + new).
    When the aggregator returns [] (empty list), it signals reset → clear accumulator.
    """
    if not new:
        return []
    return old + new


@dataclass
class State:
    """Input state for the Conjecture Prover agent."""
    theorem: str = ""
    workspacePATH: str = WORKSPACE_PATH
    blueprint_generator_prompt: str = BLUEPRINT_GENERATOR_PROMPT
    enable_module_analysis: bool = True
    enable_workspace_writes: bool = True
    # ── Blueprint refiner analyzer-experiment configuration ──────────────────
    # `blueprint_refiner_analyzer_mode` selects BOTH the prompt variant and
    # whether the `analyze_mathlib_module` tool is bound. Valid values (see
    # config.BLUEPRINT_REFINER_ANALYZER_MODES):
    #   "required" -> prompts/blueprint_refiner.md                   (analyzer on)
    #   "optional" -> prompts/blueprint_refiner_optional_analyzer.md (analyzer on)
    #   "none"     -> prompts/blueprint_refiner_wo_analyzer.md       (analyzer off)
    # `blueprint_refiner_prompt` is an explicit prompt-path override; when empty
    # the refiner node auto-resolves the file from the mode above.
    blueprint_refiner_analyzer_mode: str = "required"
    blueprint_refiner_prompt: str = ""
    blueprint_generator_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    blueprint_refiner_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    active_node: str = "blueprint_gen"
    project_root: str = str(PROJECT_ROOT)

    # Blueprint DAG as source of truth — populated after first lake build.
    # blueprint.nodes ARE the LemmaTask units of work for the parallel provers.
    blueprint: Blueprint | None = None

    # Lemma statuses — derived fresh each aggregator round from blueprint JSON
    lemma_statuses: dict[str, LemmaStatus] = field(default_factory=dict)

    # Fan-in accumulator for proof proposals from parallel provers.
    # Uses custom reducer: parallel Send tasks concat (old + new), aggregator
    # returns [] to reset for the next round.
    pending_proposals: Annotated[list[ProofProposal], _reset_or_add] = field(default_factory=list)

    # Round / budget tracking
    global_round: int = 0

    # Transient fields set by theorem_proving for prove_lemma nodes
    lemma_task: LemmaTask | None = None
    lemma_decl_text: str = ""
