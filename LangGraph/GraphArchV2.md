# LangGraph Architect — Revised Design (v2)

The goal with this pipeline is to produce a lean, verifiable proof of an input
theorem using the Goedel-Architecture, built on LeanArchitect (blueprint
extraction/dependency tracking) and lean-lsp-mcp (tactical Lean interaction).

## Steps (Nodes in the graph)

1. **Input** — theorem/conjecture + runtime configuration (model choice,
   `max_parallel_agents`, token budget, max rounds).
2. **Blueprint Generation** — decompose the theorem into a *compiling Lean
   skeleton*: every sub-lemma's type signature must already type-check
   against the others, with `@[blueprint]` tags attached, bodies left as
   `sorry`.
3. **Theorem-Proving (fan-out)** — `Send`-dispatch one task per unproved
   lemma, width capped by `max_parallel_agents`. Each task is isolated:
   read-only file access, returns a proposed edit, never writes the
   canonical file.
4. **Aggregator** — single node, runs once per round after fan-in completes.
   Applies all proposed edits to the canonical file serially, re-validates
   each match before applying, discards (does not merge) conflicting edits,
   then runs the deterministic soundness gate.
5. **Synthesizer** — reads the freshly-derived structured blueprint view,
   decides: done / refine specific lemmas / hit budget ceiling → interrupt.
6. **Blueprint Refiner** — decomposes lemmas marked too-hard into further
   sub-lemmas using LeanArchitect's same-label multi-declaration support,
   then routes back to step 3 for only the changed lemmas.

## Architecture decisions locked in from discussion

### Source of truth: the file, not a hand-rolled parallel dict

The `.lean` file is authoritative. Structured per-lemma status
(`proved` / `unproved` / `too_hard` / `failed`) is **derived fresh each
round** via `lake build :blueprintJson`, not maintained by hand in graph
state. This removes an entire class of file/state drift bugs. LeanArchitect
gives sorry-free inference and dependency inference for free — don't
duplicate either.

The richer status enum (`in_progress`, `failed_too_hard`, attempt counts)
lives *only* in runtime graph state, joined against the JSON export's binary
sorry-free signal each round — LeanArchitect has no native concept of "too
hard," so don't try to force it into blueprint attributes.

### Shared file, not per-lemma file isolation

Rejected the file-split-per-lemma approach. Search-and-replace with a
serialized, single-writer aggregator solves the concurrency problem more
simply than splitting files, and keeps LeanArchitect's dependency inference
and same-label multi-declaration merging working naturally across a single
buildable module.

### Trust boundary: provers propose, aggregator applies

Parallel prover agents get **read-only** file access during their attempt
loop (diagnostics, goal state, tactic attempts via lean-lsp-mcp). They never
call search-and-replace against the canonical file directly — that would
recreate the race condition. They return a structured edit proposal; only
the aggregator, running serially after fan-in, writes.

### Failed proofs leave a structured trace in the source

Provers that fail use `sorry_using [attempted_lemma, ...]` instead of bare
`sorry`, so the next round's refiner has a dependency trail without needing
a separate "feedback" field threaded through state.

### Parallelism is a `Send` fan-out width, not a graph-shape parameter

`max_parallel_agents` controls how many `Send` tasks run concurrently — it
does not change the graph's node topology. One `prove_lemma` node
definition, fanned out at runtime. The aggregator always runs exactly once
per round regardless of fan-out width, including the degenerate
`max_parallel_agents=1` case (still needed for cross-round staleness
re-validation, not just intra-round concurrency).

### Judge order: deterministic gate before LLM judge

