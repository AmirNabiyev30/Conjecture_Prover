"""Tests for the code_module_analyzer tool."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))


def test_tool_registered():
    from agents.code_module_analyzer import code_module_analyzer
    assert code_module_analyzer.name == "code_module_analyzer"
    assert "code_or_blueprint" in code_module_analyzer.description
    assert "Lean" in code_module_analyzer.description


def test_tool_is_async():
    from agents.code_module_analyzer import code_module_analyzer
    import inspect
    # @tool stores the async function in .coroutine
    assert inspect.iscoroutinefunction(code_module_analyzer.coroutine)
