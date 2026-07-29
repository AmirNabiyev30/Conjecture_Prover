"""
Unit tests for prove_lemma node — all external dependencies are mocked.

No network, no Lean, no LLM — fast deterministic tests.
"""

import sys
from pathlib import Path

# The agent package uses bare imports (e.g. `from config import ...`),
# which require `src/agent` to be on sys.path.
_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.messages import AIMessage

from nodes.prove_lemma import prove_lemma

pytestmark = pytest.mark.anyio


# ── Shared test data ─────────────────────────────────────────────────────────

def _make_runtime(max_turns: int = 3, model: str = "test-model"):
    """Build a mock Runtime[Context] with the given context values."""
    rt = MagicMock()
    rt.context = {"max_turns_per_lemma": max_turns, "model": model}
    return rt


SIN_LOWER_BOUND_TASK = {
    "name": "sin_lower_bound",
    "kind": "lemma",
    "statement": "For all x ∈ [0,π], (1/π)·x·(π-x) ≤ sin x",
    "proof_sketch": "Use g(x) = sin x - f(x), show g ≥ 0",
    "file": "LeanWorkspace.lean",
    "start_line": 18,
    "end_line": 35,
    "dependencies": [],
}

SIN_LOWER_BOUND_DECL = (
    "lemma sin_lower_bound (x : ℝ) (hx : x ∈ Icc (0 : ℝ) π) : "
    "(1 / π) * x * (π - x) ≤ sin x := by\n  sorry_using []"
)

VALID_PROOF = (
    "lemma sin_lower_bound (x : ℝ) (hx : x ∈ Icc (0 : ℝ) π) : "
    "(1 / π) * x * (π - x) ≤ sin x := by\n"
    "  have h := hx\n"
    "  apply mul_le_mul_of_nonneg_right\n"
    "  · exact sin_pos_of_pos_of_lt_pi (by linarith) (by linarith)\n"
    "  · nlinarith"
)

NATURAL_LANG_RESPONSE = (
    "Here is the proof: we can use the mean value theorem to show that "
    "the function g(x) = sin x - (1/π)x(π-x) is nonnegative on [0,π]. "
    "First, note that g(0) = g(π) = 0. Then g'(x) = cos x - (π-2x)/π..."
)


# ── Helpers for common mocking patterns ─────────────────────────────────────

def _setup_mocks(mock_llm, mock_mcp, mock_path_class, *,
                 llm_responses: list,
                 prompt_text: str = "You are a theorem prover."):
    """Configure the three main mocks with standard defaults.

    Args:
        mock_llm: patched `init_chat_model`
        mock_mcp: patched `create_lean_mcp_client`
        mock_path_class: patched `Path`
        llm_responses: list of AIMessage responses from the LLM
        prompt_text: text to return when the prompt file is read
    """
    # Prompt file
    mock_prompt_path = MagicMock()
    mock_prompt_path.read_text.return_value = prompt_text
    mock_path_class.return_value = mock_prompt_path

    # MCP client
    mock_tool = MagicMock()
    mock_tool.name = "lean_run"
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp.return_value = mock_client

    # LLM
    llm_instance = MagicMock()
    llm_instance.bind_tools.return_value = llm_instance
    llm_instance.ainvoke = AsyncMock(side_effect=llm_responses)
    mock_llm.return_value = llm_instance


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_missing_lemma_task():
    """No lemma_task in state → early return with feedback."""
    with patch("nodes.prove_lemma.Path") as mock_path:
        mock_path_instance = MagicMock()
        mock_path_instance.read_text.return_value = "dummy prompt"
        mock_path.return_value = mock_path_instance

        state = {}
        runtime = _make_runtime()

        result = await prove_lemma(state, runtime)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    assert proposals[0]["status"] == "FAILED"
    assert proposals[0]["proved"] is False
    assert proposals[0]["lemma_id"] == ""
    assert proposals[0]["old_str"] == ""
    assert proposals[0]["new_str"] is None
    assert proposals[0]["feedback"] == "missing lemma_task"


async def test_valid_proof_returned():
    """LLM returns valid Lean proof → proved=True, new_str set."""
    responses = [AIMessage(content=VALID_PROOF)]

    with patch("nodes.prove_lemma.init_chat_model") as mock_llm, \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:
        _setup_mocks(mock_llm, mock_mcp, mock_path, llm_responses=responses)

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime(max_turns=3)

        result = await prove_lemma(state, runtime)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "PROVED"
    assert p["proved"] is True
    assert p["lemma_id"] == "sin_lower_bound"
    assert p["old_str"] == SIN_LOWER_BOUND_DECL
    assert p["new_str"] == VALID_PROOF
    assert "PROVED" in p["feedback"]


