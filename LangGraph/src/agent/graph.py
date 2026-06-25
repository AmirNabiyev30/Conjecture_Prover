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


import os
import asyncio

from pathlib import Path
from dotenv import load_dotenv

#OpenAI
from openai import AsyncOpenAI


from pathlib import Path

load_dotenv()

from IPython.display import Image, display

client = AsyncOpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)


@traceable(
    run_type="llm",
    name="DeepSeek Chat Completion",
    metadata={"ls_provider": "deepseek", "ls_model_name": "deepseek-v4-flash"},
)
async def call_deepseek(messages: list[dict], model: str = "deepseek-v4-flash"):
    kwargs = {"model": model, "messages": messages}
    # Only use reasoning_effort for reasoning models that support it
    if "reasoner" in model or "v4" in model:
        kwargs["reasoning_effort"] = "high"
    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message


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
    workspacePATH: str = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean"
    lean_file_content:str = ""
    AIMsg: str = ""


### NODE DECLARATION

async def blueprint_generator(state:State, runtime:Runtime[Context]):
    # blueprint generator node
    prompt  = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
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
    llm.bind_tools(tools)
    #prompt the model
    response =  llm.invoke(prompt)
    return Command(update = {"AIMsg":response.content})

async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """Process input and returns output.

    Can use runtime context to alter behavior.
    """
    model_name = runtime.context.get("model", "deepseek:deepseek-chat")
    llm = init_chat_model(model_name)
    messages = [
        {"role": "system", "content": state.instructions},
    ]
    response = llm.invoke(messages)
    return Command(
        update = {"AIMsg": response.content or ""},
        goto= "__end__"
    )


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
        {"instructions": "You are a helpful assistant", "AIMsg": ""},
        context={"model": "deepseek-chat"}
    ))
    print(result["AIMsg"])

