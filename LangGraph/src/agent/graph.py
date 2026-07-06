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
from langgraph.types import Command, interrupt
from langgraph.prebuilt import ToolNode

#Langsmith imports
from langsmith import traceable
 
#LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient 
from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage, ToolMessage
from typing import Annotated as Ann


import os
import asyncio
import json
import operator

from pathlib import Path
from dotenv import load_dotenv

#OpenAI
from openai import AsyncOpenAI

load_dotenv()

from IPython.display import Image, display

from mathlib_doc_tools import doc_tools

from blueprint_converter import LemmaTask, ProofResult, blueprint_to_tasks, load_blueprint_json

### FILESYSTEM TOOLS

PROJECT_ROOT = Path("/Users/amirnabiyev/Conjecture_Prover").resolve()

config = { "configurable": {"thread_id":"11"}}


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


@tool
def mark_lemma_completed(lemma_name: str, tool_call_id: Ann[str, InjectedToolCallId]) -> Command:
    """Mark a lemma as successfully proved.

    Call this after you have written a complete proof for a lemma and verified
    it compiles. This updates the workflow state so the scheduler knows this
    lemma is done and its dependents can be unblocked.
    """
    return Command(update={
        "completed_lemmas": {lemma_name},
        "theorem_prover_messages": [ToolMessage(
            content=f"✅ Marked '{lemma_name}' as completed.",
            tool_call_id=tool_call_id,
        )],
    })


@tool
def mark_lemma_failed(lemma_name: str, tool_call_id: Ann[str, InjectedToolCallId], reason: str = "") -> Command:
    """Mark a lemma as failed (proof too hard, statement wrong, etc.).

    Call this when you cannot complete a proof and want to report it for
    blueprint refinement. The workflow scheduler will skip dependents.
    """
    return Command(update={
        "failed_lemmas": {lemma_name},
        "theorem_prover_messages": [ToolMessage(
            content=f"❌ Marked '{lemma_name}' as failed: {reason}",
            tool_call_id=tool_call_id,
        )],
    })


file_tools = [read_workspace, write_workspace, search_replace_workspace,
              create_file, list_directory, build_blueprint_json]
scheduling_tools = [mark_lemma_completed, mark_lemma_failed]
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
    token_budget : int = 1000000
    max_iterations: int = 16

### STATE DECLARATION
@dataclass
class State:
    """Input state for the agent."""
    theorem: str = ""
    workspacePATH: str = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace.lean"
    blueprint_generator_messages: Annotated[list[AnyMessage],add_messages] = field(default_factory=list)
    theorem_prover_messages: Annotated[list[AnyMessage],add_messages] = field(default_factory=list)
    active_node: str = "blueprint_gen"
    project_root: str = "/Users/amirnabiyev/Conjecture_Prover"

    # Blueprint JSON as source of truth — populated after first lake build
    blueprint: list[dict] = field(default_factory=list)
    lemma_tasks: list[LemmaTask] = field(default_factory=list)

    # Scheduling state
    completed_lemmas: Annotated[set[str], operator.or_] = field(default_factory=set)
    failed_lemmas: Annotated[set[str], operator.or_] = field(default_factory=set)
    proof_results: Annotated[list[ProofResult], operator.add] = field(default_factory=list)
    turn_count: int = 0

### NODE DECLARATION


_lean_tools = None
human_tool_node_bp = ToolNode(human_tools, messages_key="blueprint_generator_messages")
human_tool_node_tp = ToolNode(human_tools, messages_key="theorem_prover_messages")
scheduling_tool_node = ToolNode(scheduling_tools, messages_key="theorem_prover_messages")
scheduling_tool_names = {t.name for t in scheduling_tools}


async def get_lean_tools():
    global _lean_tools
    if _lean_tools is None:
        _lean_tools = await client.get_tools()
    return _lean_tools


async def blueprint_generator(state: State, runtime: Runtime[Context]):
    # blueprint generator node
    prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
    # system_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/system_prompt.md").read_text()
    # init the model
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name,timeout = 120)
    
    lean_tools = await get_lean_tools()
    llm_with_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

    if not state.blueprint_generator_messages:
        seed_msg = [SystemMessage(content = prompt),
                HumanMessage(content = state.theorem + "\n\n Workspace file:"+ state.workspacePATH+"\n\n Project Root: "+state.project_root)]
        response = await llm_with_tools.ainvoke(seed_msg)
        return {"blueprint_generator_messages":seed_msg+[response], "active_node": "blueprint_gen"}
    

    response = await llm_with_tools.ainvoke(state.blueprint_generator_messages)
    return {"blueprint_generator_messages":[response], "active_node": "blueprint_gen"}

