"""Tests for the analyze_mathlib_module tool."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))


def test_tool_registered():
    from agents.module_analyzer import analyze_mathlib_module
    assert analyze_mathlib_module.name == "analyze_mathlib_module"
    assert "module_name" in analyze_mathlib_module.description
    assert "Mathlib" in analyze_mathlib_module.description


def test_tool_is_async():
    from agents.module_analyzer import analyze_mathlib_module
    import inspect
    # @tool stores the async function in .coroutine
    assert inspect.iscoroutinefunction(analyze_mathlib_module.coroutine)
