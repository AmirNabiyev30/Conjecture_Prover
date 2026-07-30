"""
State definitions and reducer helpers for the Conjecture Prover graph.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain.messages import AnyMessage

from blueprint_converter import LemmaTask, LemmaStatus, ProofProposal
from blueprint_schema import BlueprintGraph

from config import WORKSPACE_PATH, PROJECT_ROOT


class Context(TypedDict):
    """Runtime context injected into every node via LangGraph Runtime."""
    model: str  # e.g. "deepseek-chat"
    max_iterations: int
    max_turns_per_lemma: int


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
    blueprint_generator_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    blueprint_refiner_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    active_node: str = "blueprint_gen"
    project_root: str = str(PROJECT_ROOT)

    # Blueprint JSON as source of truth — populated after first lake build
    blueprint: list[dict] = field(default_factory=list)
    blueprint_graph: BlueprintGraph | None = None
    lemma_tasks: list[LemmaTask] = field(default_factory=list)

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
