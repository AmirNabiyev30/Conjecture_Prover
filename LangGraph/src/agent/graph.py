"""LangGraph orchestration for the Conjecture Prover agent.

This module is responsible only for graph construction, node registration,
edge wiring, and the top-level entry point.  All node logic lives in
nodes/, tools in tools.py, and state/config in their own modules.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

from agents.blueprint_analyzer import fetch_mathlib_source
from agents.module_analyzer import analyze_mathlib_module
from config import WORKSPACE_PATH
from run_settings import RunSettings
from run_summary import (
    failure_payload,
    print_unsolved_scan,
    smoke_payload,
    state_get,
    success_payload,
    unsolved_scan,
    write_summary_json,
)
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
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


async def main():
    """Build the graph and invoke it. Handles human-in-the-loop via interrupt.

    All run configuration is resolved once, from the environment, into a single
    :class:`RunSettings` value (see ``run_settings.py``). That value is used both
    to build the graph (it decides the analyzer tool surface) and as the Runtime
    ``Context`` injected into every node.

    Run configuration — see ``RunSettings.from_env`` for the full list:
        MODEL_NAME, MODEL_TIMEOUT, MAX_TURNS_PER_LEMMA, MAX_REFINEMENT_ROUNDS,
        BLUEPRINT_GENERATOR_PROMPT, ENABLE_MODULE_ANALYSIS,
        BLUEPRINT_REFINER_ANALYZER_MODE, BLUEPRINT_REFINER_PROMPT,
        ENABLE_WORKSPACE_WRITES

    Autonomous execution:
        EXPERIMENT_AUTO_ANSWER=<str>           canned resume answer for ask_human
                                               interrupts (avoids blocking on input())
        EXPERIMENT_MAX_AUTO_RESUMES=<int>      cap on auto-resumes (default: 3)

    Structured results:
        EXPERIMENT_SUMMARY_JSON=<path>         dump an end-of-run summary JSON here
        EXPERIMENT_METADATA=<json object>      per-run LangSmith metadata tags

    Zero-cost pre-flight:
        GRAPH_SMOKE_TEST=1                     build the graph (incl. Lean MCP) then
                                               exit before any LLM invocation; used
                                               by `experiment_runner.py --smoke`
    """
    settings = RunSettings.from_env()
    context = settings.to_context()

    # Build the graph with the analyzer tool registered only where the run
    # condition allows it (structural guarantee at the ToolNode level).
    graph = await build_graph(settings)

    # Zero-cost pre-flight: verify the run's spawn path (env parsing + graph
    # construction + Lean MCP startup) and exit before any LLM invocation.
    # Also write a stub summary so the harness's summary-file handoff is tested.
    if os.environ.get("GRAPH_SMOKE_TEST", "").lower() in {"1", "true", "yes"}:
        print("SMOKE_OK: graph built (no LLM invocation)")
        print(f"SMOKE_OK: generator_prompt={settings.generator_prompt}")
        print(f"SMOKE_OK: enable_module_analysis={settings.enable_module_analysis}")
        print(f"SMOKE_OK: blueprint_refiner_analyzer_mode={settings.refiner_analyzer_mode}")
        summary_json_path = os.environ.get("EXPERIMENT_SUMMARY_JSON", "")
        if summary_json_path:
            write_summary_json(smoke_payload(settings, WORKSPACE_PATH))
            print(f"SMOKE_OK: wrote stub summary to {summary_json_path}")
        return

    # Per-run LangSmith metadata tags (e.g. {"condition": "with_analyzer", ...}).
    invoke_config = dict(config)
    raw_metadata = os.environ.get("EXPERIMENT_METADATA", "")
    if raw_metadata:
        try:
            invoke_config["metadata"] = json.loads(raw_metadata)
        except Exception as e:
            print(f"   ⚠️  Invalid EXPERIMENT_METADATA JSON; ignoring: {e}")

    # ── Workflow execution (wrapped so a node crash still yields a summary) ──
    result = {}
    try:
        result = await graph.ainvoke(
            {
                "theorem": (
                    "The target formalization is in the Lean workspace file "
                    f"at `{WORKSPACE_PATH}`. Read the file to find the theorem "
                    "statement and any existing definitions."
                ),
                "workspacePATH": WORKSPACE_PATH,
            },
            context=context,
            config=invoke_config,
        )

        # ── Human-in-the-loop: auto-resume for autonomous runs ──────────────
        auto_answer = os.environ.get("EXPERIMENT_AUTO_ANSWER", "")
        max_auto_resumes = int(os.environ.get("EXPERIMENT_MAX_AUTO_RESUMES", "3"))
        auto_resumes = 0
        while interrupt_val := result.get("__interrupt__"):
            print(f"\n--- GRAPH PAUSED ---")
            print(f"Question: {interrupt_val[0].value}")
            if auto_answer and auto_resumes < max_auto_resumes:
                answer = auto_answer
                auto_resumes += 1
                print(
                    f"   (autonomous) auto-resuming with {answer!r} "
                    f"({auto_resumes}/{max_auto_resumes})"
                )
            else:
                answer = input("Your response: ")
            result = await graph.ainvoke(
                Command(resume=answer),
                context=context,
                config=invoke_config,
            )
    except Exception as e:
        # A node/tool failure (e.g. OpenAI 402) must still leave a summary
        # artifact so the harness can record what round was reached.
        print(f"\n❌ WORKFLOW FAILED: {e!r}")
        write_summary_json(
            failure_payload(settings, WORKSPACE_PATH, result, repr(e))
        )
        raise

    # ── End-of-run summary ──────────────────────────────────────────────────
    # LangGraph returns the state as a dict, so reads go through state_get.
    # unsolved_scan prefers the source-text scan because the LeanArchitect
    # blueprint JSON carries no `sorryFree` field.
    workspace_path = state_get(result, "workspacePATH", WORKSPACE_PATH)
    round_reached = state_get(result, "global_round", 0)
    scan, lemma_statuses = unsolved_scan(result, workspace_path)
    print_unsolved_scan(
        round_reached, settings.max_refinement_rounds, scan, lemma_statuses
    )
    write_summary_json(
        success_payload(settings, workspace_path, round_reached, scan)
    )


if __name__ == "__main__":
    asyncio.run(main())
