"""
Lean source-text inspection: does a declaration still contain an escape hatch?

Three places in the pipeline need this answer and they must agree, because the
prover's accept/reject decision and the aggregator's proved/unproved scan are two
views of the same fact. They previously disagreed: ``blueprint`` treated ``admit``
as an escape while ``prove_lemma`` did not, so a proof using ``admit`` was
accepted by the prover but counted unsolved by the scanner.

Two distinct questions live here:

- :func:`contains_escape` — "is this proof still unfinished?" (``sorry``,
  ``sorry_using``, ``sorryAx``, ``admit``). Used by the prover and the status scan.
- :func:`has_sorry_using_placeholder` — "does this declaration still have the
  ``sorry_using [...]`` placeholder shape that ``prove_lemma`` expects?" Used by
  the dispatcher to decide what is worth dispatching. This is deliberately *not*
  the same question: a bare ``sorry`` is an escape but not a placeholder.

Matching is word-boundary based, so identifiers and prose that merely contain the
letters (``my_sorry_helper``, ``admissible``) are not flagged, and it ignores
comments and string literals so a note like ``-- sorry, this failed`` does not
make a finished proof look unfinished.
"""

from __future__ import annotations

import re

#: Tokens that mean a proof was left unfinished. ``sorry_using`` and ``sorryAx``
#: are listed explicitly because word-boundary matching does not treat ``sorry``
#: as a whole word inside them (``_`` and ``A`` are identifier characters).
ESCAPE_MARKERS: tuple[str, ...] = ("sorry", "sorry_using", "sorryAx", "admit")

#: The placeholder shape the prover prompt and the aggregator fixer both assume.
SORRY_USING_MARKER: str = "sorry_using"

_ESCAPE_RE = re.compile(r"\b(?:" + "|".join(ESCAPE_MARKERS) + r")\b")
_SORRY_USING_RE = re.compile(r"\b" + SORRY_USING_MARKER + r"\b")


def strip_comments_and_strings(text: str) -> str:
    """Blank out Lean comments and string literals, preserving length and lines.

    Lean block comments nest (``/- outer /- inner -/ still outer -/``), so a
    non-greedy regex is wrong here — it would stop at the first ``-/``. Consumed
    characters are replaced by spaces rather than removed, so offsets and line
    numbers still line up with the original text.
    """
    out: list[str] = []
    i, n = 0, len(text)
    depth = 0                 # block-comment nesting depth
    in_line_comment = False

    while i < n:
        ch = text[i]

        if in_line_comment:
            in_line_comment = ch != "\n"
            out.append(ch if ch == "\n" else " ")
            i += 1
            continue

        if depth > 0:
            if text.startswith("-/", i):
                depth -= 1
                out.append("  ")
                i += 2
            elif text.startswith("/-", i):
                depth += 1
                out.append("  ")
                i += 2
            else:
                out.append(ch if ch == "\n" else " ")
                i += 1
            continue

        if text.startswith("--", i):
            in_line_comment = True
            out.append("  ")
            i += 2
            continue

        if text.startswith("/-", i):
            depth = 1
            out.append("  ")
            i += 2
            continue

        if ch == '"':
            out.append(" ")
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:                     # closing quote
                out.append(" ")
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def contains_escape(text: str) -> bool:
    """True if ``text`` still contains an unfinished-proof escape hatch.

    Comments and string literals are ignored, and the match is on whole words, so
    ``my_sorry_helper`` and ``-- TODO: sorry`` both return False. Matching is
    case-sensitive because Lean's ``sorry`` is a lowercase keyword: ``Sorry`` is
    not a valid tactic and will fail the compile check instead.
    """
    return _ESCAPE_RE.search(strip_comments_and_strings(text)) is not None


def has_sorry_using_placeholder(text: str) -> bool:
    """True if ``text`` still holds a ``sorry_using [...]`` placeholder.

    Asked by the dispatcher, which only sends declarations the prover can splice
    into. A declaration with a bare ``sorry`` is unfinished but has no placeholder
    to replace, so it is not dispatched — see :func:`contains_escape` for the
    "is it finished?" question.
    """
    return _SORRY_USING_RE.search(strip_comments_and_strings(text)) is not None
