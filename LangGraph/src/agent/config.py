"""
Centralized configuration for the Conjecture Prover LangGraph agent.
All paths, model defaults, and tunable constants live here.
"""

from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path("/Users/amirnabiyev/Conjecture_Prover").resolve()
WORKSPACE_PATH: str = str(PROJECT_ROOT / "LeanWorkspace.lean")

# ── Prompt paths ───────────────────────────────────────────────────────────
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
BLUEPRINT_GENERATOR_PROMPT: str = str(PROMPTS_DIR / "blueprint_generator.md")
BLUEPRINT_REFINER_PROMPT: str = str(PROMPTS_DIR / "blueprint_refiner.md")
THEOREM_PROVER_PROMPT: str = str(PROMPTS_DIR / "theorem_prover.md")
AGGREGATOR_FIXER_PROMPT: str = str(PROMPTS_DIR / "aggregator_fixer.md")

# ── Model defaults ─────────────────────────────────────────────────────────
MODEL_NAME: str = "deepseek-chat"        # fallback model name
MODEL_TIMEOUT: int = 120                 # LLM invocation timeout (seconds)

# ── Graph / turn limits ────────────────────────────────────────────────────
MAX_ITERATIONS: int = 16                 # global iteration ceiling
MAX_TURNS_PER_LEMMA: int = 20            # per-agent turn budget
MAX_REFINEMENT_ROUNDS: int = 16          # safety ceiling for refinement loops

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
