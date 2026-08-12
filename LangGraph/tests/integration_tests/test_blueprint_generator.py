"""Integration test for the blueprint-generation tool-calling phase.

This test intentionally stops after the generator produces a final response.
It exercises the generator, the real ``lean-lsp-mcp`` process, and the
workspace-file tool without entering blueprint rebuilding or theorem proving.

Run with::

    pytest tests/integration_tests/test_blueprint_generator.py -m "mcp"
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from config import (  # noqa: E402
    BLUEPRINT_GENERATOR_PROMPT,
    MODEL_NAME,
    PROJECT_ROOT,
    WORKSPACE_PATH,
)
from agents.blueprint_analyzer import fetch_mathlib_source  # noqa: E402
from agents.module_analyzer import analyze_mathlib_module  # noqa: E402
from lean_tools_cache import get_lean_tools  # noqa: E402
from mathlib_doc_tools import doc_tools  # noqa: E402
from tools import file_tools, human_tools  # noqa: E402
from state import Context, State  # noqa: E402
import nodes.blueprint_generator as blueprint_generator_module  # noqa: E402


pytestmark = pytest.mark.anyio
load_dotenv()


def _route_generator_turn(state: State, turn_counter: dict[str, int]) -> str:
    """Continue only while the generator has tool calls to execute."""
    turn_counter["count"] += 1
    print(f"\n[blueprint generation turn {turn_counter['count']}/100]")
    message = state.blueprint_generator_messages[-1]
    return "tools_bp" if getattr(message, "tool_calls", None) else END


async def _run_blueprint_generation(
    *,
    name: str,
    prompt_path: Path,
    workspace: Path,
    lean_tools: list,
    enable_module_analysis: bool,
) -> dict:
    """Run one blueprint-generation variant with the production tool set."""
    retrieval_tools = [fetch_mathlib_source]
    if enable_module_analysis:
        retrieval_tools.append(analyze_mathlib_module)

    analysis_tools = (
        file_tools
        + human_tools
        + lean_tools
        + doc_tools
        + retrieval_tools
    )

    tool_node = ToolNode(analysis_tools, messages_key="blueprint_generator_messages")
    turn_counter = {"count": 0}

    builder = StateGraph(State, context_schema=Context)
    builder.add_node("blueprint_gen", blueprint_generator_module.blueprint_generator)
    builder.add_node("tools_bp", tool_node)
    builder.add_edge(START, "blueprint_gen")
    builder.add_conditional_edges(
        "blueprint_gen",
        lambda state: _route_generator_turn(state, turn_counter),
    )
    builder.add_edge("tools_bp", "blueprint_gen")
    graph = builder.compile()

    result = await graph.ainvoke(
        {
            "theorem": (
                "Generate a blueprint decomposition for the theorem(s) in the "
                "workspace. Read the workspace file before responding."
            ),
            "workspacePATH": str(workspace),
            "project_root": str(PROJECT_ROOT),
            "blueprint_generator_prompt": str(prompt_path),
            "enable_module_analysis": enable_module_analysis,
            "enable_workspace_writes": True,
        },
        context={
            "model": MODEL_NAME,
            "max_iterations": 100,
            "max_turns_per_lemma": 20,
        },
        # A model turn may be followed by a tool turn.
        config={"recursion_limit": 250},
    )

    messages = result["blueprint_generator_messages"]
    tool_calls = [
        call["name"]
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]
    analyzer_calls = [
        call for call in tool_calls if call == "analyze_mathlib_module"
    ]
    final_message = messages[-1]
    content = str(getattr(final_message, "content", ""))

    print(f"\n===== BLUEPRINT GENERATION: {name} =====")
    print(f"generator_turns={turn_counter['count']}")
    print(f"tool_calls={tool_calls}")
    print(f"final_content_chars={len(content)}")
    for index, message in enumerate(messages):
        print(f"[{index}] {type(message).__name__}")
        if getattr(message, "tool_calls", None):
            print(f"  tool_calls={message.tool_calls}")
        if getattr(message, "content", None):
            print(f"  content={str(message.content)[:1000]}")
    print("===========================================\n")

    assert turn_counter["count"] <= 100, "Blueprint generation exceeded 100 turns"
    assert "read_workspace" in tool_calls, "Generator did not read the workspace file"
    if enable_module_analysis:
        successful_analysis = [
            str(message.content)
            for message in messages
            if getattr(message, "name", None) == "analyze_mathlib_module"
            and not str(message.content).startswith("Could not find module")
        ]
        if successful_analysis:
            print("Analyzer usage: successful module analysis")
        else:
            print(
                "Analyzer usage: not selected by the model for this run "
                "(tool was available)"
            )
    else:
        assert "analyze_mathlib_module" not in tool_calls, (
            "Baseline unexpectedly used analyze_mathlib_module"
        )
    assert content, "Generator returned no final response content"
    assert len(content) > 50, "Generator response is too short"

    return {
        "name": name,
        "messages": messages,
        "tool_calls": tool_calls,
        "analyzer_calls": len(analyzer_calls),
        "content": content,
        "turns": turn_counter["count"],
    }


@pytest.mark.mcp
@pytest.mark.slow
async def test_blueprint_generator_with_module_analysis():
    """Run blueprint generation with module analysis enabled."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    workspace = Path(WORKSPACE_PATH)
    assert workspace.is_file(), f"Workspace file does not exist: {workspace}"
    source = workspace.read_text(encoding="utf-8")
    assert len(source) > 50, "Workspace source is too short to be a useful integration fixture"

    # get_lean_tools() starts the configured lean-lsp-mcp server on first use.
    lean_tools = await get_lean_tools()
    analyzer_prompt = Path(BLUEPRINT_GENERATOR_PROMPT)
    assert analyzer_prompt.is_file(), f"Analyzer prompt does not exist: {analyzer_prompt}"
    await _run_blueprint_generation(
        name="with_important_module_analysis",
        prompt_path=analyzer_prompt,
        workspace=workspace,
        lean_tools=lean_tools,
        enable_module_analysis=True,
    )
