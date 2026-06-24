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
from langsmith import traceable

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

    model: str  # e.g. "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"


@dataclass
class State:
    """Input state for the agent."""
    instructions: str = "You are a helpful assistant tasked with answering questions"
    AIMsg: str = ""

async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """Process input and returns output.

    Can use runtime context to alter behavior.
    """
    model = runtime.context.get("model", "deepseek-v4-flash")
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



graph = builder.compile(name="Amirs Graph")


if __name__ == "__main__":
    result = asyncio.run(graph.ainvoke(
        {"instructions": "You are a helpful assistant", "AIMsg": ""},
        context={"model": "deepseek-v4-flash"}
    ))
    print(result["AIMsg"])

