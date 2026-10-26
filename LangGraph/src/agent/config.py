"""
Centralized configuration for the Conjecture Prover LangGraph agent.
All paths, model defaults, and tunable constants live here.
"""

import os
from pathlib import Path
from typing import Mapping

# ── Project paths ──────────────────────────────────────────────────────────
# Derived from this file's location so the project works from any checkout path
# or machine: LangGraph/src/agent/config.py -> parents[3] is the repo root.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

#: Filename of the Lean root module the agent edits and the harness rewrites.
#: A checkout is expected to name this after its own Lake library (the
#: ``[[lean_lib]]`` entry in lakefile.toml), so it is configurable; the default
#: is the name every recorded run in this repository has used.
DEFAULT_WORKSPACE_NAME: str = "ConjectureProver.lean"


def workspace_name(env: Mapping[str, str] | None = None) -> str:
    """Return the workspace filename to use, honouring ``WORKSPACE_NAME``.

    The workspace is the Lean module the agent edits and the harness seeds. It
    is deliberately not tracked in git — a clone creates it — so the name comes
    from the environment rather than being hardcoded in both the agent and the
    harness.

    Args:
        env: Mapping to read from; defaults to ``os.environ``. Accepting one
            explicitly keeps this testable without reimporting the module.

    Returns:
        The configured filename, falling back to
        :data:`DEFAULT_WORKSPACE_NAME` when the variable is unset or blank.
    """
    source = os.environ if env is None else env
    name = (source.get("WORKSPACE_NAME") or "").strip()
    return name or DEFAULT_WORKSPACE_NAME


WORKSPACE_NAME: str = workspace_name()
WORKSPACE_PATH: str = str(PROJECT_ROOT / WORKSPACE_NAME)

#: The Lean *module* name: the workspace filename without its extension. Lake
#: emits the blueprint facet to ``.lake/build/blueprint/module/<module>.json``,
#: so everything that locates a blueprint has to agree with the module the
#: workspace is compiled into -- i.e. the ``[[lean_lib]]`` name in lakefile.toml.
#: Derived rather than configured separately so the two can never disagree.
WORKSPACE_MODULE: str = Path(WORKSPACE_NAME).stem

MATHLIB4_ROOT: Path = PROJECT_ROOT / "mathlib4"

# ── Prompt paths ───────────────────────────────────────────────────────────
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
BLUEPRINT_GENERATOR_DIR: Path = PROMPTS_DIR / "blueprint_generator"
BLUEPRINT_GENERATOR_PROMPT: str = str(BLUEPRINT_GENERATOR_DIR / "blueprint_generator.md")
BLUEPRINT_GENERATOR_WO_ANALYZER_PROMPT: str = str(
    BLUEPRINT_GENERATOR_DIR / "blueprint_generator_wo_analyzer.md"
)
BLUEPRINT_GENERATOR_OPTIONAL_ANALYZER_PROMPT: str = str(
    BLUEPRINT_GENERATOR_DIR / "blueprint_generator_optional_analyzer.md"
)
BLUEPRINT_REFINER_PROMPT: str = str(PROMPTS_DIR / "blueprint_refiner.md")
BLUEPRINT_REFINER_WO_ANALYZER_PROMPT: str = str(
    PROMPTS_DIR / "blueprint_refiner_wo_analyzer.md"
)
BLUEPRINT_REFINER_OPTIONAL_ANALYZER_PROMPT: str = str(
    PROMPTS_DIR / "blueprint_refiner_optional_analyzer.md"
)

# ── Blueprint refiner analyzer-experiment modes ─────────────────────────────
# The single State flag `blueprint_refiner_analyzer_mode` selects BOTH the
# prompt variant AND whether the `analyze_mathlib_module` tool is bound for the
# refiner model. Configure it per run (e.g. via env var in graph.main()) to run
# an experiment arm; the explicit `blueprint_refiner_prompt` State field can
# override the prompt path for a run.
BLUEPRINT_REFINER_ANALYZER_MODES: tuple[str, ...] = ("required", "optional", "none")
BLUEPRINT_REFINER_PROMPT_BY_MODE: dict[str, str] = {
    "required": BLUEPRINT_REFINER_PROMPT,                          # analyzer on, steered toward
    "optional": BLUEPRINT_REFINER_OPTIONAL_ANALYZER_PROMPT,        # analyzer on, optional
    "none": BLUEPRINT_REFINER_WO_ANALYZER_PROMPT,                  # analyzer disabled
}
THEOREM_PROVER_PROMPT: str = str(PROMPTS_DIR / "theorem_prover.md")
AGGREGATOR_FIXER_PROMPT: str = str(PROMPTS_DIR / "aggregator_fixer.md")
LEMMA_ANALYZER_PROMPT: str = str(PROMPTS_DIR / "lemma_analyzer.md")
CODE_MODULE_ANALYZER_PROMPT: str = str(PROMPTS_DIR / "code_module_analyzer.md")

# ── Model defaults ─────────────────────────────────────────────────────────
MODEL_NAME: str = "deepseek-v4-flash"   # fallback model name
MODEL_TIMEOUT: int = 120                 # LLM invocation timeout (seconds)

# ── Graph / turn limits ────────────────────────────────────────────────────
MAX_TURNS_PER_LEMMA: int = 12            # per-agent turn budget (reduced from 20:
                                         #  20-turn worst cases dominated wall-clock
                                         #  time; the refiner decomposes hard lemmas
                                         #  so later rounds can still succeed)
MAX_REFINEMENT_ROUNDS: int = 8           # safety ceiling for refinement loops
                                         #  (reduced from 16: with source-derived
                                         #  statuses rounds now terminate early when
                                         #  all provable lemmas are proved)

# ── Prover batching (barrier) ──────────────────────────────────────────────
#: Width of one prover batch — the RAM knob for the proving stage.
#:
#: ``theorem_proving`` dispatches at most this many ``Send`` tasks per pass, and
#: the ``dispatch_gate`` join node only dispatches the next batch once the
#: current one has fully finished. Every prover runs its own Lean MCP server, so
#: peak proving memory scales with this width rather than with the number of
#: unproved lemmas. Batches are barriers: batch N+1 waits for the slowest prover
#: in batch N, which is the throughput price of the bound.
MAX_PARALLEL_PROVERS: int = 3

#: Superstep ceiling for one graph run.
#:
#: Batching multiplies the superstep count by roughly
#: ``2 * ceil(unproved / MAX_PARALLEL_PROVERS)`` per round (one pass for the
#: provers, one for the gate), so the library's implicit default is no longer a
#: safe assumption. This value is deliberately generous: the round budget is the
#: intended loop bound, and this only catches a genuinely runaway graph. It is
#: passed explicitly through ``RunSettings`` -> invoke config so a batching
#: change can never silently turn into a ``GraphRecursionError``.
RECURSION_LIMIT: int = 1000

# ── Lean MCP client defaults ───────────────────────────────────────────────
LEAN_MCP_CONFIG: dict = {
    "transport": "stdio",
    "command": "uvx",
    "args": ["lean-lsp-mcp"],
    "env": {
        "LEAN_PROJECT_PATH": str(PROJECT_ROOT),
        "LEAN_REPL": "true",
    },
}
