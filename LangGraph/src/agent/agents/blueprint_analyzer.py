"""
Blueprint Analyzer — LangChain tools for Mathlib retrieval.

Provides a tool for fetching the source of a Mathlib declaration from the local
mathlib4 checkout, including its statement and proof body.
"""

from __future__ import annotations

import re

from langchain_core.tools import tool

from retrieval.local_mathlib_retriever import get_mathlib_source


# ═══════════════════════════════════════════════════════════════════════════════
# Mathlib source fetching (local)
# ═══════════════════════════════════════════════════════════════════════════════


def _fetch_mathlib_source(module_path: str) -> str | None:
    """Read the source of a Mathlib module from the local mathlib4 checkout.

    *module_path* may be dot-separated (``Mathlib.Data.Real.Basic``) or
    slash-separated (``Mathlib/Data/Real/Basic``).  Delegates to
    ``retrieval.local_mathlib_retriever.get_mathlib_source``, which resolves the
    module to its ``.lean`` file and caches the result in memory for the
    lifetime of the process.
    """
    return get_mathlib_source(module_path)


def _find_declaration_in_source(source: str, decl_name: str) -> str | None:
    """Extract the full declaration block for *decl_name* from Lean source.

    *decl_name* may be fully qualified (``AbsolutelyMonotoneOn.add``) — if the
    full name is not found at the top level, the last dot-separated component
    is tried (``add``), which matches declarations inside a namespace.

    Returns the lines from the first line matching the declaration through the
    end of its proof body.
    """
    lines = source.split("\n")

    # Try full name first, then short name
    names_to_try = [decl_name]
    if "." in decl_name:
        names_to_try.append(decl_name.rsplit(".", 1)[-1])

    start = None
    matched_name = None
    for name in names_to_try:
        pattern = re.compile(
            rf"^\s*(?:theorem|lemma|def|instance)\s+{re.escape(name)}\b"
        )
        for i, line in enumerate(lines):
            if pattern.search(line):
                start = i
                matched_name = name
                break
        if start is not None:
            break

    if start is None:
        return None

    # Walk forward: stop at the next top-level declaration (same indent level)
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip()
        if not stripped or stripped.startswith("--") or stripped.startswith("/-"):
            continue
        line_indent = len(lines[i]) - len(stripped)
        if line_indent <= indent and re.match(
            r"^(theorem|lemma|def|instance|example|inductive|structure|class|abbrev|end|#|namespace|section|open|variable|universe)\b",
            stripped,
        ):
            end = i
            break

    return "\n".join(lines[start:end])


@tool
async def fetch_mathlib_source(decl_name: str) -> str:
    """Fetch the FULL source code of a Mathlib declaration from the local mathlib4 checkout.

    Use this to examine a specific Mathlib theorem in detail. You get the
    complete Lean source — the
    statement, proof body, and all tactics — so you can understand exactly
    how Mathlib proves this theorem and which lemmas it depends on.

    Args:
        decl_name: The fully-qualified Mathlib declaration name.
                   E.g., "AbsolutelyMonotoneOn.add", "isConnected_T",
                   "Filter.Tendsto.mono".

    Returns the full source code of the declaration (statement + proof body),
    or an error message if the declaration could not be found.
    """
    from mathlib_doc_tools import _load_decl_data

    # 1. Find the module for this declaration in the docs cache
    data = _load_decl_data()
    declarations = data.get("declarations", {})
    decl = declarations.get(decl_name)

    if decl is None:
        # Try case-insensitive search
        for name, d in declarations.items():
            if name.lower() == decl_name.lower():
                decl = d
                decl_name = name
                break

    if decl is None:
        return (
            f"Declaration '{decl_name}' not found in Mathlib docs index.\n"
            "Try a different fully-qualified declaration name."
        )

    # 2. Get the module path from the doc URL
    from mathlib_doc_tools import _parse_doc_url, _doc_url
    doc_link = decl.get("docLink", "")
    if not doc_link:
        return f"Declaration '{decl_name}' has no doc link — cannot locate source."

    url = _doc_url(doc_link)
    parsed = _parse_doc_url(url)
    module = parsed.get("module", "")

    if not module:
        return f"Could not determine module for '{decl_name}' from doc URL: {url}"

    # 3. Read the source from the local mathlib4 checkout
    source = _fetch_mathlib_source(module)
    if source is None:
        return (
            f"Could not read source for module '{module}' from the local mathlib4 checkout.\n"
            f"Doc URL: {url}"
        )

    # 4. Extract the declaration
    decl_source = _find_declaration_in_source(source, decl_name)
    if decl_source is None:
        return (
            f"Module '{module}' fetched ({len(source)} chars) but declaration "
            f"'{decl_name}' not found within it. The file may use namespaces — "
            f"try the short name (last component after the last dot)."
        )

    # 5. Build header (LLM reads the source directly — no regex extraction)
    header = (
        f"## Source: {decl_name}\n"
        f"**Module**: {module}\n"
        f"**Kind**: {decl.get('kind', 'unknown')}\n"
        f"**Doc**: {url}\n\n"
        f"```lean\n{decl_source}\n```"
    )

    return header
