"""Unit tests for the experiment harness.

Two areas:

1. Matrix selection — run_id/parse_run_id/build_cells, and the Budget renderer.
2. Run plumbing — summary loading, JSONL/CSV recording, the spawn+tee helper,
   record shaping in run_single, and run_batch's skip/restore behaviour.

These live under LangGraph/tests so the one canonical command runs everything:

    cd LangGraph && .venv/bin/python -m pytest tests/unit_tests

Every test that touches the workspace monkeypatches runner.WORKSPACE (and the
other module-level paths) at a temp tree: run_single and the dry-run path write
the problem into the workspace before restoring it, and a test must never be able
to clobber the real ConjectureProver.lean.

Behavior contract:
- ``run_id`` keeps the historical ``<condition>__<problem>`` form for the default
  budget, so the recorded stage-1 run ids and their filenames stay valid.
- ``parse_run_id`` is exact: it rejects malformed or unknown ids rather than
  falling back to substring matching.
- ``build_cells`` expands the axes for a normal run, but ``only`` is taken
  literally — it must not be re-expanded into a cross product.
- A results row records the run's settings, falling back to what the harness
  launched with when no summary was produced.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from experiments import runner  # noqa: E402
from experiments.runner import (  # noqa: E402
    BUDGETS,
    CONDITIONS,
    DEFAULT_BUDGET,
    PROBLEMS,
    RESULT_FIELDS,
    Budget,
    build_cells,
    parse_run_id,
    run_id,
)


# ── run_id ───────────────────────────────────────────────────────────────────

def test_default_budget_keeps_the_historical_run_id():
    """Recorded stage-1 ids, filenames and --resume checks all depend on this."""
    assert run_id("with_analyzer", "fateX_94") == "with_analyzer__fateX_94"
    assert run_id("with_analyzer", "fateX_94", DEFAULT_BUDGET) == "with_analyzer__fateX_94"


def test_non_default_budget_is_suffixed():
    assert run_id("with_analyzer", "fateX_94", "wide") == "with_analyzer__fateX_94__wide"


# ── parse_run_id ─────────────────────────────────────────────────────────────

def test_parse_run_id_round_trips_both_forms():
    assert parse_run_id("with_analyzer__fateX_94") == (
        "with_analyzer", "fateX_94", DEFAULT_BUDGET
    )
    custom = Budget(name="wide", max_turns_per_lemma=20, max_refinement_rounds=16)
    BUDGETS["wide"] = custom
    try:
        assert parse_run_id("with_analyzer__fateX_94__wide") == (
            "with_analyzer", "fateX_94", "wide"
        )
    finally:
        del BUDGETS["wide"]


@pytest.mark.parametrize("rid", [
    "no-separator",
    "a__b__c__d",
    "",
])
def test_parse_run_id_rejects_malformed_ids(rid):
    with pytest.raises(ValueError, match="Invalid run_id"):
        parse_run_id(rid)


@pytest.mark.parametrize("rid,label", [
    ("bogus_condition__fateX_94", "condition"),
    ("with_analyzer__bogus_problem", "problem"),
])
def test_parse_run_id_rejects_unknown_axis_members(rid, label):
    with pytest.raises(ValueError, match=label):
        parse_run_id(rid)


def test_parse_run_id_rejects_an_unknown_budget():
    with pytest.raises(ValueError, match="budget"):
        parse_run_id("with_analyzer__fateX_94__bogus")


# ── build_cells ──────────────────────────────────────────────────────────────

def test_build_cells_expands_the_axes():
    cells = build_cells()
    assert set(cells) == {
        (condition, problem, DEFAULT_BUDGET)
        for condition in CONDITIONS
        for problem in PROBLEMS
    }
    assert len(cells) == len(CONDITIONS) * len(PROBLEMS)


def test_only_is_taken_literally_not_expanded():
    """Two ids naming two conditions must yield two cells, not a cross product."""
    cells = build_cells(only=["with_analyzer__fateX_94", "wo_analyzer__fateX_94"])
    assert cells == [
        ("with_analyzer", "fateX_94", DEFAULT_BUDGET),
        ("wo_analyzer", "fateX_94", DEFAULT_BUDGET),
    ]


def test_only_preserves_the_order_given():
    cells = build_cells(only=["wo_analyzer__fateX_94", "with_analyzer__fateX_94"])
    assert [c[0] for c in cells] == ["wo_analyzer", "with_analyzer"]


@pytest.mark.parametrize("kwargs,label", [
    ({"problems": ["nope"]}, "problem"),
    ({"conditions": ["nope"]}, "condition"),
    ({"budgets": ["nope"]}, "budget"),
])
def test_build_cells_rejects_unknown_axis_members(kwargs, label):
    with pytest.raises(ValueError, match=label):
        build_cells(**kwargs)


# ── Budget ───────────────────────────────────────────────────────────────────

def test_default_budget_sets_no_env_so_it_cannot_drift_from_config():
    """`None` means "use config.py's value" — the numbers are not restated here."""
    assert BUDGETS[DEFAULT_BUDGET].to_env() == {}


def test_budget_renders_only_the_fields_it_sets():
    budget = Budget(name="wide", max_turns_per_lemma=20)
    assert budget.to_env() == {"MAX_TURNS_PER_LEMMA": "20"}

    both = Budget(name="wide", max_turns_per_lemma=20, max_refinement_rounds=16)
    assert both.to_env() == {
        "MAX_TURNS_PER_LEMMA": "20",
        "MAX_REFINEMENT_ROUNDS": "16",
    }


# ── recorded schema ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("column", [
    "budget", "model", "model_timeout", "max_turns_per_lemma", "max_refinement_rounds",
])
def test_results_schema_records_the_settings(column):
    """Without these the results table cannot be traced back to its configuration."""
    assert column in runner.RESULT_FIELDS

# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Point the harness's module-level paths at a temp tree.

    Mandatory for anything that runs a cell: run_single writes the problem into
    the workspace before the graph would run, so without this a test could
    clobber the real ConjectureProver.lean.
    """
    workspace = tmp_path / "ConjectureProver.lean"
    workspace.write_text("-- pristine workspace\n", encoding="utf-8")
    graph_script = tmp_path / "graph.py"
    graph_script.write_text("# stub graph\n", encoding="utf-8")

    monkeypatch.setattr(runner, "WORKSPACE", workspace)
    monkeypatch.setattr(runner, "GRAPH_SCRIPT", graph_script)
    monkeypatch.setattr(runner, "LANGGRAPH_DIR", tmp_path)
    monkeypatch.setattr(runner, "STALE_BLUEPRINT_JSON", tmp_path / "stale.json")
    return SimpleNamespace(
        workspace=workspace, graph_script=graph_script, tmp=tmp_path,
        out=tmp_path / "out",
    )


