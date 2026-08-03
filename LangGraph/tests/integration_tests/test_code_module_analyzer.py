"""Integration test for code_module_analyzer — requires LLM API access."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))


@pytest.mark.asyncio
async def test_code_module_analyzer_with_caratheodory():
    """Pass Carathéodory's theorem source to code_module_analyzer."""
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    from agents.code_module_analyzer import code_module_analyzer

    test_file = Path(__file__).parent / "code_module_analyzer_test.txt"
    source_code = test_file.read_text(encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Input: {len(source_code)} chars of Lean source")
    print(f"{'='*60}")

    result = await code_module_analyzer.ainvoke({"code_or_blueprint": source_code})

    print(f"\n{'='*60}")
    print("LLM Response:")
    print(result)
    print(f"{'='*60}")

    assert len(result) > 50, "Response too short"
