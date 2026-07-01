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
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage


import os
import asyncio
import json

from pathlib import Path
from dotenv import load_dotenv

#OpenAI
from openai import AsyncOpenAI

load_dotenv()

from IPython.display import Image, display

from mathlib_doc_tools import doc_tools

### FILESYSTEM TOOLS

PROJECT_ROOT = Path("/Users/amirnabiyev/Conjecture_Prover").resolve()

config = { "configurable": {"thread_id":"6"}}


@tool
def read_workspace(workspace_path: str) -> str:
    """Read and return the full contents of the Lean workspace file.

    Use this before editing to understand the current
    state of the file, or to inspect the blueprint declarations,
    theorem statements, and existing proofs.
    """
    return Path(workspace_path).read_text(encoding="utf-8")


@tool
def write_workspace(workspace_path: str, content: str) -> str:
    """Overwrite the entire Lean workspace file with the given content.

    Use this when you need to replace the whole file,
    for example after generating a new blueprint skeleton or
    applying a completed proof. The file will be completely
    overwritten — ensure your content includes all existing
    declarations that should be preserved.
    """
    Path(workspace_path).write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {workspace_path}"


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


file_tools = [read_workspace, write_workspace, search_replace_workspace,
              create_file, list_directory]
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
    workspacePATH: str = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean"
    messages: Annotated[list[AnyMessage],add_messages] = field(default_factory=list)
    active_node: str = "blueprint_gen"
    project_root: str = "/Users/amirnabiyev/Conjecture_Prover"

### NODE DECLARATION


_lean_tools = None
_lean_loogle_mcp = None  # private reference for the wrapper
human_tool_node = ToolNode(human_tools)


@tool
async def lean_loogle(query: str, num_results: int = 8) -> str:
    """Search Mathlib4 by type signature, constant name, or name substring.

    The query can be:
      - A name substring:     "Monotone"
      - A type pattern:       "(?a : ℝ) → ?a ≤ ?a"
      - A conclusion shape:   "|- _ < _ → _ < _"
      - A quoted substring:   "\"comm\""

    Use this to find the EXACT type signature of a Mathlib declaration by name,
    or to discover lemmas by their type shape. For name-only lookups prefer
    search_mathlib_docs / search_mathlib_docs_multi instead — they are faster
    and already include module paths and Loogle hints.

    Returns: declaration name, type signature, and source module for each result.
    """
    loogle_mcp = _lean_loogle_mcp
    if loogle_mcp is None:
        return (
            "ERROR: lean_loogle MCP tool not available. "
            "Make sure the lean-lsp-mcp server is running."
        )

    result = await loogle_mcp.ainvoke({"query": query, "num_results": num_results})

    # Unpack MCP TextContent format → clean formatted text
    if isinstance(result, list) and result:
        first = result[0]
        text = first.get("text", str(result)) if isinstance(first, dict) else str(result)
        try:
            data = json.loads(text)
            items = data.get("items", [])
        except (json.JSONDecodeError, TypeError, KeyError):
            return text

        if not items:
            return f"No results found for '{query}'."

        lines = [f"Found {len(items)} result(s) for '{query}':\n"]
        for item in items:
            name = item.get("name", "?")
            typ  = item.get("type", "?")
            mod  = item.get("module", "?")
            lines.append(f"  {name}")
            lines.append(f"    Type:   {typ}")
            lines.append(f"    Module: {mod}")
        return "\n".join(lines)

    return str(result)


async def get_lean_tools():
    global _lean_tools, _lean_loogle_mcp
    if _lean_tools is None:
        _lean_tools = await client.get_tools()
        _lean_loogle_mcp = next(
            (t for t in _lean_tools if t.name == "lean_loogle"), None
        )
        _lean_tools = [
            lean_loogle if t.name == "lean_loogle" else t
            for t in _lean_tools
        ]
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

    if not state.messages:
        seed_msg = [SystemMessage(content = prompt),
                HumanMessage(content = state.theorem + "\n\n Workspace file:"+ state.workspacePATH+"\n\n Project Root: "+state.project_root)]
        response = await llm_with_tools.ainvoke(seed_msg)
        return {"messages":seed_msg+[response], "active_node": "blueprint_gen"}
    

    response = await llm_with_tools.ainvoke(state.messages)
    return {"messages":[response], "active_node": "blueprint_gen"}

async def theorem_proving(state: State, runtime: Runtime[Context]):
    theorem_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/theorem_prover.md").read_text()
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name, timeout=120)
    lean_tools = await get_lean_tools()
    llm_w_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

    # Replace the first SystemMessage with the theorem prover prompt
    messages = list(state.messages)
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=theorem_prompt)
    else:
        messages.insert(0, SystemMessage(content=theorem_prompt))

    response = await llm_w_tools.ainvoke(messages)
    return {"messages": [response], "active_node": "theorem_proving"}


def route_tool_calls(state: State) -> str:
    """Route tool calls: ask_human → human_tool, everything else → tools."""
    if not state.messages:
        return END
    msg = state.messages[-1]
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return END
    # If ask_human is among the calls, route to human_tool
    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return "human_tool"
    return "tools"


def route_from_blueprint(state: State):
    """After blueprint_gen: route to tools/human or to theorem_proving."""
    dest = route_tool_calls(state)
    return dest if dest != END else "theorem_proving"


def route_from_prover(state: State):
    """After theorem_proving: route to tools/human or to END."""
    return route_tool_calls(state)


def route_from_tools(state: State):
    """After tool node: route back to whichever LLM node called it."""
    return state.active_node if state.active_node else "blueprint_gen"


async def build_graph():
    lean_tools = await get_lean_tools()
    all_tools = file_tools + lean_tools + doc_tools
    tool_node = ToolNode(all_tools)

    # Define the graph
    builder = StateGraph(State, context_schema=Context)

    #nodes
    builder.add_node("blueprint_gen", blueprint_generator)
    builder.add_node("theorem_proving", theorem_proving)
    builder.add_node("tools", tool_node)
    builder.add_node("human_tool", human_tool_node)

    #edges
    builder.add_edge(START, "blueprint_gen")
    builder.add_conditional_edges(
        "blueprint_gen", route_from_blueprint,
        {"tools": "tools", "human_tool": "human_tool", "theorem_proving": "theorem_proving"}
    )
    builder.add_conditional_edges(
        "theorem_proving", route_from_prover,
        {"tools": "tools", "human_tool": "human_tool", END: END}
    )
    for tool_node_name in ("tools", "human_tool"):
        builder.add_conditional_edges(
            tool_node_name, route_from_tools,
            {"blueprint_gen": "blueprint_gen", "theorem_proving": "theorem_proving"}
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

    print(result)

if __name__ == "__main__":
    asyncio.run(main())
    
