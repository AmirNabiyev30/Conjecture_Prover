"""
File-system and workspace tools exposed to LLM agents in the graph.
All tools are registered as LangChain @tool functions.
"""

from pathlib import Path

from langchain_core.tools import tool
from langgraph.types import interrupt

from config import PROJECT_ROOT


# ── Workspace file tools ──────────────────────────────────────────────────

@tool
def read_workspace(workspace_path: str) -> str:
    """Read and return the full contents of the Lean workspace file.

    Use this before editing to understand the current state of the file,
    or to inspect the blueprint declarations, theorem statements, and
    existing proofs.

    The path can be absolute or relative to the project root.
    """
    path = Path(workspace_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.read_text(encoding="utf-8")


@tool
def write_workspace(workspace_path: str, content: str) -> str:
    """Overwrite the entire Lean workspace file with the given content.

    Use this when you need to replace the whole file, for example after
    generating a new blueprint skeleton or applying a completed proof.
    The file will be completely overwritten — ensure your content includes
    all existing declarations that should be preserved.

    The path can be absolute or relative to the project root.
    """
    path = Path(workspace_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
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
    path = (PROJECT_ROOT / relative_path).resolve()

    if not path.is_relative_to(PROJECT_ROOT):
        return "ERROR: path outside workspace"
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
    """List the contents of a directory.

    Use this to explore the project structure, find related Lean files,
    locate the blueprint directory, or check what build artifacts exist.
    Returns one entry per line; directories are suffixed with '/'.
    """
    p = Path(path)
    if not p.is_dir():
        return f"ERROR: {path} is not a directory"
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
    The parent directory must already exist.
    """
    path = Path(file_path)
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
    This regenerates `.lake/build/blueprint/module/LeanWorkspace.json` with the
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