def _run_single(sandbox, **overrides):
    """run_single with the required plumbing filled in."""
    kwargs = dict(
        output_dir=sandbox.out,
        langsmith_project="test-project",
        auto_answer="go",
        max_auto_resumes=3,
        timeout_minutes=1,
        python=sys.executable,
    )
    kwargs.update(overrides)
    return runner.run_single("fateX_94", "with_analyzer", **kwargs)


def _stub_spawn(summary=None, exit_code=0, timed_out=False, duration_s=1.5):
    """Replace _spawn_and_tee: write a log, optionally a summary, return an outcome."""
    def spawn(cmd, env, cwd, log_path, timeout_seconds):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("stub log\n", encoding="utf-8")
        if summary is not None:
            path = Path(env["EXPERIMENT_SUMMARY_JSON"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(summary), encoding="utf-8")
        return {"exit_code": exit_code, "timed_out": timed_out, "duration_s": duration_s}
    return spawn


# ── summary loading ──────────────────────────────────────────────────────────

def test_load_summary_reads_a_dict(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"total": 3}', encoding="utf-8")
    assert runner._load_summary(path) == {"total": 3}


def test_load_summary_returns_none_for_missing_or_malformed(tmp_path):
    assert runner._load_summary(tmp_path / "nope.json") is None
    malformed = tmp_path / "bad.json"
    malformed.write_text("{not json", encoding="utf-8")
    assert runner._load_summary(malformed) is None
    not_a_dict = tmp_path / "list.json"
    not_a_dict.write_text('[1, 2]', encoding="utf-8")
    assert runner._load_summary(not_a_dict) is None


# ── recording ────────────────────────────────────────────────────────────────

def test_ensure_dirs_creates_every_output_subdir(tmp_path):
    runner._ensure_dirs(tmp_path / "out")
    for sub in ("logs", "summaries", "artifacts", "backup"):
        assert (tmp_path / "out" / sub).is_dir()


def test_append_jsonl_creates_parents_and_appends(tmp_path):
    path = tmp_path / "deep" / "results.jsonl"
    runner._append_jsonl(path, {"a": 1})
    runner._append_jsonl(path, {"a": 2})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"a": 2}]


