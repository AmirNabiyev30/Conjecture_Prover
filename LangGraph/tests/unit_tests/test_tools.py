"""Unit tests for the agent's file tools and the path sandbox.

The sandbox (`_resolve_agent_path`) is the only thing standing between a
hallucinating model and the rest of the filesystem, so it is worth testing
directly rather than only through the tools that call it.

Behavior contract:
- Paths resolve relative to ``PROJECT_ROOT`` unless absolute, and anything that
  lands outside the project is refused with an ERROR string — including a path
  that is *inside* the project only via a symlink to somewhere outside.
- The experiment-output directories (``experiment_runs/``) are off-limits, both
  the directory itself and anything beneath it.
- Every tool returns an ERROR string rather than raising, because the model reads
  the result: an exception would abort the node instead of letting it recover.
- ``create_file`` creates missing parent directories (its docstring used to claim
  the opposite, which is what these tests pinned down).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

import tools  # noqa: E402


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """A temp project tree with the sandbox pointed at it.

    Patching PROJECT_ROOT matters: the tools write through to disk, so without
    this a test could create or overwrite files in the real repository.
    """
    (tmp_path / "sub").mkdir()
    (tmp_path / "experiment_runs" / "logs").mkdir(parents=True)
    (tmp_path / "ConjectureProver.lean").write_text("-- lean\n", encoding="utf-8")
    (tmp_path / "experiment_runs" / "results.csv").write_text("a,b\n", encoding="utf-8")
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    return tmp_path


# ── _resolve_agent_path ──────────────────────────────────────────────────────

def test_relative_path_resolves_under_the_project(project):
    path, err = tools._resolve_agent_path("sub")
    assert err is None
    assert path == project / "sub"


def test_absolute_path_inside_the_project_is_allowed(project):
    path, err = tools._resolve_agent_path(str(project / "ConjectureProver.lean"))
    assert err is None
    assert path == project / "ConjectureProver.lean"


def test_absolute_path_outside_the_project_is_refused(project):
    """Takes the fixture so the assertion does not depend on where the repo lives."""
    path, err = tools._resolve_agent_path("/etc/hosts")
    assert path is None
    assert "outside the project" in err


def test_traversal_escaping_the_project_is_refused(project):
    for candidate in ("../outside.txt", "sub/../../outside.txt"):
        path, err = tools._resolve_agent_path(candidate)
        assert path is None, candidate
        assert "outside the project" in err


def test_the_blocked_directory_itself_is_refused(project):
    path, err = tools._resolve_agent_path("experiment_runs")
    assert path is None
    assert "blocked directory 'experiment_runs'" in err


def test_a_path_inside_the_blocked_directory_is_refused(project):
    path, err = tools._resolve_agent_path("experiment_runs/results.csv")
    assert path is None
    assert "blocked directory 'experiment_runs'" in err


def test_a_symlink_pointing_outside_the_project_is_refused(project, tmp_path_factory):
    """The check runs after resolve(), so it sees the link's target, not the link."""
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    (project / "link.txt").symlink_to(outside / "secret.txt")

    path, err = tools._resolve_agent_path("link.txt")

    assert path is None
    assert "outside the project" in err


# ── read / write ─────────────────────────────────────────────────────────────

def test_read_workspace_returns_the_file_contents(project):
    assert tools.read_workspace.func("ConjectureProver.lean") == "-- lean\n"


def test_read_workspace_reports_a_missing_file_instead_of_raising(project):
    result = tools.read_workspace.func("nope.lean")
    assert result.startswith("ERROR: file not found")


def test_read_workspace_refuses_the_blocked_directory(project):
    result = tools.read_workspace.func("experiment_runs/results.csv")
    assert result.startswith("ERROR: path is inside blocked directory")


def test_read_workspace_refuses_a_path_outside_the_project(project):
    assert tools.read_workspace.func("/etc/hosts").startswith("ERROR: path is outside")


def test_write_workspace_writes(project):
    tools.write_workspace.func("sub/new.lean", "-- written\n")
    assert (project / "sub" / "new.lean").read_text(encoding="utf-8") == "-- written\n"


def test_write_workspace_refuses_the_blocked_directory(project):
    result = tools.write_workspace.func("experiment_runs/results.csv", "clobbered")
    assert result.startswith("ERROR: path is inside blocked directory")
    # The refusal must be a refusal: the original content survives.
    assert (project / "experiment_runs" / "results.csv").read_text(encoding="utf-8") == "a,b\n"


# ── create_file ──────────────────────────────────────────────────────────────

def test_create_file_creates_missing_parent_directories(project):
    """The docstring used to claim the opposite; the code is the friendlier one."""
    result = tools.create_file.func("a/b/c.lean", "-- deep\n")
    assert "Created" in result
    assert (project / "a" / "b" / "c.lean").read_text(encoding="utf-8") == "-- deep\n"


def test_create_file_refuses_to_overwrite_an_existing_file(project):
    result = tools.create_file.func("ConjectureProver.lean", "clobbered")
    assert "already exists" in result
    assert (project / "ConjectureProver.lean").read_text(encoding="utf-8") == "-- lean\n"


# ── search_replace_workspace ─────────────────────────────────────────────────

def test_search_replace_replaces_a_unique_occurrence(project):
    tools.search_replace_workspace.func("ConjectureProver.lean", "-- lean", "-- proof")
    assert (project / "ConjectureProver.lean").read_text(encoding="utf-8") == "-- proof\n"


def test_search_replace_rejects_an_absent_string(project):
    assert tools.search_replace_workspace.func(
        "ConjectureProver.lean", "-- missing", "x"
    ) == "ERROR: old_string not found"


def test_search_replace_rejects_an_ambiguous_string(project):
    (project / "dup.lean").write_text("x\nx\n", encoding="utf-8")
    result = tools.search_replace_workspace.func("dup.lean", "x", "y")
    assert result == "ERROR: old_string appears multiple times"
    assert (project / "dup.lean").read_text(encoding="utf-8") == "x\nx\n"


def test_search_replace_reports_a_missing_file(project):
    assert tools.search_replace_workspace.func("nope.lean", "a", "b").startswith(
        "ERROR: file not found"
    )


# ── list_directory ───────────────────────────────────────────────────────────

def test_list_directory_marks_directories_with_a_slash(project):
    listing = tools.list_directory.func(".").splitlines()
    assert "sub/" in listing
    assert "ConjectureProver.lean" in listing


def test_list_directory_refuses_a_file(project):
    assert "is not a directory" in tools.list_directory.func("ConjectureProver.lean")


def test_list_directory_refuses_the_blocked_directory(project):
    assert tools.list_directory.func("experiment_runs").startswith(
        "ERROR: path is inside blocked directory"
    )
