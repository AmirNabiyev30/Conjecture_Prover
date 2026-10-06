"""LangGraph orchestration for the Conjecture Prover agent.

This module is responsible only for graph construction, node registration,
edge wiring, and the top-level entry point.  All node logic lives in
nodes/, tools in tools.py, and state/config in their own modules.
"""

from __future__ import annotations

import asyncio
import uuid

import cli
from agents.blueprint_analyzer import fetch_mathlib_source
from agents.module_analyzer import analyze_mathlib_module
from run_settings import RunSettings
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from lean_tools_cache import get_lean_tools
from mathlib_doc_tools import doc_tools
from nodes.aggregator import aggregator
from nodes.blueprint_generator import blueprint_generator
from nodes.blueprint_refiner import blueprint_refiner
from nodes.prove_lemma import prove_lemma
from nodes.routing import (
    rebuild_blueprint,
    route_after_aggregator,
    route_after_rebuild,
    route_from_blueprint,
    route_from_refiner,
    route_from_tools,
)
from state import Context, State
from tools import file_tools, human_tools

load_dotenv()

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

human_tool_node_bp = ToolNode(human_tools, messages_key="blueprint_generator_messages")
human_tool_node_br = ToolNode(human_tools, messages_key="blueprint_refiner_messages")


def _tool_error_message(e: Exception) -> str:
    """Convert a tool exception into a message returned to the model.

    LangGraph's default ToolNode error handling *re-raises* the exception, which
    propagates out of ``graph.ainvoke()`` and kills the whole run on any single
    bad tool call (e.g. a hallucinated file path). Returning a string instead
    feeds the error back to the model so it can recover and continue.
    """
    return f"TOOL ERROR ({type(e).__name__}): {e}"


async def build_graph(settings: RunSettings | None = None):
    """Construct the full LangGraph StateGraph.

    ``settings`` decides the analyzer tool surface: ``analyze_mathlib_module`` is
    only registered on a ToolNode when the corresponding flag allows it, so the
    available tools match the run condition:

      - generator ToolNode: analyzer registered iff ``enable_module_analysis``
      - refiner ToolNode:   analyzer registered iff
        ``refiner_analyzer_mode != "none"``

    This is a structural guarantee that complements the per-node ``bind_tools``
    gating in ``nodes/blueprint_generator.py`` and ``nodes/blueprint_refiner.py``.
    ``settings`` defaults to :meth:`RunSettings.from_env`.
    """
    settings = settings or RunSettings.from_env()
    lean_tools = await get_lean_tools()
    retrieval_tools = [fetch_mathlib_source]
    if settings.enable_module_analysis:
        retrieval_tools.append(analyze_mathlib_module)
    bp_all_tools = file_tools + lean_tools + doc_tools + retrieval_tools

    br_all_tools = file_tools + lean_tools + doc_tools
    if settings.refiner_analyzer_mode != "none":
        br_all_tools.append(analyze_mathlib_module)

    tools_bp = ToolNode(
        bp_all_tools,
        messages_key="blueprint_generator_messages",
        handle_tool_errors=_tool_error_message,
    )
    tools_br = ToolNode(
        br_all_tools,
        messages_key="blueprint_refiner_messages",
        handle_tool_errors=_tool_error_message,
    )

    builder = StateGraph(State, context_schema=Context)

    builder.add_node("blueprint_gen", blueprint_generator)
    builder.add_node("blueprint_refiner", blueprint_refiner)
    builder.add_node("tools_bp", tools_bp)
    builder.add_node("human_tool_bp", human_tool_node_bp)
    builder.add_node("tools_br", tools_br)
    builder.add_node("human_tool_br", human_tool_node_br)
    builder.add_node("prove_lemma", prove_lemma)
    builder.add_node("aggregator", aggregator)
    builder.add_node("rebuild_blueprint", rebuild_blueprint)

    builder.add_edge(START, "blueprint_gen")
    builder.add_conditional_edges("blueprint_gen", route_from_blueprint)
    builder.add_conditional_edges("blueprint_refiner", route_from_refiner)

    for tool_node_name in ("tools_bp", "human_tool_bp"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_gen": "blueprint_gen"},
        )
    for tool_node_name in ("tools_br", "human_tool_br"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_refiner": "blueprint_refiner"},
        )

    builder.add_conditional_edges("rebuild_blueprint", route_after_rebuild)
    builder.add_edge("prove_lemma", "aggregator")
    builder.add_conditional_edges(
        "aggregator", route_after_aggregator,
        {"blueprint_refiner": "blueprint_refiner", END: END},
    )

    checkpointer = MemorySaver()
    graph = builder.compile(name="Conjecture Prover Graph", checkpointer=checkpointer)
    return graph


async def main() -> None:
    """Run one workflow end to end.

    Operator-facing concerns — the smoke pre-flight, LangSmith metadata tags, the
    auto-resume policy, and the summary hand-off — live in :mod:`cli`. This module
    owns graph construction, and passes its own ``build_graph`` in rather than
    letting ``cli`` import this module (which the harness runs as a script, so a
    reverse import would load it twice under two module names).
    """
    await cli.run(build_graph, base_config=config)


if __name__ == "__main__":
    asyncio.run(main())
