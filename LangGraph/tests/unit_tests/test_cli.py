"""Unit tests for the operator-facing run entry point (cli.py).

No model, Lean MCP server, or real graph is involved: ``cli.run`` takes the graph
factory as an argument, so these drive it with a stub graph. That makes the parts
that used to be locked inside an async entry point — the smoke pre-flight, the
metadata tags, and the human-in-the-loop auto-resume loop — directly testable.

Behavior contract:
- The smoke pre-flight builds the graph, writes a stub summary, and never invokes
  the model.
- ``EXPERIMENT_METADATA`` is parsed into the invoke config; malformed JSON is
  ignored with a warning rather than killing the run.
- Interrupts are auto-answered while the resume budget lasts, then fall back to
  interactive input.
- A workflow failure still records a failure summary before propagating.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

import cli  # noqa: E402
from run_settings import RunSettings  # noqa: E402

pytestmark = pytest.mark.anyio

WS = "/tmp/workspace.lean"

_CLI_ENV = (
    "GRAPH_SMOKE_TEST",
    "EXPERIMENT_METADATA",
    "EXPERIMENT_AUTO_ANSWER",
    "EXPERIMENT_MAX_AUTO_RESUMES",
    "EXPERIMENT_SUMMARY_JSON",
)


@pytest.fixture(autouse=True)
def _clean_cli_env(monkeypatch):
    """Keep these tests hermetic: they must not inherit the caller's experiment env."""
    for name in _CLI_ENV:
        monkeypatch.delenv(name, raising=False)


class _StubGraph:
    """Records invocations and replays a scripted list of results."""

    def __init__(self, results: list[dict]):
        self._results = list(results)
        self.calls: list[tuple] = []

    async def ainvoke(self, payload, *, context=None, config=None):
        self.calls.append((payload, context, config))
        return self._results.pop(0)


class _FailingGraph:
    async def ainvoke(self, payload, *, context=None, config=None):
        raise RuntimeError("boom")


def _factory(graph):
    """A stand-in for graph.build_graph."""
    async def build_graph(settings):
        return graph
    return build_graph


def _settings() -> RunSettings:
    return RunSettings.from_env({})


# ── pure helpers ─────────────────────────────────────────────────────────────

def test_initial_state_names_the_workspace():
    state = cli.initial_state(WS)
    assert state["workspacePATH"] == WS
    assert WS in state["theorem"]


def test_smoke_test_requested_reads_the_env(monkeypatch):
    assert cli.smoke_test_requested() is False
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("GRAPH_SMOKE_TEST", raw)
        assert cli.smoke_test_requested() is True
    monkeypatch.setenv("GRAPH_SMOKE_TEST", "0")
    assert cli.smoke_test_requested() is False


def test_invoke_config_is_copied_not_mutated(monkeypatch):
    base = {"configurable": {"thread_id": "t"}}
    cfg = cli.invoke_config(base)
    assert cfg == base
    assert cfg is not base


def test_invoke_config_adds_metadata(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_METADATA", '{"condition": "with_analyzer"}')
    cfg = cli.invoke_config({})
    assert cfg["metadata"] == {"condition": "with_analyzer"}


def test_invoke_config_ignores_malformed_metadata(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_METADATA", "{not json")
    assert cli.invoke_config({}) == {}  # warns, does not raise


def test_auto_resume_policy_defaults(monkeypatch):
    assert cli.auto_resume_policy() == ("", 3)


def test_auto_resume_policy_reads_the_env(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_AUTO_ANSWER", "go")
    monkeypatch.setenv("EXPERIMENT_MAX_AUTO_RESUMES", "5")
    assert cli.auto_resume_policy() == ("go", 5)


# ── smoke pre-flight ─────────────────────────────────────────────────────────

async def test_smoke_preflight_never_invokes_the_model(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAPH_SMOKE_TEST", "1")
    summary_path = tmp_path / "summary.json"
    monkeypatch.setenv("EXPERIMENT_SUMMARY_JSON", str(summary_path))
    graph = _StubGraph([{}])

    result = await cli.run(_factory(graph), settings=_settings())

    assert result == {}
    assert graph.calls == []                      # no LLM invocation
    assert summary_path.is_file()                 # hand-off still exercised


# ── auto-resume loop ─────────────────────────────────────────────────────────

async def test_run_auto_resumes_within_the_budget(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_AUTO_ANSWER", "go")
    monkeypatch.setenv("EXPERIMENT_MAX_AUTO_RESUMES", "3")
    graph = _StubGraph([
        {"__interrupt__": [SimpleNamespace(value="Approve?")], "global_round": 1},
        {"__interrupt__": [], "global_round": 2, "workspacePATH": WS,
         "lemma_statuses": {}},
    ])

    result = await cli.run(_factory(graph), settings=_settings(), base_config={})

    assert result["global_round"] == 2
    assert len(graph.calls) == 2
    payload = graph.calls[1][0]
    assert isinstance(payload, Command)
    assert payload.resume == "go"


async def test_run_falls_back_to_input_when_the_budget_is_spent(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_AUTO_ANSWER", "go")
    monkeypatch.setenv("EXPERIMENT_MAX_AUTO_RESUMES", "0")
    monkeypatch.setattr("builtins.input", lambda _prompt="": "typed manually")
    graph = _StubGraph([
        {"__interrupt__": [SimpleNamespace(value="Approve?")], "global_round": 1},
        {"__interrupt__": [], "global_round": 2, "lemma_statuses": {}},
    ])

    await cli.run(_factory(graph), settings=_settings(), base_config={})

    assert graph.calls[1][0].resume == "typed manually"


async def test_run_waits_for_input_when_no_auto_answer_is_configured(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "human says yes")
    graph = _StubGraph([
        {"__interrupt__": [SimpleNamespace(value="Approve?")], "global_round": 1},
        {"__interrupt__": [], "global_round": 2, "lemma_statuses": {}},
    ])

    await cli.run(_factory(graph), settings=_settings(), base_config={})

    assert graph.calls[1][0].resume == "human says yes"


# ── failure path ─────────────────────────────────────────────────────────────

async def test_run_records_a_failure_summary_and_reraises(monkeypatch, tmp_path):
    summary_path = tmp_path / "summary.json"
    monkeypatch.setenv("EXPERIMENT_SUMMARY_JSON", str(summary_path))

    with pytest.raises(RuntimeError, match="boom"):
        await cli.run(_factory(_FailingGraph()), settings=_settings())

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "boom" in payload["error"]
    assert payload["proved"] is None  # did not finish, so not "0 proved"