async def theorem_proving(state: State, runtime: Runtime[Context]):

    # Enforce turn limit
    max_turns = runtime.context.get("max_iterations", 100)
    turn = state.turn_count + 1
    if turn > max_turns:
        return {"active_node": "theorem_proving"}

    # Load blueprint JSON — always reload from disk if available (source of truth)
    bp_path = Path(state.project_root) / ".lake/build/blueprint/module/LeanWorkspace.json"
    if bp_path.exists():
        bp = load_blueprint_json(state.project_root)
        tasks = blueprint_to_tasks(bp)
    else:
        bp, tasks = state.blueprint, state.lemma_tasks

    theorem_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/theorem_prover.md").read_text()
   
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name, timeout=120)
    lean_tools = await get_lean_tools()
    llm_w_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools + scheduling_tools)

    # Use theorem_prover_messages — ToolNode writes to the same key, so no merging needed
    if state.theorem_prover_messages:
        messages = list(state.theorem_prover_messages)
    else:
        messages = [
            SystemMessage(content=theorem_prompt),
            HumanMessage(content="\nWorkSpace File:"+ state.workspacePATH),
        ]

    response = await llm_w_tools.ainvoke(messages)
    return {"theorem_prover_messages": [response], "active_node": "theorem_proving",
            "blueprint": bp, "lemma_tasks": tasks, "turn_count": turn}


def route_tool_calls(state: State, key: str) -> str:
    """Route tool calls to the matching dedicated ToolNode."""
    # Determine suffix based on message channel
    suffix = "bp" if key == "blueprint_generator_messages" else "tp"

    msgs = getattr(state, key)
    if not msgs:
        return END
    msg = msgs[-1]
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return END

    tool_names = {tc["name"] for tc in tool_calls}

    if tool_names & scheduling_tool_names and suffix == "tp":
        return "scheduling_tool"
    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return f"human_tool_{suffix}"
    return f"tools_{suffix}"


def route_from_blueprint(state: State):
    """After blueprint_gen: route to tools/human or to theorem_proving."""
    dest = route_tool_calls(state, "blueprint_generator_messages")
    return dest if dest != END else "theorem_proving"


def route_from_prover(state: State):
    """After theorem_proving: route to tools/human or to END."""
    return route_tool_calls(state, "theorem_prover_messages")


def route_from_tools(state: State):
    """After tool node: route back to whichever LLM node called it."""
    return state.active_node if state.active_node else "blueprint_gen"


async def build_graph():
    lean_tools = await get_lean_tools()
    bp_all_tools = file_tools + lean_tools + doc_tools

    # Separate ToolNodes per message channel
    tools_bp = ToolNode(bp_all_tools, messages_key="blueprint_generator_messages")
    tools_tp = ToolNode(bp_all_tools, messages_key="theorem_prover_messages")

    builder = StateGraph(State, context_schema=Context)

    #nodes
    builder.add_node("blueprint_gen", blueprint_generator)
    builder.add_node("theorem_proving", theorem_proving)
    builder.add_node("tools_bp", tools_bp)
    builder.add_node("human_tool_bp", human_tool_node_bp)
    builder.add_node("tools_tp", tools_tp)
    builder.add_node("human_tool_tp", human_tool_node_tp)
    builder.add_node("scheduling_tool", scheduling_tool_node)

    #edges
    builder.add_edge(START, "blueprint_gen")
    builder.add_conditional_edges(
        "blueprint_gen", route_from_blueprint,
        {"tools_bp": "tools_bp", "human_tool_bp": "human_tool_bp", "theorem_proving": "theorem_proving"}
    )
    builder.add_conditional_edges(
        "theorem_proving", route_from_prover,
        {"tools_tp": "tools_tp", "human_tool_tp": "human_tool_tp", "scheduling_tool": "scheduling_tool", END: END}
    )
    for tool_node_name in ("tools_bp", "human_tool_bp"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_gen": "blueprint_gen"}
        )
    for tool_node_name in ("tools_tp", "human_tool_tp", "scheduling_tool"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"theorem_proving": "theorem_proving"}
        )

    checkpointer = MemorySaver()
    graph = builder.compile(name="Conjecture Prover Graph", checkpointer=checkpointer)
    return graph





async def main():
    graph = await build_graph()

    result = await graph.ainvoke(
        {"theorem": "Prove the monotone convergence theorem for a sequence of real numbers. Let us have a monotone sequence of real numbers.Then the following are equivalent. the sequence has a finite limit in the reals and the sequence is bounded "},
        context={"model": "deepseek-chat"},
        config=config,
    )

    # Keep resuming as long as the graph asks for input
    while interrupt_val := result.get("__interrupt__"):
        print(f"\n--- GRAPH PAUSED ---")
        print(f"Question: {interrupt_val[0].value}")
        answer = input("Your response: ")

        result = asyncio.run(graph.ainvoke(
            Command(resume=answer),
            context= {"model": "deepseek-chat"},
            config=config,
        ))


if __name__ == "__main__":
    asyncio.run(main())
    
