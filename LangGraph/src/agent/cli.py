"""
Operator-facing entry point for a single Conjecture Prover run.

Holds everything an *operator* controls around one graph invocation, so
``graph.py`` can stay about graph construction:

- the zero-cost ``GRAPH_SMOKE_TEST`` pre-flight;
- per-run LangSmith metadata tags (``EXPERIMENT_METADATA``);
- the human-in-the-loop auto-resume policy for autonomous runs;
- the task prompt handed to the graph;
- the end-of-run summary hand-off to the experiment harness.

The graph factory is *passed in* rather than imported. That keeps this module free
of a circular import with ``graph.py`` — and, because the harness runs
``graph.py`` as a script, it also avoids loading ``graph`` twice under two
different module names. It also lets tests drive :func:`run` with a stub graph.

Environment variables owned here:

    EXPERIMENT_AUTO_ANSWER=<str>       canned resume answer for ask_human
                                       interrupts (avoids blocking on input())
    EXPERIMENT_MAX_AUTO_RESUMES=<int>  cap on auto-resumes (default: 3)
    EXPERIMENT_SUMMARY_JSON=<path>     dump an end-of-run summary JSON here
    EXPERIMENT_METADATA=<json object>  per-run LangSmith metadata tags
    GRAPH_SMOKE_TEST=1                 build the graph (incl. Lean MCP) then exit
                                       before any LLM invocation; used by
                                       `python -m experiments.runner --smoke`

Run *configuration* (model, budgets, prompts, analyzer flags) is not handled
here — see ``run_settings.RunSettings``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable

from langgraph.types import Command

from config import WORKSPACE_PATH
from run_settings import RunSettings
from run_summary import (
    failure_payload,
    print_unsolved_scan,
    smoke_payload,
    state_get,
    success_payload,
    unsolved_scan,
    write_summary_json,
)

#: Values accepted for boolean environment variables.
_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def smoke_test_requested() -> bool:
    """True when the caller asked for the zero-cost construction pre-flight."""
    return os.environ.get("GRAPH_SMOKE_TEST", "").strip().lower() in _TRUTHY


def initial_state(workspace_path: str = WORKSPACE_PATH) -> dict[str, str]:
    """The task prompt handed to the graph for a run."""
    return {
        "theorem": (
            "The target formalization is in the Lean workspace file "
            f"at `{workspace_path}`. Read the file to find the theorem "
            "statement and any existing definitions."
        ),
        "workspacePATH": workspace_path,
    }


def invoke_config(base_config: dict) -> dict:
    """The invoke config plus per-run LangSmith metadata tags, when configured."""
    cfg = dict(base_config)
    raw_metadata = os.environ.get("EXPERIMENT_METADATA", "")
    if not raw_metadata:
        return cfg
    try:
        cfg["metadata"] = json.loads(raw_metadata)
    except Exception as e:
        print(f"   ⚠️  Invalid EXPERIMENT_METADATA JSON; ignoring: {e}")
    return cfg


def auto_resume_policy() -> tuple[str, int]:
    """The (canned answer, max resumes) used to answer ask_human interrupts.

    A malformed ``EXPERIMENT_MAX_AUTO_RESUMES`` raises rather than silently
    defaulting: the caller wraps this so the run still records a failure summary.
    """
    return (
        os.environ.get("EXPERIMENT_AUTO_ANSWER", ""),
        int(os.environ.get("EXPERIMENT_MAX_AUTO_RESUMES", "3")),
    )


async def run(
    build_graph: Callable[..., Awaitable[Any]],
    *,
    settings: RunSettings | None = None,
    base_config: dict | None = None,
) -> dict:
    """Build the graph, run one workflow to completion, and write its summary.

    Args:
        build_graph: Async factory taking ``RunSettings`` and returning a
            compiled graph. Passed in to avoid importing ``graph.py``.
        settings: Run configuration; defaults to :meth:`RunSettings.from_env`.
        base_config: LangGraph invoke config to extend with metadata tags.

    Returns:
        The final graph state as a dict (empty for the smoke pre-flight).

    Raises:
        Whatever the workflow raised, after recording a failure summary.
    """
    settings = settings or RunSettings.from_env()
    context = settings.to_context()

    # Build the graph with the analyzer tool registered only where the run
    # condition allows it (structural guarantee at the ToolNode level).
    graph = await build_graph(settings)

    # Zero-cost pre-flight: verify the spawn path (env parsing + graph
    # construction + Lean MCP startup) and exit before any LLM invocation. Also
    # write a stub summary so the harness's summary-file handoff is exercised.
    if smoke_test_requested():
        print("SMOKE_OK: graph built (no LLM invocation)")
        print(f"SMOKE_OK: generator_prompt={settings.generator_prompt}")
        print(f"SMOKE_OK: enable_module_analysis={settings.enable_module_analysis}")
        print(f"SMOKE_OK: blueprint_refiner_analyzer_mode={settings.refiner_analyzer_mode}")
        summary_json_path = os.environ.get("EXPERIMENT_SUMMARY_JSON", "")
        if summary_json_path:
            write_summary_json(smoke_payload(settings, WORKSPACE_PATH))
            print(f"SMOKE_OK: wrote stub summary to {summary_json_path}")
        return {}

    cfg = invoke_config(base_config or {})

    # ── Workflow execution (wrapped so a node crash still yields a summary) ──
    result: dict = {}
    try:
        result = await graph.ainvoke(
            initial_state(), context=context, config=cfg
        )

        # ── Human-in-the-loop: auto-resume for autonomous runs ──────────────
        # Read inside the try so a malformed value still records a summary.
        auto_answer, max_auto_resumes = auto_resume_policy()
        auto_resumes = 0
        while interrupt_val := result.get("__interrupt__"):
            print("\n--- GRAPH PAUSED ---")
            print(f"Question: {interrupt_val[0].value}")
            if auto_answer and auto_resumes < max_auto_resumes:
                answer = auto_answer
                auto_resumes += 1
                print(
                    f"   (autonomous) auto-resuming with {answer!r} "
                    f"({auto_resumes}/{max_auto_resumes})"
                )
            else:
                answer = input("Your response: ")
            result = await graph.ainvoke(
                Command(resume=answer), context=context, config=cfg
            )
    except Exception as e:
        # A node/tool failure (e.g. OpenAI 402) must still leave a summary
        # artifact so the harness can record what round was reached.
        print(f"\n❌ WORKFLOW FAILED: {e!r}")
        write_summary_json(
            failure_payload(settings, WORKSPACE_PATH, result, repr(e))
        )
        raise

    # ── End-of-run summary ──────────────────────────────────────────────────
    # LangGraph returns the state as a dict, so reads go through state_get.
    # unsolved_scan prefers the source-text scan because the LeanArchitect
    # blueprint JSON carries no `sorryFree` field.
    workspace_path = state_get(result, "workspacePATH", WORKSPACE_PATH)
    round_reached = state_get(result, "global_round", 0)
    scan, lemma_statuses = unsolved_scan(result, workspace_path)
    print_unsolved_scan(
        round_reached, settings.max_refinement_rounds, scan, lemma_statuses
    )
    write_summary_json(
        success_payload(settings, workspace_path, round_reached, scan)
    )
    return result
