"""Unit tests for Mathlib retrieval (``retrieval.lean_search``)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from retrieval.lean_search import retrieve_similar_theorems


@pytest.mark.asyncio
async def test_retrieve_similar_theorems_returns_expected_schema():
    """Integration test — requires downloaded Mathlib declaration data."""
    results = await retrieve_similar_theorems("Monotone", top_k=3)
    # May be empty if Mathlib cache hasn't been downloaded; skip gracefully
    if not results:
        pytest.skip("Mathlib declaration cache not available")

    for r in results:
        assert "name" in r
        assert "statement" in r
        assert "proof" in r
        assert "metadata" in r
        assert "kind" in r["metadata"]
        assert "module" in r["metadata"]


@pytest.mark.asyncio
async def test_retrieve_similar_theorems_no_match():
    results = await retrieve_similar_theorems("xyznonexistent999abc", top_k=3)
    assert results == []
