"""
Blueprint generation node — decomposes a theorem into a @[blueprint]-annotated
Lean skeleton.
"""

from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from config import (
    BLUEPRINT_GENERATOR_PROMPT,
    MODEL_NAME,
    MODEL_TIMEOUT,
)
from state import State, Context
from tools import file_tools, human_tools
from lean_tools_cache import get_lean_tools
from mathlib_doc_tools import doc_tools
from agents.code_module_analyzer import code_module_analyzer
from nodes._utils import print_ai_response


async def blueprint_generator(state: State, runtime: Runtime[Context]):
    """LLM node — decomposes the theorem into a @[blueprint]-annotated Lean skeleton.
    Uses file_tools + lean_tools + doc_tools + human_tools."""
    print("\n" + "=" * 70)
    print("📋 BLUEPRINT GENERATOR: Decomposing theorem into dependency graph")
    print("=" * 70 + "\n")

    # Load prompt & model
    prompt = Path(BLUEPRINT_GENERATOR_PROMPT).read_text()
    model_name = runtime.context.get("model", MODEL_NAME)
    llm = init_chat_model(model_name, timeout=MODEL_TIMEOUT)

    lean_tools = await get_lean_tools()
    llm_with_tools = llm.bind_tools(
        file_tools + human_tools + lean_tools + doc_tools + [code_module_analyzer]
    )

    # First turn: seed with system prompt + theorem
    if not state.blueprint_generator_messages:
        seed_msg = [
            SystemMessage(content=prompt),
            HumanMessage(content=(
                state.theorem + "\n\n"
                "Workspace file: " + state.workspacePATH + "\n"
                "Project Root: " + state.project_root
            )),
        ]
        response = await llm_with_tools.ainvoke(seed_msg)
        print_ai_response("BP", response)
        return {
            "blueprint_generator_messages": seed_msg + [response],
            "active_node": "blueprint_gen",
        }

    # Subsequent turns: continue conversation
    response = await llm_with_tools.ainvoke(state.blueprint_generator_messages)
    print_ai_response("BP", response)
    return {
        "blueprint_generator_messages": [response],
        "active_node": "blueprint_gen",
    }
