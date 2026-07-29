"""
Lemma proving node (Map) — proves a single lemma via an isolated MCP REPL client.
Dispatched in parallel via `Send` from `theorem_proving`.


Possible future improvements:
- A function that checks for Lean File validity alongside LLM-as-Judge
(we want this function to check for sorry's, sorry_using, and axioms.
Basically any escape helper that the LLM could use to escape a proof)
"""

from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from config import THEOREM_PROVER_PROMPT, MODEL_NAME, MODEL_TIMEOUT, MAX_TURNS_PER_LEMMA
from state import State, Context
from mcp_client import create_lean_mcp_client
from nodes._utils import print_ai_response
from validation import is_valid_lean_proof


async def prove_lemma(state: State, runtime: Runtime[Context]):
    """Map node — proves a single lemma using its own isolated MCP REPL client.
    Receives lemma_task + lemma_decl_text from theorem_proving via Send."""
    # Unpack (state is a plain dict from Send)
    task = state.get("lemma_task")
    if task is None:
        print("   ⚠️  prove_lemma: no lemma_task in state, returning empty proposal.")
        return {
            "pending_proposals": [{
                "lemma_id": "", "old_str": "", "new_str": None,
                "proved": False, "feedback": "missing lemma_task",
            }]
        }

    name = task["name"]
    decl_text = state.get("lemma_decl_text", "")
    project_root = state.get("project_root", str(Path.cwd()))
    max_turns = runtime.context.get("max_turns_per_lemma", MAX_TURNS_PER_LEMMA)
    model_name = runtime.context.get("model", MODEL_NAME)

    print(f"\n{'=' * 60}")
    print(f"🔍 PROVE LEMMA: {name}  (max {max_turns} turns)")
    print(f"{'=' * 60}\n")

    # Spin up isolated MCP client in proof-only mode
    try:
        disabled_tools = [
            "lean_file_outline",
            "lean_diagnostic_messages",
            "lean_goal",
            "lean_term_goal",
            "lean_hover_info",
            "lean_declaration_file",
            "lean_references",
            "lean_completions",
            "lean_get_widgets",
            "lean_get_widget_source",
            "lean_build",
        ]
        agent_client = create_lean_mcp_client(disabled_tools=disabled_tools)
        lean_tools = await agent_client.get_tools()
        print(f"   🔌 MCP client ready for lemma '{name}' (proof-only mode)")

        # Set up LLM with only the allowed MCP tools
        theorem_prompt = Path(THEOREM_PROVER_PROMPT).read_text()
        llm = init_chat_model(model_name, timeout=MODEL_TIMEOUT)
        llm_with_tools = llm.bind_tools(lean_tools)

        deps_str = ', '.join(task['dependencies']) if task['dependencies'] else 'none'
        sketch = task.get('proof_sketch') or 'none'
        messages = [
            SystemMessage(content=theorem_prompt),
            HumanMessage(content=(
                f"You are assigned to prove the following lemma.\n\n"
                f"**Lemma name:** {name}\n"
                f"**Dependencies (already proved):** {deps_str}\n"
                f"**Proof sketch (if any):** {sketch}\n\n"
                f"**Current declaration in the file (you must replace the sorry_using body):**\n"
                f"```lean\n{decl_text}\n```\n\n"
            )),
        ]

        # Turn loop (bounded by max_turns)
        for turn in range(1, max_turns + 1):
            try:
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
                print(f"   ❌ LLM error on turn {turn}: {e}")
                break

            print_ai_response(f"PL-{name}", response)
            messages.append(response)

            # Did the LLM return a proof (no tool calls, no sorry)?
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls and hasattr(response, "content") and response.content:
                content = str(response.content)
                no_sorry = "sorry" not in content.lower() and "sorry_using" not in content.lower()
                if no_sorry:
                    if not is_valid_lean_proof(content):
                        print(f"   ⚠️  Lemma '{name}': content is natural language, not Lean code — rejected")
                        messages.append(HumanMessage(content=(
                            "Your last response was natural language, not valid Lean code. "
                            "You MUST return ONLY the Lean declaration with the proof body "
                            "(e.g., `theorem foo ... := by ...`). Do not wrap in explanations, "
                            "do not use markdown code fences, do not add commentary. "
                            "Just the raw Lean code."
                        )))
                        continue
                    print(f"   ✅ Lemma '{name}' appears proved (turn {turn})")
                    return {
                        "pending_proposals": [{
                            "lemma_id": name, "old_str": decl_text,
                            "new_str": content, "proved": True,
                            "feedback": "",
                        }]
                    }

            # Execute tool calls against the agent's own MCP client
            if tool_calls:
                for tc in tool_calls:
                    try:
                        tool_name = tc["name"]
                        tool_args = tc.get("args", {})
                        tool_fn = {t.name: t for t in lean_tools}.get(tool_name)
                        if tool_fn:
                            result = await tool_fn.ainvoke(tool_args)
                            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                    except Exception as e:
                        messages.append(ToolMessage(content=f"Tool error: {e}", tool_call_id=tc["id"]))

        # Turn limit exhausted — return failure proposal
        feedback = f"Agent exhausted {max_turns} turns without completing the proof."
        print(f"   ⏰ Lemma '{name}': turn limit ({max_turns}) reached")
        return {
            "pending_proposals": [{
                "lemma_id": name, "old_str": decl_text, "new_str": None,
                "proved": False, "feedback": feedback,
            }]
        }

    except Exception as e:
        print(f"   ❌ Failed to start MCP client for '{name}': {e}")
        return {
            "pending_proposals": [{
                "lemma_id": name, "old_str": decl_text, "new_str": None,
                "proved": False, "feedback": f"MCP start error: {e}",
            }]
        }
