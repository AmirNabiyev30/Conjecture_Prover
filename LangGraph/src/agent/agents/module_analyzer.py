"""
Module Analyzer — LangChain tool that retrieves a Mathlib module's source
from the local mathlib4 checkout, then delegates to ``code_module_analyzer``
to produce a structured analysis of the declarations it contains.

This combines the local retriever (``retrieval.local_mathlib_retriever``) with
the existing code module analyzer (``agents.code_module_analyzer``) into a
single tool call: give it a module name, get back a dependency/strategy
analysis of the whole module.
"""

from __future__ import annotations

from langchain_core.tools import tool

from agents.code_module_analyzer import code_module_analyzer
from retrieval.local_mathlib_retriever import get_mathlib_source


@tool
async def analyze_mathlib_module(module_name: str) -> str:
    """Analyze a Mathlib module by reading its source from the local mathlib4 checkout.

    Use this to understand what a Mathlib module contains and how its theorems
    are proved, WITHOUT needing the source code up front.  Given a module name
    (e.g. ``"Mathlib.Data.Real.Basic"``) the tool:
    - Reads the module's full ``.lean`` source from the local mathlib4 folder
    - Analyzes its declarations (dependencies, proof strategy, Mathlib alignment)
    - Returns a structured summary with a suggested blueprint decomposition

    Prefer this over ``fetch_mathlib_source`` + ``code_module_analyzer`` when you
    only know the module name and want an end-to-end analysis of the whole file.

    Args:
        module_name: Dot-separated Mathlib module name, e.g.
            "Mathlib.Data.Real.Basic" or "Mathlib.Analysis.Convex.Caratheodory".

    Returns a structured text analysis of the module, or an error message if the
    module could not be found in the local checkout.
    """
    source = get_mathlib_source(module_name)
    if source is None:
        return (
            f"Could not find module '{module_name}' in the local mathlib4 checkout.\n"
            "Check the module name (dot-separated, e.g. 'Mathlib.Data.Real.Basic') "
            "or use search_mathlib_docs to find valid module paths."
        )

    # Reuse the existing code_module_analyzer for the LLM analysis.
    return await code_module_analyzer.ainvoke({"code_or_blueprint": source})
