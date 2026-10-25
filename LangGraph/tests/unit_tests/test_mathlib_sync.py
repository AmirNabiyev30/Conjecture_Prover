"""Unit tests for ``experiments.mathlib_sync``.

The script aligns the Mathlib source read by code-module analysis with the revision
the compiler is checked out at. What matters is that it never destroys work, that a
drifted tree is reported as STALE rather than forced, and that only real failures
abort.

Every repository here is a throwaway built under ``tmp_path``, and ``sync`` takes the
reference tree as a parameter, so nothing touches the real ``.lake``. The CLI tests
stub ``sync``.
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from experiments import mathlib_sync  # noqa: E402


def _head(repo: Path) -> str:
    """Return the full sha at ``repo``'s HEAD."""
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    """Add an empty commit to ``repo`` and return its sha."""
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.email=test@example.com",
            "-c", "user.name=test",
            "commit", "-q", "--allow-empty", "-m", message,
        ],
        check=True,
    )
    return _head(repo)


def _make_repo(path: Path, *messages: str) -> list[str]:
    """Create a git repo at ``path`` with one empty commit per message.

    Returns the sha of each commit, oldest first.
    """
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return [_commit(path, message) for message in messages]


def _pair(tmp_path: Path) -> tuple[Path, Path, list[str]]:
    """Build a compiled repo at the tip and an analysis repo one commit behind.

    Two clones of one seed, so the analysis repo already holds the tip commit in
    its object database -- a checkout therefore needs no network, which is what
    keeps these tests hermetic. Mirrors the real layout: the compiled checkout is
    the reference, the analysis checkout is what has to catch up.
    """
    seed = tmp_path / "seed"
    shas = _make_repo(seed, "one", "two")

    compiled = tmp_path / "compiled"
    analysis = tmp_path / "analysis"
    for path in (compiled, analysis):
        subprocess.run(["git", "clone", "-q", str(seed), str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(analysis), "checkout", "-q", "--detach", shas[0]],
        check=True,
    )
    return compiled, analysis, shas


# ── sync: the four outcomes ─────────────────────────────────────────────────

def test_in_sync_when_both_trees_agree(tmp_path):
    compiled, analysis, shas = _pair(tmp_path)
    subprocess.run(
        ["git", "-C", str(analysis), "checkout", "-q", "--detach", shas[-1]],
        check=True,
    )

    outcome, detail = mathlib_sync.sync(tree=analysis, reference=compiled)

    assert outcome == mathlib_sync.IN_SYNC
    assert shas[-1][:12] in detail


def test_synced_when_the_analysis_tree_is_behind(tmp_path):
    compiled, analysis, _ = _pair(tmp_path)

    outcome, _ = mathlib_sync.sync(tree=analysis, reference=compiled)

    assert outcome == mathlib_sync.SYNCED
    assert _head(analysis) == _head(compiled)


def test_stale_and_untouched_when_the_tree_is_dirty(tmp_path):
    compiled, analysis, _ = _pair(tmp_path)
    (analysis / "stray.txt").write_text("uncommitted work", encoding="utf-8")

    outcome, detail = mathlib_sync.sync(tree=analysis, reference=compiled)

    assert outcome == mathlib_sync.STALE
    assert "uncommitted" in detail
    assert (analysis / "stray.txt").is_file()


def test_stale_when_the_revision_is_absent_and_fetching_is_off(tmp_path):
    compiled, analysis, _ = _pair(tmp_path)
    _commit(compiled, "moved ahead")  # analysis has never seen this commit

    outcome, detail = mathlib_sync.sync(tree=analysis, reference=compiled)

    assert outcome == mathlib_sync.STALE
    assert "--fetch" in detail


def test_failed_when_the_project_was_never_built(tmp_path):
    """No compiled checkout means there is no revision to match."""
    _, analysis, _ = _pair(tmp_path)

    outcome, detail = mathlib_sync.sync(tree=analysis, reference=tmp_path / "absent")

    assert outcome == mathlib_sync.FAILED
    assert "lake build" in detail


def test_failed_when_the_analysis_tree_is_not_a_checkout(tmp_path):
    compiled, _, _ = _pair(tmp_path)

    outcome, detail = mathlib_sync.sync(tree=tmp_path / "absent", reference=compiled)

    assert outcome == mathlib_sync.FAILED
    assert "not a git checkout" in detail
    # The message has to say where to clone from, or it is not actionable.
    assert mathlib_sync.MATHLIB_URL in detail


# ── CLI: failed aborts, stale only warns ─────────────────────────────────────

def test_failed_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(
        mathlib_sync, "sync", lambda **_: (mathlib_sync.FAILED, "not built")
    )
    assert mathlib_sync.main([]) == 1
    assert "ERROR" in capsys.readouterr().err


def test_stale_warns_but_does_not_stop_the_run(monkeypatch, capsys):
    monkeypatch.setattr(
        mathlib_sync, "sync", lambda **_: (mathlib_sync.STALE, "uncommitted changes")
    )
    assert mathlib_sync.main([]) == 0
    assert "WARNING" in capsys.readouterr().err


def test_an_unknown_argument_is_rejected(capsys):
    """A typo must fail loudly rather than be silently ignored."""
    assert mathlib_sync.main(["--fetchh"]) == 2
    assert "unknown argument" in capsys.readouterr().err


def test_in_sync_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(
        mathlib_sync, "sync", lambda **_: (mathlib_sync.IN_SYNC, "already at abc123")
    )
    assert mathlib_sync.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "WARNING" not in captured.err
