"""Integration test for analyze_mathlib_module — requires LLM API access.

Takes a Mathlib module name, retrieves the source from the local mathlib4
checkout, runs the LLM analysis, and prints the generated response.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))


@pytest.mark.asyncio
async def test_analyze_mathlib_module_caratheodory():
    """Pass a Mathlib module name; retrieve its local source and analyze it."""
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    from agents.module_analyzer import analyze_mathlib_module

    module_name = "Mathlib.Analysis.Convex.Caratheodory"

    print(f"\n{'='*60}")
    print(f"Module: {module_name}")
    print(f"{'='*60}")

    result = await analyze_mathlib_module.ainvoke({"module_name": module_name})

    print(f"\n{'='*60}")
    print("LLM Response:")
    print(result)
    print(f"{'='*60}")

    assert len(result) > 50, "Response too short"
