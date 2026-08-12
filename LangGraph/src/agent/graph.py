"""LangGraph orchestration for the Conjecture Prover agent.

This module is responsible only for graph construction, node registration,
edge wiring, and the top-level entry point.  All node logic lives in
nodes/, tools in tools.py, and state/config in their own modules.
"""

from __future__ import annotations
import asyncio
import uuid

from dotenv import load_dotenv

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode

from config import WORKSPACE_PATH, MODEL_NAME
from state import State, Context
from tools import file_tools, human_tools
from mathlib_doc_tools import doc_tools
from lean_tools_cache import get_lean_tools
from agents.blueprint_analyzer import fetch_mathlib_source
from agents.module_analyzer import analyze_mathlib_module

from nodes.blueprint_generator import blueprint_generator
from nodes.blueprint_refiner import blueprint_refiner
from nodes.prove_lemma import prove_lemma
from nodes.aggregator import aggregator
from nodes.routing import (
    rebuild_blueprint,
    route_from_blueprint,
    route_from_refiner,
    route_after_aggregator,
    route_after_rebuild,
    route_from_tools,
)

load_dotenv()

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

human_tool_node_bp = ToolNode(human_tools, messages_key="blueprint_generator_messages")
human_tool_node_br = ToolNode(human_tools, messages_key="blueprint_refiner_messages")


async def build_graph():
    """Construct the full LangGraph StateGraph."""
    lean_tools = await get_lean_tools()
    retrieval_tools = [
        fetch_mathlib_source,
        analyze_mathlib_module,
    ]
    bp_all_tools = file_tools + lean_tools + doc_tools + retrieval_tools
    br_all_tools = file_tools + lean_tools + doc_tools

    tools_bp = ToolNode(bp_all_tools, messages_key="blueprint_generator_messages")
    tools_br = ToolNode(br_all_tools, messages_key="blueprint_refiner_messages")

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
    """Build the graph and invoke it. Handles human-in-the-loop via interrupt."""
    graph = await build_graph()

    result = await graph.ainvoke(
        {
            "theorem": (
                "The target formalization is in the Lean workspace file "
                f"at `{WORKSPACE_PATH}`. Read the file to find the theorem "
                "statement and any existing definitions."
            ),
            "workspacePATH": WORKSPACE_PATH,
        },
        context={"model": MODEL_NAME},
        config=config,
    )

    while interrupt_val := result.get("__interrupt__"):
        print(f"\n--- GRAPH PAUSED ---")
        print(f"Question: {interrupt_val[0].value}")
        answer = input("Your response: ")
        result = await graph.ainvoke(
            Command(resume=answer),
            context={"model": MODEL_NAME},
            config=config,
        )


if __name__ == "__main__":
    asyncio.run(main())
