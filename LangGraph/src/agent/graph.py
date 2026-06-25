"""LangGraph single-node graph template.

Returns a predefined response. Replace logic and configuration as needed.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from typing_extensions import TypedDict

#LangGraph Imports
from langgraph.graph import StateGraph,START,END
from langgraph.runtime import Runtime
from langgraph.types import Command

#Langsmith imports
from langsmith import traceable
 
#LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient 
from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool


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


file_tools = [read_workspace,write_workspace,search_replace_workspace,create_file]
# @traceable(
#     run_type="llm",
#     name="DeepSeek Chat Completion",
#     metadata={"ls_provider": "deepseek", "ls_model_name": "deepseek-v4-flash"},
# )
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
    theorem:str = ""
    workspacePATH: str = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean"
    lean_file_content:str = ""
    AIMsg: str = ""

### NODE DECLARATION

async def blueprint_generator(state:State, runtime:Runtime[Context]):
    # blueprint generator node
    prompt  = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
    system_prompt = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/system_prompt.md").read_text()
    # init the model
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name)
    #bind the tools using MCP server clients
    client = MultiServerMCPClient({
        "lean":{
            "transport":"stdio",
            "command":"uvx",
            "args":["lean-lsp-mcp"],
        }
    })
    tools = await client.get_tools()
    llm.bind_tools(tools + file_tools)
    #prompt the model
    response =  llm.invoke(system_prompt + prompt)
    return Command(update = {"AIMsg":response.content})

# Define the graph
builder = StateGraph(State, context_schema=Context)

#add nodes
builder.add_node("blueprint_gen", blueprint_generator)

#add edges
builder.add_edge(START,"blueprint_gen")
builder.add_edge("blueprint_gen",END)


graph = builder.compile(name="Conjecture Prover Graph")


if __name__ == "__main__":
    result = asyncio.run(graph.ainvoke(
        {"theorem": "Prove the transitive property"},
        context={"model": "deepseek-chat"}
    ))
    print(result["AIMsg"])