def test_append_jsonl_falls_back_to_str_for_odd_values(tmp_path):
    path = tmp_path / "results.jsonl"
    runner._append_jsonl(path, {"p": Path("/tmp/x")})
    assert json.loads(path.read_text(encoding="utf-8"))["p"] == "/tmp/x"


def test_csv_round_trips_a_full_record(tmp_path):
    jsonl = tmp_path / "results.jsonl"
    record = {field: f"v-{field}" for field in RESULT_FIELDS}
    runner._append_jsonl(jsonl, record)
    runner._write_csv_from_jsonl(jsonl, tmp_path / "results.csv")
    lines = (tmp_path / "results.csv").read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",") == RESULT_FIELDS
    assert "v-budget" in lines[1]


def test_csv_tolerates_rows_recorded_before_a_column_existed(tmp_path):
    """The 17 rows already in experiment_runs/ lack the settings columns."""
    jsonl = tmp_path / "results.jsonl"
    runner._append_jsonl(jsonl, {"run_id": "a__b", "status": "completed"})
    csv_path = tmp_path / "results.csv"
    runner._write_csv_from_jsonl(jsonl, csv_path)      # must not raise
    row = csv_path.read_text(encoding="utf-8").strip().splitlines()[1]
    assert row.startswith("a__b,")
    assert len(row.split(",")) == len(RESULT_FIELDS)


