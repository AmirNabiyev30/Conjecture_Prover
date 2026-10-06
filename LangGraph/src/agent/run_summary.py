"""
Run-summary artifacts for the experiment harness.

Everything that produces a *record* of a run lives here, so ``graph.py`` stays
about building and running the graph:

- :func:`write_summary_json` — the best-effort ``EXPERIMENT_SUMMARY_JSON`` writer;
- :func:`condition_block` — the analyzer labels recorded alongside a run;
- :func:`smoke_payload`, :func:`failure_payload`, :func:`success_payload` — the
  three shapes a summary can take, as pure dict builders;
- :func:`unsolved_scan` — how many blueprint nodes the run left unsolved;
- :func:`print_unsolved_scan` — the human-readable form of that scan;
- :func:`state_get` — read a key from a LangGraph result, which may be a dict or
  an object.

The payload builders are deliberately pure, so the recorded schema can be tested
without running a graph.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from blueprint import UnsolvedSummary, scan_unsolved, scan_unsolved_from_file
from run_settings import RunSettings


def state_get(state: Any, key: str, default: Any = None) -> Any:
    """Read a key from a LangGraph result that may be a dict OR a State object.

    ``graph.ainvoke()`` returns the state as a plain ``dict`` (not the ``State``
    dataclass), so attribute access like ``result.blueprint`` raises
    ``AttributeError`` and silently killed every end-of-run summary. This helper
    normalizes access across both shapes.
    """
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def condition_block(settings: RunSettings) -> dict[str, object]:
    """The analyzer-condition labels recorded in the run summary."""
    return {
        "blueprint_generator_prompt": settings.generator_prompt,
        "enable_module_analysis": settings.enable_module_analysis,
        "blueprint_refiner_analyzer_mode": settings.refiner_analyzer_mode,
    }


def write_summary_json(payload: dict) -> None:
    """Write the structured end-of-run summary consumed by :mod:`experiments.runner`.

    Best-effort: a failure here must never take the whole run down. Does nothing
    when ``EXPERIMENT_SUMMARY_JSON`` is unset (an ordinary interactive run).
    """
    summary_json_path = os.environ.get("EXPERIMENT_SUMMARY_JSON", "")
    if not summary_json_path:
        return
    try:
        Path(summary_json_path).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        print(f"   💾 Wrote structured summary to {summary_json_path}")
    except Exception as e:
        print(f"   ⚠️  Could not write summary JSON to {summary_json_path}: {e}")


def _base_payload(settings: RunSettings, workspace_path: str) -> dict:
    """The fields every summary shares: what ran and under which arm."""
    return {
        "workspacePATH": workspace_path,
        "condition": condition_block(settings),
    }


def smoke_payload(settings: RunSettings, workspace_path: str) -> dict:
    """Stub written by the ``--smoke`` pre-flight; nothing was actually run.

    Writing it exercises the harness's summary-file handoff without spending a
    single token.
    """
    return {
        "round_reached": None,
        "total": 0,
        "proved": 0,
        "unproved": 0,
        "unsolved": [],
        **_base_payload(settings, workspace_path),
    }


def failure_payload(
    settings: RunSettings,
    workspace_path: str,
    result: Any,
    error: str,
) -> dict:
    """Written when the workflow raised, so the harness still records the round.

    Counts are ``None`` rather than ``0``: the run did not finish, so "nothing was
    proved" would be a false statement about the attempt.
    """
    return {
        "round_reached": state_get(result, "global_round", 0),
        "total": None,
        "proved": None,
        "unproved": None,
        "unsolved": [],
        **_base_payload(
            settings, state_get(result, "workspacePATH", workspace_path)
        ),
        "error": error,
    }


def success_payload(
    settings: RunSettings,
    workspace_path: str,
    round_reached: int | None,
    summary: UnsolvedSummary,
) -> dict:
    """The summary of a workflow that ran to its round/turn budget."""
    return {
        "round_reached": round_reached,
        "total": summary.total,
        "proved": summary.proved,
        "unproved": summary.unproved,
        "unsolved": summary.unsolved,
        **_base_payload(settings, workspace_path),
    }


def unsolved_scan(result: Any, workspace_path: str) -> tuple[UnsolvedSummary, dict]:
    """Count the blueprint nodes the run left unsolved.

    Prefers the source-text scan: the LeanArchitect blueprint JSON has no
    ``sorryFree`` field, so "unsolved" must be read from the real ``.lean`` bodies.
    Falls back to the status-derived scan when the workspace cannot be read or no
    blueprint was produced.

    Returns the summary and the lemma statuses (used for feedback printing).
    """
    blueprint = state_get(result, "blueprint")
    lemma_statuses = state_get(result, "lemma_statuses", {}) or {}

    workspace_source = ""
    try:
        workspace_source = Path(workspace_path).read_text()
    except Exception as e:
        print(f"   ⚠️  Could not read workspace for unsolved scan: {e}")

    try:
        if blueprint is not None and workspace_source:
            summary = scan_unsolved_from_file(blueprint, workspace_source)
        else:
            summary = scan_unsolved(blueprint, lemma_statuses)
    except Exception as e:
        print(f"   ⚠️  Unsolved scan failed; using empty summary: {e}")
        summary = UnsolvedSummary()

    return summary, lemma_statuses


def print_unsolved_scan(
    round_reached: int | None,
    max_rounds: int,
    summary: UnsolvedSummary,
    lemma_statuses: dict,
) -> None:
    """Print the end-of-run unsolved scan, with each node's prover feedback."""
    print("\n" + "=" * 70)
    print("📊 END-OF-RUN SUMMARY (unsolved scan)")
    print("=" * 70)
    print(
        f"round reached      = {round_reached}  "
        f"(budget: max_refinement_rounds={max_rounds})"
    )
    print(f"total nodes        = {summary.total}")
    print(f"proved             = {summary.proved}")
    print(f"UNSOLVED           = {summary.unproved}")
    for name in summary.unsolved:
        feedback = lemma_statuses.get(name, {}).get("feedback", "")
        print(f"   • {name}" + (f" — {feedback[:200]}" if feedback else ""))
    print("=" * 70)
