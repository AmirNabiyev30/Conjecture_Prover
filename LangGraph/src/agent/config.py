"""
Centralized configuration for the Conjecture Prover LangGraph agent.
All paths, model defaults, and tunable constants live here.
"""

from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path("/home/amirnabiyev/Conjecture_Prover").resolve()
WORKSPACE_PATH: str = str(PROJECT_ROOT / "ConjectureProver.lean")
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
MAX_ITERATIONS: int = 16                 # global iteration ceiling
MAX_TURNS_PER_LEMMA: int = 12            # per-agent turn budget (reduced from 20:
                                         #  20-turn worst cases dominated wall-clock
                                         #  time; the refiner decomposes hard lemmas
                                         #  so later rounds can still succeed)
MAX_REFINEMENT_ROUNDS: int = 8           # safety ceiling for refinement loops
                                         #  (reduced from 16: with source-derived
                                         #  statuses rounds now terminate early when
                                         #  all provable lemmas are proved)

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
