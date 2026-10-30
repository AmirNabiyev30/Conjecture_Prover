"""
Batch dispatcher, dispatch gate, and blueprint state rebuild node.

Provers are dispatched in **barrier batches** rather than all at once: each pass
enqueues at most ``max_parallel_provers`` ``prove_lemma`` tasks, and the next
batch only starts after the current one has fully finished. Every prover holds
its own Lean MCP server, so this bounds proving-stage RAM by the batch width
instead of by the number of unproved lemmas.

The barrier is structural, not a timeout or a semaphore: ``prove_lemma`` is
wired to :func:`dispatch_gate` with a **plain** edge, which LangGraph only
satisfies once every task in the superstep has completed. The gate body does no
work; the batch decision lives on its outgoing conditional edge.
"""

from pathlib import Path

from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.types import Send

from config import MAX_PARALLEL_PROVERS, MAX_REFINEMENT_ROUNDS
from state import Context, State
from lean_text import has_sorry_using_placeholder
from blueprint import (
    Blueprint,
    derive_lemma_statuses_from_workspace,
    load_blueprint_json,
)


def attempted_lemma_ids(state: State) -> set[str]:
    """Lemma ids already dispatched during the current round.

    Derived rather than stored in a dedicated state field. Every return path in
    ``prove_lemma`` carries a ``lemma_id``, and every return path in the
    aggregator resets ``pending_proposals`` to ``[]`` — so the ledger resets at
    exactly the one place a round ends, and there is no extra field for the
    aggregator's six return paths to forget.

    This ledger is what makes the batch loop terminate: without it the slicer
    would keep returning the same first batch every pass.
    """
    return {
        proposal.get("lemma_id", "")
        for proposal in state.pending_proposals
        if proposal.get("lemma_id")
    }


def _batch_width(runtime: Runtime[Context] | None) -> int:
    """Read the batch width from the run's Runtime context (config as fallback)."""
    if runtime is None:
        return MAX_PARALLEL_PROVERS
    return runtime.context.get("max_parallel_provers", MAX_PARALLEL_PROVERS)


def theorem_proving(
    state: State, runtime: Runtime[Context] | None = None
) -> list[Send]:
    """Select the next barrier batch of lemmas to prove.

    Pure in ``state`` plus the runtime's batch width: same state in, same Send
    list out. Returns at most ``max_parallel_provers`` Sends, or ``[]`` when the
    queue is drained — callers turn that empty list into the ``aggregator``
    route (see :func:`next_batch_or_aggregate`).

    Candidate filters, in order:

    1. the lemma is currently ``unproved``;
    2. it has not already been dispatched this round (the attempted ledger);
    3. its spliced declaration still contains a ``sorry_using`` placeholder.

    Filter 3 exists because the blueprint JSON does NOT encode this (there is no
    ``sorryFree`` field), so the real declaration text is inspected: a bare
    ``sorry``, a real proof, a definition with a body, or an out-of-range splice
    is skipped — both the prover prompt and the aggregator fixer assume the
    ``sorry_using`` shape. The check is comment- and word-aware, so a
    declaration that merely mentions ``sorry_using`` in a comment is not sent.

    Lemmas are taken in ``blueprint.nodes`` order, which needs no dependency
    sort: each declaration's ``sorry_using [...]`` names its helpers, and those
    helpers are trusted as stated, so any lemma can be attempted independently.
    Batch order therefore cannot affect whether a proof succeeds.
    """
    unproved_names = {
        name for name, ls in state.lemma_statuses.items()
        if ls["status"] == "unproved"
    }
    if not unproved_names:
        print("   🚦 theorem_proving: no unproved lemmas → batch queue drained")
        return []

    attempted = attempted_lemma_ids(state)
    width = _batch_width(runtime)

    # Read file, split by lines
    try:
        file_path = Path(state.workspacePATH)
        file_content = file_path.read_text()
        lines = file_content.splitlines(keepends=True)
    except Exception as e:
        print(f"   ❌ theorem_proving: failed to read file: {e}")
        return []

    sends = []
    skipped_no_sorry_using: list[str] = []
    tasks = state.blueprint.nodes if state.blueprint else []
    for task in tasks:
        name = task["name"]
        if name not in unproved_names:
            continue
        if name in attempted:
            continue
        try:
            decl_text = "".join(lines[task["start_line"] - 1: task["end_line"]])
        except (IndexError, KeyError):
            print(f"   ⚠️  Could not extract '{name}' by line range — skipping")
            continue
        if not has_sorry_using_placeholder(decl_text):
            print(f"   ⏭️  Skipping '{name}': declaration has no `sorry_using` placeholder")
            skipped_no_sorry_using.append(name)
            continue
        sends.append(Send("prove_lemma", {
            "lemma_task": task,
            "lemma_decl_text": decl_text,
            "active_node": "prove_lemma",
        }))
        # Stop splicing as soon as the batch is full: the cost of a large
        # blueprint then stays out of this pass and out of the checkpoint.
        if len(sends) >= width:
            break

    # Log the batch, including how far through the round's ledger we are.
    print(
        f"   🚀 theorem_proving: batch of {len(sends)} (width {width}, "
        f"attempted so far {len(attempted)}, "
        f"skipped {len(skipped_no_sorry_using)} without sorry_using)"
    )
    for s in sends:
        print(f"      → {s.arg['lemma_task']['name']}")
    return sends