def test_csv_skips_blank_and_malformed_lines(tmp_path):
    jsonl = tmp_path / "results.jsonl"
    jsonl.write_text('{"run_id": "x", "status": "s"}\n\nnot json\n', encoding="utf-8")
    runner._write_csv_from_jsonl(jsonl, tmp_path / "results.csv")
    lines = (tmp_path / "results.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2            # header + the single valid row


def test_error_record_covers_the_full_schema(sandbox):
    record = runner._error_record(
        "a__b", "b", "a", "default", sandbox.out,
        sandbox.out / "summaries" / "a__b.summary.json", "boom",
    )
    assert set(record) == set(RESULT_FIELDS)
    assert record["status"] == "error"
    assert record["notes"] == "boom"
    assert record["budget"] == "default"
    assert record["proved"] is None


# ── workspace backup / restore ───────────────────────────────────────────────

def test_backup_then_restore_round_trips_the_workspace(sandbox):
    runner._backup_workspace(sandbox.out)
    sandbox.workspace.write_text("-- clobbered\n", encoding="utf-8")
    runner._restore_workspace(sandbox.out)
    assert sandbox.workspace.read_text(encoding="utf-8") == "-- pristine workspace\n"


def test_backup_does_not_clobber_an_existing_backup(sandbox):
    runner._backup_workspace(sandbox.out)
    sandbox.workspace.write_text("-- changed\n", encoding="utf-8")
    runner._backup_workspace(sandbox.out)          # second call must be a no-op
    runner._restore_workspace(sandbox.out)
    assert sandbox.workspace.read_text(encoding="utf-8") == "-- pristine workspace\n"


# ── spawn + tee ──────────────────────────────────────────────────────────────

def test_spawn_and_tee_captures_output_and_exit_code(tmp_path):
    log_path = tmp_path / "logs" / "run.log"
    log_path.parent.mkdir(parents=True)
    outcome = runner._spawn_and_tee(
        [sys.executable, "-c", "print('hello from child')"],
        env=dict(os.environ),
        cwd=tmp_path,
        log_path=log_path,
        timeout_seconds=60,
    )
    assert outcome["exit_code"] == 0
    assert outcome["timed_out"] is False
    assert "hello from child" in log_path.read_text(encoding="utf-8")


def test_spawn_and_tee_kills_a_hung_child_at_the_timeout(tmp_path):
    log_path = tmp_path / "run.log"
    outcome = runner._spawn_and_tee(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        env=dict(os.environ),
        cwd=tmp_path,
        log_path=log_path,
        timeout_seconds=1,
    )
    assert outcome["timed_out"] is True
    assert outcome["exit_code"] != 0


def test_spawn_and_tee_records_a_nonzero_exit(tmp_path):
    outcome = runner._spawn_and_tee(
        [sys.executable, "-c", "raise SystemExit(3)"],
        env=dict(os.environ),
        cwd=tmp_path,
        log_path=tmp_path / "run.log",
        timeout_seconds=60,
    )
    assert outcome["exit_code"] == 3
    assert outcome["timed_out"] is False


# ── run_single: record shaping ───────────────────────────────────────────────

_RECORDED_SETTINGS = {
    "model": "recorded-model",
    "model_timeout": 7,
    "max_turns_per_lemma": 11,
    "max_refinement_rounds": 5,
}


def test_run_single_records_the_settings_the_graph_reported(sandbox, monkeypatch):
    monkeypatch.setattr(runner, "_spawn_and_tee", _stub_spawn(summary={
        "round_reached": 4, "total": 5, "proved": 3, "unproved": 2,
        "unsolved": ["a", "b"], "settings": _RECORDED_SETTINGS,
    }))
    record = _run_single(sandbox)

    assert record["status"] == "completed"
    assert record["budget"] == "default"
    assert record["round_reached"] == 4
    assert record["proved"] == 3
    assert record["unsolved"] == "a; b"
    assert record["model"] == "recorded-model"
    assert record["max_turns_per_lemma"] == 11
    assert set(record) == set(RESULT_FIELDS)


def test_run_single_falls_back_to_launch_settings_without_a_summary(sandbox, monkeypatch):
    monkeypatch.setattr(runner, "_spawn_and_tee", _stub_spawn(summary=None))
    record = _run_single(sandbox)

    assert "no summary.json produced" in record["notes"]
    # Falls back to what the harness resolved from the child's environment.
    assert record["max_turns_per_lemma"] == 12
    assert record["max_refinement_rounds"] == 8
    assert record["model"].startswith("deepseek")


def test_run_single_flags_a_summary_without_a_settings_block(sandbox, monkeypatch):
    monkeypatch.setattr(runner, "_spawn_and_tee", _stub_spawn(
        summary={"round_reached": 1, "total": None, "settings": None},
    ))
    record = _run_single(sandbox)
    assert "settings_unknown" in record["notes"]
    assert record["max_turns_per_lemma"] == 12      # launch intent


def test_run_single_marks_a_timeout(sandbox, monkeypatch):
    monkeypatch.setattr(runner, "_spawn_and_tee",
                        _stub_spawn(summary=None, exit_code=-9, timed_out=True))
    record = _run_single(sandbox, timeout_minutes=42)
    assert record["status"] == "timeout"
    assert "42 min" in record["notes"]


def test_run_single_passes_the_budget_into_the_environment(sandbox, monkeypatch):
    """A non-default budget must reach the child, and change the run id."""
    BUDGETS["wide"] = Budget(name="wide", max_turns_per_lemma=20,
                             max_refinement_rounds=16)
    seen = {}

    def spawn(cmd, env, cwd, log_path, timeout_seconds):
        seen.update(env)
        return {"exit_code": 0, "timed_out": False, "duration_s": 0.1}

    monkeypatch.setattr(runner, "_spawn_and_tee", spawn)
    try:
        record = _run_single(sandbox, budget="wide")
    finally:
        del BUDGETS["wide"]

    assert seen["MAX_TURNS_PER_LEMMA"] == "20"
    assert seen["MAX_REFINEMENT_ROUNDS"] == "16"
    assert json.loads(seen["EXPERIMENT_METADATA"])["budget"] == "wide"
    assert record["run_id"] == "with_analyzer__fateX_94__wide"


def test_run_single_never_leaves_the_workspace_clobbered(sandbox, monkeypatch):
    """run_single writes the problem into the workspace; run_batch restores it."""
    monkeypatch.setattr(runner, "_spawn_and_tee", _stub_spawn(summary=None))
    _run_single(sandbox)
    assert "EXPERIMENT RUN" in sandbox.workspace.read_text(encoding="utf-8")


# ── run_batch ────────────────────────────────────────────────────────────────

def _run_batch(sandbox, cells, **overrides):
    kwargs = dict(
        output_dir=sandbox.out,
        timeout_minutes=1,
        langsmith_project="test-project",
        auto_answer="go",
        max_auto_resumes=3,
        python=sys.executable,
    )
    kwargs.update(overrides)
    return runner.run_batch(cells, **kwargs)


def test_run_batch_restores_the_workspace_after_a_dry_run(sandbox):
    """This is why --dry-run is safe: the problem written in is restored after."""
    _run_batch(sandbox, [("with_analyzer", "fateX_94", DEFAULT_BUDGET)], dry_run=True)
    assert sandbox.workspace.read_text(encoding="utf-8") == "-- pristine workspace\n"


def test_run_batch_records_a_row_per_cell(sandbox):
    _run_batch(sandbox, [("with_analyzer", "fateX_94", DEFAULT_BUDGET)], dry_run=True)
    records = [json.loads(line) for line in
               (sandbox.out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["status"] == "dry_run"
    assert (sandbox.out / "results.csv").is_file()


def test_run_batch_skips_cells_that_already_have_a_summary(sandbox):
    summaries = sandbox.out / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "with_analyzer__fateX_94.summary.json").write_text("{}", encoding="utf-8")

    _run_batch(sandbox, [("with_analyzer", "fateX_94", DEFAULT_BUDGET)], dry_run=True)

    assert not (sandbox.out / "results.jsonl").exists()      # nothing was recorded


def test_run_batch_runs_again_when_resume_is_disabled(sandbox):
    summaries = sandbox.out / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "with_analyzer__fateX_94.summary.json").write_text("{}", encoding="utf-8")

    _run_batch(sandbox, [("with_analyzer", "fateX_94", DEFAULT_BUDGET)],
               dry_run=True, resume=False)

    assert (sandbox.out / "results.jsonl").is_file()


def test_run_batch_restores_the_workspace_even_when_a_cell_explodes(sandbox, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(runner, "run_single", boom)
    _run_batch(sandbox, [("with_analyzer", "fateX_94", DEFAULT_BUDGET)])

    assert sandbox.workspace.read_text(encoding="utf-8") == "-- pristine workspace\n"
    record = json.loads(
        (sandbox.out / "results.jsonl").read_text(encoding="utf-8").strip()
    )
    assert record["status"] == "error"
    assert "model exploded" in record["notes"]