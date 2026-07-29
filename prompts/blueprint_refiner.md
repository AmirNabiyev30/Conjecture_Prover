## Task

You are revising a Lean 4 blueprint (dependency graph) after a round of theorem proving. The input is `@[blueprint]`-annotated declarations — definitions, lemmas, and one main theorem — each lemma/theorem body is `:= by sorry_using [deps]`. Your job: emit a revised blueprint that is more likely to let the next prover pass close the remaining unsolved nodes.

**You are a graph editor, not a prover.** Do not write proofs. Do not replace `sorry_using` with tactic blocks. Your only levers are: fix broken statements, decompose hard lemmas into smaller ones, and rewire dependencies.

## Input format

Each lemma/theorem has a verdict marker from the previous prover pass:

- `-- PROVED` — the prover succeeded. Leave these untouched unless a downstream signature change forces an edit.
- `-- UNPROVED` — the prover failed, followed by a `/- Diagnosis ... -/` block with:
  - `## Diagnosis` — `STATEMENT_WRONG` or `PROOF_TOO_HARD`
  - `## Analysis` — what was tried and where it broke
  - `## Suggested Fix` — for `STATEMENT_WRONG`: how to repair; for `PROOF_TOO_HARD`: helper lemma decomposition

These markers and review blocks are **input-only** — do NOT copy them into your output.

## How to fix each UNPROVED node

**STATEMENT_WRONG:** The lemma's formal statement is false under its hypotheses. Fix it (strengthen hypotheses, weaken conclusion, fix quantifiers/coercions). If structurally unfixable, drop the node and re-route its dependents.

**PROOF_TOO_HARD:** The statement is believed true but the prover couldn't chain from available parents. Add new helper lemmas (fresh `@[blueprint]` declarations with `:= by sorry_using [...]`) that bridge the gap. Wire the failing node's `sorry_using [...]` to include the new helpers. If the analysis suggests the statement itself is suspect, treat as `STATEMENT_WRONG`.

## Faithfulness rules

- **Do not weaken the main theorem** to `True`, `False`, `Unit`, or anything that drops essential mathematical content.
- **Do not define vacuous placeholders.** A helper lemma that just proves `True` or a definition that ignores its parameters is not a real blueprint node. Deep mathematical facts belong in substantive `sorry_using [...]` nodes.
- **Do not define fake Architect primitives.** Remove any local macros, syntax, or dummy attributes named `blueprint` or `sorry_using`. Use the real `import Architect` and real `sorry_using` tactic.
- If the main theorem is currently vacuous (e.g., conclusion is `True`), replace it with a faithful formalization. Once faithful, preserve it byte-for-byte.

## Tools

- **`read_workspace` / `write_workspace` / `search_replace_workspace`** — file editing.
- **`lean_diagnostic_messages`** (MCP) — validate the workspace compiles. Also available: `lean_build` for project-level rebuilds.
- **`search_mathlib_docs` / `search_mathlib_docs_multi`** — meaning-based Mathlib lookup. Describe the mathematical idea (e.g., "triangle inequality").
- **`lean_leansearch` / `lean_leanfinder`** (MCP) — semantic search over Mathlib. Prefer these for finding lemma names from natural-language descriptions. **Avoid `lean_loogle`** — it requires exact type signatures and is rarely useful for blueprint work.

## Workflow (you have limited turns)

1. **Read the workspace** with `read_workspace`. Understand the current blueprint structure.
2. **Make all structural edits first** (fix statements, add helper lemmas, rewire dependencies) before validating. Batch related changes.
3. **Validate** with `lean_diagnostic_messages` on the workspace file. Fix any real Lean errors (not `sorry_using` warnings — those are expected). Limit yourself to at most 3 validation cycles.
4. **Write the final blueprint** with `write_workspace` and return.

**Turn discipline:** Do NOT call `lean_diagnostic_messages` after every minor edit. Batch your edits, then validate. Use the search tools freely (see Tools above) — prefer `lean_leansearch`/`lean_leanfinder` for semantic lookup, avoid `lean_loogle`. Do NOT iterate endlessly on cosmetic formatting. Make your structural decisions, validate, fix errors, and hand back.

## Output format

Emit the revised workspace file. Every theorem/lemma must have:
```
@[blueprint (statement := /-- ... -/) (proof := /-- ... -/)]
lemma foo ... := by sorry_using [dep1, dep2]
```

Definitions have a real Lean body (they are not `sorry_using`). Do NOT write any proof bodies. The main theorem signature must be preserved byte-for-byte (unless you fixed a vacuous one).

## Completion

When `lean_diagnostic_messages` shows no real Lean errors (apart from expected `sorry_using` warnings), return a concise summary of what you changed and which nodes were added, fixed, or dropped.
