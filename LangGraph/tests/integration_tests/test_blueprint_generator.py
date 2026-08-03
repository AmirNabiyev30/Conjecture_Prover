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

from config import MODEL_NAME, PROJECT_ROOT, WORKSPACE_PATH  # noqa: E402
from agents.code_module_analyzer import code_module_analyzer  # noqa: E402
from lean_tools_cache import get_lean_tools  # noqa: E402
from mathlib_doc_tools import doc_tools  # noqa: E402
from tools import human_tools, list_directory, read_workspace  # noqa: E402
from state import Context, State  # noqa: E402
import nodes.blueprint_generator as blueprint_generator_module  # noqa: E402


pytestmark = pytest.mark.anyio
load_dotenv()


def _route_generator_turn(state: State) -> str:
    """Continue only while the generator has tool calls to execute."""
    message = state.blueprint_generator_messages[-1]
    return "tools_bp" if getattr(message, "tool_calls", None) else END


@pytest.mark.mcp
@pytest.mark.slow
async def test_blueprint_generator_reads_workspace_with_real_mcp(monkeypatch):
    """Process the checked-in Lean workspace through the real blueprint node."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    workspace = Path(WORKSPACE_PATH)
    assert workspace.is_file(), f"Workspace file does not exist: {workspace}"
    source = workspace.read_text(encoding="utf-8")
    assert len(source) > 50, "Workspace source is too short to be a useful integration fixture"

    # Keep the generator's read-only analysis surface while removing every
    # workspace-mutating tool (write_workspace, search_replace_workspace,
    # create_file, and build_blueprint_json).
    read_only_file_tools = [read_workspace, list_directory]
    monkeypatch.setattr(blueprint_generator_module, "file_tools", read_only_file_tools)

    # get_lean_tools() starts the configured lean-lsp-mcp server on first use.
    lean_tools = await get_lean_tools()
    analysis_tools = (
        read_only_file_tools
        + human_tools
        + lean_tools
        + doc_tools
        + [code_module_analyzer]
    )
    tool_node = ToolNode(analysis_tools, messages_key="blueprint_generator_messages")

    builder = StateGraph(State, context_schema=Context)
    builder.add_node("blueprint_gen", blueprint_generator)
    builder.add_node("tools_bp", tool_node)
    builder.add_edge(START, "blueprint_gen")
    builder.add_conditional_edges("blueprint_gen", _route_generator_turn)
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
        },
        context={"model": MODEL_NAME, "max_iterations": 16, "max_turns_per_lemma": 20},
    )

    messages = result["blueprint_generator_messages"]
    tool_calls = [
        call["name"]
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]

    print("\n===== BLUEPRINT GENERATOR TRAJECTORY =====")
    for index, message in enumerate(messages):
        print(f"[{index}] {type(message).__name__}")
        if getattr(message, "tool_calls", None):
            print(f"  tool_calls={message.tool_calls}")
        if getattr(message, "content", None):
            print(f"  content={str(message.content)[:1000]}")
    print("===========================================\n")

    assert "read_workspace" in tool_calls, "Generator did not read the workspace file"
    assert not set(tool_calls) & {
        "write_workspace",
        "search_replace_workspace",
        "create_file",
        "build_blueprint_json",
    }, "Generator attempted to use a mutating workspace tool"

    final_message = messages[-1]
    content = str(getattr(final_message, "content", ""))

    assert content, "Blueprint generator returned no final response content"
    assert len(content) > 50, "Blueprint generator response is too short"
