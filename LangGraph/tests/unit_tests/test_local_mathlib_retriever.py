"""Unit tests for the local Mathlib source retriever.

Uses temporary fake mathlib trees so no real mathlib4 checkout or network is
required.  A real mathlib4 smoke test is included but skips gracefully when the
checkout isn't present.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from retrieval.local_mathlib_retriever import get_mathlib_source, clear_cache


@pytest.fixture(autouse=True)
def clear_source_cache():
    """Ensure the in-memory cache doesn't leak between tests."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def fake_mathlib(tmp_path):
    """Create a minimal fake mathlib4 tree with known module contents."""
    basic = tmp_path / "Mathlib" / "Data" / "Real" / "Basic.lean"
    basic.parent.mkdir(parents=True)
    basic.write_text(
        "-- Mathlib.Data.Real.Basic\n\ntheorem foo : True := by trivial\n",
        encoding="utf-8",
    )

    order = tmp_path / "Mathlib" / "Order" / "Basic.lean"
    order.parent.mkdir(parents=True)
    order.write_text("-- Mathlib.Order.Basic\n", encoding="utf-8")

    return tmp_path


def test_dot_separated_module_name_maps_to_file(fake_mathlib):
    source = get_mathlib_source("Mathlib.Data.Real.Basic", root=fake_mathlib)
    assert source is not None
    assert "theorem foo : True" in source


def test_slash_separated_module_name(fake_mathlib):
    source = get_mathlib_source("Mathlib/Data/Real/Basic", root=fake_mathlib)
    assert source is not None
    assert "theorem foo : True" in source


def test_returns_exact_file_contents(fake_mathlib):
    source = get_mathlib_source("Mathlib.Order.Basic", root=fake_mathlib)
    assert source == "-- Mathlib.Order.Basic\n"


def test_missing_module_returns_none(fake_mathlib):
    assert get_mathlib_source("Mathlib.DoesNotExist.Module", root=fake_mathlib) is None


def test_empty_and_whitespace_names_return_none(fake_mathlib):
    assert get_mathlib_source("", root=fake_mathlib) is None
    assert get_mathlib_source("   ", root=fake_mathlib) is None


def test_path_escape_returns_none(fake_mathlib):
    # ".." traversal must not escape the mathlib root
    assert get_mathlib_source("../secret", root=fake_mathlib) is None


def test_caching_returns_original_content(fake_mathlib):
    first = get_mathlib_source("Mathlib.Data.Real.Basic", root=fake_mathlib)

    # Modify the file on disk after the first read
    target = fake_mathlib / "Mathlib" / "Data" / "Real" / "Basic.lean"
    target.write_text("-- changed on disk\n", encoding="utf-8")

    second = get_mathlib_source("Mathlib.Data.Real.Basic", root=fake_mathlib)
    assert second == first  # cached content, not the on-disk change
    assert "theorem foo" in second


def test_clear_cache_invalidates(fake_mathlib):
    first = get_mathlib_source("Mathlib.Data.Real.Basic", root=fake_mathlib)
    assert "theorem foo" in first

    target = fake_mathlib / "Mathlib" / "Data" / "Real" / "Basic.lean"
    target.write_text("-- changed\n", encoding="utf-8")

    clear_cache()
    second = get_mathlib_source("Mathlib.Data.Real.Basic", root=fake_mathlib)
    assert second == "-- changed\n"


def test_reads_real_mathlib4_file():
    """Smoke test against the real mathlib4 checkout, if present."""
    from config import MATHLIB4_ROOT

    if not (MATHLIB4_ROOT / "Mathlib").is_dir():
        pytest.skip("mathlib4 checkout not present")

    source = get_mathlib_source("Mathlib.Data.Real.Basic")
    assert source is not None
    assert len(source) > 100