async def dispatch_gate(state: State) -> dict:
    """Barrier join node between prover batches — intentionally does nothing.

    It exists because a plain edge into a node only fires once every upstream
    task in the superstep has completed, which is exactly the fan-in guarantee
    the barrier needs. The batch decision is not made here: it lives on this
    node's outgoing conditional edge (:func:`route_after_batch`), which can
    therefore be evaluated exactly once per batch, on fully merged state.

    Returning an empty update keeps the reducers untouched, so the
    ``pending_proposals`` ledger that drives batching survives intact between
    batches.
    """
    return {}


async def rebuild_blueprint(state: State) -> dict:
    """Rebuild blueprint JSON and derive fresh lemma_statuses.
    Called after the refiner finishes writing to the file."""
    print("\n🔄 REBUILD BLUEPRINT: Refreshing blueprint state from JSON...")

    try:
        blueprint = Blueprint.from_blueprint_json(
            load_blueprint_json(state.project_root),
            project_root=state.project_root,
        )
        # Derive from the real source text (the blueprint JSON has no
        # `sorryFree` field, so JSON-derived statuses always show 0 proved and
        # the round loop can never terminate). Fall back to JSON on error.
        fresh_statuses = derive_lemma_statuses_from_workspace(
            blueprint, state.workspacePATH
        )
        proved_count = sum(1 for ls in fresh_statuses.values() if ls["status"] == "proved")
        print(f"   📊 {len(fresh_statuses)} lemmas, {proved_count} proved")
        print(f"   📊 Blueprint: {len(blueprint.nodes)} nodes, root='{blueprint.root_node()}'")
        return {
            "blueprint": blueprint,
            "lemma_statuses": fresh_statuses,
            "active_node": "rebuild_blueprint",
        }
    except Exception as e:
        print(f"   ⚠️  Blueprint rebuild failed: {e}")
        return {"active_node": "rebuild_blueprint"}


# ── Routing helpers ───────────────────────────────────────────────────────

def route_tool_calls(state: State, key: str) -> str:
    """Route tool calls to the matching dedicated ToolNode."""
    suffixes = {
        "blueprint_generator_messages": "bp",
        "blueprint_refiner_messages": "br",
    }
    suffix = suffixes.get(key)
    if suffix is None:
        return END

    msgs = getattr(state, key)
    if not msgs:
        return END
    msg = msgs[-1]
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return END

    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return f"human_tool_{suffix}"
    return f"tools_{suffix}"


def route_from_blueprint(state: State):
    """After blueprint_gen: route to tools/human, or rebuild + dispatch."""
    dest = route_tool_calls(state, "blueprint_generator_messages")
    if dest != END:
        print(f"   🚦 Routing: blueprint_gen → {dest}")
        return dest
    print(f"   🚦 Routing: blueprint_gen → rebuild_blueprint (first pass)")
    return "rebuild_blueprint"


def route_from_refiner(state: State):
    """After blueprint_refiner: route to tools/human or to rebuild_blueprint."""
    dest = route_tool_calls(state, "blueprint_refiner_messages")
    if dest != END:
        print(f"   🚦 Routing: blueprint_refiner → {dest}")
        return dest
    print(f"   🚦 Routing: blueprint_refiner → rebuild_blueprint")
    return "rebuild_blueprint"


def route_after_aggregator(state: State, runtime: Runtime[Context]) -> str:
    """After aggregator: route to refiner if unproved and rounds remain, else END.

    The round budget is a per-run setting, so it is read from the Runtime context:
    ``MAX_REFINEMENT_ROUNDS`` is only the fallback for a hand-built context.
    """
    max_rounds = runtime.context.get("max_refinement_rounds", MAX_REFINEMENT_ROUNDS)
    if state.global_round >= max_rounds:
        print(f"   🚦 Route: aggregator → END (reached max {max_rounds} rounds)")
        return END
    if any(ls["status"] != "proved" for ls in state.lemma_statuses.values()):
        print(f"   🚦 Route: aggregator → blueprint_refiner (round {state.global_round})")
        return "blueprint_refiner"
    print(f"   🚦 Route: aggregator → END (all lemmas proved)")
    return END


def next_batch_or_aggregate(
    state: State, runtime: Runtime[Context] | None = None
) -> list[Send] | str:
    """The single dispatch decision shared by every entry point into proving.

    Two places start proving work — ``rebuild_blueprint`` (the first batch of a
    round) and ``dispatch_gate`` (every later batch) — and both must behave
    identically: send the next batch, or move on to the aggregator.

    The ``"aggregator"`` fallback is load-bearing. Returning an empty ``Send``
    list schedules nothing at all, so a drained queue would silently end the
    branch instead of reaching the aggregator; the round counter would never
    advance and the run would report round 0 with nothing applied.
    """
    sends = theorem_proving(state, runtime)
    if sends:
        return sends
    print("   🚦 Routing: batch queue drained → aggregator")
    return "aggregator"


def route_after_rebuild(state: State, runtime: Runtime[Context]):
    """After rebuild_blueprint: dispatch the round's first prover batch."""
    print("   🚦 Routing: rebuild_blueprint → theorem_proving (first batch)")
    return next_batch_or_aggregate(state, runtime)


def route_after_batch(state: State, runtime: Runtime[Context]):
    """After dispatch_gate: dispatch the next batch, or hand off to the aggregator.

    Evaluated once per batch, on fully merged state, because the gate node it
    hangs off has executed exactly once after the fan-in.
    """
    return next_batch_or_aggregate(state, runtime)


def route_from_tools(state: State):
    """After tool node: route back to whichever LLM node called it."""
    result = state.active_node if state.active_node else "blueprint_gen"
    print(f"   🚦 Routing: tool_node → {result}")
    return result
