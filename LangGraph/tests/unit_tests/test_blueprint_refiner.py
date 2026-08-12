"""Unit tests for the blueprint-refiner node.

These tests deliberately do not start a model or Lean MCP server.  They verify
that the node builds the refinement context correctly and continues an existing
conversation without rebuilding the wider graph.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.messages import AIMessage, HumanMessage, SystemMessage

_AGENT_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "agent"
sys.path.insert(0, str(_AGENT_SRC))

from blueprint import Blueprint  # noqa: E402
from nodes.blueprint_refiner import blueprint_refiner  # noqa: E402
from state import State  # noqa: E402


pytestmark = pytest.mark.anyio


def _runtime(model: str = "test-model"):
    runtime = MagicMock()
    runtime.context = {"model": model}
    return runtime


def _blueprint() -> Blueprint:
    return Blueprint(
        theorem_name="target_theorem",
        statement="A target theorem.",
        nodes=[
            {
                "name": "easy_helper",
                "kind": "lemma",
                "statement": "P",
                "proof_sketch": None,
                "file": "LeanWorkspace.lean",
                "start_line": 1,
                "end_line": 2,
                "dependencies": [],
                "sorry_free": True,
            },
            {
                "name": "hard_lemma",
                "kind": "lemma",
                "statement": "Q",
                "proof_sketch": "Use the local structure.",
                "file": "LeanWorkspace.lean",
                "start_line": 4,
                "end_line": 6,
                "dependencies": ["easy_helper"],
                "sorry_free": False,
            },
        ],
    )


def _state(**overrides):
    state = {
        "theorem": "Prove the target theorem.",
        "workspacePATH": "/tmp/refinement/LeanWorkspace.lean",
        "project_root": "/tmp/refinement",
        "blueprint": _blueprint(),
        "lemma_statuses": {
            "easy_helper": {
                "name": "easy_helper", "status": "proved", "dependencies": [],
                "feedback": "", "statement": "P", "sorry_free": True,
            },
            "hard_lemma": {
                "name": "hard_lemma", "status": "unproved",
                "dependencies": ["easy_helper"], "statement": "Q",
                "sorry_free": False,
                "feedback": "PROOF_TOO_HARD: split the argument into a local helper.",
            },
        },
        "blueprint_refiner_messages": [],
    }
    state.update(overrides)
    return state


async def test_initial_turn_includes_blueprint_and_feedback():
    response = AIMessage(content="I will inspect the workspace and refine hard_lemma.")
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=response)

    with patch("nodes.blueprint_refiner.Path") as path_cls, \
         patch("nodes.blueprint_refiner.init_chat_model", return_value=llm), \
         patch("nodes.blueprint_refiner.get_lean_tools", new=AsyncMock(return_value=[])):
        path_cls.return_value.read_text.return_value = "REFINER PROMPT"
        result = await blueprint_refiner(State(**_state()), _runtime())

    messages = llm.ainvoke.await_args.args[0]
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == "REFINER PROMPT"
    assert isinstance(messages[1], HumanMessage)
    assert "target_theorem" in messages[1].content
    assert "hard_lemma" in messages[1].content
    assert "PROOF_TOO_HARD" in messages[1].content
    assert "easy_helper" in messages[1].content
    assert "Full dependency graph" in messages[1].content
    assert result["blueprint_refiner_messages"] == messages + [response]
    assert result["active_node"] == "blueprint_refiner"


async def test_subsequent_turn_continues_existing_refiner_conversation():
    prior = [
        SystemMessage(content="prompt"),
        HumanMessage(content="initial context"),
        AIMessage(content="Please provide the file."),
    ]
    response = AIMessage(content="The refinement is complete.")
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=response)

    with patch("nodes.blueprint_refiner.Path") as path_cls, \
         patch("nodes.blueprint_refiner.init_chat_model", return_value=llm), \
         patch("nodes.blueprint_refiner.get_lean_tools", new=AsyncMock(return_value=[])):
        path_cls.return_value.read_text.return_value = "REFINER PROMPT"
        result = await blueprint_refiner(
            State(**_state(blueprint_refiner_messages=prior)), _runtime("override-model")
        )

    assert llm.ainvoke.await_args.args[0] == prior
    assert result["blueprint_refiner_messages"] == [response]
    llm.bind_tools.assert_called_once()
    assert llm.ainvoke.await_count == 1


async def test_refiner_handles_missing_blueprint():
    response = AIMessage(content="No blueprint is loaded.")
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=response)

    with patch("nodes.blueprint_refiner.Path") as path_cls, \
         patch("nodes.blueprint_refiner.init_chat_model", return_value=llm), \
         patch("nodes.blueprint_refiner.get_lean_tools", new=AsyncMock(return_value=[])):
        path_cls.return_value.read_text.return_value = "REFINER PROMPT"
        await blueprint_refiner(State(**_state(blueprint=None)), _runtime())

    human_message = llm.ainvoke.await_args.args[0][1]
    assert "(no blueprint loaded)" in human_message.content
