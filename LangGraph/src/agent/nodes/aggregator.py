"""
Aggregator node (Reduce) — applies proof proposals via LLM, verifies with Lean
diagnostics, and rebuilds the blueprint JSON with rollback on failure.
"""

from pathlib import Path
import subprocess

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from config import (
    AGGREGATOR_FIXER_PROMPT,
    MODEL_NAME,
    MODEL_TIMEOUT,
    MAX_TURNS_PER_LEMMA,
)
from state import State, Context
from tools import file_tools
from mcp_client import create_lean_mcp_client
from blueprint_converter import (
    blueprint_to_tasks,
    load_blueprint_json,
    derive_lemma_statuses,
)
from nodes._utils import print_ai_response


async def aggregator(state: State, runtime: Runtime[Context]):
    """Reduce node — gives all proposals to an LLM agent which applies them via
    search_replace_workspace and verifies with lean_diagnostic_messages.
    After the LLM finishes, rebuilds blueprint JSON (rollback on failure)."""
    # Setup
    print("\n" + "=" * 70)
    print(f"AGGREGATOR: Applying proofs (round {state.global_round + 1})")
    print(f"   Received {len(state.pending_proposals)} proposal(s)")
    print("=" * 70 + "\n")

    new_round = state.global_round + 1
    workspace_path = state.workspacePATH
    model_name = runtime.context.get("model", MODEL_NAME)
    max_turns = runtime.context.get("max_turns_per_lemma", MAX_TURNS_PER_LEMMA)

    # Save original for full rollback
    try:
        original_content = Path(workspace_path).read_text()
    except Exception as e:
        print(f"   ❌ Failed to read workspace: {e}")
        return {
            "global_round": new_round, "pending_proposals": [],
            "lemma_statuses": dict(state.lemma_statuses),
        }

    # Spin up MCP client (for lean diagnostics)
    try:
        mcp_client = create_lean_mcp_client()
        lean_tools = await mcp_client.get_tools()
    except Exception as e:
        print(f"   ❌ Aggregator MCP start failed: {e}")
        return {
            "global_round": new_round, "pending_proposals": [],
            "lemma_statuses": dict(state.lemma_statuses),
        }

    # Build proposal list for the LLM
    proposal_lines = []
    for prop in state.pending_proposals:
        name = prop["lemma_id"]
        if not name or not prop["proved"] or prop["new_str"] is None:
            continue
        proposal_lines.append(
            f"Lemma: {name}\n"
            f"  old_str (EXACT text in file to replace):\n"
            f"  ```lean\n{prop['old_str']}\n```\n"
            f"  new_str (replacement text):\n"
            f"  ```lean\n{prop['new_str']}\n```\n"
        )

    if not proposal_lines:
        print("   📭 No valid proposals to apply")
        return {
            "global_round": new_round, "pending_proposals": [],
            "lemma_statuses": dict(state.lemma_statuses),
        }

    proposals_text = "\n".join(proposal_lines)

    # LLM agent: apply edits, check diagnostics, fix
    llm = init_chat_model(model_name, timeout=MODEL_TIMEOUT)
    all_tools = lean_tools + file_tools
    llm_with_tools = llm.bind_tools(all_tools)

    fixer_prompt = Path(AGGREGATOR_FIXER_PROMPT).read_text()

    messages = [
        SystemMessage(content=fixer_prompt),
        HumanMessage(content=(
            f"Apply each of the following proof proposals to the workspace file "
            f"at `{workspace_path}`. For each proposal:\n\n"
            f"1. Call `search_replace_workspace` with the old_str and new_str.\n"
            f"2. Call `lean_diagnostic_messages` on the file to verify it compiles.\n"
            f"3. If there are errors, fix them with additional search-replace calls.\n"
            f"4. If UNFIXABLE, skip that lemma and move to the next.\n\n"
            f"Process ALL proposals. When you are done, stop making tool calls.\n\n"
            f"--- Proposals ---\n\n{proposals_text}"
        )),
    ]

    for turn in range(1, max_turns + 1):
        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            print(f"   ⚠️  Aggregator LLM error on turn {turn}: {e}")
            break

        print_ai_response("AG", response)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            print(f"   ✅ Aggregator LLM finished after {turn} turn(s)")
            break

        for tc in tool_calls:
            try:
                tool_fn = {t.name: t for t in all_tools}.get(tc["name"])
                if tool_fn:
                    result = await tool_fn.ainvoke(tc.get("args", {}))
                    messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
            except Exception as e:
                messages.append(ToolMessage(content=f"Tool error: {e}", tool_call_id=tc["id"]))
    else:
        print(f"   ⏰ Aggregator: hit turn limit ({max_turns})")

    # Rebuild blueprint JSON — roll back on failure
    try:
        result = subprocess.run(
            ["lake", "build", ":blueprintJson"],
            cwd=state.project_root,
            capture_output=True, text=True, timeout=600,
        )
    except Exception as e:
        print(f"   ⚠️  Blueprint build error: {e}")
        Path(workspace_path).write_text(original_content)
        return {
            "global_round": new_round, "pending_proposals": [],
            "lemma_statuses": dict(state.lemma_statuses),
        }

    if result.returncode != 0:
        print(f"   ⚠️  Blueprint build FAILED — full rollback to original")
        print(f"   {result.stderr[:400]}")
        Path(workspace_path).write_text(original_content)
        updated = dict(state.lemma_statuses)
        for prop in state.pending_proposals:
            name = prop["lemma_id"]
            if name and name in updated:
                updated[name] = {
                    **updated[name],
                    "status": "unproved",
                    "feedback": f"Build failed: {result.stderr[:300]}",
                }
        return {
            "global_round": new_round, "pending_proposals": [],
            "lemma_statuses": updated,
        }

    # Build succeeded — derive fresh statuses
    bp_json = load_blueprint_json(state.project_root)
    fresh_statuses = derive_lemma_statuses(bp_json)
    # Carry forward feedback for any lemmas that the JSON says are still sorry
    old_feedback = {
        name: ls.get("feedback", "")
        for name, ls in state.lemma_statuses.items()
    }
    for name, ls in fresh_statuses.items():
        if not ls["sorry_free"] and name in old_feedback:
            fresh_statuses[name] = {**ls, "feedback": old_feedback[name]}

    lemma_tasks = blueprint_to_tasks(bp_json)
    proved_count = sum(1 for ls in fresh_statuses.values() if ls["status"] == "proved")
    print(f"   📊 Blueprint JSON: {len(fresh_statuses)} lemmas, {proved_count} proved")
    return {
        "global_round": new_round, "pending_proposals": [],
        "lemma_statuses": fresh_statuses, "lemma_tasks": lemma_tasks,
        "blueprint": bp_json,
    }
