"""LangGraph single-node graph template.

Returns a predefined response. Replace logic and configuration as needed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Annotated
from typing_extensions import TypedDict

#LangGraph Imports
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt, Send
from langgraph.prebuilt import ToolNode

#Langsmith imports
from langsmith import traceable
 
#LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient 
from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage, ToolMessage


import os
import asyncio
import json
import operator
import uuid

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from mathlib_doc_tools import doc_tools

from blueprint_converter import (
    LemmaTask, LemmaStatus, ProofProposal,
    blueprint_to_tasks, load_blueprint_json, derive_lemma_statuses,
)

### FILESYSTEM TOOLS

PROJECT_ROOT = Path("/Users/amirnabiyev/Conjecture_Prover").resolve()

config = { "configurable": {"thread_id": str(uuid.uuid4())} }


@tool
def read_workspace(workspace_path: str) -> str:
    """Read and return the full contents of the Lean workspace file.

    Use this before editing to understand the current
    state of the file, or to inspect the blueprint declarations,
    theorem statements, and existing proofs.

    The path can be absolute or relative to the project root.
    """
    path = Path(workspace_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.read_text(encoding="utf-8")


@tool
def write_workspace(workspace_path: str, content: str) -> str:
    """Overwrite the entire Lean workspace file with the given content.

    Use this when you need to replace the whole file,
    for example after generating a new blueprint skeleton or
    applying a completed proof. The file will be completely
    overwritten — ensure your content includes all existing
    declarations that should be preserved.

    The path can be absolute or relative to the project root.
    """
    path = Path(workspace_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


@tool
def search_replace_workspace(relative_path: str, old_string: str, new_string: str) -> str:
    """Replace exactly one occurrence of `old_string` in a workspace file with `new_string`.

    Use this for targeted edits — replacing a lemma body, fixing a single line,
    or inserting new declarations relative to existing ones.
    `old_string` must appear exactly once in the file, or the operation is rejected
    to avoid ambiguity. The path is relative to the project root.
    """
    path = (PROJECT_ROOT / relative_path).resolve()

    if not path.is_relative_to(PROJECT_ROOT):
        return "ERROR: path outside workspace"

    if not path.is_file():
        return f"ERROR: file not found: {relative_path}"

    content = path.read_text(encoding="utf-8")

    count = content.count(old_string)
    if count == 0:
        return "ERROR: old_string not found"
    if count > 1:
        return "ERROR: old_string appears multiple times"

    updated = content.replace(old_string, new_string)
    path.write_text(updated, encoding="utf-8")

    return (
        f"Replaced 1 occurrence in {relative_path} "
        f"({len(old_string)} → {len(new_string)} chars)"
    )


@tool
def list_directory(path: str) -> str:
    """List the contents of a directory.

    Use this to explore the project structure, find
    related Lean files, locate the blueprint directory,
    or check what build artifacts exist. Returns one
    entry per line; directories are suffixed with '/'.
    """
    p = Path(path)
    if not p.is_dir():
        return f"ERROR: {path} is not a directory"
    entries = []
    for child in sorted(p.iterdir()):
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{child.name}{suffix}")
    return "\n".join(entries) if entries else "(empty)"


@tool
def create_file(file_path: str, content: str) -> str:
    """Create a new file at the given path with the given content.

    WARNING: Only use this if you are 100% sure the file is needed.
    Most files already exist in the project — prefer `read_workspace`,
    `write_workspace`, or `search_replace_workspace` for existing files.
    Use `list_directory` first to confirm the file does not already exist.
    The parent directory must already exist.
    """
    path = Path(file_path)
    if path.exists():
        return f"ERROR: {file_path} already exists — use write_workspace to modify it"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Created {file_path} ({len(content)} characters)"

@tool
def ask_human(question: str) -> str:
    """Ask the human a clarifying question when you need more information
    to proceed. Use this whenever you're unsure, need a decision from the
    user, or are missing required information."""
    answer = interrupt(question)
    return str(answer)


@tool
def build_blueprint_json() -> str:
    """Run `lake build :blueprintJson` to regenerate the blueprint dependency graph JSON.

    Call this AFTER writing a blueprint file and verifying it compiles cleanly.
    This regenerates `.lake/build/blueprint/module/LeanWorkspace.json` with the
    latest dependency edges from `@[blueprint]` annotations and `sorry_using [...]`.

    The JSON file contains the full dependency graph used by the blueprint web
    visualization (HTML + dependency graph). Always call this before handing back
    to ensure the blueprint is up to date.
    """
    import subprocess
    result = subprocess.run(
        ["lake", "build", ":blueprintJson"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode != 0:
        return f"ERROR: lake build :blueprintJson failed (exit {result.returncode}):\n{err[:2000]}"
    return f"✅ blueprint JSON regenerated successfully.\n{out[:500]}" if out else "✅ blueprint JSON regenerated successfully."


file_tools = [read_workspace, write_workspace, search_replace_workspace,
              create_file, list_directory, build_blueprint_json]
human_tools = [ask_human]
# @traceable(
#     run_type="llm",
#     name="DeepSeek Chat Completion",
#     metadata={"ls_provider": "deepseek", "ls_model_name": "deepseek-v4-flash"},
# )
client = MultiServerMCPClient({
        "lean": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["lean-lsp-mcp"],
            "env":{
                "LEAN_PROJECT_PATH":"/Users/amirnabiyev/Conjecture_Prover",
                "LEAN_REPL":"true",
            }
        }
    })
class Context(TypedDict):
    """Context parameters for the agent.
    Set these when creating assistants OR when invoking the graph.
    See: https://langchain-ai.github.io/langgraph/cloud/how-tos/configuration_cloud/
    """

    model: str = "deepseek-chat"  # e.g. "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"
    max_iterations: int = 16
    max_turns_per_lemma: int = 30          # per-agent turn limit


def _reset_or_add(old: list, new: list) -> list:
    """Reducer for pending_proposals: parallel provers add via concat (old + new).
    When the aggregator returns [] (empty list), it signals reset → clear the accumulator."""
    if not new:
        return []
    return old + new


### STATE DECLARATION
@dataclass
class State:
    """Input state for the agent."""
    theorem: str = ""
    workspacePATH: str = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace.lean"
    blueprint_generator_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    blueprint_refiner_messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    active_node: str = "blueprint_gen"
    project_root: str = "/Users/amirnabiyev/Conjecture_Prover"

    # Blueprint JSON as source of truth — populated after first lake build
    blueprint: list[dict] = field(default_factory=list)
    lemma_tasks: list[LemmaTask] = field(default_factory=list)

    # Lemma statuses — derived fresh each aggregator round from blueprint JSON
    lemma_statuses: dict[str, LemmaStatus] = field(default_factory=dict)

    # Fan-in accumulator for proof proposals from parallel provers.
    # Uses custom reducer: parallel Send tasks concat (old + new), aggregator
    # returns [] to reset for the next round.
    pending_proposals: Annotated[list[ProofProposal], _reset_or_add] = field(default_factory=list)

    # Round / budget tracking
    global_round: int = 0

    # Transient fields set by theorem_proving for prove_lemma nodes
    lemma_task: LemmaTask | None = None
    lemma_decl_text: str = ""

### NODE DECLARATION


_lean_tools = None
human_tool_node_bp = ToolNode(human_tools, messages_key="blueprint_generator_messages")
human_tool_node_br = ToolNode(human_tools, messages_key="blueprint_refiner_messages")


async def get_lean_tools():
    global _lean_tools
    if _lean_tools is None:
        _lean_tools = await client.get_tools()
    return _lean_tools


async def blueprint_generator(state: State, runtime: Runtime[Context]):
    """LLM node — decomposes the theorem into a @[blueprint]-annotated Lean skeleton.
    Uses file_tools + lean_tools + doc_tools + human_tools."""

    print("\n" + "="*70)
    print("📋 BLUEPRINT GENERATOR: Decomposing theorem into dependency graph...")
    print("="*70 + "\n")

    # ── 1. Load prompt & model ─────────────────────────────────────────────

    prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name, timeout=120)

    lean_tools = await get_lean_tools()
    llm_with_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

    # ── 2. First turn: seed with system prompt + theorem ────────────────────

    if not state.blueprint_generator_messages:
        seed_msg = [
            SystemMessage(content=prompt),
            HumanMessage(content=(
                state.theorem + "\n\n"
                "Workspace file: " + state.workspacePATH + "\n\n"
                "Project Root: " + state.project_root
            )),
        ]
        response = await llm_with_tools.ainvoke(seed_msg)
        _print_ai_response("BP", response)
        return {"blueprint_generator_messages": seed_msg + [response],
                "active_node": "blueprint_gen"}

    # ── 3. Subsequent turns: continue conversation ──────────────────────────

    response = await llm_with_tools.ainvoke(state.blueprint_generator_messages)
    _print_ai_response("BP", response)
    return {"blueprint_generator_messages": [response],
            "active_node": "blueprint_gen"}

async def blueprint_refiner(state: State, runtime: Runtime[Context]):
    """LLM node — decomposes unproved lemmas into simpler sub-lemmas.
    Receives the full dependency graph + prover feedback."""

    # ── 1. Print diagnostics ───────────────────────────────────────────────

    print("\n" + "="*70)
    print("🔧 BLUEPRINT REFINER: Revising blueprint based on prover feedback...")
    unproved = [name for name, ls in state.lemma_statuses.items()
                if ls["status"] != "proved"]
    if unproved:
        print(f"   Unproved lemmas to address: {', '.join(sorted(unproved))}")
        for name in unproved:
            fb = state.lemma_statuses.get(name, {}).get("feedback", "")
            if fb:
                print(f"     • {name}: {fb[:120]}...")
    print("="*70 + "\n")

    # ── 2. Load model & tools ──────────────────────────────────────────────

    prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_refiner.md").read_text()
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name, timeout=120)

    lean_tools = await get_lean_tools()
    llm_with_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

    # ── 3. Build context: full dependency graph + prover feedback ───────────

    bp_json_str = json.dumps(state.blueprint, indent=2) if state.blueprint else "(no blueprint loaded)"
    proved_names = [name for name, ls in state.lemma_statuses.items() if ls["status"] == "proved"]
    unproved_summary = "\n".join(
        f"- **{name}** (depends on: {', '.join(state.lemma_statuses.get(name, {}).get('dependencies', []))}): "
        f"{state.lemma_statuses.get(name, {}).get('feedback', 'no feedback')}"
        for name in unproved
    ) if unproved else ""

    # ── 4. First turn: seed with system prompt + context ────────────────────

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
        _print_ai_response("BR", response)
        return {"blueprint_refiner_messages": seed_msg + [response],
                "active_node": "blueprint_refiner"}

    # ── 5. Subsequent turns: continue conversation ──────────────────────────

    response = await llm_with_tools.ainvoke(state.blueprint_refiner_messages)
    _print_ai_response("BR", response)
    return {"blueprint_refiner_messages": [response],
            "active_node": "blueprint_refiner"}


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregator (Reduce node) — LLM-driven edit application + verification
# ═══════════════════════════════════════════════════════════════════════════════

async def aggregator(state: State, runtime: Runtime[Context]):
    """Reduce node — gives all proposals to an LLM agent which applies them via
    search_replace_workspace and verifies with lean_diagnostic_messages.
    After the LLM finishes, rebuilds blueprint JSON (rollback on failure)."""

    # ── 1. Setup ────────────────────────────────────────────────────────────

    print("\n" + "="*70)
    print(f"📦 AGGREGATOR: Applying proofs (round {state.global_round + 1})")
    print(f"   Received {len(state.pending_proposals)} proposal(s)")
    print("="*70 + "\n")

    new_round = state.global_round + 1
    workspace_path = state.workspacePATH
    model_name = runtime.context.get("model", "deepseek-chat")
    max_turns = runtime.context.get("max_turns_per_lemma", 30)

    # ── 2. Save original for full rollback ──────────────────────────────────

    try:
        original_content = Path(workspace_path).read_text()
    except Exception as e:
        print(f"   ❌ Failed to read workspace: {e}")
        return {"global_round": new_round, "pending_proposals": [],
                "lemma_statuses": dict(state.lemma_statuses)}

    # ── 3. Spin up MCP client (for lean diagnostics) ────────────────────────

    try:
        async with MultiServerMCPClient({
            "lean": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["lean-lsp-mcp"],
                "env": {
                    "LEAN_PROJECT_PATH": state.project_root,
                    "LEAN_REPL": "true",
                }
            }
        }) as mcp_client:
            lean_tools = await mcp_client.get_tools()
    except Exception as e:
        print(f"   ❌ Aggregator MCP start failed: {e}")
        return {"global_round": new_round, "pending_proposals": [],
                "lemma_statuses": dict(state.lemma_statuses)}

    # ── 4. Build proposal list for the LLM ──────────────────────────────────

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
        return {"global_round": new_round, "pending_proposals": [],
                "lemma_statuses": dict(state.lemma_statuses)}

    proposals_text = "\n".join(proposal_lines)

    # ── 5. LLM agent: apply edits, check diagnostics, fix ───────────────────

    llm = init_chat_model(model_name, timeout=120)
    all_tools = lean_tools + file_tools
    llm_with_tools = llm.bind_tools(all_tools)

    fixer_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/aggregator_fixer.md").read_text()

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

        _print_ai_response("AG", response)
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

    # ── 6. Rebuild blueprint JSON — roll back on failure ────────────────────

    try:
        import subprocess
        result = subprocess.run(
            ["lake", "build", ":blueprintJson"],
            cwd=state.project_root,
            capture_output=True, text=True, timeout=600,
        )
    except Exception as e:
        print(f"   ⚠️  Blueprint build error: {e}")
        Path(workspace_path).write_text(original_content)
        return {"global_round": new_round, "pending_proposals": [],
                "lemma_statuses": dict(state.lemma_statuses)}

    if result.returncode != 0:
        print(f"   ⚠️  Blueprint build FAILED — full rollback to original")
        print(f"   {result.stderr[:400]}")
        Path(workspace_path).write_text(original_content)
        updated = dict(state.lemma_statuses)
        for prop in state.pending_proposals:
            name = prop["lemma_id"]
            if name and name in updated:
                updated[name] = {**updated[name], "status": "unproved",
                                 "feedback": f"Build failed: {result.stderr[:300]}"}
        return {"global_round": new_round, "pending_proposals": [],
                "lemma_statuses": updated}

    # ── Build succeeded — derive fresh statuses ─────────────────────────────

    bp_json = load_blueprint_json(state.project_root)
    fresh_statuses = derive_lemma_statuses(bp_json)
    # Carry forward feedback for any lemmas that the JSON says are still sorry
    old_feedback = {name: ls.get("feedback", "")
                    for name, ls in state.lemma_statuses.items()}
    for name, ls in fresh_statuses.items():
        if not ls["sorry_free"] and name in old_feedback:
            fresh_statuses[name] = {**ls, "feedback": old_feedback[name]}

    lemma_tasks = blueprint_to_tasks(bp_json)
    proved_count = sum(1 for ls in fresh_statuses.values() if ls["status"] == "proved")
    print(f"   📊 Blueprint JSON: {len(fresh_statuses)} lemmas, {proved_count} proved")
    return {"global_round": new_round, "pending_proposals": [],
            "lemma_statuses": fresh_statuses, "lemma_tasks": lemma_tasks,
            "blueprint": bp_json}


# ═══════════════════════════════════════════════════════════════════════════════
# Fan-out routing (Send dispatcher)
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# Theorem Proving (fan-out dispatcher via Send)
# ═══════════════════════════════════════════════════════════════════════════════

def theorem_proving(state: State) -> list[Send]:
    """Read the file once, splice each unproved lemma by line range, dispatch all
    in parallel via Send."""

    # ── 1. Collect unproved lemma names ─────────────────────────────────────

    unproved_names = {name for name, ls in state.lemma_statuses.items()
                      if ls["status"] == "unproved"}
    if not unproved_names:
        print("   🚦 theorem_proving: no unproved lemmas → routing to aggregator")
        return []

    # ── 2. Read file, split by lines ────────────────────────────────────────

    try:
        file_path = Path(state.workspacePATH)
        file_content = file_path.read_text()
        lines = file_content.splitlines(keepends=True)
    except Exception as e:
        print(f"   ❌ theorem_proving: failed to read file: {e}")
        return []

    # ── 3. Splice each unproved lemma by line range, build Send list ────────

    sends = []
    for task in state.lemma_tasks:
        name = task["name"]
        if name not in unproved_names:
            continue
        try:
            decl_text = "".join(lines[task["start_line"] - 1 : task["end_line"]])
        except (IndexError, KeyError):
            print(f"   ⚠️  Could not extract '{name}' by line range — skipping")
            continue
        sends.append(Send("prove_lemma", {
            "lemma_task": task,
            "lemma_decl_text": decl_text,
            "active_node": "prove_lemma",
        }))

    # ── 4. Dispatch ─────────────────────────────────────────────────────────

    print(f"   🚀 theorem_proving: dispatching {len(sends)} parallel agent(s)")
    for s in sends:
        print(f"      → {s.arg['lemma_task']['name']}")
    return sends


def route_after_aggregator(state: State) -> str:
    """After aggregator: route to refiner if any unproved and rounds remain, else END."""
    MAX_ROUNDS = 16   # safety ceiling — prevents infinite refinement loops
    if state.global_round >= MAX_ROUNDS:
        print(f"   🚦 Route: aggregator → END (reached max {MAX_ROUNDS} rounds)")
        return END
    if any(ls["status"] != "proved" for ls in state.lemma_statuses.values()):
        print(f"   🚦 Route: aggregator → blueprint_refiner (round {state.global_round})")
        return "blueprint_refiner"
    print(f"   🚦 Route: aggregator → END (all lemmas proved)")
    return END


# ═══════════════════════════════════════════════════════════════════════════════
# Lemma Prover (Map node) — proves one lemma per invocation
# ═══════════════════════════════════════════════════════════════════════════════

async def prove_lemma(state: State, runtime: Runtime[Context]):
    """Map node — proves a single lemma using its own isolated MCP REPL client.
    Receives lemma_task + lemma_decl_text from theorem_proving via Send."""

    # ── 1. Unpack (state is a plain dict from Send) ─────────────────────────

    task = state.get("lemma_task")
    if task is None:
        print("   ⚠️  prove_lemma: no lemma_task in state, returning empty proposal.")
        return {"pending_proposals": [{"lemma_id": "", "old_str": "", "new_str": None,
                                        "proved": False, "feedback": "missing lemma_task"}]}

    name = task["name"]
    decl_text = state.get("lemma_decl_text", "")
    project_root = state.get("project_root", "/Users/amirnabiyev/Conjecture_Prover")
    workspace_path = state.get("workspacePATH", "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace.lean")
    max_turns = runtime.context.get("max_turns_per_lemma", 30)
    model_name = runtime.context.get("model", "deepseek-chat")

    print(f"\n{'='*60}")
    print(f"🔍 PROVE LEMMA: {name}  (max {max_turns} turns)")
    print(f"{'='*60}\n")

    # ── 2. Spin up isolated MCP client ──────────────────────────────────────

    try:
        async with MultiServerMCPClient({
            "lean": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["lean-lsp-mcp"],
                "env": {
                    "LEAN_PROJECT_PATH": project_root,
                    "LEAN_REPL": "true",
                }
            }
        }) as agent_client:
            lean_tools = await agent_client.get_tools()
            print(f"   🔌 MCP client ready for lemma '{name}' ({len(lean_tools)} tools)")

            # ── 3. Set up LLM with Lean-only tools ──────────────────────────

            theorem_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/theorem_prover.md").read_text()
            llm = init_chat_model(model_name, timeout=120)
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
                    f"Workspace file: {workspace_path}\n"
                    f"Project root: {project_root}\n\n"
                    f"Use the Lean REPL tools to inspect the goal, try tactics, and get diagnostics. "
                    f"When you have a complete proof, return the full lemma declaration with the "
                    f"proof body replacing \"sorry_using [...]\" or \"sorry\". "
                    f"If you cannot complete the proof within your turn budget, report what you "
                    f"tried and the remaining goal state."
                )),
            ]

            # ── 4. Turn loop (bounded by max_turns) ─────────────────────────

            for turn in range(1, max_turns + 1):
                try:
                    response = await llm_with_tools.ainvoke(messages)
                except Exception as e:
                    print(f"   ❌ LLM error on turn {turn}: {e}")
                    break

                _print_ai_response(f"PL-{name}", response)
                messages.append(response)

                # ── 4a. Did the LLM return a proof (no tool calls, no sorry)? ──

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls and hasattr(response, "content") and response.content:
                    content = str(response.content)
                    if "sorry" not in content.lower() and "sorry_using" not in content.lower():
                        print(f"   ✅ Lemma '{name}' appears proved (turn {turn})")
                        return {"pending_proposals": [{"lemma_id": name, "old_str": decl_text,
                                                        "new_str": content, "proved": True,
                                                        "feedback": ""}]}

                # ── 4b. Execute tool calls against the agent's own MCP client ───

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

            # ── 5. Turn limit exhausted — return failure proposal ───────────

            feedback = f"Agent exhausted {max_turns} turns without completing the proof."
            print(f"   ⏰ Lemma '{name}': turn limit ({max_turns}) reached")
            return {"pending_proposals": [{"lemma_id": name, "old_str": decl_text, "new_str": None,
                                            "proved": False, "feedback": feedback}]}

    except Exception as e:
        print(f"   ❌ Failed to start MCP client for '{name}': {e}")
        return {"pending_proposals": [{"lemma_id": name, "old_str": decl_text, "new_str": None,
                                        "proved": False, "feedback": f"MCP start error: {e}"}]}


# ═══════════════════════════════════════════════════════════════════════════════
# Routing helpers
# ═══════════════════════════════════════════════════════════════════════════════

def route_tool_calls(state: State, key: str) -> str:
    """Route tool calls to the matching dedicated ToolNode."""
    suffixes = {
        "blueprint_generator_messages": "bp",
        "blueprint_refiner_messages": "br",
    }
    suffix = suffixes.get(key)
    if suffix is None:
        return END

    msgs = getattr(state, key)
    if not msgs:
        return END
    msg = msgs[-1]
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return END

    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return f"human_tool_{suffix}"
    return f"tools_{suffix}"


# ──────────────────────────────────────────────────────────────────────────────
# Per-node routing functions
# ──────────────────────────────────────────────────────────────────────────────

def route_from_blueprint(state: State):
    """After blueprint_gen: route to tools/human, or rebuild + dispatch theorem_proving.
    Never routes to theorem_proving directly — blueprint JSON must be loaded first."""
    dest = route_tool_calls(state, "blueprint_generator_messages")
    if dest != END:
        print(f"   🚦 Routing: blueprint_gen → {dest}")
        return dest
    # No tool calls — rebuild blueprint JSON into state before fanning out
    print(f"   🚦 Routing: blueprint_gen → rebuild_blueprint (first pass)")
    return "rebuild_blueprint"


def route_from_refiner(state: State):
    """After blueprint_refiner: route to tools/human or to rebuild_blueprint."""
    dest = route_tool_calls(state, "blueprint_refiner_messages")
    if dest != END:
        print(f"   🚦 Routing: blueprint_refiner → {dest}")
        return dest
    # No tool calls — rebuild blueprint state before fanning out
    print(f"   🚦 Routing: blueprint_refiner → rebuild_blueprint")
    return "rebuild_blueprint"


# ═══════════════════════════════════════════════════════════════════════════════
# Blueprint state rebuild (post-refiner bridge)
# ═══════════════════════════════════════════════════════════════════════════════

async def rebuild_blueprint(state: State) -> dict:
    """Rebuild blueprint JSON and derive fresh lemma_statuses/lemma_tasks.
    Called after the refiner finishes writing to the file."""

    print("\n🔄 REBUILD BLUEPRINT: Refreshing blueprint state from JSON...")

    try:
        bp_json = load_blueprint_json(state.project_root)
        fresh_tasks = blueprint_to_tasks(bp_json)
        fresh_statuses = derive_lemma_statuses(bp_json)
        proved_count = sum(1 for ls in fresh_statuses.values() if ls["status"] == "proved")
        print(f"   📊 {len(fresh_statuses)} lemmas, {proved_count} proved")
        return {"blueprint": bp_json, "lemma_tasks": fresh_tasks,
                "lemma_statuses": fresh_statuses, "active_node": "rebuild_blueprint"}
    except Exception as e:
        print(f"   ⚠️  Blueprint rebuild failed: {e}")
        return {"active_node": "rebuild_blueprint"}


def route_after_rebuild(state: State):
    """After rebuild_blueprint: always dispatch theorem_proving, never skip to aggregator."""
    print(f"   🚦 Routing: rebuild_blueprint → theorem_proving")
    return theorem_proving(state)


# ──────────────────────────────────────────────────────────────────────────────
# Tool-loop routing & printing
# ──────────────────────────────────────────────────────────────────────────────

def route_from_tools(state: State):
    """After tool node: route back to whichever LLM node called it."""
    result = state.active_node if state.active_node else "blueprint_gen"
    print(f"   🚦 Routing: tool_node → {result}")
    return result


def _print_ai_response(label: str, msg: AnyMessage):
    """Print the AI's response content and any tool calls."""
    if hasattr(msg, "content") and msg.content:
        content = str(msg.content)
        if content.strip():
            print(f"   💬 {label} AI says: {content[:500]}")
            if len(content) > 500:
                print(f"      ... ({len(content)} total chars)")
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        print(f"   🛠️  {label} AI made {len(tool_calls)} tool call(s):")
        for tc in tool_calls:
            print(f"      → {tc['name']}")


