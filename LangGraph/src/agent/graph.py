"""LangGraph single-node graph template.

Returns a predefined response. Replace logic and configuration as needed.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from langgraph.graph import StateGraph,START,END
from langgraph.runtime import Runtime
from typing_extensions import TypedDict
from langgraph.types import Command

import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

#Langsmith imports
from langsmith import traceable
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

    


### NODE DECLARATION

async def blueprint_generator(State):
    # blueprint generator node
    prompt  = Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text()
    #call model with prompt
    #use tools to write the file



async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """Process input and returns output.

    Can use runtime context to alter behavior.
    """
    model = runtime.context.get("model", "deepseek-chat")
    messages = [
        {"role": "system", "content": state.instructions},
    ]
    response = await call_deepseek(messages, model=model)
    return Command(
        update = {"AIMsg": response.content or ""},
        goto= "__end__"
    )


# Define the graph

builder = StateGraph(State, context_schema=Context)
builder.add_node(call_model)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", END)



graph = builder.compile(name="Conjecture Prover Graph")


if __name__ == "__main__":
    result = asyncio.run(graph.ainvoke(
        {"instructions": "You are a helpful assistant", "AIMsg": ""},
        context={"model": "deepseek-chat"}
    ))
    print(result["AIMsg"])

