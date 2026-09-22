#!/usr/bin/env python3
"""Summarize experiment results produced by ``experiment_runner.py``.

Reads ``experiment_runs/results.jsonl`` and prints:
  * a per-run table (one row per (condition x problem) run),
  * a per-condition comparison of proved/unproved/round/duration over runs that
    produced a structured summary (i.e. ``total`` is not null),
  * a per-problem comparison,
  * and (optionally) writes a stage-1 markdown report to ``experiment_runs/``.

Token usage is tracked in LangSmith (project set by ``--langsmith-project`` on the
runner); this script does not fetch it.  Dry-run rows are shown in the per-run
table but excluded from the comparison aggregates.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

DEFAULT_DIR = "experiment_runs"


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_results(dir_path: Path) -> list[dict]:
    jsonl = dir_path / "results.jsonl"
    if not jsonl.exists():
        return []
    records = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _agg(records: list[dict], key: str):
    values = [_num(r.get(key)) for r in records if _num(r.get(key)) is not None]
    if not values:
        return None
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(statistics.mean(values), 2),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def compare_by_key(records: list[dict], key: str) -> dict[str, list[dict]]:
    """Group records by ``key``; keep only real runs with a numeric ``total``.

    Synthetic rows — statuses ``dry_run`` and ``smoke`` — are excluded from the
    comparison aggregates (they only exist to validate the harness plumbing).
    """
    grouped: dict[str, list[dict]] = {}
    for r in records:
        if str(r.get("status")) in {"dry_run", "smoke"}:
            continue
        if _num(r.get("total")) is None:
            continue  # no structured summary -> not comparable
        grouped.setdefault(str(r.get(key)), []).append(r)
    return grouped


def _cell(v) -> str:
    """Render a results-table cell: None/empty -> '—', else str(v)."""
    if v is None or v == "" or str(v) == "None":
        return "—"
    return str(v)


def print_per_run_table(records: list[dict]) -> None:
    print("\n" + "=" * 120)
    print("PER-RUN TABLE")
    print("=" * 120)
    header = ("run_id", "problem", "condition", "status", "exit", "dur_s",
              "round", "total", "proved", "unproved", "notes")
    widths = {h: len(h) for h in header}
    rows = []
    for r in records:
        row = (
            str(r.get("run_id", "")),
            str(r.get("problem_id", "")),
            str(r.get("condition", "")),
            _cell(r.get("status")),
            _cell(r.get("exit_code")),
            _cell(r.get("duration_s")),
            _cell(r.get("round_reached")),
            _cell(r.get("total")),
            _cell(r.get("proved")),
            _cell(r.get("unproved")),
            str(r.get("notes", ""))[:44],
        )
        rows.append(row)
        for h, cell in zip(header, row):
            widths[h] = max(widths[h], len(cell))
    fmt = "  ".join(f"{{:<{widths[h]}}}" for h in header)
    print(fmt.format(*header))
    print("  ".join("-" * widths[h] for h in header))
    for row in rows:
        print(fmt.format(*row))
    print()


def print_status_summary(records: list[dict]) -> None:
    """Roll up statuses (incl. timeout/failed/insufficient_balance) so a batch
    that mostly crashed or timed out is legible at a glance, not just a table of
    '—' cells."""
    counts: dict[str, int] = {}
    for r in records:
        status = str(r.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    n_with_summary = sum(1 for r in records if _num(r.get("total")) is not None)
    print("=" * 60)
    print("STATUS ROLLUP (all recorded runs)")
    print("=" * 60)
    for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"   {status:<24} = {n}")
    print(f"   {'runs with summary':<24} = {n_with_summary}")
    print()


def _fmt_agg(agg: dict | None) -> str:
    if agg is None:
        return "  —"
    return (f" n={agg['n']} mean={agg['mean']} med={agg['median']} "
            f"min={agg['min']} max={agg['max']} sum={agg['sum']}")


def print_comparison(records: list[dict], key: str, label: str) -> None:
    grouped = compare_by_key(records, key)
    print("=" * 100)
    print(f"COMPARISON BY {label.upper()} (runs with a structured summary)")
    print("=" * 100)
    print(f"{label:<18} {'runs':>4}  {'proved':<34} {'unproved':<34} {'round':<34} {'dur_s':<28}")
    for group in sorted(grouped):
        g = grouped[group]
        proved = _agg(g, "proved")
        unproved = _agg(g, "unproved")
        round_ = _agg(g, "round_reached")
        dur = _agg(g, "duration_s")
        print(f"{group:<18} {len(g):>4}  {_fmt_agg(proved):<34} {_fmt_agg(unproved):<34} "
              f"{_fmt_agg(round_):<34} {_fmt_agg(dur):<28}")
    print()


def _unsolved_brief(records: list[dict]) -> str:
    names: list[str] = []
    for r in records:
        for item in str(r.get("unsolved", "")).split(";"):
            item = item.strip()
            if item and item not in names:
                names.append(item)
    return ", ".join(names) if names else "—"


def write_report(records: list[dict], out: Path, stage: str, langsmith_project: str) -> None:
    lines: list[str] = []
    lines.append(f"# Conjecture Prover — Analyzer-Utilization Experiment (Stage {stage})")
    lines.append("")
    lines.append(f"- Source: `results.jsonl` ({len(records)} recorded run(s))")
    lines.append(f"- LangSmith project: `{langsmith_project}` (token usage)")
    lines.append("")
    lines.append("## Per-run table")
    lines.append("")
    lines.append("| run_id | problem | condition | status | exit | dur_s | round | total | proved | unproved | notes |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        notes = str(r.get("notes", "")).replace("|", "/")
        lines.append(
            f"| {r.get('run_id','')} | {r.get('problem_id','')} | {r.get('condition','')} "
            f"| {_cell(r.get('status'))} | {_cell(r.get('exit_code'))} | {_cell(r.get('duration_s'))} "
            f"| {_cell(r.get('round_reached'))} | {_cell(r.get('total'))} | {_cell(r.get('proved'))} "
            f"| {_cell(r.get('unproved'))} | {notes} |"
        )
    lines.append("")
    lines.append("## Status rollup")
    lines.append("")
    lines.append("| status | count |")
    lines.append("|---|---|")
    status_counts: dict[str, int] = {}
    for r in records:
        status = str(r.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    for status, n in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {status} | {n} |")
    lines.append("")
    lines.append("## Comparison by condition")
    lines.append("")
    lines.append("| condition | runs | proved mean/med | unproved mean/med | round mean/med | dur_s mean/med |")
    lines.append("|---|---|---|---|---|---|")
    grouped = compare_by_key(records, "condition")
    for group in sorted(grouped):
        g = grouped[group]
        proved = _agg(g, "proved")
        unproved = _agg(g, "unproved")
        round_ = _agg(g, "round_reached")
        dur = _agg(g, "duration_s")
        p = f"{proved['mean']}/{proved['median']}" if proved else "—"
        u = f"{unproved['mean']}/{unproved['median']}" if unproved else "—"
        rd = f"{round_['mean']}/{round_['median']}" if round_ else "—"
        d = f"{dur['mean']}/{dur['median']}" if dur else "—"
        lines.append(f"| {group} | {len(g)} | {p} | {u} | {rd} | {d} |")
    lines.append("")
    lines.append("## Comparison by problem")
    lines.append("")
    lines.append("| problem | runs | proved mean/med | unproved mean/med | round mean/med | dur_s mean/med |")
    lines.append("|---|---|---|---|---|---|")
    by_problem = compare_by_key(records, "problem_id")
    for group in sorted(by_problem):
        g = by_problem[group]
        proved = _agg(g, "proved")
        unproved = _agg(g, "unproved")
        round_ = _agg(g, "round_reached")
        dur = _agg(g, "duration_s")
        p = f"{proved['mean']}/{proved['median']}" if proved else "—"
        u = f"{unproved['mean']}/{unproved['median']}" if unproved else "—"
        rd = f"{round_['mean']}/{round_['median']}" if round_ else "—"
        d = f"{dur['mean']}/{dur['median']}" if dur else "—"
        lines.append(f"| {group} | {len(g)} | {p} | {u} | {rd} | {d} |")
    lines.append("")
    lines.append("## Unsolved nodes (union across runs, per condition)")
    lines.append("")
    for group in sorted(grouped):
        lines.append(f"- **{group}**: {_unsolved_brief(grouped[group])}")
    lines.append("")
    lines.append("> Token usage is not captured here — filter the LangSmith project "
                 "by the `condition`/`problem` metadata tags.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"📄 Wrote report to {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize Conjecture Prover experiment results.")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="experiment output directory")
    parser.add_argument("--stage", default="1")
    parser.add_argument("--langsmith-project", default="conjecture_experiment")
    parser.add_argument("--no-report", action="store_true",
                        help="do not write the markdown report")
    args = parser.parse_args(argv)

    records = load_results(Path(args.dir))
    if not records:
        print(f"⚠️  No results found in {args.dir}/results.jsonl — run experiment_runner.py first.")
        return 1

    print_per_run_table(records)
    print_status_summary(records)
    print_comparison(records, "condition", "condition")
    print_comparison(records, "problem_id", "problem")

    if not args.no_report:
        write_report(
            records,
            Path(args.dir) / f"report_stage{args.stage}.md",
            args.stage,
            args.langsmith_project,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
