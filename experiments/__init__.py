"""
Experiment harness for the Conjecture Prover analyzer-utilization study.

Two entry points, both run from the repository root:

    python -m experiments.runner      # run the (problem x condition) matrix
    python -m experiments.summarize   # per-run table and comparison report

The harness applies an arm of the study by rendering it to environment variables
(see ``LangGraph/src/agent/conditions.py``) and spawning the graph as an isolated
subprocess. Recorded runs — logs, artifacts, summaries and the results table —
land in ``experiment_runs/``.

The agent is not an installed package: it uses bare imports (``from config
import ...``) and relies on ``LangGraph/src/agent`` being importable. That path is
put on ``sys.path`` here, once, when this package is imported — which lets the
submodules import agent code at the top of the file, instead of after a
``sys.path`` insert that would need a ``noqa: E402`` to silence.

Importing the package for that side effect is deliberate: run the tools as
``python -m experiments.<tool>`` so it happens before the submodule body executes.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Agent source directory — also where the graph entry point lives.
AGENT_SRC: Path = Path(__file__).resolve().parents[1] / "LangGraph" / "src" / "agent"

if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))
