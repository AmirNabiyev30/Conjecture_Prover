"""Align the Mathlib source read by code-module analysis with the compiled revision.

``analyze_mathlib_module`` reads Mathlib source from the root ``mathlib4/`` checkout
(``config.MATHLIB4_ROOT``). The Lean project compiles a *different* checkout,
``.lake/packages/mathlib``. They are separate clones, so they drift -- and then the
analyzer reads source the REPL cannot compile, which looks like a model failure
rather than stale data.

The reference is simply whatever ``.lake/packages/mathlib`` is checked out at. There
is no manifest to parse, and no way for the target to disagree with what actually
compiled.

:func:`sync` reports one of four outcomes so the caller decides what to do:

``IN_SYNC``
    Both trees are at the same revision. Continue.
``SYNCED``
    The analysis tree was moved to the compiled revision. Continue.
``STALE``
    Left alone; the detail says why. Warn, then continue.
``FAILED``
    The sync could not be performed at all. Stop.

Advancing Mathlib is not this script's job: that is ``lake update``, which moves the
compiled tree and therefore the reference.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import MATHLIB4_ROOT

REPO_ROOT: Path = Path(__file__).resolve().parents[1]

#: The tree Lean compiles. Its HEAD *is* the revision analysis must match, so the
#: target is read from here rather than from a manifest that could disagree.
COMPILED_MATHLIB: Path = REPO_ROOT / ".lake" / "packages" / "mathlib"

#: Canonical upstream. Fetching from the URL rather than from ``origin`` means a
#: pinned revision does not depend on which remote a local clone happens to have.
MATHLIB_URL: str = "https://github.com/leanprover-community/mathlib4.git"

IN_SYNC = "in_sync"
SYNCED = "synced"
STALE = "stale"
FAILED = "failed"

#: The one accepted command-line argument.
FETCH_FLAG: str = "--fetch"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo`` without raising on a non-zero exit."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def git_head(repo: Path) -> str | None:
    """Return the full sha at ``repo``'s HEAD, or None if it is not a git tree."""
    if not repo.is_dir():
        return None
    result = _git(repo, "rev-parse", "HEAD")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def is_dirty(repo: Path) -> bool:
    """Return whether ``repo`` has uncommitted changes."""
    return bool(_git(repo, "status", "--porcelain").stdout.strip())


def has_commit(repo: Path, rev: str) -> bool:
    """Return whether ``rev`` exists in ``repo``'s object database."""
    return _git(repo, "cat-file", "-e", f"{rev}^{{commit}}").returncode == 0


def sync(
    *,
    allow_fetch: bool = False,
    tree: Path | None = None,
    reference: Path | None = None,
) -> tuple[str, str]:
    """Align the analysis tree with the revision the compiler is checked out at.

    Args:
        allow_fetch: Permit ``git fetch`` when that revision is absent locally.
            Off by default so a run never touches the network implicitly.
        tree: Checkout to align; defaults to ``config.MATHLIB4_ROOT``.
        reference: The compiled checkout to match; defaults to
            :data:`COMPILED_MATHLIB`. A parameter so tests avoid the real ``.lake``.

    Returns:
        ``(outcome, detail)`` where outcome is :data:`IN_SYNC`, :data:`SYNCED`,
        :data:`STALE` or :data:`FAILED`, and detail is a log-ready message.
    """
    path = MATHLIB4_ROOT if tree is None else tree
    compiled = COMPILED_MATHLIB if reference is None else reference

    rev = git_head(compiled)
    if rev is None:
        return FAILED, f"{compiled} is not checked out; run `lake build` first"

    head = git_head(path)
    if head is None:
        return FAILED, f"{path} is not a git checkout; git clone {MATHLIB_URL} {path}"
    if is_dirty(path):
        return STALE, f"{path} has uncommitted changes; left as-is"
    if head == rev:
        return IN_SYNC, f"already at {rev[:12]}"

    if not has_commit(path, rev):
        if not allow_fetch:
            return STALE, f"{rev[:12]} not present locally; pass --fetch to download"
        if _git(path, "fetch", MATHLIB_URL).returncode != 0:
            return STALE, f"git fetch from {MATHLIB_URL} failed in {path}; left as-is"
        if not has_commit(path, rev):
            return STALE, f"{rev[:12]} still absent after fetching"

    checked_out = _git(path, "checkout", "--detach", rev)
    if checked_out.returncode != 0:
        return FAILED, f"git checkout {rev[:12]} failed: {checked_out.stderr.strip()}"
    if git_head(path) != rev:
        return FAILED, f"{path} is not at {rev[:12]} after checkout"
    return SYNCED, f"checked out {rev[:12]}"


def main(argv: list[str] | None = None) -> int:
    """Run the sync and turn its outcome into an exit status.

    ``FAILED`` exits 1 so a caller can stop; ``STALE`` warns and exits 0 so a
    drifted-but-usable tree does not block a run.
    """
    args = sys.argv[1:] if argv is None else argv
    unknown = [arg for arg in args if arg != FETCH_FLAG]
    if unknown:
        print(
            f"usage: python -m experiments.mathlib_sync [{FETCH_FLAG}]",
            file=sys.stderr,
        )
        print(f"unknown argument(s): {' '.join(unknown)}", file=sys.stderr)
        return 2

    outcome, detail = sync(allow_fetch=FETCH_FLAG in args)
    if outcome == FAILED:
        print(f"ERROR: Mathlib sync failed: {detail}", file=sys.stderr)
        return 1
    if outcome == STALE:
        print(f"WARNING: Mathlib analysis source is stale: {detail}", file=sys.stderr)
        return 0
    if outcome == SYNCED:
        print(f"Mathlib analysis source {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
