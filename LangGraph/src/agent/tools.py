"""
File-system and workspace tools exposed to LLM agents in the graph.
All tools are registered as LangChain @tool functions.
"""

from pathlib import Path

from langchain_core.tools import tool
from langgraph.types import interrupt

from config import PROJECT_ROOT


# ── Path resolution & agent file sandbox ──────────────────────────────────

# Directories that are experiment-harness output and therefore off-limits to the
# agent's file tools. A run's own summary/log is only written *after* the run
# ends, so an agent that tries to read it mid-run would hit a missing file;
# blocking these dirs (a) prevents that class of crash and (b) protects results
# artifacts from accidental reads or overwrites by the model.
BLOCKED_DIRS: tuple[str, ...] = (
    "experiment_runs",  # logs/, summaries/, artifacts/, backup/, results.*
)


def _resolve_agent_path(path_str: str) -> tuple[Path | None, str | None]:
    """Resolve an agent-supplied path and enforce the read/write sandbox.

    Accepts an absolute path or a path relative to ``PROJECT_ROOT`` (the
    convention documented on the workspace tools). Returns ``(path, None)`` when
    the resolved path is inside the project and outside the blocked
    experiment-output dirs; otherwise returns ``(None, error_message)``.
    Existence is *not* checked here — each tool decides whether its target must
    be a file, a directory, etc.
    """
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_relative_to(PROJECT_ROOT):
        return None, f"ERROR: path is outside the project: {path}"
    for name in BLOCKED_DIRS:
        blocked_root = (PROJECT_ROOT / name).resolve()
        if path == blocked_root or blocked_root in path.parents:
            return None, f"ERROR: path is inside blocked directory '{name}': {path}"
    return path, None


# ── Workspace file tools ──────────────────────────────────────────────────

@tool
def read_workspace(workspace_path: str) -> str:
    """Read and return the full contents of a workspace/Lean file inside the project.

    Use this before editing to understand the current state of the file,
    or to inspect the blueprint declarations, theorem statements, and
    existing proofs.

    The path can be absolute or relative to the project root. Reads are
    restricted to files inside the project and outside the experiment-output
    directories (e.g. ``experiment_runs/``). A missing file returns an ERROR
    string rather than raising.
    """
    path, err = _resolve_agent_path(workspace_path)
    if err:
        return err
    if not path.is_file():
        return f"ERROR: file not found: {path}"
    return path.read_text(encoding="utf-8")


@tool
def write_workspace(workspace_path: str, content: str) -> str:
    """Overwrite the entire Lean workspace file with the given content.

    Use this when you need to replace the whole file, for example after
    generating a new blueprint skeleton or applying a completed proof.
    The file will be completely overwritten — ensure your content includes
    all existing declarations that should be preserved.

    The path can be absolute or relative to the project root. Writes are
    restricted to files inside the project and outside the experiment-output
    directories (e.g. ``experiment_runs/``).
    """
    path, err = _resolve_agent_path(workspace_path)
    if err:
        return err
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


@tool
def search_replace_workspace(relative_path: str, old_string: str, new_string: str) -> str:
    """Replace exactly one occurrence of `old_string` in a workspace file with `new_string`.

    Use this for targeted edits — replacing a lemma body, fixing a single line,
    or inserting new declarations relative to existing ones.
    `old_string` must appear exactly once in the file, or the operation is rejected
    to avoid ambiguity. The path is relative to the project root.
    """
    path, err = _resolve_agent_path(relative_path)
    if err:
        return err
    if not path.is_file():
        return f"ERROR: file not found: {relative_path}"

    content = path.read_text(encoding="utf-8")

    count = content.count(old_string)
    if count == 0:
        return "ERROR: old_string not found"
    if count > 1:
        return "ERROR: old_string appears multiple times"

    updated = content.replace(old_string, new_string)
    path.write_text(updated, encoding="utf-8")

    return (
        f"Replaced 1 occurrence in {relative_path} "
        f"({len(old_string)} → {len(new_string)} chars)"
    )


@tool
def list_directory(path: str) -> str:
    """List the contents of a directory inside the project.

    Use this to explore the project structure, find related Lean files,
    locate the blueprint directory, or check what build artifacts exist.
    Returns one entry per line; directories are suffixed with '/'.

    The path can be absolute or relative to the project root. Listing is
    restricted to directories inside the project and outside the
    experiment-output directories (e.g. ``experiment_runs/``).
    """
    p, err = _resolve_agent_path(path)
    if err:
        return err
    if not p.is_dir():
        return f"ERROR: {p} is not a directory"
    entries = []
    for child in sorted(p.iterdir()):
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{child.name}{suffix}")
    return "\n".join(entries) if entries else "(empty)"


@tool
def create_file(file_path: str, content: str) -> str:
    """Create a new file at the given path with the given content.

    WARNING: Only use this if you are 100% sure the file is needed.
    Most files already exist in the project — prefer `read_workspace`,
    `write_workspace`, or `search_replace_workspace` for existing files.
    Use `list_directory` first to confirm the file does not already exist.
    Missing parent directories are created. The path can be absolute or relative
    to the project root, and is subject to the same sandbox as the other file
    tools: anything outside the project, or inside the experiment-output
    directories, is refused.
    """
    path, err = _resolve_agent_path(file_path)
    if err:
        return err
    if path.exists():
        return f"ERROR: {file_path} already exists — use write_workspace to modify it"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Created {file_path} ({len(content)} characters)"


# ── Human-in-the-loop tool ────────────────────────────────────────────────

@tool
def ask_human(question: str) -> str:
    """Ask the human a clarifying question when you need more information
    to proceed. Use this whenever you're unsure, need a decision from the
    user, or are missing required information."""
    answer = interrupt(question)
    return str(answer)


# ── Blueprint JSON rebuild tool ───────────────────────────────────────────

@tool
def build_blueprint_json() -> str:
    """Run `lake build :blueprintJson` to regenerate the blueprint dependency graph JSON.

    Call this AFTER writing a blueprint file and verifying it compiles cleanly.
    This regenerates `.lake/build/blueprint/module/ConjectureProver.json` with the
    latest dependency edges from `@[blueprint]` annotations and `sorry_using [...]`.

    The JSON file contains the full dependency graph used by the blueprint web
    visualization (HTML + dependency graph). Always call this before handing back
    to ensure the blueprint is up to date.
    """
    import subprocess
    result = subprocess.run(
        ["lake", "build", ":blueprintJson"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode != 0:
        return f"ERROR: lake build :blueprintJson failed (exit {result.returncode}):\n{err[:2000]}"
    return f"✅ blueprint JSON regenerated successfully.\n{out[:500]}" if out else "✅ blueprint JSON regenerated successfully."


# ── Tool lists ────────────────────────────────────────────────────────────

file_tools = [
    read_workspace, write_workspace, search_replace_workspace,
    create_file, list_directory, build_blueprint_json,
]

human_tools = [ask_human]
