"""Production graph wiring test.

Builds the REAL graph returned by ``graph.build_graph`` — the same object
``cli.run`` invokes — with only the Lean MCP tool loader stubbed out, so there
is no LLM call, no Lean server, and no LangSmith traffic.

This replaces ``tests/integration_tests/test_graph.py``, which was vendored
template boilerplate: it awaited a module-level ``graph.ainvoke`` that this
project has never exposed (the entry point is the ``build_graph`` factory), so
it had been failing since the template was added. Nothing was being integrated
there, hence the move to unit tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

import graph as graph_module  # noqa: E402

pytestmark = pytest.mark.anyio

#: Every node the production graph must register. Written out explicitly rather
#: than derived, so deleting a node is a test failure instead of a silent shape
#: change.
EXPECTED_NODES = {
    "blueprint_gen",
    "blueprint_refiner",
    "tools_bp",
    "human_tool_bp",
    "tools_br",
    "human_tool_br",
    "prove_lemma",
    "dispatch_gate",
    "aggregator",
    "rebuild_blueprint",
}


async def _build(monkeypatch):
    """Build the production graph without spawning a Lean MCP server."""

    async def _no_lean_tools(*args, **kwargs):
        return []

    monkeypatch.setattr(graph_module, "get_lean_tools", _no_lean_tools)
    return await graph_module.build_graph()


async def test_build_graph_registers_every_node(monkeypatch):
    compiled = await _build(monkeypatch)

    registered = set(compiled.get_graph().nodes)
    assert EXPECTED_NODES <= registered


async def test_batching_gate_is_part_of_the_production_graph(monkeypatch):
    """The barrier join must exist under the names the routers return.

    ``route_after_batch`` routes to the literal names ``"aggregator"`` and the
    next prover batch, while ``prove_lemma`` reaches the gate over a plain edge.
    LangGraph only *warns* ("wrote to unknown channel") when a routing target
    does not exist and then drops the task silently — so a renamed or deleted
    gate would break batching without raising anything.
    """
    compiled = await _build(monkeypatch)

    registered = set(compiled.get_graph().nodes)
    assert {"prove_lemma", "dispatch_gate", "aggregator"} <= registered


async def test_the_entry_point_is_the_graph_factory():
    """``main`` builds via the factory; there is no module-level graph object."""
    assert callable(graph_module.build_graph)
    assert callable(graph_module.main)
    assert not hasattr(graph_module, "ainvoke")
