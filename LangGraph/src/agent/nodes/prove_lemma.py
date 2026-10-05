"""
Lemma proving node (Map) — proves a single lemma via an isolated MCP REPL client.
Dispatched in parallel via `Send` from `theorem_proving`.


Possible future improvements:
- A function that checks for Lean File validity alongside LLM-as-Judge
(we want this function to check for sorry's, sorry_using, and axioms.
Basically any escape helper that the LLM could use to escape a proof)
"""

from pathlib import Path

from llm import init_chat_model
from langchain.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from config import THEOREM_PROVER_PROMPT, MODEL_NAME, MODEL_TIMEOUT, MAX_TURNS_PER_LEMMA
from state import State, Context

from mcp_client import create_lean_mcp_client
from mathlib_doc_tools import doc_tools
from nodes._utils import print_ai_response
from validation import is_valid_lean_proof


async def prove_lemma(state: State, runtime: Runtime[Context]):
    """Map node — proves a single lemma using its own isolated MCP REPL client.
    Receives lemma_task + lemma_decl_text from theorem_proving via Send."""

    # Helper: state may be a dict (from Send) or a State object (from direct graph call)
    def _st(key, default=None):
        return state.get(key, default) if isinstance(state, dict) else getattr(state, key, default)

    task = _st("lemma_task")
    if task is None:
        print("   ⚠️  prove_lemma: no lemma_task in state, returning empty proposal.")
        return {
            "pending_proposals": [{
                "lemma_id": "", "status": "TOO_HARD", "old_str": "", "new_str": None,
                "proved": False, "feedback": "missing lemma_task",
            }]
        }

    name = task["name"]
    decl_text = _st("lemma_decl_text", "")
    project_root = _st("project_root", str(Path.cwd()))
    max_turns = runtime.context.get("max_turns_per_lemma", MAX_TURNS_PER_LEMMA)
    model_name = runtime.context.get("model", MODEL_NAME)

    print(f"\n{'=' * 60}")
    print(f"🔍 PROVE LEMMA: {name}  (max {max_turns} turns)")
    print(f"{'=' * 60}\n")

    # Spin up isolated MCP client in proof-only mode.
    # Sessions are short-lived: `get_tools()` opens (and tears down) a fresh
    # REPL session per tool call. We deliberately do NOT hold one persistent
    # REPL for the whole lemma — a single long-lived REPL was observed to
    # exhaust memory over multi-round runs.
    llm = None
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

        # Set up LLM with MCP tools + local doc-search tools
        theorem_prompt = Path(THEOREM_PROVER_PROMPT).read_text()
        llm = init_chat_model(
            model_name, timeout=runtime.context.get("model_timeout", MODEL_TIMEOUT)
        )
        all_tools = lean_tools + doc_tools
        llm_with_tools = llm.bind_tools(all_tools)

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
        trial_log: list[str] = []  # accumulate feedback from each attempt
        for turn in range(1, max_turns + 1):
            # On the last turn the proof budget is exhausted. Do NOT let the model
            # spend it on one more proof attempt (tool calls are wasted — there is
            # no budget left to consume their results). Instead, redirect it to hand
            # back a final report: comprehensive feedback + the best declaration it
            # has, so nothing is lost when we return TOO_HARD.
            if turn == max_turns:
                messages.append(HumanMessage(content=(
                    "⏹️ FINAL TURN — your proof budget is exhausted. Stop trying to "
                    "prove the lemma.\n\n"
                    "Do NOT call any tools and do NOT attempt the proof again. "
                    "Your only remaining job is to hand back a FINAL PROPOSAL that "
                    "matches the required proof-proposal shape, EXACTLY like this:\n\n"
                    "[FINAL PROPOSAL]\n"
                    "status: VERIFIED | UNRESOLVED\n"
                    "new_str:\n"
                    "```lean\n"
                    "<best Lean declaration — the full `lemma ... := by ...`>\n"
                    "```\n"
                    "feedback:\n"
                    "[TRIAL FEEDBACK]\n"
                    "Attempted: <approaches you tried>\n"
                    "Result: <why each failed>\n"
                    "Next plan: <concrete suggestions: different decomposition, "
                    "proof strategy, or specific Mathlib lemmas>\n\n"
                    "Rules:\n"
                    "- `status: VERIFIED` means `new_str` holds a complete, correct "
                    "proof with NO `sorry`. `status: UNRESOLVED` means you could "
                    "not finish — still put your best partial declaration in "
                    "`new_str`, leaving `sorry` for unsolved subgoals; it is "
                    "recorded for reference only and will never be inserted into "
                    "the file as-is.\n"
                    "- `feedback` is the most important part — be specific about "
                    "what failed and what might work next. It guides future "
                    "attempts.\n"
                    "- If you already have a complete, verified proof, mark it "
                    "VERIFIED and return it in `new_str`."
                )))

            try:
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
                print(f"   ❌ LLM error on turn {turn}: {e}")
                trial_log.append(f"[Turn {turn}] LLM error: {e}")
                break

            print_ai_response(f"PL-{name}", response)
            messages.append(response)

            # Extract [TRIAL FEEDBACK] from ANY response (text or tool-call)
            resp_text = str(response.content) if hasattr(response, "content") and response.content else ""

            # Statement-wrong short-circuit: if the LLM concludes the statement is
            # FALSE (emits [STATEMENT_WRONG]), bail early instead of burning turns.
            if "statement_wrong" in resp_text.lower():
                trial_log.append(f"[Turn {turn}] {resp_text}")
                print(f"   ⚠️  Lemma '{name}': LLM flagged the statement as WRONG → STATEMENT_WRONG")
                return {
                    "pending_proposals": [{
                        "lemma_id": name, "status": "STATEMENT_WRONG", "old_str": decl_text,
                        "new_str": None, "proved": False,
                        "feedback": "\n".join(trial_log),
                    }]
                }

            if "[TRIAL FEEDBACK]" in resp_text:
                trial_log.append(f"[Turn {turn}] {resp_text}")

            # On the final turn the whole response is the hand-off report: capture
            # it verbatim (feedback + final declaration) so nothing is lost even if
            # it omits the [TRIAL FEEDBACK] marker or contains `sorry` placeholders.
            if turn == max_turns:
                trial_log.append(f"[Turn {turn}] FINAL REPORT:\n{resp_text}")

            # Did the LLM return a proof (no tool calls, no sorry)?
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls and hasattr(response, "content") and response.content:
                content = str(response.content)

                no_sorry = "sorry" not in content.lower() and "sorry_using" not in content.lower()
                if no_sorry:
                    if not is_valid_lean_proof(content):
                        # Natural-language response — treat as trial feedback
                        trial_log.append(f"[Turn {turn}] Thinking: {content[:300]}")
                        print(f"   ⚠️  Lemma '{name}': content is natural language, not Lean code — captured as feedback")
                        messages.append(HumanMessage(content=(
                            "Your last response was natural language, not valid Lean code. "
                            "You MUST return ONLY the Lean declaration with the proof body "
                            "(e.g., `theorem foo ... := by ...`). Do not wrap in explanations, "
                            "do not use markdown code fences, do not add commentary. "
                            "Just the raw Lean code."
                        )))
                        continue
                    print(f"   ✅ Lemma '{name}' appears proved (turn {turn})")
                    trial_log.append(f"[Turn {turn}] PROVED")
                    return {
                        "pending_proposals": [{
                            "lemma_id": name, "status": "PROVED", "old_str": decl_text,
                            "new_str": content, "proved": True,
                            "feedback": "\n".join(trial_log),
                        }]
                    }

            # Execute tool calls against the agent's own MCP client
            if tool_calls:
                for tc in tool_calls:
                    try:
                        tool_name = tc["name"]
                        tool_args = tc.get("args", {})
                        tool_fn = {t.name: t for t in all_tools}.get(tool_name)
                        if tool_fn:
                            result = await tool_fn.ainvoke(tool_args)
                            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                    except Exception as e:
                        messages.append(ToolMessage(content=f"Tool error: {e}", tool_call_id=tc["id"]))

        # Turn limit exhausted — return failure proposal
        trial_log.append(f"TOO_HARD: turn limit ({max_turns}) exceeded")
        print(f"   ⏰ Lemma '{name}': turn limit ({max_turns}) reached")
        return {
            "pending_proposals": [{
                "lemma_id": name, "status": "TOO_HARD", "old_str": decl_text, "new_str": None,
                "proved": False, "feedback": "\n".join(trial_log),
            }]
        }

    except Exception as e:
        print(f"   ❌ Failed to start MCP client for '{name}': {e}")
        return {
            "pending_proposals": [{
                "lemma_id": name, "status": "TOO_HARD", "old_str": decl_text, "new_str": None,
                "proved": False, "feedback": f"MCP start error: {e}",
            }]
        }
    finally:
        # Close the LLM's underlying httpx connection pool (AsyncOpenAI client) so
        # the transport doesn't fire callbacks after the event loop has closed.
        if llm is not None:
            try:
                root = getattr(llm, "root_async_client", None)
                inner = getattr(root, "_client", None)
                if inner is not None and hasattr(inner, "aclose"):
                    await inner.aclose()
            except Exception as e:
                print(f"   ⚠️  LLM client close failed for '{name}': {e}")
