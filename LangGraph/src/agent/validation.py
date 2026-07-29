"""
Validation utilities for Lean code produced by LLM agents.

These are cheap pre-filters — the aggregator re-validates at compile time.
"""


def is_valid_lean_proof(text: str) -> bool:
    """Quick sanity check: is this likely valid Lean code, not natural language?

    Rejects responses that are dominantly prose with no Lean syntax markers.
    This is a cheap pre-filter — the aggregator will re-validate at compile time.

    Args:
        text: The LLM response to validate.

    Returns:
        True if the text looks like valid Lean code.
    """
    t = text.strip()
    if not t:
        return False

    # Must contain at least one Lean proof/tactic marker
    lean_markers = [
        ":= by", ":= ", "theorem ", "lemma ", "def ", "example ",
        "have ", "show ", "apply ", "exact ", "intro ", "refine ",
        "calc", "rw ", "simp", "ring", "linarith", "omega",
    ]
    has_lean = any(m in t for m in lean_markers)
    if not has_lean:
        return False

    # Heuristic: if the response is very long and has no newlines, it's likely prose
    lines = t.split("\n")
    if len(lines) < 3 and len(t) > 500:
        return False

    # If the first line is a natural-language sentence (starts with
    # "Here", "The", "We", "I", "This", "Let me", etc.) and there's
    # no code fence, it's likely an explanation, not a proof.
    first_line = lines[0].strip().lower()
    prose_starters = (
        "here", "the proof", "we ", "i ", "this ", "let me",
        "to prove", "first", "note that", "observe that",
        "the lemma", "the theorem",
    )
    if any(first_line.startswith(s) for s in prose_starters):
        code_like = [l for l in lines if any(m in l for m in lean_markers)]
        if len(code_like) < 2:
            return False

    return True