async def test_natural_language_rejected():
    """LLM returns prose → is_valid_lean_proof rejects, retries, eventually fails."""
    # First response: prose (rejected). Second: prose again (rejected).
    # Third: still prose → turn limit reached (with max_turns=3, we need to exhaust)
    # Actually: each prose response gets a retry with corrective message.
    # With 3 turns and 3 prose responses, turn limit is reached.
    responses = [
        AIMessage(content=NATURAL_LANG_RESPONSE),
        AIMessage(content=NATURAL_LANG_RESPONSE),
        AIMessage(content=NATURAL_LANG_RESPONSE),
    ]

    with patch("nodes.prove_lemma.init_chat_model") as mock_llm, \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:
        _setup_mocks(mock_llm, mock_mcp, mock_path, llm_responses=responses)

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime(max_turns=3)

        result = await prove_lemma(state, runtime)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "TOO_HARD"
    assert p["proved"] is False
    assert p["new_str"] is None
    assert "TOO_HARD" in p["feedback"]


async def test_turn_limit_exhausted_too_hard():
    """LLM always returns sorry → turn limit hit, TOO_HARD feedback."""
    sorry_response = AIMessage(content="lemma sin_lower_bound ... := by\n  sorry")

    with patch("nodes.prove_lemma.init_chat_model") as mock_llm, \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:
        _setup_mocks(mock_llm, mock_mcp, mock_path, llm_responses=[sorry_response])

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime(max_turns=1)

        result = await prove_lemma(state, runtime)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "TOO_HARD"
    assert p["proved"] is False
    assert p["new_str"] is None
    assert p["feedback"].startswith("TOO_HARD:")
    assert "1" in p["feedback"]  # turn limit number is present


async def test_mcp_client_startup_fails():
    """MCP client raises → proved=False with MCP error feedback."""
    with patch("nodes.prove_lemma.init_chat_model"), \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:
        mock_prompt_path = MagicMock()
        mock_prompt_path.read_text.return_value = "You are a theorem prover."
        mock_path.return_value = mock_prompt_path

        mock_mcp.side_effect = RuntimeError("lean-lsp-mcp not found")

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime()

        result = await prove_lemma(state, runtime)

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "FAILED"
    assert p["proved"] is False
    assert p["new_str"] is None
    assert p["feedback"].startswith("MCP start error:")
    assert "lean-lsp-mcp not found" in p["feedback"]


async def test_tool_call_then_proof():
    """Turn 1: tool call (lean_run). Turn 2: valid proof → proved=True."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "id": "call_1",
            "name": "lean_run",
            "args": {"code": "import Mathlib\n#check 1+1"},
        }]
    )
    proof_msg = AIMessage(content=VALID_PROOF)

    with patch("nodes.prove_lemma.init_chat_model") as mock_llm, \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:

        # Setup mocks, but we need more control over MCP tool invocation
        mock_prompt_path = MagicMock()
        mock_prompt_path.read_text.return_value = "You are a theorem prover."
        mock_path.return_value = mock_prompt_path

        # MCP client with a real-ish tool that returns a result
        mock_tool = MagicMock()
        mock_tool.name = "lean_run"
        mock_tool.ainvoke = AsyncMock(return_value="'#check 1+1' : 1+1 = 2")
        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=[mock_tool])
        mock_mcp.return_value = mock_client

        # LLM: first turn tool call, second turn proof
        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(side_effect=[tool_call_msg, proof_msg])
        mock_llm.return_value = llm_instance

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime(max_turns=5)

        result = await prove_lemma(state, runtime)

    # Verify the tool was called
    mock_tool.ainvoke.assert_awaited_once_with({"code": "import Mathlib\n#check 1+1"})

    proposals = result["pending_proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "PROVED"
    assert p["proved"] is True
    assert p["lemma_id"] == "sin_lower_bound"
    assert p["new_str"] == VALID_PROOF
    assert "PROVED" in p["feedback"]


async def test_doc_tools_included_in_bind_tools():
    """Verify that search_mathlib_docs and other doc_tools are passed to bind_tools."""
    responses = [AIMessage(content=VALID_PROOF)]

    with patch("nodes.prove_lemma.init_chat_model") as mock_llm, \
         patch("nodes.prove_lemma.create_lean_mcp_client") as mock_mcp, \
         patch("nodes.prove_lemma.Path") as mock_path:
        _setup_mocks(mock_llm, mock_mcp, mock_path, llm_responses=responses)

        state = {
            "lemma_task": SIN_LOWER_BOUND_TASK,
            "lemma_decl_text": SIN_LOWER_BOUND_DECL,
            "project_root": "/tmp/test",
        }
        runtime = _make_runtime(max_turns=3)

        await prove_lemma(state, runtime)

    # Capture the tools passed to bind_tools
    llm_instance = mock_llm.return_value
    llm_instance.bind_tools.assert_called_once()
    tools_passed = llm_instance.bind_tools.call_args[0][0]

    tool_names = {t.name for t in tools_passed}
    assert "search_mathlib_docs" in tool_names, \
        f"Expected search_mathlib_docs in bound tools, got: {sorted(tool_names)}"
    assert "search_mathlib_docs_multi" in tool_names, \
        f"Expected search_mathlib_docs_multi in bound tools, got: {sorted(tool_names)}"
    assert "refresh_mathlib_docs_cache" in tool_names, \
        f"Expected refresh_mathlib_docs_cache in bound tools, got: {sorted(tool_names)}"
