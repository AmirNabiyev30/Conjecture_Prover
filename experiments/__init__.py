"""
Experiment harness for the Conjecture Prover analyzer-utilization study.

Two entry points, both run from the repository root:

    python -m experiments.runner      # run the (problem x condition) matrix
    python -m experiments.summarize   # per-run table and comparison report

The harness applies an arm of the study by rendering it to environment variables
(see ``LangGraph/src/agent/conditions.py``) and spawning the graph as an isolated
subprocess. Recorded runs — logs, artifacts, summaries and the results table —
land in ``experiment_runs/``.

The agent package itself is imported via an explicit ``sys.path`` insert to
``LangGraph/src/agent`` (the same convention the unit tests use), because the
agent is not an installed package.
"""
