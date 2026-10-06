#!/usr/bin/env python3
"""Autonomous experiment runner for the Conjecture Prover analyzer-utilization study.

Design
------
Each stage-1 run pairs one problem with one analyzer "condition" (arm). A run is an
isolated subprocess that executes ``LangGraph/src/agent/graph.py main()`` with
environment-variable overrides, so that:

  * the terminal output of the run is teed to a per-run log file,
  * the run is crash-isolated (a failure in one run does not stop the batch),
  * completed runs can be skipped on re-invocation (``--resume``, the default),
  * a structured ``summary.json`` is produced per run for the results table,
  * LangSmith traces land in a dedicated project with per-run metadata tags.

Conditions (3 aligned arms) map the code-module-analyzer usage across BOTH
route-planning stages (blueprint generator + blueprint refiner):

  with_analyzer       generator uses the analyzer, refiner mode=required
  wo_analyzer         analyzer unavailable everywhere, refiner mode=none
  optional_analyzer   analyzer available (model decides), refiner mode=optional

The generator side is driven by ``BLUEPRINT_GENERATOR_PROMPT`` +
``ENABLE_MODULE_ANALYSIS``; the refiner side by ``BLUEPRINT_REFINER_ANALYZER_MODE``.
Conditions and their prompt paths are defined once in
``LangGraph/src/agent/conditions.py``; the graph reads the variables through
``RunSettings.from_env``.

Usage (from the repository root):

    LangGraph/.venv/bin/python -m experiments.runner --list
    LangGraph/.venv/bin/python -m experiments.runner --only with_analyzer__fateX_94
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
# This module lives in <repo>/experiments/, so the repo root is one level up.
REPO_ROOT: Path = Path(__file__).resolve().parents[1]
LANGGRAPH_DIR: Path = REPO_ROOT / "LangGraph"
AGENT_SRC: Path = LANGGRAPH_DIR / "src" / "agent"
GRAPH_SCRIPT: Path = AGENT_SRC / "graph.py"
WORKSPACE: Path = REPO_ROOT / "ConjectureProver.lean"
STALE_BLUEPRINT_JSON: Path = (
    REPO_ROOT / ".lake" / "build" / "blueprint" / "module" / "ConjectureProver.json"
)

# The condition table lives with the agent, next to the settings it maps onto, so
# the harness imports it rather than restating prompt paths. Same path convention
# the unit tests use for the agent package.
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from conditions import CONDITIONS, AnalyzerCondition  # noqa: E402

# ── Experiment manifest (stage 1) ─────────────────────────────────────────────
# Stage-1 is currently scoped to a single problem (fateX_94); expand here to
# bring other problems/categories back into the matrix.
PROBLEMS: dict[str, str] = {
    "fateX_94": "experiment_problems/fateX/94.txt",
}

# Condition slugs, prompt paths and analyzer flags are defined once in
# LangGraph/src/agent/conditions.py (imported above) — the harness applies an arm
# by rendering it to environment variables via AnalyzerCondition.to_env().

DEFAULT_AUTO_ANSWER = "Proceed autonomously with your best judgment"

RESULT_FIELDS = [
    "run_id", "problem_id", "condition", "status", "exit_code",
    "started_at", "ended_at", "duration_s",
    "round_reached", "total", "proved", "unproved", "unsolved",
    "log_path", "summary_path", "artifact_path", "notes",
]


def run_id(condition: str, problem_id: str) -> str:
    """Canonical identifier for a (condition, problem) run."""
    return f"{condition}__{problem_id}"


def _default_python() -> str:
    """Prefer the LangGraph uv virtualenv (has all agent dependencies) for runs."""
    venv_python = LANGGRAPH_DIR / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def _ensure_dirs(output_dir: Path) -> None:
    for sub in ("logs", "summaries", "artifacts", "backup"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)


def _backup_workspace(output_dir: Path) -> Path:
    """Back up the pristine workspace once (never clobber the original)."""
    backup_path = output_dir / "backup" / "ConjectureProver.lean.original"
    if not backup_path.exists() and WORKSPACE.exists():
        shutil.copy2(WORKSPACE, backup_path)
        print(f"💾 Backed up ConjectureProver.lean -> {backup_path}")
    return backup_path


def _restore_workspace(output_dir: Path) -> None:
    backup_path = output_dir / "backup" / "ConjectureProver.lean.original"
    if backup_path.exists():
        shutil.copy2(backup_path, WORKSPACE)
        print(f"♻️  Restored ConjectureProver.lean from {backup_path}")


def _clear_stale_blueprint_json() -> None:
    """Remove a leftover blueprint JSON so a fresh problem does not inherit it."""
    try:
        if STALE_BLUEPRINT_JSON.exists():
            STALE_BLUEPRINT_JSON.unlink()
            print(f"   🧹 Cleared stale blueprint JSON: {STALE_BLUEPRINT_JSON}")
    except OSError as e:
        print(f"   ⚠️  Could not clear stale blueprint JSON {STALE_BLUEPRINT_JSON}: {e}")


def _load_summary(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _write_csv_from_jsonl(jsonl_path: Path, csv_path: Path) -> None:
    records: list[dict] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def _spawn_and_tee(
    cmd: list[str],
    env: dict[str, str],
    cwd: Path,
    log_path: Path,
    timeout_seconds: float | None,
) -> dict:
    """Spawn the subprocess, teeing stdout+stderr to both the terminal and the log."""
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    def _tee() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            log_handle.write(line)
            log_handle.flush()
            sys.stdout.write(line)
            sys.stdout.flush()

    with open(log_path, "w", encoding="utf-8") as log_handle:
        tee_thread = threading.Thread(target=_tee, daemon=True)
        tee_thread.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        except KeyboardInterrupt:
            proc.kill()
            proc.wait()
            raise
        finally:
            tee_thread.join(timeout=10)

    return {
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - start, 1),
    }


def run_single(
    problem_id: str,
    condition: str,
    *,
    output_dir: Path,
    langsmith_project: str,
    auto_answer: str,
    max_auto_resumes: int,
    timeout_minutes: int,
    python: str,
    stage: str = "1",
    dry_run: bool = False,
    smoke: bool = False,
) -> dict:
    """Run one (problem, condition) pair and return a results record."""
    # Absolute paths are required: the graph subprocess runs with cwd=LangGraph/,
    # so a relative summary/log path would be resolved against the wrong directory.
    output_dir = output_dir.resolve()
    condition_cfg: AnalyzerCondition = CONDITIONS[condition]
    problem_rel = PROBLEMS[problem_id]
    rid = run_id(condition, problem_id)

    log_path = output_dir / "logs" / f"{rid}.log"
    summary_path = output_dir / "summaries" / f"{rid}.summary.json"
    artifact_dir = output_dir / "artifacts" / rid
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_workspace = artifact_dir / "ConjectureProver.lean"

    problem_source = (REPO_ROOT / problem_rel).read_text(encoding="utf-8")
    generator_prompt = Path(condition_cfg.generator_prompt)
    if not generator_prompt.is_file():
        raise FileNotFoundError(f"generator prompt not found: {generator_prompt}")

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print("\n" + "=" * 78)
    print(f"▶️  RUN {rid}")
    print(f"   problem        = {problem_id}  ({problem_rel})")
    print(f"   condition      = {condition}")
    print(f"   generator      = {generator_prompt}")
    print(f"   module analysis= {condition_cfg.enable_module_analysis}")
    print(f"   refiner mode   = {condition_cfg.refiner_analyzer_mode}")
    print(f"   log            = {log_path}")
    print(f"   summary        = {summary_path}")
    print("=" * 78 + "\n")

    # 1. Write the problem into the workspace (with a run-identifying header).
    header_comment = (
        "/-\n"
        f"EXPERIMENT RUN {rid} (stage {stage}, condition={condition}, problem={problem_id})\n"
        "Generated by experiments/runner.py — do not edit by hand.\n"
        "-/\n\n"
    )
    WORKSPACE.write_text(header_comment + problem_source, encoding="utf-8")
    _clear_stale_blueprint_json()

    # 2. Build the subprocess environment (all consumed by graph.py main()).
    env = dict(os.environ)
    env.update(condition_cfg.to_env())
    env["LANGSMITH_PROJECT"] = langsmith_project
    env["LANGSMITH_TRACING"] = "true"  # the experiment always needs token traces
    env["EXPERIMENT_METADATA"] = json.dumps({
        "run_id": rid,
        "stage": stage,
        "condition": condition,
        "problem": problem_id,
        "category": problem_id.split("_")[0],
    })
    env["EXPERIMENT_AUTO_ANSWER"] = auto_answer
    env["EXPERIMENT_MAX_AUTO_RESUMES"] = str(max_auto_resumes)
    env["EXPERIMENT_SUMMARY_JSON"] = str(summary_path)
    if smoke:
        env["GRAPH_SMOKE_TEST"] = "1"

    timed_out = False
    exit_code = 0
    notes = ""
    if dry_run:
        # Simulate a run without spawning the graph or spending tokens.
        print("   🧪 DRY-RUN: not spawning the graph; writing placeholder artifacts.")
        log_path.write_text(
            "# DRY-RUN placeholder log\n"
            "========================================================\n"
            "📊 END-OF-RUN SUMMARY (unsolved scan)\n"
            "round reached      = 3  (budget: MAX_REFINEMENT_ROUNDS=16)\n"
            "total nodes        = 6\n"
            "proved             = 4\n"
            "UNSOLVED           = 2\n"
            "   • unproved_lemma_a\n"
            "   • unproved_lemma_b\n"
            "========================================================\n",
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps({
                "round_reached": 3,
                "total": 6,
                "proved": 4,
                "unproved": 2,
                "unsolved": ["unproved_lemma_a", "unproved_lemma_b"],
                "workspacePATH": str(WORKSPACE),
                "condition": condition_cfg.to_dict(),
            }, indent=2),
            encoding="utf-8",
        )
        status = "dry_run"
        notes = "dry-run (no LLM calls)"
    else:
        timeout_seconds = timeout_minutes * 60 if timeout_minutes else None
        outcome = _spawn_and_tee(
            [python, str(GRAPH_SCRIPT)],
            env=env,
            cwd=LANGGRAPH_DIR,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        exit_code = outcome["exit_code"]
        timed_out = outcome["timed_out"]
        duration_s = outcome["duration_s"]
        if timed_out:
            status = "timeout"
            notes = f"killed after {timeout_minutes} min wall-clock timeout"
        elif exit_code == 0:
            status = "smoke" if smoke else "completed"
            if smoke:
                notes = "smoke (no LLM invocation)"
        else:
            status = "failed"

    # 3. Preserve the final workspace state for this run.
    try:
        shutil.copy2(WORKSPACE, artifact_workspace)
    except OSError as e:
        notes = (notes + "; " if notes else "") + f"artifact copy failed: {e}"

    # 4. Collect the structured summary produced by the run.
    summary = _load_summary(summary_path)
    if summary:
        round_reached = summary.get("round_reached")
        total = summary.get("total")
        proved = summary.get("proved")
        unproved = summary.get("unproved")
        unsolved = summary.get("unsolved", [])
    else:
        round_reached = total = proved = unproved = None
        unsolved = []
        notes = (notes + "; " if notes else "") + "no summary.json produced"

    # 5. Classify billing failures so the results table distinguishes them from
    # genuine workflow bugs. The OpenAI client raises HTTP 402 (Insufficient
    # Balance), which currently manifests as a bare exit-code-1 "failed".
    if status == "failed" and log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "Insufficient Balance" in log_text or "Error code: 402" in log_text:
            status = "insufficient_balance"
            notes = (notes + "; " if notes else "") + "OpenAI API 402 Insufficient Balance"

    # 6. Integrity check: the analyzer must never be invoked in a wo_analyzer
    # run. ``print_ai_response`` emits "→ analyze_mathlib_module" for real tool
    # calls, so scanning the log for that marker catches any leak.
    if condition == "wo_analyzer" and log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "→ analyze_mathlib_module" in log_text:
            notes = (notes + "; " if notes else "") + (
                "ANALYZER_LEAK: analyze_mathlib_module invoked despite wo_analyzer"
            )

    ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    duration_s = duration_s if not dry_run else 0.0

    return {
        "run_id": rid,
        "problem_id": problem_id,
        "condition": condition,
        "status": status,
        "exit_code": exit_code,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_s": duration_s,
        "round_reached": round_reached,
        "total": total,
        "proved": proved,
        "unproved": unproved,
        "unsolved": "; ".join(unsolved),
        "log_path": str(log_path),
        "summary_path": str(summary_path),
        "artifact_path": str(artifact_dir),
        "notes": notes,
    }


def run_batch(
    problems: list[str],
    conditions: list[str],
    *,
    output_dir: Path,
    resume: bool = True,
    restore: bool = True,
    timeout_minutes: int,
    dry_run: bool = False,
    smoke: bool = False,
    langsmith_project: str,
    auto_answer: str,
    max_auto_resumes: int,
    python: str,
    stage: str = "1",
) -> None:
    """Run the (problems x conditions) matrix sequentially, recording results."""
    _ensure_dirs(output_dir)
    _backup_workspace(output_dir)

    results_jsonl = output_dir / "results.jsonl"
    results_csv = output_dir / "results.csv"

    print("\n" + "=" * 78)
    print(f"🧪 EXPERIMENT BATCH (stage {stage}): {len(conditions)} condition(s) x "
          f"{len(problems)} problem(s) = {len(conditions) * len(problems)} runs")
    for condition in conditions:
        for problem_id in problems:
            print(f"   • {run_id(condition, problem_id)}")
    print("=" * 78 + "\n")

    counts: dict[str, int] = {}
    stop = False
    try:
        for condition in conditions:
            for problem_id in problems:
                if stop:
                    break
                rid = run_id(condition, problem_id)
                summary_path = output_dir / "summaries" / f"{rid}.summary.json"

                if resume and summary_path.is_file():
                    print(f"⏭️  SKIP {rid}: summary already exists ({summary_path.name})")
                    counts["skipped"] = counts.get("skipped", 0) + 1
                    continue

                try:
                    record = run_single(
                        problem_id,
                        condition,
                        output_dir=output_dir,
                        langsmith_project=langsmith_project,
                        auto_answer=auto_answer,
                        max_auto_resumes=max_auto_resumes,
                        timeout_minutes=timeout_minutes,
                        python=python,
                        stage=stage,
                        dry_run=dry_run,
                        smoke=smoke,
                    )
                except KeyboardInterrupt:
                    print("\n⏹️  Batch interrupted — restoring workspace and stopping.")
                    stop = True
                    break
                except Exception as e:  # per-run isolation
                    print(f"   ❌ RUN {rid} ERROR: {e}")
                    record = {
                        "run_id": rid,
                        "problem_id": problem_id,
                        "condition": condition,
                        "status": "error",
                        "exit_code": None,
                        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "duration_s": 0.0,
                        "round_reached": None,
                        "total": None,
                        "proved": None,
                        "unproved": None,
                        "unsolved": "",
                        "log_path": str(output_dir / "logs" / f"{rid}.log"),
                        "summary_path": str(summary_path),
                        "artifact_path": "",
                        "notes": str(e),
                    }

                counts[record["status"]] = counts.get(record["status"], 0) + 1
                _append_jsonl(results_jsonl, record)
                _write_csv_from_jsonl(results_jsonl, results_csv)
                print(f"   ✅ {record['run_id']} -> status={record['status']} "
                      f"(proved={record['proved']}, unproved={record['unproved']})")
            if stop:
                break
    finally:
        if restore:
            _restore_workspace(output_dir)

    print("\n" + "=" * 78)
    print("📈 BATCH SUMMARY")
    for status, n in counts.items():
        print(f"   {status:<12} = {n}")
    print(f"   results        = {results_jsonl}")
    print(f"   results table  = {results_csv}")
    print("=" * 78 + "\n")


def _resolve_problems(args_problems: str | None, only: list[str] | None) -> list[str]:
    if only:
        wanted_conditions = set(only)
        problems = [
            p for p in PROBLEMS
            if any(p in rid for rid in wanted_conditions)
        ]
        return problems or list(PROBLEMS)
    if args_problems:
        return [p.strip() for p in args_problems.split(",") if p.strip()]
    return list(PROBLEMS)


def _resolve_conditions(args_conditions: str | None, only: list[str] | None) -> list[str]:
    if only:
        return [c for c in CONDITIONS if any(c in rid for rid in only)] or list(CONDITIONS)
    if args_conditions:
        return [c.strip() for c in args_conditions.split(",") if c.strip()]
    return list(CONDITIONS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Conjecture Prover analyzer-utilization experiment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--problems", help="comma-separated problem ids (default: all stage-1)")
    parser.add_argument("--conditions", help="comma-separated condition slugs (default: all)")
    parser.add_argument("--only", help="comma-separated run_ids to run exclusively")
    parser.add_argument("--no-resume", action="store_true",
                        help="re-run even if a summary.json already exists")
    parser.add_argument("--timeout-minutes", type=int, default=90,
                        help="wall-clock timeout per run (0 = no timeout)")
    parser.add_argument("--output-dir", default="experiment_runs",
                        help="directory for logs, summaries, artifacts, and results")
    parser.add_argument("--langsmith-project", default="conjecture_experiment",
                        help="LangSmith project for this experiment's traces")
    parser.add_argument("--auto-answer", default=DEFAULT_AUTO_ANSWER,
                        help="canned answer used to auto-resume ask_human interrupts")
    parser.add_argument("--max-auto-resumes", type=int, default=3,
                        help="cap on auto-resumes per run")
    parser.add_argument("--dry-run", action="store_true",
                        help="simulate runs without spawning the graph (no LLM calls)")
    parser.add_argument("--smoke", action="store_true",
                        help="real-spawn pre-flight: build the graph (incl. Lean MCP) then "
                             "exit before any LLM call (zero cost)")
    parser.add_argument("--no-restore", action="store_true",
                        help="do not restore the original workspace after the batch")
    parser.add_argument("--stage", default="1", help="experiment stage tag")
    parser.add_argument("--list", action="store_true", help="print the run matrix and exit")
    parser.add_argument("--python", default=_default_python(),
                        help="python interpreter for runs (default: LangGraph/.venv)")
    args = parser.parse_args(argv)

    for cond_name, cond in CONDITIONS.items():
        for label, prompt_path in (
            ("generator", cond.generator_prompt),
            ("refiner", cond.refiner_prompt),
        ):
            if not Path(prompt_path).is_file():
                print(f"❌ Missing {label} prompt for condition '{cond_name}': {prompt_path}")
                return 2

    if args.smoke and args.dry_run:
        print("⚠️  --smoke takes precedence over --dry-run; ignoring --dry-run.")
        args.dry_run = False

    only: list[str] = []
    if args.only:
        only = [r.strip() for r in args.only.split(",") if r.strip()]
        for rid in only:
            if "__" not in rid:
                print(f"❌ Invalid run_id '{rid}' (expected <condition>__<problem_id>)")
                return 2
            cond_part, prob_part = rid.split("__", 1)
            if cond_part not in CONDITIONS:
                print(f"❌ Unknown condition '{cond_part}' in run_id '{rid}'")
                return 2
            if prob_part not in PROBLEMS:
                print(f"❌ Unknown problem '{prob_part}' in run_id '{rid}'")
                return 2

    problems = _resolve_problems(args.problems, only)
    conditions = _resolve_conditions(args.conditions, only)

    unknown_p = [p for p in problems if p not in PROBLEMS]
    unknown_c = [c for c in conditions if c not in CONDITIONS]
    if unknown_p or unknown_c:
        print(f"❌ Unknown problems: {unknown_p}; unknown conditions: {unknown_c}")
        return 2

    if args.list:
        print(f"\nStage-{args.stage} matrix ({len(conditions)} condition(s) x "
              f"{len(problems)} problem(s) = {len(conditions) * len(problems)} runs):")
        for condition in conditions:
            for problem_id in problems:
                print(f"   • {run_id(condition, problem_id)}")
        print()
        return 0

    if not GRAPH_SCRIPT.is_file():
        print(f"❌ Graph script not found: {GRAPH_SCRIPT}")
        return 2

    output_dir = Path(args.output_dir)
    run_batch(
        problems,
        conditions,
        output_dir=output_dir,
        resume=not args.no_resume,
        restore=not args.no_restore,
        timeout_minutes=args.timeout_minutes,
        dry_run=args.dry_run,
        smoke=args.smoke,
        langsmith_project=args.langsmith_project,
        auto_answer=args.auto_answer,
        max_auto_resumes=args.max_auto_resumes,
        python=args.python,
        stage=args.stage,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
