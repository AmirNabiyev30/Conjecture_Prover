"""
Blueprint refinement node — revises the dependency graph based on prover feedback
for unproved lemmas.
"""

from pathlib import Path
import json

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from config import (
    BLUEPRINT_REFINER_PROMPT,
    MODEL_NAME,
    MODEL_TIMEOUT,
)
from state import State, Context
from tools import file_tools, human_tools
from lean_tools_cache import get_lean_tools
from mathlib_doc_tools import doc_tools
from nodes._utils import print_ai_response


async def blueprint_refiner(state: State, runtime: Runtime[Context]):
    """LLM node — decomposes unproved lemmas into simpler sub-lemmas.
    Receives the full dependency graph + prover feedback."""
    print("\n" + "=" * 70)
    print("🔧 BLUEPRINT REFINER: Revising blueprint based on prover feedback")
    unproved = [name for name, ls in state.lemma_statuses.items()
                if ls["status"] != "proved"]
    if unproved:
        print(f"   Unproved lemmas to address: {', '.join(sorted(unproved))}")
        for name in unproved:
            fb = state.lemma_statuses.get(name, {}).get("feedback", "")
            if fb:
                print(f"     • {name}: {fb[:120]}...")
    print("=" * 70 + "\n")

    # Load model & tools
    prompt = Path(BLUEPRINT_REFINER_PROMPT).read_text()
    model_name = runtime.context.get("model", MODEL_NAME)
    llm = init_chat_model(model_name, timeout=MODEL_TIMEOUT)

    lean_tools = await get_lean_tools()
    llm_with_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

    # Build context: full dependency graph + prover feedback
    bp_json_str = (
        json.dumps(state.blueprint.to_dict(), indent=2)
        if state.blueprint
        else "(no blueprint loaded)"
    )
    proved_names = [
        name for name, ls in state.lemma_statuses.items()
        if ls["status"] == "proved"
    ]
    unproved_summary = (
        "\n".join(
            f"- **{name}** (depends on: {', '.join(state.lemma_statuses.get(name, {}).get('dependencies', []))}): "
            f"{state.lemma_statuses.get(name, {}).get('feedback', 'no feedback')}"
            for name in unproved
        )
        if unproved
        else ""
    )

    # First turn: seed with system prompt + context
    if not state.blueprint_refiner_messages:
        seed_msg = [
            SystemMessage(content=prompt),
            HumanMessage(content=(
                f"Target theorem:\n{state.theorem}\n\n"
                f"Workspace file: {state.workspacePATH}\n\n"
                f"Project root: {state.project_root}\n\n"
                f"Already proved: {', '.join(proved_names) if proved_names else 'none'}\n\n"
                f"Unproved lemmas with prover feedback:\n{unproved_summary or 'none'}\n\n"
                f"Full dependency graph (blueprint JSON):\n```json\n{bp_json_str}\n```"
            )),
        ]
        response = await llm_with_tools.ainvoke(seed_msg)
        print_ai_response("BR", response)
        return {
            "blueprint_refiner_messages": seed_msg + [response],
            "active_node": "blueprint_refiner",
        }

    # Subsequent turns: continue conversation
    response = await llm_with_tools.ainvoke(state.blueprint_refiner_messages)
    print_ai_response("BR", response)
    return {
        "blueprint_refiner_messages": [response],
        "active_node": "blueprint_refiner",
    }
