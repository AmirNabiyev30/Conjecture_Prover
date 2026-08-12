"""Three-arm experiment for blueprint generation and module analysis."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

_INTEGRATION_DIR = Path(__file__).resolve().parent
_AGENT_SRC = _INTEGRATION_DIR.parent.parent / "src" / "agent"
sys.path.insert(0, str(_INTEGRATION_DIR))
sys.path.insert(0, str(_AGENT_SRC))

from config import (  # noqa: E402
    BLUEPRINT_GENERATOR_OPTIONAL_ANALYZER_PROMPT,
    BLUEPRINT_GENERATOR_PROMPT,
    BLUEPRINT_GENERATOR_WO_ANALYZER_PROMPT,
    PROJECT_ROOT,
    WORKSPACE_PATH,
)
from lean_tools_cache import get_lean_tools  # noqa: E402
from test_blueprint_generator import _run_blueprint_generation  # noqa: E402


pytestmark = pytest.mark.anyio
load_dotenv()


@pytest.mark.mcp
@pytest.mark.slow
async def test_blueprint_generator_ab(tmp_path):
    """Compare disabled, optional, and forced analyzer conditions.

    Each condition receives an identical copy of the initial workspace. This is
    essential because blueprint generation writes to the workspace and a later
    arm must not inherit declarations or edits from an earlier arm.
    """
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    workspace = Path(WORKSPACE_PATH)
    baseline_prompt = Path(BLUEPRINT_GENERATOR_WO_ANALYZER_PROMPT)
    optional_prompt = Path(BLUEPRINT_GENERATOR_OPTIONAL_ANALYZER_PROMPT)
    analyzer_prompt = Path(BLUEPRINT_GENERATOR_PROMPT)

    assert workspace.is_file(), f"Workspace file does not exist: {workspace}"
    assert baseline_prompt.is_file(), f"Baseline prompt does not exist: {baseline_prompt}"
    assert optional_prompt.is_file(), f"Optional prompt does not exist: {optional_prompt}"
    assert analyzer_prompt.is_file(), f"Analyzer prompt does not exist: {analyzer_prompt}"
    initial_source = workspace.read_text(encoding="utf-8")
    assert len(initial_source) > 50

    # All arms use the same model, tools, theorem input, and initial source.
    # Only the prompt/tool-availability condition differs.
    lean_tools = await get_lean_tools()
    arms = [
        ("without_module_analysis", baseline_prompt, False),
        ("optional_module_analysis", optional_prompt, True),
        ("with_important_module_analysis", analyzer_prompt, True),
    ]
    results = []
    for name, prompt_path, enable_module_analysis in arms:
        arm_workspace = tmp_path / f"{name}.lean"
        shutil.copy2(workspace, arm_workspace)
        result = await _run_blueprint_generation(
            name=name,
            prompt_path=prompt_path,
            workspace=arm_workspace,
            lean_tools=lean_tools,
            enable_module_analysis=enable_module_analysis,
        )
        results.append(result)
        print("AB_RESULT " + json.dumps({
            "name": result["name"],
            "turns": result["turns"],
            "tool_calls": len(result["tool_calls"]),
            "analyzer_calls": result["analyzer_calls"],
            "content_chars": len(result["content"]),
        }, sort_keys=True))

    assert [result["name"] for result in results] == [name for name, _, _ in arms]
    assert results[0]["analyzer_calls"] == 0

    # The optional condition exposes the analyzer but does not require the
    # model to call it; usage is an outcome metric, not a pass/fail condition.
    assert results[1]["analyzer_calls"] >= 0
    assert results[2]["analyzer_calls"] >= 0
