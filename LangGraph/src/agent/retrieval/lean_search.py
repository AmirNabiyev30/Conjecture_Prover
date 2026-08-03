"""
Lean Retrieval Interface — wraps the existing Mathlib documentation search.

Provides a clean ``retrieve_similar_theorems()`` function that queries Mathlib
for declarations matching a natural-language or keyword query.  This is a thin
wrapper around ``mathlib_doc_tools``; no vector database is used.
"""

from __future__ import annotations

from typing import Optional


async def retrieve_similar_theorems(
    query: str,
    top_k: int = 8,
    *,
    _decl_data: Optional[dict] = None,
) -> list[dict]:
    """Search Mathlib for declarations matching *query*.

    Uses the same declaration-data cache as ``mathlib_doc_tools``.  Results are
    returned as a list of dicts with the canonical schema:

    .. code-block:: python

        {
            "name": str,          # fully-qualified Lean name, e.g. "IsConnected"
            "statement": str,     # documentation string / type hint (if available)
            "proof": str,         # always "" — Mathlib docs do not include proof bodies
            "metadata": {
                "kind": str,      # "theorem" | "lemma" | "def" | "inductive" | ...
                "module": str,    # dot-separated module path
                "doc_url": str,   # full URL to Mathlib4 docs page
                "loogle_name": str,
                "loogle_module": str,
            },
        }

    Parameters
    ----------
    query:
        Name fragment or keyword to search for (e.g. ``"Monotone"``,
        ``"IsConnected"``, ``"spectral radius"``).
    top_k:
        Maximum number of results to return.
    """
    import re
    from mathlib_doc_tools import _load_decl_data, _doc_url, _parse_doc_url

    data = _decl_data if _decl_data is not None else _load_decl_data()
    declarations = data.get("declarations", {})
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results: list[dict] = []

    for name, decl in declarations.items():
        if pattern.search(name):
            doc_link = decl.get("docLink", "")
            url = _doc_url(doc_link) if doc_link else ""
            parsed = _parse_doc_url(url) if url else {}

            results.append({
                "name": name,
                "statement": decl.get("doc", ""),
                "proof": "",  # Mathlib docs do not include proof bodies
                "metadata": {
                    "kind": decl.get("kind", "unknown"),
                    "module": parsed.get("module", ""),
                    "doc_url": url,
                    "loogle_name": parsed.get("loogle_name", name),
                    "loogle_module": parsed.get("loogle_module", ""),
                },
            })
            if len(results) >= top_k:
                break

    return results
