"""Unit tests for the run-summary artifacts.

Behavior contract:
- The three payload builders produce JSON-serialisable dicts that always carry
  ``workspacePATH`` and the same ``condition`` block.
- ``smoke_payload`` reports zeros (nothing ran); ``failure_payload`` reports
  ``None`` counts (the run did not finish, so "0 proved" would be a false claim)
  and records the error plus whatever round the run reached.
- ``write_summary_json`` writes when ``EXPERIMENT_SUMMARY_JSON`` is set, is a
  no-op when it is not, and never raises — a summary failure must not take the
  run down.
- ``state_get`` reads both dicts (LangGraph's result shape) and objects.
- ``unsolved_scan`` falls back to status-derived counts when the workspace
  cannot be read.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from blueprint import UnsolvedSummary  # noqa: E402
from run_settings import RunSettings  # noqa: E402
from run_summary import (  # noqa: E402
    condition_block,
    failure_payload,
    smoke_payload,
    state_get,
    success_payload,
    unsolved_scan,
    write_summary_json,
)

WS = "/tmp/workspace.lean"


def _settings() -> RunSettings:
    return RunSettings.from_env({})


def _unproved(name: str) -> dict:
    return {
        "name": name,
        "statement": "",
        "sorry_free": False,
        "status": "unproved",
        "dependencies": [],
        "feedback": "",
    }


# ── state_get ────────────────────────────────────────────────────────────────

def test_state_get_reads_dicts():
    assert state_get({"a": 1}, "a") == 1
    assert state_get({"a": 1}, "missing") is None
    assert state_get({"a": 1}, "missing", "fallback") == "fallback"


def test_state_get_reads_objects():
    obj = SimpleNamespace(a=2)
    assert state_get(obj, "a") == 2
    assert state_get(obj, "missing", "fallback") == "fallback"


# ── payload shapes ───────────────────────────────────────────────────────────

def test_smoke_payload_reports_zeros():
    """The pre-flight stub says "nothing ran" without claiming a failure."""
    payload = smoke_payload(_settings(), WS)
    assert payload["round_reached"] is None
    assert payload["total"] == payload["proved"] == payload["unproved"] == 0
    assert payload["unsolved"] == []


def test_failure_payload_reports_none_counts_and_the_error():
    payload = failure_payload(
        _settings(), WS, {"global_round": 4}, "RuntimeError('boom')"
    )
    assert payload["round_reached"] == 4
    assert payload["total"] is None
    assert payload["proved"] is None
    assert payload["unproved"] is None
    assert payload["unsolved"] == []
    assert payload["error"] == "RuntimeError('boom')"


def test_failure_payload_prefers_the_workspace_from_the_result():
    payload = failure_payload(
        _settings(), WS, {"workspacePATH": "/from/state.lean"}, "err"
    )
    assert payload["workspacePATH"] == "/from/state.lean"


def test_success_payload_carries_the_scan():
    scan = UnsolvedSummary(total=5, proved=3, unproved=2, unsolved=["a", "b"])
    payload = success_payload(_settings(), WS, 3, scan)
    assert payload["round_reached"] == 3
    assert payload["total"] == 5
    assert payload["proved"] == 3
    assert payload["unproved"] == 2
    assert payload["unsolved"] == ["a", "b"]


def test_every_payload_carries_the_shared_fields_and_serializes():
    """The harness json-dumps these, so every shape must round-trip."""
    settings = _settings()
    payloads = [
        smoke_payload(settings, WS),
        failure_payload(settings, WS, {"global_round": 1}, "err"),
        success_payload(settings, WS, 1, UnsolvedSummary(total=1, proved=1)),
    ]
    for payload in payloads:
        assert payload["workspacePATH"] == WS
        assert payload["condition"] == condition_block(settings)
        assert json.loads(json.dumps(payload)) == payload


# ── write_summary_json ───────────────────────────────────────────────────────

def test_write_summary_json_noops_without_the_env_var(monkeypatch):
    """An ordinary interactive run has no summary path and must not fail."""
    monkeypatch.delenv("EXPERIMENT_SUMMARY_JSON", raising=False)
    write_summary_json({"anything": True})


def test_write_summary_json_writes_the_payload(monkeypatch, tmp_path):
    target = tmp_path / "summary.json"
    monkeypatch.setenv("EXPERIMENT_SUMMARY_JSON", str(target))
    payload = {"round_reached": 2, "unsolved": ["a"]}
    write_summary_json(payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_write_summary_json_is_best_effort(monkeypatch, tmp_path):
    """An unwritable path must not take the run down."""
    monkeypatch.setenv(
        "EXPERIMENT_SUMMARY_JSON", str(tmp_path / "missing-dir" / "summary.json")
    )
    write_summary_json({"a": 1})  # must not raise


# ── unsolved_scan ────────────────────────────────────────────────────────────

def test_unsolved_scan_uses_statuses_when_there_is_no_blueprint(tmp_path):
    workspace = tmp_path / "Workspace.lean"
    workspace.write_text("-- empty\n", encoding="utf-8")
    statuses = {"a": _unproved("a")}

    scan, returned_statuses = unsolved_scan(
        {"lemma_statuses": statuses}, str(workspace)
    )

    assert scan.total == 1
    assert scan.unproved == 1
    assert scan.unsolved == ["a"]
    assert returned_statuses == statuses


def test_unsolved_scan_survives_an_unreadable_workspace(tmp_path):
    """A missing workspace file must degrade to the status-derived scan."""
    statuses = {"a": _unproved("a")}

    scan, _ = unsolved_scan(
        {"lemma_statuses": statuses}, str(tmp_path / "does-not-exist.lean")
    )

    assert scan.unproved == 1