async def build_graph():
    lean_tools = await get_lean_tools()
    bp_all_tools = file_tools + lean_tools + doc_tools
    br_all_tools = file_tools + lean_tools + doc_tools

    # ToolNodes for blueprint_generator and blueprint_refiner
    tools_bp = ToolNode(bp_all_tools, messages_key="blueprint_generator_messages")
    tools_br = ToolNode(br_all_tools, messages_key="blueprint_refiner_messages")

    builder = StateGraph(State, context_schema=Context)

    # Nodes 
    builder.add_node("blueprint_gen", blueprint_generator)
    builder.add_node("blueprint_refiner", blueprint_refiner)
    builder.add_node("tools_bp", tools_bp)
    builder.add_node("human_tool_bp", human_tool_node_bp)
    builder.add_node("tools_br", tools_br)
    builder.add_node("human_tool_br", human_tool_node_br)

    # Map-Reduce nodes
    builder.add_node("prove_lemma", prove_lemma)
    builder.add_node("aggregator", aggregator)
    builder.add_node("rebuild_blueprint", rebuild_blueprint)

    # Edges 
    builder.add_edge(START, "blueprint_gen")
    # route_from_blueprint returns string (tool/human) or list[Send] (fan-out)
    builder.add_conditional_edges("blueprint_gen", route_from_blueprint)
    builder.add_conditional_edges("blueprint_refiner", route_from_refiner)

    # Tool → LLM loops
    for tool_node_name in ("tools_bp", "human_tool_bp"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_gen": "blueprint_gen"}
        )
    for tool_node_name in ("tools_br", "human_tool_br"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_refiner": "blueprint_refiner"}
        )

    # Rebuild → fan_out or aggregator
    builder.add_conditional_edges("rebuild_blueprint", route_after_rebuild)

    # Map-Reduce flow: prove_lemma → aggregator
    builder.add_edge("prove_lemma", "aggregator")

    # Aggregator → refiner | END | interrupt
    builder.add_conditional_edges(
        "aggregator", route_after_aggregator,
        {"blueprint_refiner": "blueprint_refiner", END: END}
    )

    checkpointer = MemorySaver()
    graph = builder.compile(name="Conjecture Prover Graph", checkpointer=checkpointer)
    return graph





# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Build the graph and invoke it. Handles human-in-the-loop via interrupt."""

    # ── 1. Read the theorem from the workspace file ─────────────────────────

    workspace_path = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace.lean"
    try:
        ws_content = Path(workspace_path).read_text()
        # Extract the main theorem name as a rough identifier
        theorem_ident = "theorem in LeanWorkspace.lean"
        for line in ws_content.splitlines():
            if "theorem" in line or "conjecture" in line:
                theorem_ident = line.strip()[:120]
                break
    except Exception:
        theorem_ident = "theorem in LeanWorkspace.lean"

    # ── 2. Build graph ─────────────────────────────────────────────────────

    graph = await build_graph()

    # ── 3. Initial invocation ──────────────────────────────────────────────

    result = await graph.ainvoke(
        {"theorem": theorem_ident, "workspacePATH": workspace_path},
        context={"model": "deepseek-chat"},
        config=config,
    )

    # ── 4. Handle interrupt/resume cycles (human-in-the-loop) ───────────────

    while interrupt_val := result.get("__interrupt__"):
        print(f"\n--- GRAPH PAUSED ---")
        print(f"Question: {interrupt_val[0].value}")
        answer = input("Your response: ")
        result = await graph.ainvoke(
            Command(resume=answer),
            context={"model": "deepseek-chat"},
            config=config,
        )


if __name__ == "__main__":
    asyncio.run(main())
    
