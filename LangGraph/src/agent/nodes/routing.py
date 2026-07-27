"""
Fan-out dispatcher and blueprint state rebuild node.
"""

from pathlib import Path

from langgraph.graph import END
from langgraph.types import Send

from config import MAX_REFINEMENT_ROUNDS
from state import State
from blueprint_converter import (
    blueprint_to_tasks,
    load_blueprint_json,
    derive_lemma_statuses,
)


def theorem_proving(state: State) -> list[Send]:
    """Read the file once, splice each unproved lemma by line range, dispatch all
    in parallel via Send."""
    # Collect unproved lemma names
    unproved_names = {
        name for name, ls in state.lemma_statuses.items()
        if ls["status"] == "unproved"
    }
    if not unproved_names:
        print("   🚦 theorem_proving: no unproved lemmas → routing to aggregator")
        return []

    # Read file, split by lines
    try:
        file_path = Path(state.workspacePATH)
        file_content = file_path.read_text()
        lines = file_content.splitlines(keepends=True)
    except Exception as e:
        print(f"   ❌ theorem_proving: failed to read file: {e}")
        return []

    # Splice each unproved lemma by line range, build Send list
    sends = []
    for task in state.lemma_tasks:
        name = task["name"]
        if name not in unproved_names:
            continue
        try:
            decl_text = "".join(lines[task["start_line"] - 1: task["end_line"]])
        except (IndexError, KeyError):
            print(f"   ⚠️  Could not extract '{name}' by line range — skipping")
            continue
        sends.append(Send("prove_lemma", {
            "lemma_task": task,
            "lemma_decl_text": decl_text,
            "active_node": "prove_lemma",
        }))

    # Dispatch
    print(f"   🚀 theorem_proving: dispatching {len(sends)} parallel agent(s)")
    for s in sends:
        print(f"      → {s.arg['lemma_task']['name']}")
    return sends


async def rebuild_blueprint(state: State) -> dict:
    """Rebuild blueprint JSON and derive fresh lemma_statuses/lemma_tasks.
    Called after the refiner finishes writing to the file."""
    print("\n🔄 REBUILD BLUEPRINT: Refreshing blueprint state from JSON...")

    try:
        bp_json = load_blueprint_json(state.project_root)
        fresh_tasks = blueprint_to_tasks(bp_json)
        fresh_statuses = derive_lemma_statuses(bp_json)
        proved_count = sum(1 for ls in fresh_statuses.values() if ls["status"] == "proved")
        print(f"   📊 {len(fresh_statuses)} lemmas, {proved_count} proved")
        return {
            "blueprint": bp_json, "lemma_tasks": fresh_tasks,
            "lemma_statuses": fresh_statuses, "active_node": "rebuild_blueprint",
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


def route_after_aggregator(state: State) -> str:
    """After aggregator: route to refiner if unproved and rounds remain, else END."""
    if state.global_round >= MAX_REFINEMENT_ROUNDS:
        print(f"   🚦 Route: aggregator → END (reached max {MAX_REFINEMENT_ROUNDS} rounds)")
        return END
    if any(ls["status"] != "proved" for ls in state.lemma_statuses.values()):
        print(f"   🚦 Route: aggregator → blueprint_refiner (round {state.global_round})")
        return "blueprint_refiner"
    print(f"   🚦 Route: aggregator → END (all lemmas proved)")
    return END


def route_after_rebuild(state: State):
    """After rebuild_blueprint: always dispatch theorem_proving."""
    print(f"   🚦 Routing: rebuild_blueprint → theorem_proving")
    return theorem_proving(state)


def route_from_tools(state: State):
    """After tool node: route back to whichever LLM node called it."""
    result = state.active_node if state.active_node else "blueprint_gen"
    print(f"   🚦 Routing: tool_node → {result}")
    return result
