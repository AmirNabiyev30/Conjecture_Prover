"""
Mathlib4 Documentation Search Tools
Local LangChain tools that replace the lean-mathlib-docs-mcp server.

Data source: https://leanprover-community.github.io/mathlib4_docs/declarations/declaration-data.bmp
(JSON file despite the .bmp extension)

Usage:
    from mathlib_docs_tools import doc_tools, doc_tool_names
    # then add to your bind_tools call:
    llm_with_tools = llm.bind_tools(file_tools + human_tools + lean_tools + doc_tools)

Workflow the model should follow:
    1. search_mathlib_docs / search_mathlib_docs_multi  →  find candidate names + Loogle hints
    2. lean_loogle (with the returned loogle query string)  →  get exact type signature
    3. Use the exact Mathlib name in the blueprint; never redefine what already exists.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from langchain_core.tools import tool

from config import PROJECT_ROOT

# ── Config ────────────────────────────────────────────────────────────────────

# Local cache lives under the project root so it moves with the repo.
_CACHE_PATH = PROJECT_ROOT / ".cache" / "declaration-data.json"
_DOCS_BASE  = "https://leanprover-community.github.io/mathlib4_docs/"
_DATA_URL   = _DOCS_BASE + "declarations/declaration-data.bmp"

# Module-level declaration cache — loaded once per process, thread-safe
_decl_data: Optional[dict] = None
_load_lock  = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_decl_data() -> dict:
    """Load declaration data from local cache, downloading if necessary."""
    global _decl_data

    if _decl_data is not None:
        return _decl_data

    with _load_lock:
        # Double-checked locking: re-check after acquiring the lock
        if _decl_data is not None:
            return _decl_data

        if not _CACHE_PATH.exists():
            print(f"[mathlib_docs] Downloading declaration data from {_DATA_URL} ...")
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            try:
                resp = requests.get(_DATA_URL, timeout=30)
                resp.raise_for_status()
                _CACHE_PATH.write_bytes(resp.content)
                print(f"[mathlib_docs] Saved to {_CACHE_PATH}")
            except requests.RequestException as e:
                raise RuntimeError(f"Failed to download declaration data: {e}") from e

        print(f"[mathlib_docs] Loading {_CACHE_PATH} ...")
        _decl_data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        decl_count = len(_decl_data.get("declarations", {}))
        print(f"[mathlib_docs] Loaded {decl_count:,} declarations.")

    return _decl_data


def _doc_url(doc_link: str) -> str:
    """Convert a docLink field value to a full absolute URL."""
    return _DOCS_BASE + doc_link.lstrip("./")


def _parse_doc_url(doc_url: str) -> dict:
    """Extract module path and ready-made Loogle query strings from a Mathlib doc URL.

    Mathlib doc URLs encode the full module path in their path component:
        .../mathlib4_docs/Mathlib/Order/Monotone/Basic.html#Monotone
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^
                          module path (dots = slashes)      declaration (fragment)

    Returns a dict with:
        module          – dot-separated Lean module name  e.g. 'Mathlib.Order.Monotone.Basic'
        declaration     – declaration name from URL fragment, e.g. 'Monotone'
        loogle_name     – best Loogle query string by name
        loogle_module   – Loogle query string to list all decls in the module
    """
    parsed   = urlparse(doc_url)
    path     = parsed.path      # e.g. /mathlib4_docs/Mathlib/Order/Monotone/Basic.html
    fragment = parsed.fragment  # e.g. 'Monotone'  (may be empty)

    # Strip the /mathlib4_docs/ prefix
    prefix = "/mathlib4_docs/"
    if prefix in path:
        path = path[path.index(prefix) + len(prefix):]

    # Strip .html suffix → gives us the slash-separated module path
    path = path.removesuffix(".html")

    # Convert path separators to dots → Lean-style module name
    module_path = path.replace("/", ".")  # e.g. 'Mathlib.Order.Monotone.Basic'

    # Prefer the URL fragment as the declaration name; fall back to last path segment
    decl_name = fragment if fragment else module_path.split(".")[-1]

    return {
        "module":         module_path,
        "declaration":    decl_name,
        "loogle_name":    decl_name,
        "loogle_module":  module_path,
    }


def _format_result(name: str, decl: dict, indent: str = "") -> str:
    """Format a single declaration result with doc URL and Loogle query hints."""
    kind     = decl.get("kind", "unknown")
    doc_link = decl.get("docLink", "")

    if not doc_link:
        return f"{indent}{kind}: {name}\n{indent}  Docs: (no link available)"

    url    = _doc_url(doc_link)
    parsed = _parse_doc_url(url)

    return (
        f"{indent}{kind}: {name}\n"
        f"{indent}  Docs:          {url}\n"
        f"{indent}  Module:        {parsed['module']}\n"
        f"{indent}  Loogle (name): {parsed['loogle_name']}\n"
        f"{indent}  Loogle (mod):  {parsed['loogle_module']}"
    )


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def search_mathlib_docs(query: str, max_results: int = 8) -> str:
    """Search Mathlib4 declaration names and return kind, doc URL, and ready-made
    Loogle query strings for each result.

    Use this BEFORE defining any type, predicate, or operation in a blueprint to
    check whether Mathlib already provides an equivalent. Prefer Mathlib's existing
    declarations over custom ones — use the exact Mathlib name in the blueprint
    rather than redefining it.

    Query by name fragment:
      - 'Monotone'       → finds Monotone, MonotoneOn, StrictMono, ...
      - 'lintegral'      → finds MeasureTheory.lintegral and related lemmas
      - 'Tendsto'        → finds Filter.Tendsto and variants
      - 'BddAbove'       → finds boundedness predicates

    Workflow after calling this tool:
      1. Pick the most relevant result.
      2. Pass its 'Loogle (name)' string to lean_loogle to get the exact type signature.
      3. Use the exact Mathlib name in the blueprint — never redefine what already exists.
    """
    data         = _load_decl_data()
    declarations = data.get("declarations", {})
    pattern      = re.compile(re.escape(query), re.IGNORECASE)
    results      = []

    for name, decl in declarations.items():
        if pattern.search(name):
            results.append(_format_result(name, decl))
            if len(results) >= max_results:
                break

    if not results:
        return (
            f"No declarations found matching '{query}'.\n"
            "Try a shorter or different name fragment, "
            "or use lean_loogle for type-signature search."
        )

    header = f"Found {len(results)} declaration(s) matching '{query}':\n\n"
    return header + "\n\n".join(results)


@tool
def search_mathlib_docs_multi(queries: list[str], max_results_per_query: int = 5) -> str:
    """Search Mathlib4 for multiple name fragments in one call.

    Identical to search_mathlib_docs but batches several queries so you avoid
    multiple round-trips. Each result includes kind, doc URL, module path, and
    ready-made Loogle query strings.

    Use this when drafting a blueprint and you want to check several potential
    Mathlib names at once — e.g. before writing definitions for a theorem that
    involves monotonicity, boundedness, and convergence concepts simultaneously.

    Example: queries=['Monotone', 'BddAbove', 'Tendsto', 'lintegral_mono']

    Workflow after calling this tool:
      1. Pick relevant results from each section.
      2. Pass each 'Loogle (name)' string to lean_loogle to confirm the type signature.
      3. Use exact Mathlib names in the blueprint; never define a custom equivalent.
    """
    data         = _load_decl_data()
    declarations = data.get("declarations", {})
    all_sections = []

    for query in queries:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        results = []

        for name, decl in declarations.items():
            if pattern.search(name):
                results.append(_format_result(name, decl, indent="  "))
                if len(results) >= max_results_per_query:
                    break

        if results:
            section = (
                f"=== '{query}' — {len(results)} result(s) ===\n"
                + "\n\n".join(results)
            )
        else:
            section = (
                f"=== '{query}' — no results ===\n"
                "  Try a shorter fragment or lean_loogle for type-signature search."
            )

        all_sections.append(section)

    return "\n\n".join(all_sections)


@tool
def refresh_mathlib_docs_cache() -> str:
    """Re-download the Mathlib4 declaration data from the official docs site.

    Use this if search results seem stale (e.g. a known Mathlib declaration is
    not found) or if the local cache file is missing or corrupted.

    Cache location: {_CACHE_PATH}
    """
    global _decl_data

    print(f"[mathlib_docs] Re-downloading from {_DATA_URL} ...")
    try:
        resp = requests.get(_DATA_URL, timeout=30)
        resp.raise_for_status()
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_bytes(resp.content)
    except requests.RequestException as e:
        return f"ERROR: Download failed: {e}"

    # Invalidate in-memory cache so the next call reloads from disk
    with _load_lock:
        _decl_data = None

    # Immediately reload so we can report the count
    data       = _load_decl_data()
    decl_count = len(data.get("declarations", {}))
    return (
        f"Cache refreshed successfully.\n"
        f"Saved to:   {_CACHE_PATH}\n"
        f"Loaded:     {decl_count:,} declarations"
    )


# ── Exports ───────────────────────────────────────────────────────────────────

doc_tools      = [search_mathlib_docs, search_mathlib_docs_multi, refresh_mathlib_docs_cache]
doc_tool_names = {t.name for t in doc_tools}