`lean_verify`'s axiom check (only `propext`, `Classical.choice`, `Quot.sound`
allowed) and pattern scan run first and are non-negotiable. The LLM judge
only ever sees proofs that already passed this gate — narrowing its job from
"is this proof legitimate" to "did the model exploit a technically-sound but
illegitimate shortcut," which needs to be backed by concrete examples in its
prompt (vacuous hypotheses, proving a weaker statement, classical-logic
shortcuts that defeat the exercise's purpose).

### Termination: deterministic budget ceiling → single interrupt

No general HITL in v1 (no human arbitration of ambiguous theorems or
structurally-wrong blueprints — those are out of scope, hard-fail with
partial output). The one exception: when round or token ceiling is hit, the
graph pauses via a single `interrupt()` call asking continue-with-more-budget
or terminate-with-partial-result. This is the only human touchpoint in v1.

## State Design

```python
from typing import TypedDict, Literal, Annotated
import operator

class LemmaStatus(TypedDict):
    """Derived fresh each round from lake build :blueprintJson,
    joined with locally-tracked attempt/refinement counters."""
    id: str
    statement: str            # lean signature
    sorry_free: bool          # from LeanArchitect JSON export
    status: Literal["unproved", "in_progress", "proved", "too_hard", "failed"]
    depends_on: list[str]     # inferred by LeanArchitect, not hand-maintained
    attempts: int
    refinement_round: int
    last_feedback: str | None # goal state / error at point of failure

class ProofProposal(TypedDict):
    """What a single parallel prover agent returns. Never applied directly —
    only the aggregator writes to the canonical file."""
    lemma_id: str
    old_str: str               # full lemma declaration, must be unique in file
    new_str: str | None        # None if failed
    status: Literal["proved", "too_hard", "failed"]
    feedback: str
    tokens_used: int

class GraphState(TypedDict):
    input_theorem: str
    workspace_path: str
    lean_file_content: str
    blueprint: dict[str, LemmaStatus]   # derived view, refreshed post-aggregation

    # fan-out / fan-in
    pending_proposals: Annotated[list[ProofProposal], operator.add]

    # budget + termination
    global_round: int
    max_rounds: int
    tokens_spent: int
    token_budget: int
    max_parallel_agents: int

    # audit trail
    history: list[dict]   # lineage: which lemma spawned which, per round
```

## Node Specifications

### 1. Input
Runtime config passed via LangGraph's runtime context: model selection,
`max_parallel_agents`, `token_budget`, `max_rounds`. Input theorem accepted
as natural language (optionally with an informal proof sketch).

### 2. Blueprint Generation
A capable LLM decomposes the natural-language theorem into Lean lemma
*signatures* (bodies as `sorry`), tagged `@[blueprint]`, using the
LeanArchitect library conventions. Hard requirement: the skeleton must
compile — every cross-referencing signature has to type-check before any
proving starts, since the dependency graph is only meaningful once that's
true.

Tool use: `lean_local_search` / `lean_loogle` to confirm referenced Mathlib
declarations actually exist before finalizing signatures — do not let the
LLM guess plausible-sounding lemma names. `lean_build` to verify the
skeleton compiles with sorries before proceeding.

*Known v1 limitation:* if the decomposition is structurally wrong (lemmas
individually provable but don't actually compose into the parent theorem),
there is no automatic detection or regeneration path. Out of scope for v1.

### 3. Theorem-Proving (fan-out)
```python
def fan_out_provers(state: GraphState):
    candidates = [lid for lid, l in state["blueprint"].items()
                  if l["status"] in ("unproved", "too_hard")]
    width = state["max_parallel_agents"]
    # dispatch in batches of `width` if no native concurrency cap is available
    return [Send("prove_lemma", {"lemma_id": lid}) for lid in candidates]
```

Each `prove_lemma` task:
- Reads its lemma's current goal state (`lean_goal`) and the relevant file
  region (read-only).
- Uses `lean_multi_attempt` to screen tactic candidates before committing,
  `lean_state_search` / `lean_hammer_premise` for goal-conditioned premise
  retrieval, `lean_leansearch` / `lean_leanfinder` / `lean_loogle` for
  broader Mathlib search.
- On success: returns a `ProofProposal` with `old_str` = the full current
  lemma declaration (signature + `sorry` body, scoped enough to be a unique
  match in the file) and `new_str` = the completed proof.
- On failure: returns `status="too_hard"` or `"failed"`, with `new_str`
  rewriting the body to `sorry_using [...]` listing what it tried, and
  `feedback` = the goal state at the point it gave up.
- Enforces its own per-agent token/attempt budget; reports `tokens_used`
  regardless of outcome.

`lean_run_code` disabled by default for these agents (arbitrary code
execution is a different risk tier than diagnostics/tactic attempts) —
revisit only on demonstrated need.

### 4. Aggregator
Single node, same underlying prover-agent model with a distinct prompt is
acceptable, but the *write* still happens through a deterministic,
re-validated apply step regardless of which model proposed the edit:

1. For each `ProofProposal` in `pending_proposals` (processed serially):
   - Re-check that `old_str` still matches uniquely in the current file
     state. If not (a refiner or another proposal already invalidated it),
     discard — do not attempt a merge — and mark that lemma for retry next
     round.
   - Apply the search-and-replace.
2. After all proposals are applied: `lake build :blueprintJson` to derive
   the fresh structured blueprint view, and `lean_diagnostic_messages` /
   `lean_build` to confirm the file still compiles.
3. For every lemma now `sorry_free`: run `lean_verify`. Anything beyond the
   three standard axioms (`propext`, `Classical.choice`, `Quot.sound`) — most
   importantly `sorryAx` — or a pattern-scan hit, forces `status="too_hard"`
   regardless of what the prover claimed. This is the self-grading guard:
   an LLM aggregator's claim of success is never sufficient on its own.

The LLM-judge step (qualitative "did the model cheese this") runs here,
*after* the deterministic gate, only on lemmas that passed it.

### 5. Synthesizer (conditional edges, not node-internal logic)
Pure routing logic over the freshly-derived `blueprint` view plus budget
state:

```python
def route(state: GraphState) -> str:
    if state["global_round"] >= state["max_rounds"] or \
       state["tokens_spent"] >= state["token_budget"]:
        return "budget_interrupt"
    if all(l["status"] == "proved" for l in state["blueprint"].values()):
        return "END"
    if any(l["status"] == "too_hard" for l in state["blueprint"].values()):
        return "blueprint_refiner"
    return "prove_lemma"  # remaining unproved, no refinement needed yet
```

`budget_interrupt` node:
```python
def budget_interrupt(state: GraphState):
    decision = interrupt({
        "reason": "round/token ceiling reached",
        "rounds_used": state["global_round"],
        "tokens_spent": state["tokens_spent"],
        "unproved_lemmas": [...],
    })
    if decision == "continue":
        return {"max_rounds": state["max_rounds"] + EXTRA_ROUNDS, ...}
    return Command(goto=END)  # terminate with partial result
```

This is the **only** interrupt point in v1.

### 6. Blueprint Refiner
For each `too_hard` lemma: decomposes into further sub-lemmas using
LeanArchitect's same-label multi-declaration support (so the parent node's
"done" status automatically becomes "true once all children are sorry-free,"
via the library's own merge semantics rather than hand-tracked
parent/child logic). Re-queues only the changed lemmas back to step 3 —
proved lemmas are never re-touched.

Convention: refiner-introduced scaffolding lemmas that exist only to make a
proof tractable get `proofUses := [-X]` suppression so they don't pollute
the dependency graph a human would see.

## Tool Use

**LeanArchitect** (blueprint/dependency layer, invoked between rounds only):
- `lake build :blueprintJson` — structured blueprint export, called once per
  round by the aggregator after edits are applied. Never called inside the
  per-agent proving loop (too expensive for that cadence).

**lean-lsp-mcp** (tactical layer, invoked heavily inside the proving loop):
- `lean_goal`, `lean_diagnostic_messages`, `lean_multi_attempt` — core
  attempt/feedback loop.
- `lean_local_search`, `lean_loogle`, `lean_leansearch`, `lean_leanfinder`,
  `lean_state_search`, `lean_hammer_premise` — Mathlib/premise search,
  available to both Blueprint Generation and Theorem-Proving.
- `lean_verify` — deterministic soundness gate, aggregator only.
- `lean_profile_proof` — optional, for catching a prover stuck in a slow
  tactic before it burns its budget.
- `lean_build` — concurrency mode set to `share`, since the aggregator is
  the only writer and proving agents shouldn't trigger overlapping rebuilds.
- `lean_run_code` — disabled by default.

Filesystem access: search-and-replace exposed asymmetrically — read-only
for parallel prover agents, write access reserved for the aggregator node
only.

## Deferred / Known Gaps (explicit, not silent)

- **No general HITL** beyond the budget-ceiling interrupt. Ambiguous
  theorem statements and structurally-wrong blueprint decompositions hard-
  fail with partial output rather than asking a human.
- **No detection of structurally-wrong decomposition** — if individually
  provable lemmas don't actually compose into the parent theorem, this
  pipeline has no automatic recovery path.
- **No cross-round dependency-drift diffing** — the synthesizer trusts each
  round's fresh `blueprintJson` snapshot without diffing against the prior
  round's structure. A refiner edit that incidentally changes an unrelated
  lemma's inferred dependencies could silently change next-round scheduling.
- **No cost/observability layer beyond `tokens_spent`** — no per-lemma or
  per-round breakdown surfaced for post-hoc analysis. `history` is present
  in state as a hook for this but not yet populated with detail.