"""
Local Mathlib Retriever — reads Lean source directly from the local mathlib4
checkout instead of fetching from GitHub.

Provides a single utility function, ``get_mathlib_source``, that maps a
dot-separated (or slash-separated) Mathlib module name to the corresponding
``.lean`` file under the ``mathlib4/`` folder and returns its full contents.
Results are cached in memory for the lifetime of the process.
"""

from __future__ import annotations

from pathlib import Path

from config import MATHLIB4_ROOT

# In-memory source cache: resolved absolute file path → file contents
_source_cache: dict[str, str] = {}


def _module_to_relative_path(module_name: str) -> Path:
    """Map a dot-separated module name to its relative ``.lean`` file path.

    E.g. ``"Mathlib.Data.Real.Basic"`` → ``Path("Mathlib/Data/Real/Basic.lean")``.
    Slash-separated names (``"Mathlib/Data/Real/Basic"``) are also accepted.
    """
    normalized = module_name.replace(".", "/").strip("/")
    return Path(f"{normalized}.lean")


def get_mathlib_source(module_name: str, root: Path | None = None) -> str | None:
    """Read the full source of a Mathlib module from the local mathlib4 folder.

    *module_name* may be dot-separated (``Mathlib.Data.Real.Basic``) or
    slash-separated (``Mathlib/Data/Real/Basic``).  *root* overrides the
    mathlib4 root directory — used primarily in tests with temporary trees.

    Returns the file contents as a string, or ``None`` if the module could not
    be found (or the resolved path escapes the root directory).
    """
    name = (module_name or "").strip()
    if not name:
        return None

    base = (root or MATHLIB4_ROOT).resolve()
    path = (base / _module_to_relative_path(name)).resolve()

    # Only resolve paths that stay inside the root — prevents escaping the
    # mathlib4 tree via tricks like ``..`` in the module name.
    if base not in path.parents:
        return None

    key = str(path)
    if key in _source_cache:
        return _source_cache[key]

    if not path.is_file():
        return None

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    _source_cache[key] = source
    return source


def clear_cache() -> None:
    """Clear the in-memory source cache (used by tests)."""
    _source_cache.clear()
