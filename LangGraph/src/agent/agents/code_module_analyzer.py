"""
Code Module Analyzer — LangChain tool that takes Lean source code or blueprint
JSON and returns a structured text analysis of the proof's dependencies,
strategy, and a suggested decomposition.
"""

from __future__ import annotations

from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool

from config import MODEL_NAME, MODEL_TIMEOUT, CODE_MODULE_ANALYZER_PROMPT


@tool
async def code_module_analyzer(code_or_blueprint: str) -> str:
    """Analyze Lean proof source code and return a structured summary.

    Use this AFTER fetch_mathlib_source to understand a proof's:
    - Dependencies (which lemmas and theorems it calls)
    - Proof strategy (induction, epsilon-delta, algebraic, etc.)
    - Mathlib alignment (are there better Mathlib alternatives?)
    - Suggested blueprint decomposition (how to structure the proof)

    Args:
        code_or_blueprint: Lean source code or blueprint JSON to analyze.

    Returns a structured text analysis with clear sections.
    """
    prompt = Path(CODE_MODULE_ANALYZER_PROMPT).read_text()
    llm = init_chat_model(MODEL_NAME, timeout=MODEL_TIMEOUT)

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Analyze this proof:\n\n```lean\n{code_or_blueprint}\n```"),
    ]

    response = await llm.ainvoke(messages)
    return response.content if hasattr(response, "content") else str(response)
