# Conjecture Prover — Analyzer-Utilization Experiment

Stage-1 experiment: does the code-module analyzer
([`analyze_mathlib_module`](../LangGraph/src/agent/agents/module_analyzer.py) →
[`code_module_analyzer`](../LangGraph/src/agent/agents/code_module_analyzer.py))
help **formalization route planning**? Each run pairs one problem with one
"condition" (arm) that controls how the analyzer is used across both
route-planning stages — the blueprint **generator** (initial decomposition) and
the blueprint **refiner** (re-decomposition of unproved lemmas).

## Conditions (3 aligned arms)

| slug | generator prompt | `enable_module_analysis` | refiner mode | refiner prompt |
|---|---|---|---|---|
| `with_analyzer` | `../prompts/blueprint_generator/blueprint_generator.md` | `true` | `required` | `../prompts/blueprint_refiner.md` |
| `wo_analyzer` | `../prompts/blueprint_generator/blueprint_generator_wo_analyzer.md` | `false` | `none` | `../prompts/blueprint_refiner_wo_analyzer.md` |
| `optional_analyzer` | `../prompts/blueprint_generator/blueprint_generator_optional_analyzer.md` | `true` | `optional` | `../prompts/blueprint_refiner_optional_analyzer.md` |

These three arms are defined once in
[`conditions.py`](../LangGraph/src/agent/conditions.py); the table above mirrors
that source of truth.

## Problems (stage 1)

| id | source | theorem |
|---|---|---|
| `fateH_94` | `../experiment_problems/fateH/94.txt` | `ringKrullDim_quot_annihilator_eq` |
| `fateX_94` | `../experiment_problems/fateX/94.txt` | `zeroSet_finite_or_contain_arithmetic_progression` |
| `putnam_a6_1972` | `../experiment_problems/putnam/a6_1972.txt` | `putnam_1972_a6` |

Stage 1 = 3 problems × 3 conditions = **9 runs**, executed sequentially (each
run can take up to ~1 hour).

## How it works

Each run is an **isolated subprocess** that invokes
[`LangGraph/src/agent/graph.py`](../LangGraph/src/agent/graph.py) with
environment-variable overrides consumed by `main()`:

- `BLUEPRINT_GENERATOR_PROMPT` + `ENABLE_MODULE_ANALYSIS` — generator arm
- `BLUEPRINT_REFINER_ANALYZER_MODE` — refiner arm
- `EXPERIMENT_AUTO_ANSWER` / `EXPERIMENT_MAX_AUTO_RESUMES` — autonomous
  auto-resume of `ask_human` interrupts (no blocking `input()`)
- `EXPERIMENT_SUMMARY_JSON` — structured end-of-run summary per run
- `EXPERIMENT_METADATA` — LangSmith per-run tags
  (`condition`, `problem`, `category`, `stage`, `run_id`)

The orchestrator ([`experiments/runner.py`](../experiments/runner.py)) writes each
problem into [`ConjectureProver.lean`](../ConjectureProver.lean) (with a
run-identifying header), tees the run's terminal output to a per-run log, saves
a copy of the final workspace per run, and records a results row. A pristine
backup of the original workspace is kept in `backup/` and restored after the
batch.

### Analyzer-tool binding guarantee

In the `wo_analyzer` arm, `analyze_mathlib_module` is **not** bound or
registered anywhere:

- the blueprint generator only binds it when `enable_module_analysis` is true
  ([`nodes/blueprint_generator.py`](../LangGraph/src/agent/nodes/blueprint_generator.py)),
- the blueprint refiner only binds it when the refiner mode is not `none`
  ([`nodes/blueprint_refiner.py`](../LangGraph/src/agent/nodes/blueprint_refiner.py)),
- the graph's ToolNodes only register it for the generator when
  `enable_module_analysis` is true and for the refiner when the mode is not
  `none` ([`graph.py build_graph()`](../LangGraph/src/agent/graph.py)).

As a final safeguard, the runner scans each `wo_analyzer` run's log for a real
`analyze_mathlib_module` tool call (`→ analyze_mathlib_module`); if one ever
appears, the run's results row is flagged with `ANALYZER_LEAK` in the `notes`
field so the run can be discarded.

## Turn / budget limits per step (exact, from the code)

Every limit is *declared* in
[`LangGraph/src/agent/config.py`](../LangGraph/src/agent/config.py) as its system
default and can be overridden per run through the environment
([`run_settings.py`](../LangGraph/src/agent/run_settings.py) reads
`MODEL_TIMEOUT`, `MAX_TURNS_PER_LEMMA` and `MAX_REFINEMENT_ROUNDS`). The values
below are the committed defaults, and each is enforced in the node file named. A
single run of the whole graph is bounded by the **tightest** of these:

