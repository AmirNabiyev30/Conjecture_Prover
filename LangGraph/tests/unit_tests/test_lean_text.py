"""Unit tests for Lean escape-hatch detection.

Behavior contract:
- Escape detection is shared by the prover and the status scan so they cannot
  disagree about whether a proof is finished. Previously ``blueprint`` treated
  ``admit`` as an escape while ``prove_lemma`` did not.
- Matching is on whole words, so identifiers and prose that merely contain the
  letters (``my_sorry_helper``, ``admissible``) are not flagged.
- Comments and string literals are ignored, so a note such as ``-- sorry, this
  failed`` does not make a finished proof look unfinished.
- ``has_sorry_using_placeholder`` answers a *different* question from
  ``contains_escape``: a bare ``sorry`` is an escape but not a placeholder.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "agent"))

from lean_text import (  # noqa: E402
    contains_escape,
    has_sorry_using_placeholder,
    strip_comments_and_strings,
)


# ── strip_comments_and_strings ───────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "lemma a : True := by\n  sorry\n",
    "-- a comment\ncode here\n",
    "/- block -/ code",
    'def s := "a string"',
    "",
])
def test_stripping_preserves_length(text):
    """Length is preserved so offsets and line numbers still line up."""
    assert len(strip_comments_and_strings(text)) == len(text)


def test_line_comment_is_blanked_but_newline_survives():
    out = strip_comments_and_strings("code -- sorry\nrfl")
    assert "\n" in out
    assert out.count("\n") == 1
    assert "sorry" not in out
    assert "code" in out
    assert "rfl" in out


def test_block_comment_is_blanked():
    out = strip_comments_and_strings("code /- sorry -/ rfl")
    assert "sorry" not in out
    assert "code" in out and "rfl" in out


def test_nested_block_comments_are_blanked():
    """Lean block comments nest; a non-greedy regex would stop at the first `-/`."""
    out = strip_comments_and_strings("code /- outer /- inner -/ still outer -/ rfl")
    assert "sorry" not in out
    assert "inner" not in out
    assert "outer" not in out
    assert "rfl" in out


def test_string_literal_is_blanked():
    out = strip_comments_and_strings('def s := "sorry inside a string"')
    assert "sorry" not in out
    assert "def s" in out


def test_escaped_quote_does_not_end_the_string():
    out = strip_comments_and_strings('def s := "a \\" sorry" ++ rfl')
    assert "sorry" not in out
    assert "rfl" in out


def test_comment_markers_inside_a_string_are_not_comments():
    """`--` and `/-` inside a literal must not blank the rest of the line."""
    out = strip_comments_and_strings('def s := "not -- a comment" ++ rfl')
    assert "rfl" in out


# ── contains_escape ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "lemma a : True := by\n  sorry\n",
    "theorem a : True := by\n  sorry_using []\n",
    "lemma a : True := by\n  exact sorryAx\n",
    "lemma a : True := by\n  admit\n",
    "lemma a : True := by\n  exact Lean.sorryAx P\n",
])
def test_escapes_are_detected(text):
    assert contains_escape(text) is True


@pytest.mark.parametrize("text", [
    "lemma a : True := by\n  rfl\n",
    "lemma a : True := by\n  trivial\n",
    "",
    "-- TODO: sorry\nlemma a : True := by\n  rfl\n",       # line comment
    "/- sorry -/\nlemma a : True := by\n  rfl\n",            # block comment
    'lemma a : True := by\n  exact "sorry"\n',              # string literal
])
def test_finished_proofs_have_no_escape(text):
    assert contains_escape(text) is False


@pytest.mark.parametrize("identifier", [
    "my_sorry_helper",
    "h_sorry",
    "sorry_free_lemma",
    "admissible",
    "admits",
    "not_admit",
    "sorry_usage",
])
def test_identifiers_that_merely_contain_the_letters_are_not_escapes(identifier):
    """The old substring check flagged `admissible`; whole-word matching does not."""
    assert contains_escape(f"lemma {identifier} : True := by rfl") is False


def test_escape_after_a_comment_on_a_later_line_is_still_detected():
    text = "lemma a : True := by\n  -- try rfl next\n  sorry\n"
    assert contains_escape(text) is True


def test_matching_is_case_sensitive():
    """Lean's `sorry` is a lowercase keyword; `Sorry` fails the compile check."""
    assert contains_escape("lemma a : True := by\n  Sorry\n") is False


# ── has_sorry_using_placeholder ──────────────────────────────────────────────

def test_placeholder_is_detected():
    assert has_sorry_using_placeholder("lemma a : True := by\n  sorry_using []\n")


def test_bare_sorry_is_not_a_placeholder():
    """An escape but not placeholder-shaped — the prover cannot splice it."""
    assert contains_escape("lemma a : True := by\n  sorry\n") is True
    assert has_sorry_using_placeholder("lemma a : True := by\n  sorry\n") is False


def test_placeholder_in_a_comment_is_not_a_placeholder():
    text = "lemma a : True := by\n  -- sorry_using [] goes here\n  rfl\n"
    assert has_sorry_using_placeholder(text) is False


def test_a_real_proof_has_no_placeholder():
    assert has_sorry_using_placeholder("lemma a : True := by\n  rfl\n") is False
