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
from langgraph.prebuilt import ToolNode, tools_condition

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

from pathlib import Path
from dotenv import load_dotenv

#OpenAI
from openai import AsyncOpenAI

load_dotenv()

from IPython.display import Image, display

### FILESYSTEM TOOLS

PROJECT_ROOT = Path("/Users/amirnabiyev/Conjecture_Prover").resolve()

config = { "configurable": {"thread_id":"1"}}


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

### NODE DECLARATION

#### Tool Nodes
tool_executor = ToolNode(file_tools)
human_tool = ToolNode(human_tools)


async def blueprint_generator(state: State, runtime: Runtime[Context]):
    # blueprint generator node
    prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
    # system_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/system_prompt.md").read_text()
    # init the model
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name)
    # bind the tools using MCP server clients
    tools = await client.get_tools()
    llm_with_tools = llm.bind_tools(file_tools + human_tools + tools)

    if not state.messages:
        seed_msg = [SystemMessage(content = prompt),
                HumanMessage(content = state.theorem + "\n\n"+ state.workspacePATH)]
        response = await llm_with_tools.ainvoke(seed_msg)
        return {"messages":seed_msg+[response]}
    

    response = await llm_with_tools.ainvoke(state.messages)
    return {"messages":[response]}


def call_tools(state: State):
    if not state.messages:
        print("No Messages")
        return END
    msg = state.messages[-1]
    if not msg or not msg.tool_calls:
        print("No tool calls")
        return END
    # route ask_human separately
    if any(tc["name"] == "ask_human" for tc in msg.tool_calls):
        return "human_tool"
    return "tool_executor"


# Define the graph
builder = StateGraph(State, context_schema=Context)

#nodes
builder.add_node("blueprint_gen", blueprint_generator)
builder.add_node("tool_executor", tool_executor)
builder.add_node("human_tool", human_tool)

#edges
builder.add_edge(START, "blueprint_gen")
builder.add_conditional_edges(
    "blueprint_gen", call_tools,
    {END: END, "tool_executor": "tool_executor", "human_tool": "human_tool"}
)
builder.add_edge("tool_executor", "blueprint_gen")
builder.add_edge("human_tool", "blueprint_gen")


checkpointer = MemorySaver()
graph = builder.compile(name="Conjecture Prover Graph", checkpointer=checkpointer)


if __name__ == "__main__":
    result = asyncio.run(graph.ainvoke(
        {"theorem": "Prove the transitive property where if a = b , b = c , then a = c and write to your workspace file which the path is specified in your state"},
        context={"model": "deepseek-chat"},
        config=config,
    ))

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