| Step | Limit | Value | Where enforced |
|---|---|---|---|
| Any single LLM call | per-call timeout | **120 s** (`MODEL_TIMEOUT`) | every `init_chat_model(..., timeout=MODEL_TIMEOUT)` in the nodes |
| One lemma prover | turns per lemma per round | **12** (`MAX_TURNS_PER_LEMMA`) | [`nodes/prove_lemma.py`](../LangGraph/src/agent/nodes/prove_lemma.py) `for turn in range(1, max_turns + 1)` |
| Aggregator (apply + verify) | turns per round | **12** (`MAX_TURNS_PER_LEMMA`) | [`nodes/aggregator.py`](../LangGraph/src/agent/nodes/aggregator.py) `for turn in range(1, max_turns + 1)` |
| Full refinement loop | rounds | **8** (`MAX_REFINEMENT_ROUNDS`) | [`nodes/routing.py`](../LangGraph/src/agent/nodes/routing.py) `route_after_aggregator` → `END` |
| Blueprint generator | model turns | **unbounded** — model loops on tool calls until it answers; only capped by the graph recursion limit and the runner wall-clock timeout | [`nodes/blueprint_generator.py`](../LangGraph/src/agent/nodes/blueprint_generator.py) + routing |
| Blueprint refiner | model turns | **unbounded** — same as generator | [`nodes/blueprint_refiner.py`](../LangGraph/src/agent/nodes/blueprint_refiner.py) + routing |
| Whole graph | recursion steps | **10007** (langgraph 1.2.11 default, effectively unbounded) | langgraph `pregel/_config.py` (`LANGGRAPH_DEFAULT_RECURSION_LIMIT`) |
| `ask_human` interrupts | auto-resumes per run | **3** (`EXPERIMENT_MAX_AUTO_RESUMES`, runner flag `--max-auto-resumes`) | [`cli.py`](../LangGraph/src/agent/cli.py) `run()` |
| One experiment run | wall clock | **90 min** by default (`--timeout-minutes`) | [`experiments/runner.py`](../experiments/runner.py) |

Notes:

- The effective global ceilings are `MAX_REFINEMENT_ROUNDS` (**8** refinement
  rounds) and the runner's per-run wall-clock timeout.
- Because the prover and aggregator each allow up to 12 turns *per round* and
  refinement can run up to 8 rounds, a pathological run can still issue a large
  number of LLM calls — this is why the runner defaults to a 90-minute
  wall-clock timeout per run.
- The end-of-run summary prints the round budget it actually used
  (`budget: max_refinement_rounds=<n>`), so the results table's `round_reached`
  column should be compared against that value, not a hardcoded constant.

## Layout

```
experiment_runs/
  backup/ConjectureProver.lean.original   # pristine workspace (never overwritten)
  logs/<condition>__<problem>.log        # full terminal output per run
  summaries/<condition>__<problem>.summary.json  # round/total/proved/unsolved
  artifacts/<condition>__<problem>/      # final workspace copy per run
  results.jsonl                          # one JSON record per run (source of truth)
  results.csv                            # same data as a table
  report_stage1.md                       # generated by experiments.summarize
```

## Commands (use the uv venv, Python 3.12, from the repository root)

```bash
# Run the full stage-1 batch (9 runs). Resumable: re-running skips completed runs.
LangGraph/.venv/bin/python -m experiments.runner

# Partial / targeted runs
LangGraph/.venv/bin/python -m experiments.runner --conditions with_analyzer      # one arm across all 3 problems
LangGraph/.venv/bin/python -m experiments.runner --problems fateH_94             # one problem across all 3 arms
LangGraph/.venv/bin/python -m experiments.runner --only with_analyzer__fateH_94  # exactly one run

# Re-run even if summaries already exist
LangGraph/.venv/bin/python -m experiments.runner --no-resume

# Preview the run matrix without running anything
LangGraph/.venv/bin/python -m experiments.runner --list

# Sanity-check the harness plumbing (no LLM calls). Note it still writes the
# problem into ConjectureProver.lean; the batch restores backup/ afterwards.
LangGraph/.venv/bin/python -m experiments.runner --only with_analyzer__fateH_94 --dry-run

# Options
#   --timeout-minutes 90   wall-clock timeout per run (0 = none)
#   --langsmith-project conjecture_experiment
#   --auto-answer "Proceed autonomously with your best judgment"
#   --max-auto-resumes 3
#   --no-restore           keep the last problem in ConjectureProver.lean after the batch
```

### After runs complete

```bash
# Per-run table + per-condition/per-problem comparison + report_stage1.md
LangGraph/.venv/bin/python -m experiments.summarize
```

Token usage is not in the results files — it is tracked in LangSmith under the
`conjecture_experiment` project. Filter traces by the `condition` / `problem`
metadata tags to compare token cost across arms.
